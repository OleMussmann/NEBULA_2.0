# Replacing NEBULA: Quarto, Hugo and Astro Starlight compared

## What this is about

[NEBULA](https://github.com/esciencecenter-digital-skills/NEBULA) is the
Netherlands eScience Center's platform for teaching material. It is a Nuxt
application that turns a lesson repository (for example
[research-software-support](https://github.com/esciencecenter-digital-skills/research-software-support))
into a website: a hub with one card per module, and per module a set of
pages (information, reading, exercises) and reveal.js slide decks in the
eScience Center's theme (`escience_theme`). Lesson authors write Markdown
with a small frontmatter (`title`, `type`, `order`) and need no knowledge of
the platform.

NEBULA is custom code that has to be maintained. This repository tests
whether an off-the-shelf static site generator can do the same job, by
building **the same site three times** from the same, unmodified lesson
content:

| Variant | Live site |
|---|---|
| Quarto 1.10 | https://olemussmann.github.io/NEBULA_2.0/quarto/ |
| Hugo 0.170 | https://olemussmann.github.io/NEBULA_2.0/hugo/ |
| Astro Starlight 0.43 | https://olemussmann.github.io/NEBULA_2.0/starlight/ |

The content is a copy of three modules of research-software-support
(software licenses, the research software landscape, generative AI) plus its
About, Contribute, Workshops and Yellow Pages pages.

**Status:** all three variants are built, deployed and checked. This
document records what was observed. It does not contain a recommendation
yet.

## What every variant had to do

Each variant meets the same requirements, and the same automated browser
test (`tools/verify_site.py`, 67 checks per variant) confirms them on every
build:

- **Hub:** modules grouped by category, each with thumbnail and abstract.
- **Module pages, as in NEBULA:** a module opens on its first page (the
  learning objectives); every page shows a bar with all pages of the module
  in order, each with an icon for its type (info, reading, exercise,
  slides).
- **Slides:** the deck runs with the eScience theme; `S` opens the speaker
  view with notes; `?annotations` shows notes under the slides.
- **Study view:** every deck also appears as a normal web page, with each
  slide followed by its notes, a stable anchor per slide and a "present
  from slide N" link into the deck. Readable in light and dark mode (text
  contrast is measured).
- **Links into slides:** a text page can link to a slide by its id.
- **Search**, **"Edit this page"** links to the source on GitHub, and
  photo credits for the module thumbnails in the page footer.
- **Hosting:** static files on GitHub Pages, served from a sub-path.
- **Authoring without tools:** a typo fix made in the GitHub web editor
  gets a preview of the whole site, linked from the pull request.

All of these hold for all three variants.

Some parts are shared and not generator-specific, so they say nothing about
the generators:

| Shared part | Lines | What it does |
|---|---|---|
| `tools/build_study.py` | 275 | turns a slides file into a deck page and a study-view page; warns about inline colours in slides |
| `tools/nebula_content.py` | 180 | reads the lesson repository's configuration and modules, rewrites links, builds the module page bar |
| `shared/study.css`, `shared/module-nav.css`, `shared/icons/` | 162 + 4 icons | look of the study view and the page bar |
| `.github/workflows/` | 96 | build, test and deploy; PR previews |
| `tools/verify_site.py` | 499 | the browser test |

## The variants at a glance

| | Quarto | Hugo | Astro Starlight |
|---|---|---|---|
| Generator-specific code (excluding the PoC's own info page) | ~340 lines: a Python pre-render script (277), config, CSS | ~480 lines: Go templates (267), config, CSS (140) | ~560 lines: TypeScript/JS (~460), config, CSS, a small copy script |
| Tools to install | Quarto (one install) + Python | Hugo (one binary) + Python; Node only for search | Node + npm (288 packages) + Python |
| Clean build (laptop) | 7.5 s | ~2 s | ~5 s (3 s of it `npm ci`) |
| Search | built in | added (Pagefind) | built in |
| "Edit this page" | built in; position varies (see below) | own template (15 lines) | built in |
| Light/dark mode switch | built in | own code (~30 lines JS) | built in |
| Table of contents per page | built in | none yet | built in |
| Frontmatter errors | produce a wrong page | produce a wrong page | fail the build with file and field |
| How the content gets in | copied into the project by a script | mounted in place by Hugo | read in place by a custom content loader |
| Upgrade risk | low: script writes ordinary Quarto input | medium: Hugo deprecates template functions often | medium: Starlight is pre-1.0 and has broken config between minor versions |

Build times are for this small site (22–24 pages) and say little about
large sites; all three are fast enough.

## Findings that apply to any generator

- **NEBULA's links need rewriting.** Lesson content links to other pages
  with root-absolute, extension-less paths (`/modules/softwarelandscape/slides`,
  `/main/yellowpages`). They break as soon as the site is served from a
  sub-path or the generator's URLs differ from NEBULA's. Every variant
  rewrites them. Links to modules that are not part of the site are sent
  to the module's current NEBULA site.
- **The content is CommonMark** (NEBULA uses Nuxt Content, reveal.js uses
  marked). A generator with a different Markdown dialect misreads some of
  it, for example a line indented by four or more spaces inside an HTML
  table. Quarto needed to be switched to CommonMark for this reason.
- **The module `index.md` is metadata, not a page.** Its frontmatter feeds
  the hub card and the page bar; its body is the thumbnail's photo credit,
  which (for a CC BY-SA photo) has to be shown somewhere. The variants show
  all credits in the page footer. Each generator needed its own way to read
  these files without making them pages.
- **Slides shown outside the deck.** The study view puts slide HTML on an
  ordinary web page. The eScience theme sets text colours per slide
  background; a box that sets only an inline background colour
  (`style="background: lightgray"`) keeps the surrounding text colour and
  becomes unreadable on a dark slide or on a page in dark mode. This was
  solved in the theme and the content rather than per site:
  - `escience_theme` 0.4.0 provides its layout classes (`.card`,
    `.columns`, `.stepper`, `.muted`) as a separate `components.css` that
    also works outside a deck; the study views load it and follow the
    site's light or dark mode.
  - The gen-ai lesson was rewritten to use these classes instead of inline
    colours. This change is a pull request in research-software-support;
    it can be merged once NEBULA uses theme 0.4.0. The PoC already uses it.
  - `build_study.py` warns about inline text or background colours in
    slides, and the browser test measures text contrast on every slide (in
    the deck with all fragments shown, and in the study view in light and
    dark mode). Not measured: text over background images.
- **The study view loses some of the deck.** Background images and videos
  are not shown, all fragments are expanded, and a deck's `<style>` blocks
  end up on the page. Whether reveal.js's own scroll view (the rendered
  slides as a scrolling page) would be a better study view has not been
  tried.
- **PR previews work for branches, not forks.** Every pull request is
  built and published under `/NEBULA_2.0/pr-preview/pr-<n>/`, with a link
  posted on the pull request and removed when it closes. Pull requests
  from forks get a read-only token and cannot publish a preview. Edits in
  the GitHub web editor by people with write access create a branch in the
  repository, so they do get one.
- **The serving path must be a build setting.** Previews live one level
  deeper than the site. Quarto writes only relative links and works under
  any path unchanged. Hugo and Starlight write absolute paths into every
  page and take the path as a build parameter.
- **GitHub Pages needs a `.nojekyll` file**, or its default Jekyll
  processing drops folders starting with `_` (Astro's `_astro/`).

## Quarto

### How it works

A Python script (`quarto/prepare.py`) runs before each Quarto render. It
copies the lesson content into the Quarto project and adjusts it on the
way, without changing the source:

- NEBULA's frontmatter is mapped to Quarto's: `abstract` → `description`,
  `thumbnail` → `image`, the page `type` → a category badge under the
  title. Values are re-written with proper types, because Quarto reserves
  `order` and rejects it as a string.
- Exercise pages are wrapped in a callout box titled "Exercise".
- Each module page gets the page bar as raw HTML.
- The hub is a generated page with one card grid (a Quarto "listing") per
  category, in the configured category order, showing only visible
  modules.
- A slides file is replaced by its study view under the same name, so
  NEBULA's `/modules/<m>/slides` maps one to one and "Edit this page" opens
  the slides source.

Search and "Edit this page" are Quarto features. No templates, Lua filters
or JavaScript were written.

### What was awkward

- Quarto's default Markdown is Pandoc's, not CommonMark. The content needs
  `from: commonmark_x`, but the generated hub needs Pandoc Markdown (its
  `:::` listing placeholders are not CommonMark).
- In the study view, Quarto wraps headings in `<section>` elements that
  overlap the study view's own wrappers; Quarto's HTML post-processing then
  closes the wrappers early and the slide boxes end up empty. Turning off
  `section-divs` on study pages fixes it.
- Automatic heading ids collide with the slide ids (`#about-copyright`
  twice). Turning automatic ids off crashes Quarto's own filters and
  `id-prefix` has no effect, so the script writes explicit heading ids.
- In listings defined in a YAML file, `path` is resolved relative to the
  YAML file but `image` relative to the page.
- Files and folders starting with `_` are silently ignored, including
  listing YAML files.
- Generated pages must be listed in the project's `render` list.

### Upgrade risk

The script writes ordinary Quarto input and relies on documented options
(listings from YAML, `metadata-files`, `repo-actions`, `section-divs`,
`from:`). Two workarounds depend on details that could change: the
`path`/`image` resolution difference and how Quarto treats overlapping
sections.

### Open issues

- **The edit link moves.** Quarto puts "Edit this page" under the table of
  contents. On a page without table-of-contents entries it moves to the
  page footer, where it is easy to miss: pages without headings (such as
  the learning objectives) and exercise pages (next point).
- **Exercise headings are missing from the table of contents**, because
  Quarto leaves out headings inside callout boxes. An exercise whose only
  heading is inside the box has an empty table of contents. A possible fix:
  an own edit link under the page bar on every page, and the exercise
  frame as a styled block instead of a callout.
- The generated hub has no edit link; changing it means changing the
  script or the lesson repository's `config.json`.
- With several lesson repositories, the edit-link base is set for the
  whole project; per-page links to a second repository are untested.
- Quarto itself emits a few duplicate element ids (theme `<link>`s, figure
  ids in one study view); harmless so far.

## Hugo

### How it works

Hugo reads the lesson content in place: `hugo.toml` mounts the content
folder into Hugo's content, assets, static and data folders, with filters.
There is no pre-processing script of its own.

- NEBULA's `type` happens to be Hugo's layout selector, so `type: exercise`
  and `type: slides` pick their own page layouts without any mapping.
  `order`, `category`, `abstract`, `thumbnail` and `visibility` are read
  directly in the templates.
- The module `index.md` files are read by a Hugo *content adapter*
  (`content/modules/_content.gotmpl`), which turns each into a module
  section that is listed but not rendered as a page.
- A link render hook resolves NEBULA's root-absolute links to the actual
  pages, so they also work in new pages.
- The page bar is a template partial; the icons are inlined from the
  shared SVG files.

Hugo ships no theme. The look is a hand-written base template and about
140 lines of CSS, including a light/dark/auto switch. Search is added with
Pagefind, which indexes the built site. "Edit this page" is a short
template using the page's source path. A community theme would reduce the
CSS but adds a dependency whose templates would have to be overridden for
NEBULA's page types.

### What was awkward

- **Leaf bundles.** For Hugo, a folder that contains `index.md` is a single
  page whose other Markdown files are not rendered. Every NEBULA module has
  an `index.md`, and mounts cannot rename it. The content adapter (Hugo
  ≥ 0.126) works around this.
- **Mount filters:** the first matching pattern wins, so exclusions must
  come before inclusions; the other order silently includes everything.
  The documentation does not say so.
- **API churn:** four options or functions used here were removed or
  deprecated in recent releases (`includeFiles`/`excludeFiles`,
  `site.Data`, `languageCode`, `.Language.LanguageCode`); most examples
  online use the old forms.
- `uglyURLs` is needed so `info.md` becomes `info.html` next to the
  module's `media/` folder and the content's relative image paths work.
- Automatic heading ids collide with slide ids in the study view; a
  heading render hook adds a suffix on slides pages.
- A section that is not rendered also drops out of its parent's page lists
  unless `list: always` is set explicitly, although the documentation gives
  that as the default.
- Inside nested template blocks, `.` and `$` refer to different pages;
  loops need named variables.

### Upgrade risk

The templates use only public functions, but Hugo changes those often. The
content adapter and the mount syntax used are recent (0.126, 0.153). Pin
the Hugo version and expect small template changes on upgrades.

### Open issues

- No table of contents on pages (the other two variants have one); Hugo
  provides one (`.TableOfContents`) that the layouts do not use yet.
- No previous/next navigation within a module.
- The top navigation wraps to two lines at 1280 px width.
- With several lesson repositories, edit links would need to know each
  page's repository; untested.

## Astro Starlight

### How it works

Starlight is a documentation theme for Astro. A custom content loader
(`starlight/src/nebula-loader.ts`) reads the lesson content in place and
hands each page to Starlight:

- **Frontmatter validation.** The content schema extends Starlight's with
  NEBULA's fields, and module `index.md` files get a stricter schema of
  their own. A typo fails the build and names the file and field:
  ```
  docs → modules/softwarelandscape/exercise2 data does not match collection schema.
    type: Invalid option: expected one of "info"|"reading"|"exercise"|"slides"
  ```
  ```
  …/modules/softwarelandscape/index.md: invalid module frontmatter
  ✖ Invalid input: expected number, received string
    → at order
  ```
  Quarto and Hugo silently produce a wrong page in these cases.
- Exercise pages are wrapped in an "Exercise" aside; each page gets the
  page bar (the same markup as the shared Python code, re-implemented in
  TypeScript); slides pages show their study view; NEBULA's links are
  rewritten.
- The sidebar has one group per category and one collapsible group per
  module, with pages in order and their type as a badge. It is built in
  `astro.config.mjs` from the content.
- Search (Pagefind), "Edit this page", light/dark mode and the table of
  contents are Starlight features. Markdown images are optimised to WebP.

### What was awkward

- **Starlight assumes pages live in `src/content/docs/`.** Content from a
  custom loader bypasses several features:
  - automatic sidebars match pages by file path, so they find none; the
    sidebar is built in the config instead;
  - callout syntax and heading anchor links only work after
    `markdown.processedDirs` is pointed at the content folder;
  - Markdown images stay unresolved unless the loader passes
    `assetImports`, as Astro's own loader does. This is not documented for
    custom loaders and was found by reading Astro's source.
- **The sidebar is read once at startup**, so in the development server a
  new page appears in the sidebar only after a restart (builds are not
  affected).
- **Version churn:** Starlight 0.39 removed a sidebar option used by the
  original plan. Starlight is pre-1.0; minor versions can break config.
- Automatic heading ids collide with slide ids in the study view; the
  loader adds a suffix to heading ids, their anchor links and the table of
  contents entries.
- `build.format: 'file'` keeps `info.html` next to `media/`, and links are
  written with `.html` so they work on any static host.
- Inside the build, `import.meta.url` points into Astro's bundle, not the
  source file; paths are resolved from the working directory instead.
- The page bar duplicates the sidebar, which already lists each module's
  pages. It is kept for parity with NEBULA and the other variants; a
  Starlight-only site would drop one of the two.

### Upgrade risk

The loader uses Astro's public content-loader API, but relies on
`assetImports`, which is undocumented for custom loaders. Starlight is 0.x
and has broken config between minor versions; the sidebar and
`processedDirs` settings are the exposed parts. Versions are pinned
exactly; updates would come as pull requests (Renovate or Dependabot) and
be checked through their previews.

### Open issues

- New pages need a development-server restart to appear in the sidebar.
- Several lesson repositories: the loader takes a list of sources, each
  with its own edit-link base, but only one source is wired up (untested
  with two).
- Harmless build warnings (no `i18n` collection, no `404` entry).

## How an author adds an exercise

The same in all three variants:

1. On GitHub, open `content/modules/<module>/` and choose "Add file →
   Create new file".
2. Name it, for example `ex_my_exercise.md`, and copy the frontmatter of
   another exercise (`title`, `type: exercise`, `order`).
3. Write the exercise, then "Commit changes" → "Create a new branch and
   start a pull request".
4. The pull request gets a preview link; the new exercise appears in the
   module's page bar at its `order`.

No generator-specific step. The one difference: in Starlight, a mistake in
the frontmatter fails the preview build with a readable message; in Quarto
and Hugo it produces a page in the wrong place or with the wrong type.
