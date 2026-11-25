#!/usr/bin/env python3
"""Check a built variant against the PoC acceptance criteria in a real browser.

Serves the built site under a sub-path (as GitHub Pages will) and drives
headless Chromium with Playwright. Expected content is read from content/,
so nothing here is hard-coded per lesson.

  python3 tools/verify_site.py quarto --site quarto/_site [--shots DIR] [--theme DIR]

Needs network access: decks load reveal.js and escience_theme from jsDelivr.
--theme DIR answers the escience_theme requests from a local checkout
instead (for a theme version that is not published yet).
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

# Path the site is served under (make passes SITE_PATH; PR previews use a
# deeper one, e.g. /NEBULA_2.0/pr-preview/pr-3).
PREFIX = os.environ.get("SITE_PATH", "/NEBULA_2.0").strip("/")


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


def starlight_search(page: Page, term: str) -> int:
    page.locator("button[data-open-modal]").first.click()
    return pagefind_search(page, term)


def quarto_scheme(page: Page, scheme: str) -> None:
    """Quarto: one toggle between the light and the dark theme."""
    dark = "quarto-dark" in (page.evaluate("document.body.className") or "")
    if dark != (scheme == "dark"):
        page.locator(".quarto-color-scheme-toggle").first.click()


def hugo_scheme(page: Page, scheme: str) -> None:
    """Hugo: our header button cycles Auto -> Light -> Dark."""
    btn = page.locator("#theme-toggle")
    for _ in range(3):
        if btn.inner_text().strip().lower() == scheme:
            return
        btn.click()


def starlight_scheme(page: Page, scheme: str) -> None:
    page.locator("starlight-theme-select select").first.select_option(scheme)


VARIANTS = {
    "quarto": dict(
        page="modules/{m}/{stem}.html",        # text page / study view
        main="main/{stem}.html",
        example_link_page="poc.html",
        search=quarto_search,
        scheme=quarto_scheme,
    ),
    "hugo": dict(
        page="modules/{m}/{stem}.html",
        main="main/{stem}.html",
        example_link_page="poc.html",
        search=pagefind_search,
        scheme=hugo_scheme,
    ),
    "starlight": dict(
        page="modules/{m}/{stem}.html",
        main="main/{stem}.html",
        example_link_page="poc.html",
        search=starlight_search,
        scheme=starlight_scheme,
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


# Fragments the deck shows one at a time in the same place are all visible
# in the study view; none may overlap another.
OVERLAPS_JS = """() => {
  const out = [];
  for (const slide of document.querySelectorAll('.study-slide')) {
    const fr = [...slide.querySelectorAll('.study-slide-content .fragment')];
    for (let i = 0; i < fr.length; i++) for (let j = i + 1; j < fr.length; j++) {
      if (fr[i].contains(fr[j]) || fr[j].contains(fr[i])) continue;
      const a = fr[i].getBoundingClientRect(), b = fr[j].getBoundingClientRect();
      const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (w > 2 && h > 2) { out.push(slide.id); break; }
    }
  }
  return [...new Set(out)];
}"""

# Text whose contrast with its effective background is below 3:1 (WCAG
# large-text minimum). The text colour is blended with the background by its
# alpha and the opacity of its ancestors (.muted). Fragments the author
# semi-fades on purpose (.semi-fade-out) are left out.
# `scope` selects the elements to check, `stop` ends the walk up to find a
# background, `fallback` is the background when none is found below `stop`.
LOW_CONTRAST_JS = """([scope, stop, fallback]) => {
  const rgba = c => { const m = (c.match(/[\\d.]+/g) || []).map(Number); return [m[0], m[1], m[2], m[3] ?? 1]; };
  const lum = ([r, g, b]) => [r, g, b].map(v => (v /= 255) <= 0.03928 ? v / 12.92
                             : ((v + 0.055) / 1.055) ** 2.4)
                           .reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i], 0);
  const bg = el => {
    for (; el && !el.matches(stop); el = el.parentElement) {
      const c = rgba(getComputedStyle(el).backgroundColor);
      if (c[3] > 0.5) return c;
    }
    if (el) { const c = rgba(getComputedStyle(el).backgroundColor); if (c[3] > 0.5) return c; }
    return fallback;
  };
  const opacity = el => { let o = 1; for (; el; el = el.parentElement) o *= Number(getComputedStyle(el).opacity); return o; };
  const bad = [];
  for (const el of document.querySelectorAll(scope)) {
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own || getComputedStyle(el).visibility === 'hidden') continue;
    // not drawn, or visually hidden screen-reader text (clipped to 1px)
    const box = el.getBoundingClientRect();
    if (box.width <= 1 || box.height <= 1) continue;
    // faded on purpose by the author: "not the focus right now"
    if (el.closest('.fragment.semi-fade-out.visible')) continue;
    const fg = rgba(getComputedStyle(el).color), back = bg(el);
    const a = fg[3] * opacity(el);
    const seen = [0, 1, 2].map(i => fg[i] * a + back[i] * (1 - a));
    const l1 = lum(seen), l2 = lum(back);
    const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    if (ratio < 3) bad.push((el.closest('[id]') || el).id + ': ' + el.textContent.trim().slice(0, 30)
                            + ` (${ratio.toFixed(1)}:1)`);
  }
  return bad;
}"""


def deck_ready(page: Page) -> None:
    page.wait_for_function("window.Reveal && Reveal.isReady && Reveal.isReady()", timeout=20_000)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("variant", choices=VARIANTS)
    ap.add_argument("--site", type=Path, required=True, help="built site directory")
    ap.add_argument("--shots", type=Path, help="write screenshots here")
    ap.add_argument("--theme", type=Path,
                    help="escience_theme checkout to load the theme from instead of jsDelivr")
    args = ap.parse_args()
    v = VARIANTS[args.variant]
    src = load(REPO / "content")
    r = Report()

    tmp = Path(tempfile.mkdtemp(prefix="verify-"))
    try:
        (tmp / PREFIX).mkdir(parents=True)
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

            def local_theme(target) -> None:
                """Serve escience_theme requests from --theme (page or context)."""
                if not args.theme:
                    return
                def answer(route) -> None:
                    name = route.request.url.split("?")[0].rsplit("/", 1)[-1]
                    f = args.theme / name
                    if f.is_file():
                        route.fulfill(path=str(f), headers={"access-control-allow-origin": "*"})
                    else:
                        route.fulfill(status=404)
                target.route(re.compile(r"https://cdn\.jsdelivr\.net/npm/escience_theme@[^/]+/[^/]+$"), answer)

            local_theme(ctx)
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

            # 2. modules: the hub card opens the first page; every module page
            #    shows the page bar (all pages in order, type icons, current one
            #    marked); the module index.md body (the thumbnail's photo
            #    credit) is in the page footer
            for m in visible:
                page.goto(base)
                page.locator(f"a:has(img[src*='{m.slug}/media/'])").first.click()
                page.wait_for_load_state()
                first = m.pages[0]
                r.check(f"hub card {m.slug} opens its first page ({first.stem})",
                        page.url.split("#")[0].endswith(
                            v["page"].format(m=m.slug, stem=first.stem)), page.url)
                titles = [p.meta.get("title", p.stem) for p in m.pages]
                for p in (first, next((q for q in m.pages if q.type == "slides"), first)):
                    if p is not first:
                        page.goto(base + v["page"].format(m=m.slug, stem=p.stem))
                    bar = page.locator("nav.module-nav")
                    tabs = bar.locator("a.module-nav-page")
                    got = [t.strip() for t in tabs.all_inner_texts()] if bar.count() == 1 else []
                    cur = bar.locator("a[aria-current=page]")
                    r.check(f"{m.slug}/{p.stem}: page bar lists pages in order, current marked",
                            got == titles and cur.count() == 1
                            and cur.inner_text().strip() == p.meta.get("title", p.stem),
                            " > ".join(got))
                    icons = bar.locator(".module-nav-icon svg").count()
                    r.check(f"{m.slug}/{p.stem}: page bar has a type icon per page",
                            icons == sum(q.type in ("info", "reading", "exercise", "slides")
                                         for q in m.pages), f"{icons} icons")
                    if p is first and m.slug == visible[0].slug:
                        shot("module")
                hrefs = re.findall(r'href="([^"]+)"', m.body)
                if hrefs:
                    page.goto(base)
                    missing = [h for h in hrefs if not page.evaluate(
                        "h => [...document.querySelectorAll('a')].some("
                        "a => a.getAttribute('href') === h && a.closest('footer'))", h)]
                    r.check(f"{m.slug}: thumbnail credit (index.md body) in the footer",
                            not missing, ", ".join(missing[:2]))

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

            for mod in visible:
                sp = next((p for p in mod.pages if p.type == "slides"), None)
                if sp is None:
                    continue
                page.goto(base + v["page"].format(m=mod.slug, stem=sp.stem))
                page.evaluate("document.querySelectorAll('img').forEach(i => i.loading = 'eager')")
                page.wait_for_function("[...document.images].every(i => i.complete)", timeout=20_000)
                bad = page.evaluate("[...document.querySelectorAll('.study-slide img')]"
                                    ".filter(i => !i.naturalWidth).map(i => i.getAttribute('src'))")
                total = page.locator(".study-slide img").count()
                r.check(f"study view {mod.slug}: all {total} slide images load", not bad,
                        ", ".join(bad[:3]))
                over = page.evaluate(OVERLAPS_JS)
                r.check(f"study view {mod.slug}: no overlapping fragments", not over,
                        ", ".join(over[:3]))
                v["scheme"](page, "light")
                page.wait_for_timeout(300)
                low = page.evaluate(LOW_CONTRAST_JS, [".study-slide-content *", "body", [255, 255, 255]])
                r.check(f"study view {mod.slug}: slide text readable in light mode", not low,
                        "; ".join(low[:3]))
                dark = browser.new_page(viewport={"width": 1280, "height": 860},
                                        color_scheme="dark")
                local_theme(dark)
                dark.goto(page.url)
                v["scheme"](dark, "dark")
                dark.wait_for_timeout(300)
                low = dark.evaluate(LOW_CONTRAST_JS, [".study-slide-content *", "body", [255, 255, 255]])
                r.check(f"study view {mod.slug}: slide text readable in dark mode", not low,
                        "; ".join(low[:3]))
                dark.close()

                # Every deck slide with all its fragments shown: text readable
                # on the slide (or on the box it sits in).
                page.goto(base + v["page"].format(m=mod.slug, stem=sp.stem).replace(".html", ".deck.html"))
                deck_ready(page)
                # fragments fade in; measure their final state
                page.add_style_tag(content="*, *::before, *::after { transition: none !important; }")
                low = []
                for i in range(page.evaluate("Reveal.getSlides().length")):
                    page.evaluate("i => { const ix = Reveal.getIndices(Reveal.getSlides()[i]);"
                                  " Reveal.slide(ix.h, ix.v, 999); }", i)
                    page.wait_for_timeout(100)
                    light = page.evaluate("Reveal.getCurrentSlide().classList.contains('has-light-background')")
                    low += page.evaluate(LOW_CONTRAST_JS, [
                        ".reveal .slides section.present:not(.stack) *", "section",
                        [255, 255, 255] if light else [25, 25, 25]])
                r.check(f"deck {mod.slug}: slide text readable, all fragments shown", not low,
                        "; ".join(low[:3]))

            # 4b. colour-scheme switch overrides the system setting both ways
            body_dark = ("() => { const c = getComputedStyle(document.body).backgroundColor"
                         ".match(/\\d+/g).map(Number); return c[0] + c[1] + c[2] < 384; }")
            for system, want in (("dark", "light"), ("light", "dark")):
                sp = browser.new_page(color_scheme=system)
                sp.goto(base)
                v["scheme"](sp, want)
                sp.wait_for_timeout(300)
                sp.reload()                       # the choice is remembered
                sp.wait_for_timeout(300)
                r.check(f"scheme switch: {want} on a {system} system",
                        sp.evaluate(body_dark) == (want == "dark"))
                sp.close()

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
