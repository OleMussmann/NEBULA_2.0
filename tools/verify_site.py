#!/usr/bin/env python3
"""Check a built variant against the PoC acceptance criteria in a real browser.

Serves the built site under a sub-path (as GitHub Pages will) and drives
headless Chromium with Playwright. Expected content is read from content/,
so nothing here is hard-coded per lesson.

  python3 tools/verify_site.py quarto --site quarto/_site [--shots DIR]

Needs network access: decks load reveal.js and escience_theme from jsDelivr.
Run inside `nix develop .#verify`.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import re
import shutil
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import build_study  # noqa: E402
from nebula_content import load  # noqa: E402

PREFIX = "NEBULA_2.0"


# --- per-variant knowledge: URLs and search UI ------------------------------

def quarto_search(page: Page, term: str) -> int:
    page.locator("#quarto-search").click()
    page.locator("input.aa-Input").fill(term)
    page.locator(".aa-Item").first.wait_for(timeout=10_000)
    return page.locator(".aa-Item").count()


def pagefind_search(page: Page, term: str) -> int:
    page.locator(".pagefind-ui__search-input").fill(term)
    page.locator(".pagefind-ui__result").first.wait_for(timeout=10_000)
    return page.locator(".pagefind-ui__result").count()


VARIANTS = {
    "quarto": dict(
        module="modules/{m}/",                 # module page
        page="modules/{m}/{stem}.html",        # text page / study view
        main="main/{stem}.html",
        example_link_page="poc.html",
        search=quarto_search,
    ),
    "hugo": dict(
        module="modules/{m}/",
        page="modules/{m}/{stem}.html",
        main="main/{stem}.html",
        example_link_page="poc.html",
        search=pagefind_search,
    ),
}


# --- harness ----------------------------------------------------------------

class Report:
    def __init__(self) -> None:
        self.failed = 0

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


def serve(root: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    handler = functools.partial(QuietHandler, directory=str(root))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


def index_of(text: str, needle: str, start: int = 0) -> int:
    return text.find(needle, start)


def in_order(text: str, needles: list[str]) -> bool:
    pos = -1
    for n in needles:
        pos = text.find(n, pos + 1)
        if pos < 0:
            return False
    return True


def deck_ready(page: Page) -> None:
    page.wait_for_function("window.Reveal && Reveal.isReady && Reveal.isReady()", timeout=20_000)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("variant", choices=VARIANTS)
    ap.add_argument("--site", type=Path, required=True, help="built site directory")
    ap.add_argument("--shots", type=Path, help="write screenshots here")
    args = ap.parse_args()
    v = VARIANTS[args.variant]
    src = load(REPO / "content")
    r = Report()

    tmp = Path(tempfile.mkdtemp(prefix="verify-"))
    try:
        (tmp / PREFIX).mkdir()
        os.symlink(args.site.resolve(), tmp / PREFIX / args.variant)
        fixture_dir = tmp / "fixture"
        build_study.build(REPO / "tools" / "fixtures" / "presenter_only.md", fixture_dir)
        srv, origin = serve(tmp)
        base = f"{origin}/{PREFIX}/{args.variant}/"
        if args.shots:
            args.shots.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(viewport={"width": 1280, "height": 860})
            broken: list[str] = []
            ctx.on("response", lambda resp: broken.append(f"{resp.status} {resp.url}")
                   if resp.url.startswith(origin) and resp.status >= 400 else None)
            page = ctx.new_page()

            def shot(name: str, p: Page | None = None) -> None:
                if args.shots:
                    (p or page).screenshot(path=str(args.shots / f"{name}.png"), full_page=False)

            # 1. hub
            page.goto(base)
            text = page.inner_text("body")
            visible = [m for m in src.modules if m.visible]
            for m in visible:
                cat = m.meta.get("category", "")
                r.check(f"hub lists {m.slug} under '{cat}'",
                        in_order(text, [cat, m.meta["title"]]) and m.meta["abstract"] in text)
                img = page.locator(f"img[src*='{m.slug}/media/{m.meta['thumbnail']}']").first
                loaded = img.count() and img.evaluate("i => i.complete && i.naturalWidth > 0")
                r.check(f"hub thumbnail for {m.slug} loads", bool(loaded))
            cats = [c for c in src.category_order
                    if any(m.meta.get("category") == c for m in visible)]
            r.check("hub categories in categoryOrder", in_order(text, cats), " > ".join(cats))
            shot("hub")

            # 2. module pages
            for m in visible:
                page.goto(base + v["module"].format(m=m.slug))
                titles = [p.meta.get("title", p.stem) for p in m.pages]
                r.check(f"module {m.slug} lists pages in order",
                        in_order(page.inner_text("main") if page.locator("main").count()
                                 else page.inner_text("body"), titles), " > ".join(titles))
                if m.slug == visible[0].slug:
                    shot("module")

            # 3. edit link on a text page
            m = src.module("licenses")
            info = next(p for p in m.pages if p.type == "info")
            page.goto(base + v["page"].format(m="licenses", stem=info.stem))
            want = f"/edit/main/content/modules/licenses/{info.path.name}"
            r.check("text page has 'Edit this page' to its source",
                    page.locator(f"a[href$='{want}']").count() > 0, want)

            # 4. study view: every slide, anchors, present-from-here
            slides = next(p for p in m.pages if p.type == "slides")
            n_slides = len(build_study.split_slides(build_study.parse_frontmatter(
                slides.path.read_text())[1]))
            page.goto(base + v["page"].format(m="licenses", stem=slides.stem) + "#about-copyright")
            r.check("study view shows every slide",
                    page.locator(".study-slide").count() == n_slides,
                    f"{page.locator('.study-slide').count()} of {n_slides}")
            r.check("study anchor #about-copyright exists and is in view",
                    page.locator("#about-copyright").is_visible()
                    and page.evaluate("document.getElementById('about-copyright')"
                                      ".getBoundingClientRect().top < innerHeight"))
            r.check("study view shows notes", page.locator(".study-notes").count() > 0)
            shot("study")
            page.locator("#about-copyright .study-present a").click()
            page.wait_for_url(re.compile(r"\.deck\.html#/about-copyright$"))
            deck_ready(page)
            r.check("present-from-here opens deck at that slide",
                    page.evaluate("Reveal.getCurrentSlide().id") == "about-copyright")

            # 5. deck: theme, slide count, hash, notes
            deck_url = base + v["page"].format(m="licenses", stem=slides.stem).replace(".html", ".deck.html")
            page.goto(deck_url + "#/about-copyright")
            deck_ready(page)
            # JS: a CORS module fetch reports its status; CSS is no-cors
            # (status 0), so check that the <link> produced a stylesheet.
            loaded = page.evaluate("""[
                ...performance.getEntriesByType('resource')
                  .filter(e => e.name.includes('escience_theme') && e.responseStatus === 200)
                  .map(e => e.name.split('/').pop()),
                ...[...document.querySelectorAll('link[href*=escience_theme]')]
                  .filter(l => l.sheet).map(l => l.href.split('/').pop())]""")
            r.check("deck loads escience_theme (js + css)",
                    {"escience.js", "escience.css"} <= set(loaded), ", ".join(loaded))
            r.check("deck slide count matches separators",
                    page.evaluate("Reveal.getSlides().length") == n_slides)
            r.check("deck hash #/about-copyright lands on that slide",
                    page.evaluate("Reveal.getCurrentSlide().id") == "about-copyright")
            page.wait_for_timeout(2000)            # theme overlays fade in
            shot("deck")
            with page.expect_popup(timeout=10_000) as pop:
                page.keyboard.press("s")
            speaker = pop.value
            speaker.wait_for_load_state()
            speaker.wait_for_function(
                "document.querySelector('.speaker-controls-notes') &&"
                " document.querySelector('.speaker-controls-notes').innerText.trim().length > 20",
                timeout=15_000)
            r.check("S opens speaker view with notes", True)
            speaker.wait_for_timeout(2000)
            shot("speaker", speaker)
            speaker.close()
            page.goto(deck_url + "?annotations#/about-copyright")
            deck_ready(page)
            notes = page.locator(".reveal .speaker-notes")
            r.check("?annotations shows notes inline",
                    notes.is_visible() and len(notes.inner_text().strip()) > 20)
            page.wait_for_timeout(2000)
            shot("deck-annotations")

            # 6. presenter-only notes (fixture deck)
            page.goto(f"{origin}/fixture/presenter_only.deck.html?annotations")
            deck_ready(page)
            r.check("presenter-only hidden in on-screen notes",
                    "Learner note text" in page.inner_text(".reveal .speaker-notes")
                    and not any(e.is_visible() for e in page.get_by_text("Presenter secret text").all()))
            with page.expect_popup(timeout=10_000) as pop:
                page.keyboard.press("s")
            speaker = pop.value
            speaker.wait_for_function(
                "document.querySelector('.speaker-controls-notes') &&"
                " document.querySelector('.speaker-controls-notes').innerText.includes('Presenter secret')",
                timeout=15_000)
            r.check("presenter-only shown in speaker view", True)
            speaker.close()
            study_fixture = (fixture_dir / "presenter_only.study.md").read_text()
            r.check("presenter-only dropped from study view",
                    "Presenter secret" not in study_fixture and "Learner note text" in study_fixture)

            # 7. a text page links to a slide by id
            page.goto(base + v["example_link_page"])
            link = page.locator("a[href*='#about-copyright']").first
            r.check("example text page links to a slide id", link.count() > 0)
            if link.count():
                link.click()
                page.wait_for_url(re.compile(r"#about-copyright$"))
                r.check("slide-id link lands on the slide",
                        page.locator("#about-copyright.study-slide").is_visible())

            # 8. main/ pages
            for p in src.main_pages:
                resp = page.goto(base + v["main"].format(stem=p.stem))
                r.check(f"main page {p.stem} renders",
                        resp.ok and p.meta["title"] in page.inner_text("body"))
            page.goto(base)
            for p in src.main_pages:
                r.check(f"hub navigation links to {p.stem}",
                        page.locator(f"a[href*='{p.stem}']").count() > 0)

            # 9. search
            page.goto(base)
            try:
                n = v["search"](page, "copyright")
                r.check("search finds 'copyright'", n > 0, f"{n} results")
                shot("search")
            except Exception as e:  # noqa: BLE001
                r.check("search finds 'copyright'", False, str(e).splitlines()[0])

            # 10. sub-path: nothing same-origin 404s
            r.check(f"no broken same-origin requests under /{PREFIX}/{args.variant}/",
                    not broken, "; ".join(sorted(set(broken))[:5]))
            browser.close()
        srv.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{args.variant}: {'all checks passed' if not r.failed else f'{r.failed} check(s) failed'}")
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main())
