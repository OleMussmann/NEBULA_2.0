#!/usr/bin/env python3
"""Turn a NEBULA-style reveal.js Markdown deck into a deck page and a study view.

Input: a slides file from the content repo (frontmatter with `type: slides`,
slides separated by `===`, vertical slides by `==`, notes after `Note:`).
That is the same dialect NEBULA's components/Slides.vue feeds to reveal.js.

Outputs, both written next to each other in the output directory:

  <stem>.deck.html  stand-alone reveal.js page (vanilla reveal.js + escience_theme)
  <stem>.study.md   generator-agnostic Markdown: every slide as a section,
                    followed by its notes as prose, with stable anchors and
                    "present from here" links into the deck

Every slide gets a stable id, derived from its first heading (or an explicit
`id="..."` in its `<!-- .slide: -->` comment), so links survive inserting
slides. The same id is used as the deck hash (#/<id>) and the study anchor.

Presenter-only notes: wrap text inside a Note: block in
`<div class="presenter-only"> ... </div>`. It is removed from the study view
and hidden in the deck's on-screen notes, but stays in the speaker view.

Standard library only, so it runs anywhere Python 3.9+ runs.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Same separators as NEBULA's Slides.vue
H_SEP = re.compile(r"^\r?\n?===\r?\n?$", re.M)
V_SEP = re.compile(r"^\r?\n?==\r?\n?$", re.M)
NOTES_SEP = re.compile(r"^Note:", re.M)
FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
SLIDE_ATTR = re.compile(r"<!--\s*\.slide:\s*(.*?)-->", re.S)
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.M)
PRESENTER_ONLY = re.compile(
    r'<div class="presenter-only">.*?</div>', re.S | re.I
)

REVEAL_VERSION = "5.2.1"   # pin; NEBULA uses ~5.2.1
THEME_VERSION = "0.3.0"    # escience_theme


@dataclass
class Slide:
    h: int            # horizontal index
    v: int            # vertical index
    body: str         # slide Markdown without the attribute comment
    notes: str        # notes Markdown ("" if none)
    attrs: str        # raw attribute string from <!-- .slide: ... -->
    sid: str = ""     # stable id


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, text[m.end():]


def slugify(s: str) -> str:
    s = re.sub(r"<[^>]+>|[*_`\[\]()]", "", s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "slide"


def split_slides(md: str) -> list[Slide]:
    slides = []
    for h, hchunk in enumerate(H_SEP.split(md)):
        for v, chunk in enumerate(V_SEP.split(hchunk)):
            parts = NOTES_SEP.split(chunk, maxsplit=1)
            body = parts[0]
            notes = parts[1].strip() if len(parts) > 1 else ""
            attrs = " ".join(a.strip() for a in SLIDE_ATTR.findall(body))
            body = SLIDE_ATTR.sub("", body).strip()
            slides.append(Slide(h, v, body, notes, attrs))
    return slides


def assign_ids(slides: list[Slide]) -> None:
    seen: dict[str, int] = {}
    for s in slides:
        explicit = re.search(r'\bid="([^"]+)"', s.attrs)
        if explicit:
            base = explicit.group(1)
        else:
            m = HEADING.search(s.body)
            base = slugify(m.group(2)) if m else f"slide-{s.h}-{s.v}"
        n = seen.get(base, 0)
        seen[base] = n + 1
        s.sid = base if n == 0 else f"{base}-{n + 1}"


def rebuild_deck_md(slides: list[Slide]) -> str:
    """Deck Markdown with ids merged into each slide's attribute comment."""
    out_h: list[list[str]] = []
    for s in slides:
        attrs = re.sub(r'\s*\bid="[^"]*"', "", s.attrs).strip()
        attrs = f'id="{s.sid}" {attrs}'.strip()
        chunk = f"<!-- .slide: {attrs} -->\n\n{s.body}"
        if s.notes:
            chunk += f"\n\nNote:\n{s.notes}"
        if s.v == 0:
            out_h.append([chunk])
        else:
            out_h[-1].append(chunk)
    return "\n\n===\n\n".join("\n\n==\n\n".join(v) for v in out_h)


def demote_headings(md: str, by: int = 1) -> str:
    """Slide '#'/'##' headings become one level lower in the study page."""
    return HEADING.sub(lambda m: "#" * min(6, len(m.group(1)) + by) + " " + m.group(2), md)


