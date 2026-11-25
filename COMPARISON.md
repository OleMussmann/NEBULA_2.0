# Comparison: Quarto, Hugo, Astro Starlight

Draft, filled in per variant as it is built; completed in step 6 with
screenshots and a recommendation. Findings and opinion are kept apart:
everything under "Findings" was observed while building and checking.

Acceptance checks are automated: `tools/verify_site.py <variant>` serves the
built site under `/NEBULA_2.0/<variant>/` and drives headless Chromium
through hub, module pages, study view, deck (theme, `#/<id>`, `S` speaker
view, `?annotations`), presenter-only notes, slide-id links, `main/` pages,
search and broken requests.

## Shared (all variants)

Code every variant uses, not counted per variant:

| File | Lines | Purpose |
|---|---|---|
| `tools/build_study.py` | 242 | decks + study views |
| `tools/nebula_content.py` | 148 | read config/modules/pages, rewrite links |
| `shared/study.css` | 78 | study-view layout |
| `tools/verify_site.py` | 285 | acceptance checks (test code) |

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

## Quarto (1.10.18)

### Findings

- **All acceptance checks pass** locally under the sub-path (32/32),
  except the CI/Pages and web-editor PR preview items (step 5).
- **Custom code:** `quarto/prepare.py` 276 lines (pre-render),
  `_quarto.yml` 49, `styles.css` 16, `poc.qmd` 24 (PoC page with the
  example slide link). No templates, no Lua filters, no EJS.
- **Toolchain:** Quarto (bundles Pandoc, Deno, Dart Sass) + Python 3 for
  the pre-render. One binary install; no npm.
- **Clean build:** 7.5 s (`make clean && make quarto`; 22 pages).
- **Frontmatter mapping** happens in `prepare.py`, which mirrors `content/`
  into the project (content is never edited):
  - `abstract` → `description`, `thumbnail` → `image: media/<file>`
  - page `type` → `categories` (rendered as a badge; module table "Type"
    column)
  - `type: exercise` body wrapped in a callout
  - module page: a listing of its pages in `order`, from a generated
    YAML file
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
4. The PR preview (step 5) shows it in the module table at its `order`,
   with the exercise callout.

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

## Hugo

Not built yet (step 3).

## Astro Starlight

Not built yet (step 4).
