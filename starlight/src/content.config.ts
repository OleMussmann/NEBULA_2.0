import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { docsSchema } from '@astrojs/starlight/schema';
import { fileURLToPath } from 'node:url';
import { nebulaLoader } from './nebula-loader';
import { BASE } from './site.mjs';

const here = (p: string) => fileURLToPath(new URL(p, import.meta.url));

export const collections = {
	docs: defineCollection({
		loader: nebulaLoader({
			sources: [
				{
					root: process.env.NEBULA_CONTENT ?? here('../../content'),
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
