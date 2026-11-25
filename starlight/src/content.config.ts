import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { docsSchema } from '@astrojs/starlight/schema';
import { fileURLToPath } from 'node:url';
import { moduleSchema, nebulaLoader, nebulaModulesLoader } from './nebula-loader';
import { BASE } from './site.mjs';

const here = (p: string) => fileURLToPath(new URL(p, import.meta.url));

const contentRoot = process.env.NEBULA_CONTENT ?? here('../../content');

export const collections = {
	// Module index.md: frontmatter + rendered body (thumbnail credit), for
	// the footer. Not pages: a module opens on its first page.
	modules: defineCollection({
		loader: nebulaModulesLoader({ roots: [contentRoot] }),
		schema: moduleSchema.extend({
			author: z.string().optional(),
			categoryRank: z.number(),
		}),
	}),
	docs: defineCollection({
		loader: nebulaLoader({
			sources: [
				{
					root: contentRoot,
					editBase: 'https://github.com/OleMussmann/NEBULA_2.0/edit/main/content/',
				},
			],
			base: BASE,
			extraPages: { poc: here('./poc.md') },
		}),
		// NEBULA frontmatter on top of Starlight's: a typo such as
		// `type: exersice` or `order: "two"` fails the build with the file
		// name and field.
		schema: docsSchema({
			extend: z.object({
				type: z.enum(['info', 'reading', 'exercise', 'slides']).optional(),
				order: z.number().optional(),
				author: z.string().optional(),
				category: z.string().optional(),
				abstract: z.string().optional(),
				thumbnail: z.string().optional(),
				visibility: z.enum(['visible', 'hidden']).optional(),
				module: z.string().optional(),
			}),
		}),
	}),
};
