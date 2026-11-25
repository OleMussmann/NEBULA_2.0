---
title: About this PoC
noedit: true
---

This is the **Hugo** variant of the
[NEBULA successor PoC](https://github.com/OleMussmann/NEBULA_2.0): the same
three lessons are also built with Quarto and Astro Starlight.

## Linking to a slide

Every slide has a stable id, taken from its first heading or an explicit
`id="..."`. Text pages can link to it with a NEBULA-style link, which the
link render hook resolves:

- the study view, at that slide:
  [About copyright](/modules/licenses/slides#about-copyright)
- the deck, opened at that slide:
  [About copyright (presentation)](modules/licenses/slides.deck.html#/about-copyright)

## Presenting

Open a deck and press **S** for the speaker view. Add `?annotations` to the
deck URL to show the notes beside the slides, as learners see them in NEBULA:
[deck with notes](modules/licenses/slides.deck.html?annotations#/about-copyright).
