# NEBULA successor PoC

The same three-lesson site (Software Licenses, The Research Software Landscape,
Generative AI)
built three times — with Quarto, Hugo and Astro Starlight — to compare them
as a replacement for NEBULA.

Slides stay vanilla reveal.js with the `escience_theme`. Each generator only
renders the text pages, module pages and hub, and ships the decks as static
files.

## Layout

```
tools/build_study.py      slides.md → slides.deck.html (reveal.js) + slides.study.md (study view)
tools/nebula_content.py   read content/ (config, modules, pages) and rewrite its site links
tools/verify_site.py      acceptance checks in headless Chromium, per variant
tools/import_content.sh   refresh content/ from research-software-support
content/                  sparse copy of research-software-support (see content/SOURCE)
shared/study.css          study-view styles, used by all variants
shared/module-nav.css     module page bar (pages in order, type icons), used by all variants
shared/icons/             page-type icons for the bar
quarto/  hugo/  starlight/
.devcontainer/            Python + Quarto + Hugo + Node for Codespaces
flake.nix                 the same toolchain on Nix
```

`content/` is a committed copy rather than a submodule, so a typo fix made in
the GitHub web editor of this repo gets a PR preview. Do not edit it to make
a generator work; map frontmatter inside the variant instead.

## Build

```sh
nix develop          # or open in a devcontainer / Codespace
make study           # generate decks and study views next to each slides.md
make quarto          # build the Quarto variant into quarto/_site
make hugo            # build the Hugo variant into hugo/public (+ Pagefind)
make starlight       # build the Starlight variant into starlight/dist
make serve           # all three as Pages serves them: http://localhost:8000/NEBULA_2.0/
nix develop .#verify --command make verify-quarto   # browser checks (or verify-hugo, verify-starlight)
                     #   THEME_DIR=<escience_theme checkout>: unpublished theme
make content REF=…   # re-import content from upstream (default: main)
                     #   CONTENT_REPO=<path>: e.g. a local clone's branch
make clean
```

Generated `*.deck.html` and `*.study.md` are build artefacts and git-ignored.

## CI and previews

- `.github/workflows/deploy.yml`: every push to `main` builds all three
  variants, runs the browser checks and publishes `_site/NEBULA_2.0/` to the
  `gh-pages` branch, served at https://olemussmann.github.io/NEBULA_2.0/.
- `.github/workflows/preview.yml`: every pull request is built under
  `/NEBULA_2.0/pr-preview/pr-<number>/` and published to `gh-pages` too
  ([rossjrw/pr-preview-action](https://github.com/rossjrw/pr-preview-action));
  the action comments the link on the PR and removes the preview when the
  PR closes. The preview goes up before the checks run.

The path the site is served under comes from `SITE_PATH` (default
`/NEBULA_2.0`), e.g. `make site SITE_PATH=/NEBULA_2.0/pr-preview/pr-1`.
Repository settings: Pages deploys from the `gh-pages` branch (root);
Actions have read and write permissions.

## License

The code in this repository (everything outside `content/`) is licensed
under the [Apache License 2.0](LICENSE).

`content/` is **not** covered by that license. It is a copy of
[research-software-support](https://github.com/esciencecenter-digital-skills/research-software-support)
by the Netherlands eScience Center, at the commit recorded in
`content/SOURCE`. Its text is licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); image files keep
their own terms, as credited in the lessons. See
[`content/LICENSE.md`](content/LICENSE.md).
