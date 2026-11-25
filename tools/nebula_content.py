"""Read a NEBULA content repo: config, modules, pages, links.

Generator-agnostic helpers shared by the variants' pre-build scripts.
Standard library only. Frontmatter is the flat `key: value` subset NEBULA
content uses; nested YAML is not supported (and not used by the content).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)

# Root-absolute site links as NEBULA writes them: [x](/main/about),
# [x](/modules/<module>/<page>), href="/modules/...". Not "//host" links.
SITE_LINK = re.compile(
    r'(?P<pre>\]\(|href=")(?P<path>/(?:main|modules)(?:/[^)"#?\s]*)?)(?P<frag>#[^)"\s]*)?'
)


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = FRONTMATTER.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t", "#")):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, text[m.end():]


def yaml_str(s: str) -> str:
    """A YAML double-quoted scalar (JSON strings are valid YAML)."""
    return json.dumps(s, ensure_ascii=False)


def order_key(meta: dict) -> tuple[float, str]:
    try:
        o = float(meta.get("order", ""))
    except ValueError:
        o = float("inf")
    return (o, meta.get("title", ""))


@dataclass
class Page:
    path: Path            # source file
    meta: dict[str, str]
    body: str

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def type(self) -> str:
        return self.meta.get("type", "")


@dataclass
class Module:
    slug: str
    dir: Path
    meta: dict[str, str]  # from index.md
    body: str
    pages: list[Page] = field(default_factory=list)  # ordered, without index.md

    @property
    def visible(self) -> bool:
        return self.meta.get("visibility", "visible") == "visible"

    @property
    def thumbnail(self) -> str | None:
        t = self.meta.get("thumbnail")
        return f"media/{t}" if t else None


@dataclass
class Source:
    """One content repo checkout (e.g. content/)."""

    root: Path
    config: dict
    modules: list[Module]
    main_pages: list[Page]

    @property
    def props(self) -> dict:
        return self.config.get("publicProps", {})

    @property
    def category_order(self) -> list[str]:
        return self.props.get("categoryOrder", [])

    @property
    def upstream_site(self) -> str:
        """Where the NEBULA site for this repo lives today."""
        p = self.props
        return f"https://{p['repoOwner']}.github.io/{p['baseURL']}".lower()

    def module(self, slug: str) -> Module | None:
        return next((m for m in self.modules if m.slug == slug), None)


def read_page(path: Path) -> Page:
    meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
    return Page(path, meta, body)


def load(root: Path) -> Source:
    root = Path(root)
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    modules = []
    for d in sorted((root / "modules").iterdir()):
        if not (d / "index.md").is_file():
            continue
        idx = read_page(d / "index.md")
        pages = [
            read_page(p) for p in d.glob("*.md")
            if p.name != "index.md" and not p.name.endswith(".study.md")
        ]
        pages.sort(key=lambda p: order_key(p.meta))
        modules.append(Module(d.name, d, idx.meta, idx.body, pages))
    main = sorted(
        (read_page(p) for p in (root / "main").glob("*.md")),
        key=lambda p: order_key(p.meta),
    )
    return Source(root, config, modules, main)


def rewrite_site_links(text: str, resolve) -> str:
    """Replace NEBULA root-absolute links using resolve(path) -> url | None.

    `path` is e.g. "/modules/licenses/copyright"; returning None keeps the
    link unchanged. The #fragment is carried over.
    """

    def sub(m: re.Match) -> str:
        url = resolve(m.group("path").rstrip("/"))
        if url is None:
            return m.group(0)
        return f'{m.group("pre")}{url}{m.group("frag") or ""}'

    return SITE_LINK.sub(sub, text)


ICONS = Path(__file__).resolve().parent.parent / "shared" / "icons"
NAV_TYPES = ("info", "reading", "exercise", "slides")


def module_nav_html(mod: Module, current: Page) -> str:
    """The module page bar (styled by shared/module-nav.css) as raw HTML.

    One line without blank lines, so Markdown keeps it a single HTML block.
    Links are relative: a module's pages are siblings in every variant.
    """
    from html import escape

    items = []
    for p in mod.pages:
        icon = ""
        if p.type in NAV_TYPES:
            icon = (f'<span class="module-nav-icon" title="{p.type}">'
                    f'{(ICONS / f"{p.type}.svg").read_text(encoding="utf-8").strip()}</span>')
        cur = ' aria-current="page"' if p.path == current.path else ""
        items.append(f'<li><a class="module-nav-page" href="{p.stem}.html"{cur}>{icon}'
                     f'<span>{escape(p.meta.get("title", p.stem))}</span></a></li>')
    return (f'<nav class="module-nav" aria-label="Pages in this module">'
            f'<div class="module-nav-title">{escape(mod.meta.get("title", mod.slug))}</div>'
            f'<ul class="module-nav-pages">{"".join(items)}</ul></nav>')


def thumbnail_credit(mod: Module) -> str:
    """The module index.md body (its thumbnail's photo credit) as one line
    of Markdown/HTML, for a site footer; "" if the body is empty."""
    return " ".join(mod.body.split())
