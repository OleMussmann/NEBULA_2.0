# Comparison: Quarto, Hugo, Astro Starlight

Draft, filled in per variant as it is built; completed in step 6 with
screenshots and a recommendation. Findings and opinion are kept apart:
everything under "Findings" was observed while building and checking.

Acceptance checks are automated: `tools/verify_site.py <variant>` serves the
built site under `/NEBULA_2.0/<variant>/` and drives headless Chromium
through hub, module page bar, study view, deck (theme, `#/<id>`, `S` speaker
view, `?annotations`), presenter-only notes, slide-id links, `main/` pages,
search and broken requests.

## Shared (all variants)

Code every variant uses, not counted per variant:

| File | Lines | Purpose |
|---|---|---|
| `tools/build_study.py` | 275 | decks + study views, inline-colour lint |
| `tools/nebula_content.py` | 180 | read config/modules/pages, rewrite links, module page bar |
| `shared/study.css` | 97 | study-view layout |
| `shared/module-nav.css` | 65 | module page bar |
| `shared/icons/*.svg` | 4 files | page-type icons (info, reading, exercise, slides) |
| `tools/verify_site.py` | 499 | acceptance checks (test code) |

Findings that apply to every generator:

- **Content links are root-absolute and extension-less**
  (`/modules/softwarelandscape/slides`, `/main/yellowpages`). They break
  under a sub-path and in any generator whose URLs differ from NEBULA's.
  Every variant must rewrite them. Links to modules that are not in the
  site (`/modules/researchsoftware/...`) are sent to the module's current
  NEBULA site.
- **NEBULA content is CommonMark** (reveal.js uses marked; NEBULA uses Nuxt
  Content). A generator whose Markdown differs will misparse some of it,
  e.g. a 4+-space indented line inside an HTML table.
- `build_study.py` swallowed the blank line after slide headings (regex
  bug), which merged headings with following HTML blocks. Fixed in step 2.
- The deck instance is exposed as `window.Reveal` (as in reveal.js's
  non-module build) so tools can inspect it.
- **Module navigation follows NEBULA:**
  a module opens on its first page in `order` (the learning objectives in
  every lesson), and every page of a module starts with a bar listing all
  its pages in `order`, each with a page-type icon, the current one
  marked. Same markup and CSS in all variants (`shared/module-nav.css`,
  `shared/icons/`). The module `index.md` is not rendered as a page, as
  in NEBULA: its frontmatter feeds the hub card and the bar. Its body
  (the thumbnail's photo credit; gen-ai's is CC BY-SA and must be shown)
  goes into the site footer as "Thumbnails: <module>: <credit> · …", in
  hub order. Per variant: Quarto generates the footer's left part in
  `prepare.py`; Hugo renders `.RawContent` of the module sections in
  `baseof.html` (ordering shared with the hub via a partial); Starlight
  adds a second content collection (`modules`) so Astro renders the
  bodies, and the footer override reads it. NEBULA-style links
  to `/modules/<m>` go to the module's first page.

- **HTML-heavy deck (gen-ai):** the deck renders as in NEBULA (background
  video and images, fragments, grids). The study view builds every slide
  (35) and shows each one without its `data-background-*` images/video and
  with all fragments expanded; the deck's `<style>` blocks end up in the
  page.
