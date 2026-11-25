#!/usr/bin/env python3
"""Starlight pre-build (npm `prebuild`): decks, study views, static files.

- tools/build_study.py writes <stem>.deck.html + <stem>.study.md next to
  each slides source in content/ (the content loader reads the study view)
- media/ folders and decks are copied to public/modules/<m>/ so pages,
  study views and decks find them at the same relative paths as in NEBULA
- shared/study.css is copied to src/styles/

Generated paths are git-ignored.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "tools"))

import build_study  # noqa: E402
from nebula_content import load, split_frontmatter  # noqa: E402

CONTENT = REPO / "content"


def main() -> int:
    public = HERE / "public" / "modules"
    if public.exists():
        shutil.rmtree(public)
    for p in (CONTENT / "modules").glob("*/*.md"):
        if p.name.endswith(".study.md"):
            continue
        if split_frontmatter(p.read_text(encoding="utf-8"))[0].get("type") == "slides":
            build_study.build(p, p.parent)
    for mod in load(CONTENT).modules:
        out = public / mod.slug
        if (mod.dir / "media").is_dir():
            shutil.copytree(mod.dir / "media", out / "media")
        out.mkdir(parents=True, exist_ok=True)
        for deck in mod.dir.glob("*.deck.html"):
            shutil.copy2(deck, out / deck.name)
    styles = HERE / "src" / "styles"
    styles.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / "shared" / "study.css", styles / "study.css")
    print(f"prepare.py: decks and media for {len(list(public.iterdir()))} modules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
