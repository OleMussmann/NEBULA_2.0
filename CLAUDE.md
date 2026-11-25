# NEBULA successor PoC

The brief (requirements, established facts, architecture, steps, acceptance
criteria, open questions) and progress logs live in the vault, project
`NEBULA_2.0`: run `vault brief NEBULA_2.0`. Read it before working here.
Findings per variant go in `COMPARISON.md`.

## Commands

All tooling comes from `flake.nix`; `make` is not installed system-wide.

- Build: `nix develop --command make quarto|hugo|starlight`
- Everything as Pages will serve it: `nix develop --command make site`
  (`make serve` also starts a server on http://localhost:8000/NEBULA_2.0/)
- Browser acceptance checks (Playwright, separate shell):
  `nix develop .#verify --command make verify-quarto|verify-hugo|verify-starlight`
  Needs network: decks load reveal.js and escience_theme from jsDelivr.

## Rules and gotchas

- Never edit `content/` to make a generator work; map frontmatter inside
  the variant. Refresh it only with `make content`.
- Build Hugo with `make hugo`, not plain `hugo`: search (Pagefind) runs as
  a separate step.
- `make clean` removes the build output of all three variants.
- Decks/study views are generated next to the slides sources in
  `content/` (git-ignored); every variant runs `tools/build_study.py`
  first.
- Screenshots of decks need ~2 s for the theme overlays to fade in.
- GitHub-side operations (push, Pages settings, PRs): give Ole the exact
  steps; do not run them.
