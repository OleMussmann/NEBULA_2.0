#!/usr/bin/env python3
"""Quarto pre-render: turn NEBULA content into Quarto project input.

Runs as `project.pre-render` (cwd = this directory). Content is never edited
in place; it is mirrored into this project with these mappings:

- decks: tools/build_study.py writes <stem>.deck.html + <stem>.study.md
- `type: slides` sources are replaced by their study view (same file name)
- page `type` becomes a Quarto `categories` badge; `type: exercise` bodies
  are wrapped in a callout
- every module page starts with the module's page bar (all its pages in
  `order`, with type icons), as NEBULA's chapter bar; module index.md is not
  rendered as a page: its frontmatter feeds the hub card, its body (the
  thumbnail's photo credit) goes into the page footer, and the module opens
  on its first page
- NEBULA root-absolute links (/main/x, /modules/m/p) become relative links
  to the mirrored .md files (/modules/m: the module's first page); links to
  modules not in this site go to the module's current NEBULA site
- index.qmd (hub, one listing per category in categoryOrder), the navbar
  entries for main/ pages and the footer's left part (content licence and
  thumbnail credits) are generated

Generated paths are git-ignored. The mirror keeps content/'s layout, so
`repo-subdir: content` makes Quarto's "Edit this page" point at the source.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "tools"))

import build_study  # noqa: E402
from nebula_content import (  # noqa: E402
    Module, Page, Source, load, module_nav_html, rewrite_site_links,
    thumbnail_credit, yaml_str,
)

# Content repos merged into this site. One today; the hub iterates over all.
SOURCES = [REPO / "content"]

GENERATED = ["main", "modules", "hub", "_shared", "index.qmd", "_generated.yml"]


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def clean() -> None:
    for name in GENERATED:
        p = HERE / name
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()


def link_resolver(src: Source, page_out: Path):
    """resolve(path) for rewrite_site_links, relative to the output page."""

    def rel(target: Path) -> str:
        return os.path.relpath(target, page_out.parent).replace(os.sep, "/")

    def resolve(path: str) -> str | None:
        parts = path.strip("/").split("/")
        if parts[0] == "main" and len(parts) == 2:
            if (src.root / "main" / f"{parts[1]}.md").is_file():
                return rel(HERE / "main" / f"{parts[1]}.md")
        elif parts[0] == "modules" and len(parts) >= 2:
            mod = src.module(parts[1])
            if mod is None:
                return src.upstream_site + path     # not in this site
            if len(parts) == 2 and mod.pages:
                return rel(HERE / "modules" / mod.slug / mod.pages[0].path.name)
            page = next((p for p in mod.pages if p.stem == parts[2]), None)
            if page is not None:
                return rel(HERE / "modules" / mod.slug / page.path.name)
        print(f"prepare.py: unresolved site link {path}", file=sys.stderr)
        return None

    return resolve


def front(fields: dict[str, object], extra: str = "") -> str:
    lines = ["---"]
    for k, v in fields.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(yaml_str(x) for x in v)}]")
        elif re.fullmatch(r"-?\d+(\.\d+)?", str(v)):
            lines.append(f"{k}: {v}")           # Quarto requires numeric `order`
        else:
            lines.append(f"{k}: {yaml_str(str(v))}")
    return "\n".join(lines) + ("\n" + extra.rstrip() if extra else "") + "\n---\n"


def write_page(src: Source, page: Page, out: Path, extra_meta: dict | None = None,
               extra_yaml: str = "", mod: Module | None = None) -> None:
    body = rewrite_site_links(page.body, link_resolver(src, out))
    meta = {k: v for k, v in page.meta.items()}
    if page.type in ("info", "reading", "exercise"):
        meta["categories"] = [page.type]
    if page.type == "study":
        meta["categories"] = ["slides"]
    if page.type == "exercise":
        body = f'::: {{.callout-tip icon="false" title="Exercise"}}\n\n{body.strip()}\n\n:::\n'
    if mod is not None:
        body = f"{module_nav_html(mod, page)}\n\n{body}"
    meta.update(extra_meta or {})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(front(meta, extra_yaml) + body, encoding="utf-8")


STUDY_SECTION = re.compile(r'<section class="study-slide" id="([^"]+)">')
ATX = re.compile(r"^(#{1,6}[ \t]+.+?)[ \t]*$", re.M)


def explicit_heading_ids(body: str) -> str:
    """Give study-view headings ids derived from their slide id.

    Pandoc's automatic heading ids would duplicate the slide ids that
    build_study.py puts on each <section> (a slide titled "About copyright"
    has id about-copyright), and Quarto breaks without heading ids.
    """
    out, sid, n = [], "study", 0
    for part in re.split(r"(?=<section class=\"study-slide\")", body):
        m = STUDY_SECTION.match(part)
        if m:
            sid, n = m.group(1), 0

        def sub(h: re.Match) -> str:
            nonlocal n
            n += 1
            return f"{h.group(1)} {{#{sid}--{n}}}"

        out.append(ATX.sub(sub, part))
    return "".join(out)


def mirror_module(src: Source, mod: Module) -> None:
    out_dir = HERE / "modules" / mod.slug
    # media, decks and any other non-Markdown files, as-is
    for f in mod.dir.rglob("*"):
        if f.is_file() and f.suffix != ".md":
            dest = out_dir / f.relative_to(mod.dir)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
    for p in mod.pages:
        if p.type == "slides":
            # The study view takes the deck source's place (slides.md ->
            # slides.html): "Edit this page" then opens the deck source, and
            # NEBULA's /modules/<m>/slides URL maps 1:1.
            study = mod.dir / f"{p.stem}.study.md"
            sp = Page(study, *_split(study))
            sp.body = explicit_heading_ids(sp.body)
            # section-divs would wrap headings in <section>s that overlap the
            # raw study-slide wrappers; Quarto's HTML pass then closes them early.
            # The bar marks the slides page as current: same path as `p`.
            sp.path = p.path
            write_page(src, sp, out_dir / p.path.name,
                       {"title": p.meta.get("title", p.stem)}, "section-divs: false", mod)
        else:
            write_page(src, p, out_dir / p.path.name, mod=mod)


def _split(path: Path):
    from nebula_content import split_frontmatter
    return split_frontmatter(path.read_text(encoding="utf-8"))


def write_hub(sources: list[Source]) -> None:
    title = sources[0].props.get("title", "Lessons")
    categories: list[str] = []
    for s in sources:
        categories += [c for c in s.category_order if c not in categories]
        categories += sorted({m.meta.get("category", "Other") for m in s.modules} - set(categories))
    hub = HERE / "hub"
    hub.mkdir()
    listings, sections = [], []
    for cat in categories:
        mods = [(s, m) for s in sources for m in s.modules
                if m.visible and m.meta.get("category", "Other") == cat]
        if not mods:
            continue
        mods.sort(key=lambda sm: (float(sm[1].meta.get("order", "inf")), sm[1].slug))
        items = []
        for _, m in mods:
            first = m.pages[0].path.name if m.pages else "index.md"
            item = (f"- title: {yaml_str(m.meta.get('title', m.slug))}\n"
                    f"  path: ../modules/{m.slug}/{first}\n"
                    f"  description: {yaml_str(m.meta.get('abstract', ''))}")
            if m.thumbnail:
                # `image` is relative to the hub page, unlike `path` (relative to this file)
                item += f"\n  image: modules/{m.slug}/{m.thumbnail}"
            items.append(item)
        (hub / f"{slug(cat)}.yml").write_text("\n".join(items) + "\n", encoding="utf-8")
        listings.append(
            f"  - id: cat-{slug(cat)}\n"
            f"    contents: hub/{slug(cat)}.yml\n"
            f"    type: grid\n    grid-columns: 3\n    sort: false\n"
            f"    fields: [image, title, description]"
        )
        sections.append(f"## {cat}\n\n::: {{#cat-{slug(cat)}}}\n:::\n")
    (HERE / "index.qmd").write_text(
        f"---\ntitle: {yaml_str(title)}\npage-layout: full\nfrom: markdown\n"
        f"repo-actions: false\nlisting:\n" + "\n".join(listings) + "\n---\n\n"
        + "\n".join(sections),
        encoding="utf-8",
    )


FOOTER = (
    "Lesson content © Netherlands eScience Center, "
    "[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (images: see credits); "
    "source: [research-software-support]"
    "(https://github.com/esciencecenter-digital-skills/research-software-support)."
)


def hub_modules(src: Source) -> list[Module]:
    """Visible modules in hub order: categoryOrder, then `order`."""
    cats = src.category_order
    def key(m: Module):
        c = m.meta.get("category", "Other")
        return (cats.index(c) if c in cats else len(cats), c,
                float(m.meta.get("order", "inf")), m.slug)
    return sorted((m for m in src.modules if m.visible), key=key)


def write_navbar(sources: list[Source]) -> None:
    """main/ pages as navbar entries, and the footer with thumbnail credits,
    merged via metadata-files."""
    entries = [("index.qmd", "Lessons")] + [
        (f"main/{p.path.name}", p.meta.get("title", p.stem))
        for s in sources for p in s.main_pages
    ]
    lines = ["website:", "  navbar:", "    left:"]
    for href, text in entries:
        lines += [f"      - href: {href}", f"        text: {yaml_str(text)}"]
    credits = [f"{m.meta.get('title', m.slug)}: {thumbnail_credit(m)}"
               for s in sources for m in hub_modules(s) if thumbnail_credit(m)]
    left = FOOTER + ("<br>Thumbnails: " + " · ".join(credits) if credits else "")
    lines += ["  page-footer:", f"    left: {yaml_str(left)}"]
    (HERE / "_generated.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    clean()
    sources = []
    for root in SOURCES:
        slides = [p for p in (root / "modules").glob("*/*.md")
                  if not p.name.endswith(".study.md")
                  and _split(p)[0].get("type") == "slides"]
        for s in slides:
            build_study.build(s, s.parent)
        sources.append(load(root))
    for src in sources:
        for mod in src.modules:
            mirror_module(src, mod)
        for p in src.main_pages:
            write_page(src, p, HERE / "main" / p.path.name)
    write_hub(sources)
    write_navbar(sources)
    (HERE / "_shared").mkdir()
    for css in ("study.css", "module-nav.css"):
        shutil.copy2(REPO / "shared" / css, HERE / "_shared" / css)
    print(f"prepare.py: {sum(len(s.modules) for s in sources)} modules mirrored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
