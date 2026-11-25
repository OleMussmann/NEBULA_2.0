// Read a NEBULA content repo: config, modules, pages.
// Shared by astro.config.mjs (sidebar) and the content loader. Plain JS so
// the Astro config can import it without a TypeScript step.

import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join, basename } from 'node:path';
import { parse as parseYaml } from 'yaml';

const FRONTMATTER = /^---\s*\n([\s\S]*?)\n---\s*\n/;

export function splitFrontmatter(text) {
	const m = FRONTMATTER.exec(text);
	if (!m) return [{}, text];
	return [parseYaml(m[1]) ?? {}, text.slice(m[0].length)];
}

function readPage(file, id) {
	const [meta, body] = splitFrontmatter(readFileSync(file, 'utf8'));
	return { id, file, meta, body };
}

const byOrder = (a, b) =>
	(a.meta.order ?? Infinity) - (b.meta.order ?? Infinity) ||
	String(a.meta.title).localeCompare(String(b.meta.title));

/** One content repo checkout, e.g. ../content. */
export function loadSource(root) {
	const config = JSON.parse(readFileSync(join(root, 'config.json'), 'utf8'));
	const props = config.publicProps ?? {};
	const modules = [];
	for (const slug of readdirSync(join(root, 'modules')).sort()) {
		const dir = join(root, 'modules', slug);
		if (!existsSync(join(dir, 'index.md'))) continue;
		const index = readPage(join(dir, 'index.md'), `modules/${slug}`);
		const pages = readdirSync(dir)
			.filter((f) => f.endsWith('.md') && f !== 'index.md' && !f.endsWith('.study.md'))
			.map((f) => readPage(join(dir, f), `modules/${slug}/${basename(f, '.md')}`))
			.sort(byOrder);
		modules.push({ slug, dir, index, pages, meta: index.meta });
	}
	const mainDir = join(root, 'main');
	const main = readdirSync(mainDir)
		.filter((f) => f.endsWith('.md'))
		.map((f) => readPage(join(mainDir, f), `main/${basename(f, '.md')}`))
		.sort(byOrder);
	return {
		root,
		props,
		categoryOrder: props.categoryOrder ?? [],
		upstreamSite: `https://${props.repoOwner}.github.io/${props.baseURL}`.toLowerCase(),
		modules,
		main,
	};
}

/** Categories in categoryOrder, then any others alphabetically. */
export function categories(source) {
	const used = [...new Set(source.modules.map((m) => m.meta.category ?? 'Other'))];
	return [
		...source.categoryOrder.filter((c) => used.includes(c)),
		...used.filter((c) => !source.categoryOrder.includes(c)).sort(),
	];
}

export const isVisible = (mod) => (mod.meta.visibility ?? 'visible') === 'visible';
