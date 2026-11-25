// Where the site is served: GitHub Pages project site, one sub-path per
// variant. The Makefile passes SITE_ORIGIN and SITE_PATH (PR previews are
// served under a deeper path).
export const SITE = process.env.SITE_ORIGIN ?? 'https://olemussmann.github.io';
export const BASE = `${process.env.SITE_PATH ?? '/NEBULA_2.0'}/starlight`;
