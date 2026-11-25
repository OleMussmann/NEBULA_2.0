// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import { fileURLToPath } from 'node:url';
import { loadSource, categories, isVisible } from './src/nebula.mjs';
import { SITE, BASE } from './src/site.mjs';

const source = loadSource(
	process.env.NEBULA_CONTENT ?? fileURLToPath(new URL('../content', import.meta.url)),
);

// Sidebar: one group per category (categoryOrder), one collapsible group
// per visible module, its pages in `order` with their type as a badge.
// Built here rather than with `autogenerate`: autogenerate matches pages by
// file path under src/content/docs/, and these pages live in ../content.
const badge = (type) =>
	type && type !== 'info'
		? { text: type, variant: type === 'exercise' ? 'caution' : 'note' }
		: undefined;
const sidebar = [
	...categories(source)
		.map((cat) => ({
			label: cat,
			items: source.modules
				.filter((m) => isVisible(m) && (m.meta.category ?? 'Other') === cat)
				.sort((a, b) => (a.meta.order ?? 0) - (b.meta.order ?? 0))
				.map((m) => ({
					label: m.meta.title,
					collapsed: true,
					items: [
						{ slug: m.index.id, label: 'Overview' },
						...m.pages.map((p) => ({ slug: p.id, badge: badge(p.meta.type) })),
					],
				})),
		}))
		.filter((g) => g.items.length),
	{ label: 'About', items: [...source.main.map((p) => p.id), 'poc'] },
];

export default defineConfig({
	site: SITE,
	base: BASE,
	// info.md -> info.html next to media/, so the content's relative image
	// paths (media/x.png) work unchanged, as in NEBULA.
	build: { format: 'file' },
	trailingSlash: 'never',
	integrations: [
		starlight({
			title: source.props.title ?? 'Lessons',
			sidebar,
			editLink: { baseUrl: 'https://github.com/OleMussmann/NEBULA_2.0/edit/main/' },
			// Starlight's Markdown transforms (asides, heading anchor links)
			// only run on src/content/docs unless other folders are listed.
			markdown: { processedDirs: ['../content'] },
			customCss: ['./src/styles/site.css', './src/styles/study.css'],
			components: { Footer: './src/components/Footer.astro' },
		}),
	],
});