def deck_html(title: str, deck_md: str) -> str:
    # The Markdown goes into a <textarea data-template> so reveal.js reads it
    # verbatim; only a literal </textarea> would need escaping.
    safe_md = deck_md.replace("</textarea>", "&lt;/textarea>")
    cdn = "https://cdn.jsdelivr.net/npm"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{cdn}/reveal.js@{REVEAL_VERSION}/dist/reveal.css">
<link rel="stylesheet" href="{cdn}/reveal.js@{REVEAL_VERSION}/dist/theme/black.css">
<link rel="stylesheet" href="{cdn}/reveal.js@{REVEAL_VERSION}/plugin/highlight/monokai.css">
<link rel="stylesheet" href="{cdn}/escience_theme@{THEME_VERSION}/escience.css">
<style>.reveal .speaker-notes .presenter-only {{ display: none; }}</style>
</head>
<body>
<div class="reveal"><div class="slides">
<section data-markdown
         data-separator="^\\r?\\n===\\r?\\n$"
         data-separator-vertical="^\\r?\\n==\\r?\\n$"
         data-separator-notes="^Note:">
<textarea data-template>
{safe_md}
</textarea>
</section>
</div></div>
<script type="module">
import Reveal from "{cdn}/reveal.js@{REVEAL_VERSION}/dist/reveal.esm.js";
import Markdown from "{cdn}/reveal.js@{REVEAL_VERSION}/plugin/markdown/markdown.esm.js";
import Notes from "{cdn}/reveal.js@{REVEAL_VERSION}/plugin/notes/notes.esm.js";
import Search from "{cdn}/reveal.js@{REVEAL_VERSION}/plugin/search/search.esm.js";
import Math from "{cdn}/reveal.js@{REVEAL_VERSION}/plugin/math/math.esm.js";
import Escience from "{cdn}/escience_theme@{THEME_VERSION}/escience.js";
const params = new URLSearchParams(location.search);
// Exposed as window.Reveal, like reveal.js's non-module build (debugging,
// tools/verify_site.py).
const deck = window.Reveal = new Reveal({{
  hash: true, controls: true, progress: true, center: true, transition: "none",
  // ?annotations shows notes under the slides (NEBULA default). Not ?notes:
  // the notes plugin auto-opens the speaker window for that parameter.
  showNotes: params.has("annotations"),
  plugins: [Markdown, Notes, Search, Math, Escience],
}});
deck.initialize();
</script>
</body>
</html>
"""


def study_md(meta: dict, slides: list[Slide], deck_href: str) -> str:
    title = meta.get("title", "Slides")
    lines = [
        "---",
        f'title: "{title} (study view)"',
        "type: study",
        f"order: {meta.get('order', 0)}",
        "---",
        "",
        f'<p class="study-intro"><a href="{deck_href}">Open as presentation</a> · '
        f'<a href="{deck_href}?annotations">with notes</a></p>',
        "",
    ]
    for i, s in enumerate(slides, 1):
        notes = PRESENTER_ONLY.sub("", s.notes).strip()
        lines += [
            f'<section class="study-slide" id="{s.sid}">',
            "",
            f'<div class="study-slide-content">',
            "",
            demote_headings(s.body),
            "",
            "</div>",
            "",
        ]
        if notes:
            lines += ['<div class="study-notes">', "", notes, "", "</div>", ""]
        lines += [
            f'<p class="study-present"><a href="{deck_href}#/{s.sid}">'
            f"Present from slide {i}</a></p>",
            "",
            "</section>",
            "",
        ]
    return "\n".join(lines)


def build(src: Path, outdir: Path) -> tuple[Path, Path]:
    meta, md = parse_frontmatter(src.read_text(encoding="utf-8"))
    if meta.get("type") not in (None, "slides"):
        raise SystemExit(f"{src}: not a slides file (type: {meta.get('type')})")
    slides = split_slides(md)
    assign_ids(slides)
    outdir.mkdir(parents=True, exist_ok=True)
    deck_path = outdir / f"{src.stem}.deck.html"
    study_path = outdir / f"{src.stem}.study.md"
    deck_path.write_text(deck_html(meta.get("title", src.stem), rebuild_deck_md(slides)), encoding="utf-8")
    study_path.write_text(study_md(meta, slides, deck_path.name), encoding="utf-8")
    return deck_path, study_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("slides", nargs="+", type=Path, help="slides Markdown file(s)")
    ap.add_argument("-o", "--outdir", type=Path, default=None,
                    help="output directory (default: next to each input)")
    args = ap.parse_args(argv)
    for src in args.slides:
        deck, study = build(src, args.outdir or src.parent)
        print(f"{src} -> {deck.name}, {study.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
