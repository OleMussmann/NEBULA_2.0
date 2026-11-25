# NEBULA successor PoC

The same two-lesson site (Software Licenses, The Research Software Landscape)
built three times — with Quarto, Hugo and Astro Starlight — to compare them
as a replacement for NEBULA.

Slides stay vanilla reveal.js with the `escience_theme`. Each generator only
renders the text pages, module pages and hub, and ships the decks as static
files.

## Layout

```
tools/build_study.py      slides.md → slides.deck.html (reveal.js) + slides.study.md (study view)
tools/import_content.sh   refresh content/ from research-software-support
content/                  sparse copy of research-software-support (see content/SOURCE)
shared/study.css          study-view styles, used by all variants
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
make content REF=…   # re-import content from upstream (default: main)
make clean
```

Generated `*.deck.html` and `*.study.md` are build artefacts and git-ignored.