- **Slide content outside the deck (theme):** `escience_theme` sets text
  colour per slide through reveal.js's `has-light/dark-background` classes
  (from `data-state`); its `.card` sets its own dark text. A box with only
  an inline light background (`style="background: lightgray"`, as gen-ai
  used) inherits the surrounding text colour: white on light grey on a dark
  slide, and in the study view in dark mode. Fix at the source rather than
  per site:
  - `escience_theme` 0.4.0 (branch, unpublished) ships the layout classes
    as `components.css`, usable outside a deck under `.escience-components`;
    adds a `.details` panel for steppers whose steps are tiles, and
    `.muted`; card links get a darker blue (the brand blue was 2.2:1 on the
    card's grey).
  - Study views load `components.css` and wrap every slide in
    `.escience-components`; slides follow the site's light/dark mode.
    Steppers show every step with its detail in place (the risk map keeps
    which detail belongs to which category).
  - gen-ai rewritten to the theme classes (branch for upstream).
  - `build_study.py` warns about inline `color`/`background` per slide;
    `verify_site.py` checks text contrast (3:1, opacity included) in every
    deck slide with all fragments shown and in the study view in light and
    dark mode, and overlapping fragments. Against the old gen-ai the lint
    gives 9 warnings and the dark study view fails.
  - Not checked: text on background images (the scan assumes the overlay
    colour), and fragments the author semi-fades on purpose.
  Whether reveal.js's scroll view (rendered slides as a scrolling page)
  works with `escience_theme` is untested.
- **CI and previews (step 5):** one workflow builds all three variants
  with Nix, runs the browser checks and deploys to GitHub Pages
  (`gh-pages` branch); a second one publishes every PR under
  `/NEBULA_2.0/pr-preview/pr-<n>/` with a link comment and removes it when
  the PR closes. Tested end to end: deploy, PR preview from a web-editor
  edit, removal on close. Fork PRs get no preview (read-only token);
  web-editor edits by people with write access create a branch, not a
  fork. Pages needs `.nojekyll`, or Jekyll drops Astro's `_astro/`.
- **Serving path (CI previews):** PR previews live one level deeper than
  the site (`/NEBULA_2.0/pr-preview/pr-<n>/<variant>/`), so the base path
  is a build parameter (`SITE_PATH`). Quarto's output is fully relative and
  works under any path unchanged (only `sitemap.xml`/`robots.txt` carry the
  absolute URL). Hugo takes it as `--baseURL`, Starlight as Astro `base`
  (read from the environment in `src/site.mjs`); both write absolute paths
  into every page.

## Quarto (1.10.18)

### Findings

- **All acceptance criteria met:** 67/67 browser checks (`verify_site.py`)
  locally, under the PR-preview path and in CI; deployed to GitHub Pages;
  a typo fix in the GitHub web editor got a PR preview (step 5).
- **Custom code:** `quarto/prepare.py` 251 lines (pre-render),
  `_quarto.yml` 50, `styles.css` 16, `poc.qmd` 24 (PoC page with the
  example slide link). No templates, no Lua filters, no EJS.
- **Toolchain:** Quarto (bundles Pandoc, Deno, Dart Sass) + Python 3 for
  the pre-render. One binary install; no npm.
- **Clean build:** 7.5 s (`make clean && make quarto`; 22 pages).
- **Frontmatter mapping** happens in `prepare.py`, which mirrors `content/`
  into the project (content is never edited):
  - `abstract` → `description`, `thumbnail` → `image: media/<file>`
  - page `type` → `categories` (rendered as a badge under the title)
  - `type: exercise` body wrapped in a callout
  - module page bar: raw HTML from `module_nav_html()` prepended to each
    module page's body; module `index.md` is not mirrored at all
  - hub: one grid listing per category, in `categoryOrder`; only
    `visibility: visible` modules
  - `type: slides` source is replaced by its study view under the same
    name (`slides.md` → `slides.html`), so NEBULA's `/modules/<m>/slides`
    maps 1:1 and "Edit this page" opens the deck source
- **Edit this page:** native (`repo-actions: [edit]` + `repo-subdir:
  content`), correct for every content page because the mirror keeps
  `content/`'s layout. Disabled on the generated hub and the PoC page.
- **Search:** built in, works offline, no extra step.

### What was awkward

- Quarto reserves `order` and rejects it as a string; frontmatter has to be
  re-emitted with typed values.
- Pandoc Markdown ≠ CommonMark: needed `from: commonmark_x` for content,
  but the generated hub needs Pandoc Markdown (`:::` listing placeholders
  do not parse as CommonMark).
- Study view: Quarto's `section-divs` wraps headings in `<section>`s that
  overlap the raw `<section>/<div>` wrappers from `build_study.py`; Quarto's
  HTML post-processing then closes the wrappers early and the slide boxes
  end up empty. Fixed with `section-divs: false` on study pages.
- Pandoc's automatic heading ids collide with the slide ids
  (`#about-copyright` twice). Turning `auto_identifiers` off crashes
  Quarto's Lua filters, `id-prefix` has no effect; `prepare.py` now writes
  explicit heading ids (`{#about-copyright--1}`).
- Listings from a YAML file resolve `path` relative to the YAML file but
  `image` relative to the page.
- Files and directories starting with `_` are silently ignored, including
  listing YAML files.
- Generated files must be listed in `project.render`; the pre-render hook
  does run before Quarto collects inputs, so generating pages there works.

### How a non-coder adds an exercise

1. On GitHub, open `content/modules/<module>/`, "Add file → Create new file".
2. Name it e.g. `ex_my_exercise.md`; copy the frontmatter of another
   exercise (`title`, `type: exercise`, `order`).
3. Write the exercise; "Commit changes" → "Create a new branch and start a
   pull request".
4. The PR preview (step 5) shows it in the module page bar at its
   `order`, with the exercise callout.

No Quarto-specific step; `prepare.py` picks it up.

### Upgrade risk

`prepare.py` uses no Quarto internals; it writes ordinary input files.
It depends on documented behaviour: listings from YAML, `metadata-files`,
`repo-actions`, `section-divs`, `from:`. The fixes above depend on details
that could change: the `path`/`image` resolution difference, and how
Quarto's HTML pass treats overlapping sections.

### Open issues

- Quarto itself emits a few duplicate ids (light/dark theme `<link>`s,
  `fig-*` on images in the Landscape study view). Not ours; harmless so far.
- With several content repos, `repo-subdir` is project-wide: edit links for
  a second repo would need per-page `repo-url` (untested).
- Generated pages (hub) have no edit link; editing the hub means editing
  `prepare.py` or `config.json`.

## Hugo (0.170.0 extended)

### Findings

- **All acceptance criteria met:** 67/67 browser checks (`verify_site.py`)
  locally, under the PR-preview path and in CI; deployed to GitHub Pages;
  a typo fix in the GitHub web editor got a PR preview (step 5). No duplicate ids.
- **Custom code:** 228 lines of Go templates (`layouts/` 195 + content
  adapter 33), `hugo.toml` 75 (mostly commented mounts), `site.css` 117,
  `poc.md` 25. No pre-build script of its own: only the shared
  `build_study.py` runs before Hugo (`make hugo` depends on `make study`).
- **Toolchain:** one Hugo binary + Python 3 (decks) + Node only for
  `npx pagefind` (search). No Go toolchain needed (no Hugo Modules
  imports).
- **Clean build:** ~2 s for `make clean && make hugo` (decks + Hugo +
  Pagefind); Hugo itself takes ~20 ms for 24 pages.
- **Content is mounted, not copied.** `hugo.toml` mounts `../content`
  into `content/`, `assets/`, `static/` and `data/` with file filters;
  mounts outside the project directory work.
- **Frontmatter mapping:**
  - NEBULA `type` is Hugo's reserved layout selector, which here is an
    advantage: `type: exercise` uses `layouts/exercise/single.html`,
    `type: slides` uses `layouts/slides/single.html`. No mapping needed.
  - `order` read directly (`sort .Pages "Params.order"`); `category`,
    `abstract`, `thumbnail`, `visibility` read as params in templates.
  - Module `index.md` cannot be mounted as content (see below); a
    *content adapter* (`content/modules/_content.gotmpl`) reads it from
    `assets/` and creates the module section page, frontmatter → params.
    The section is built with `render: never` (a module opens on its
    first page) and `list: always`.
  - Module page bar: a partial (`_partials/module-nav.html`) in the three
    page layouts; icons are mounted from `shared/icons` into `assets/` and
    inlined with `resources.Get`.
- **Study view:** `slides.md` renders its generated study view from
  `assets/` via `.RenderString`, so the page keeps the source's path
  (`/modules/<m>/slides.html`) and its edit link.
- **Links:** a link render hook resolves NEBULA's root-absolute links
  with `site.GetPage`; unknown modules go to the current NEBULA site.
  NEBULA-style links therefore also work in new pages (the PoC page uses
  `/modules/licenses/slides#about-copyright`).
- **Edit this page:** no built-in; a 15-line partial using `.File.Path`
  (relative to the mount, so it mirrors `content/`). The adapter-made
  module pages carry their source path as a param.
- **Search:** none built in; Pagefind (indexes `public/` after the build,
  ~0.06 s) with its default UI.
- **Theme:** Hugo ships none. The look is a hand-written `baseof.html` +
  ~140 lines of CSS, including a light/dark/auto switch (~30 lines of
  inline JS, `data-theme` on `<html>`, remembered in `localStorage`) that
  Quarto and Starlight provide built in. A community theme would reduce the CSS but adds a
  dependency whose templates we would have to override for `type`s.

### What was awkward

- **Leaf bundles.** A folder containing `index.md` is a leaf bundle in
  Hugo: its other `.md` files become non-rendered resources. Every NEBULA
  module has an `index.md`, and mounts cannot rename it to `_index.md`.
  Solved with the content adapter (requires Hugo ≥ 0.126).
- **Mount filters:** the first matching pattern wins, so exclusions must
  precede the include (`["! */index.md", "*/*.md"]`); the other order
  silently includes everything. Not stated in the docs.
- **API churn:** `includeFiles`/`excludeFiles` (removed in 0.153),
  `site.Data` (deprecated 0.156), `languageCode` and
  `.Language.LanguageCode` (deprecated 0.158) all had to be updated for
  the current release; most examples online use the old forms.
- `uglyURLs = true` is needed so `info.md` becomes `info.html` next to
  `media/` and the content's relative image paths work; section pages
  still become `<module>/index.html`.
- Goldmark's automatic heading ids collide with slide ids in the study
  view; fixed with a heading render hook that suffixes ids on `slides`
  pages.
- A section with `build.render: never` also drops out of its parent's
  `.Sections` and `.Pages` unless `list: always` is
  set explicitly, although the docs give `always` as the default.
- Template scoping: inside `range` + `with`, `.` and `$` point at
  different pages; loops need a named variable (`range $p := …`).

### How a non-coder adds an exercise

Same as Quarto: add `content/modules/<module>/<name>.md` with `title`,
`type: exercise`, `order` in the GitHub web editor and open a PR. The
mount picks it up; no Hugo-specific step.

### Upgrade risk

Templates use only public Hugo template functions, but Hugo changes those
often (four deprecations hit this PoC on its current release). The content
adapter and mount `files` syntax are recent (0.126, 0.153). Pin the Hugo
version in CI and expect small template/config edits on upgrades.

### Open issues

- The navigation wraps to two lines at 1280 px; cosmetic.
- No previous/next navigation inside a module (not required; would be
  more template code).
- Several content repos: one mount set per repo; edit links would need the
  repo per page (a param from the mount is not available; untested).

## Astro Starlight (Starlight 0.43.1, Astro 7.4.13)

### Findings

- **All acceptance criteria met:** 67/67 browser checks (`verify_site.py`)
  locally, under the PR-preview path and in CI; deployed to GitHub Pages;
  a typo fix in the GitHub web editor got a PR preview (step 5). No duplicate ids.
- **Custom code:** content loader `nebula-loader.ts` 177 lines, content
  reader `nebula.mjs` 65, `content.config.ts` 38 (schema),
  `astro.config.mjs` 56 (sidebar from content), hub `index.astro` 39,
  `Footer.astro` 20, `site.css` 41, `prepare.py` 54, `poc.md` 23. About
  510 lines, TypeScript/JS for the most part.
- **Toolchain:** Node 22 + npm (288 packages, lockfile committed) + Python 3
  (decks). Pagefind is built in.
- **Clean build:** 4.8 s for `make clean && make starlight`, of which
  ~3 s is `npm ci`; the Astro build itself ~1.1 s for 23 pages.
- **Frontmatter validation (the win):** the collection schema extends
  Starlight's with NEBULA's fields; module `index.md` files are also
  checked by a stricter schema. A typo fails the build with file and field:
  ```
  docs → modules/softwarelandscape/exercise2 data does not match collection schema.
    type: Invalid option: expected one of "info"|"reading"|"exercise"|"slides"
  ```
  ```
  …/modules/softwarelandscape/index.md: invalid module frontmatter
  ✖ Invalid input: expected number, received string
    → at order
  ```
- **Frontmatter mapping** happens in the content loader (content is read
  in place): `editUrl` per page pointing at `content/`; exercise body
  wrapped in a `:::tip[Exercise]` aside; every module page gets the page
  bar (raw HTML, same markup as `module_nav_html()`, reimplemented in TS);
  module `index.md` is validated but not added as a page, so the hub reads
  module frontmatter from the source directly; `slides` pages render their
  study view; NEBULA root-absolute links rewritten.
- **Sidebar:** one group per category in `categoryOrder`, a collapsible
  group per visible module, pages in `order` with the type as a badge;
  built in `astro.config.mjs` from the content (see "awkward").
- **Edit this page:** built in; set per page by the loader.
- **Search:** built in (Pagefind runs as part of `astro build`).
- **Images:** Markdown images (`![](media/x.png)`) are resolved and
  optimised to WebP by Astro; raw `<img>` and decks use the copied
  `public/modules/<m>/media/`.

### What was awkward

- **Starlight assumes files under `src/content/docs/`** in several places
  that a custom loader bypasses:
  - sidebar `autogenerate` matches pages by file path below that folder,
    so it finds none; the sidebar is built in the config instead, and the
    planned `order` → `sidebar.order` mapping is not needed;
  - asides and heading anchor links only run there until
    `markdown.processedDirs: ['../content']` is set;
  - Markdown images stay as `__ASTRO_IMAGE_` placeholders unless the
    loader passes `assetImports`, as Astro's own glob loader does
    (undocumented for custom loaders; found by reading Astro's source).
- **The sidebar is read at config time**, so in `astro dev` a new page
  appears in the sidebar only after a restart (builds are unaffected).
- **Version churn:** Starlight 0.39 removed `autogenerate` groups with a
  label (the error message says exactly what to change). Starlight is
  pre-1.0; minor versions can break config.
- Heading ids in study views collide with slide ids, as in the other
  variants; the loader suffixes heading ids, their anchor links and the
  TOC entries.
- `build.format: 'file'` keeps `info.html` next to `media/`; links are
  written with `.html` so they work on any static host.
- Harmless build warnings: no `i18n` collection, no `404` entry.
- `import.meta.url` in a page (the hub) or in the loader points into
  Astro's build bundle, not the source file; paths to `content/` and
  `shared/` are resolved from the working directory (`starlight/`).
- The module page bar duplicates Starlight's sidebar, which already lists
  each module's pages (with type badges). Kept for parity with NEBULA and
  the other variants; in a Starlight-only build one of the two would go.

### How a non-coder adds an exercise

Same as Quarto and Hugo: add `content/modules/<module>/<name>.md` with
`title`, `type: exercise`, `order` in the GitHub web editor and open a PR.
The loader and sidebar pick it up. Difference: a frontmatter mistake fails
the PR build with a readable message instead of producing a wrong page.

### Upgrade risk

The loader uses Astro's public content-loader API (`parseData`,
`renderMarkdown`, `store.set`), but relies on `assetImports`, which is
not documented for custom loaders. Starlight is 0.x and has broken config
between minors; the sidebar and `processedDirs` settings are the exposed
parts. Pin exact versions (done) and let Renovate/Dependabot propose
updates through PR previews.

### Open issues

- Sidebar needs a dev-server restart for new pages (see above).
- Several content repos: the loader takes a list of sources with their
  own `editBase`, which fits; the sidebar and hub already iterate over
  modules, but only one source is wired (untested with two).
