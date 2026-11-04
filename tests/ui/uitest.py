#!/usr/bin/env python3
"""Farglow UI test engine: plays the game in headless Chromium and checks every screen.

    python3 uitest.py --url http://127.0.0.1:18090 --out /reports [--viewports 1366x768,1920x1080]

What it does
  1. Plays a short game as a real player would: sign up, found a civilization, advance the
     clock, confirm advisor suggestions, set the allocation, queue research, survey, ask the
     advisor. Every step must work (a failed step is a FAIL with a screenshot).
  2. Visits every screen at every viewport, in light and dark, and checks:
       FAIL  console errors, CSP violations, failed requests (HTTP >= 400)
       FAIL  horizontal scrolling (the page is wider than the window)
       FAIL  covered controls: a visible button or link whose centre is under another element
       FAIL  over the density budget: the page is taller than budgets.json allows at that size
       WARN  text under 11 px, click targets under 24 px (the design system's floors)
       WARN  clipped text (content wider than its box, without a scrollbar)
  3. Writes report.html (one page, screenshots, every finding) and summary.json.

Exit 0 when nothing FAILed, 1 otherwise. Needs only Playwright for Python.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Error as PWError
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ATTRS = {"curiosity": 2, "industry": 0, "growth": -1, "cohesion": 1, "martial": -2, "openness": 0}

# Runs in the page: layout findings. Returns a list of {level, check, detail}.
CHECKS_JS = r"""
() => {
  const out = [];
  const add = (level, check, detail) => out.push({level, check, detail});
  const doc = document.documentElement;
  if (doc.scrollWidth > window.innerWidth + 1)
    add('FAIL', 'horizontal-scroll', `page is ${doc.scrollWidth}px wide in a ${window.innerWidth}px window`);
  const hiddenByDetails = el => { const d = el.closest('details:not([open])'); return d && !(el.closest('summary') && el.closest('summary').parentElement === d); };
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity !== 0
      && !hiddenByDetails(el); };
  const label = el => (el.innerText || el.getAttribute('aria-label') || el.value || el.tagName).trim().replace(/\s+/g, ' ').slice(0, 50);
  const controls = [...document.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, summary')].filter(visible);
  let covered = 0, small = 0;
  for (const el of controls) {
    const r = el.getBoundingClientRect();
    const x = r.left + r.width / 2, y = r.top + r.height / 2;
    if (y < 0 || y > window.innerHeight || x < 0 || x > window.innerWidth) continue;   // off screen: not checked
    // scrolled out of sight inside a scrolling box: not covered, just not on screen
    let clippedByScroll = false;
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      const ov = getComputedStyle(a).overflowY;
      if (ov === 'auto' || ov === 'scroll') { const ar = a.getBoundingClientRect();
        if (y < ar.top || y > ar.bottom) { clippedByScroll = true; break; } }
    }
    if (clippedByScroll) continue;
    const top = document.elementFromPoint(x, y);
    if (top && top !== el && !el.contains(top) && !top.contains(el) && !(el.labels && [...el.labels].some(l => l.contains(top)))) {
      if (covered++ < 8) add('FAIL', 'covered-control', `"${label(el)}" is under <${top.tagName.toLowerCase()} class="${top.className}">`);
    }
    const inline = getComputedStyle(el).display === 'inline' && el.tagName === 'A';
    if (!inline && r.height < 23.5 && el.type !== 'checkbox' && el.type !== 'radio') {
      if (small++ < 6) add('WARN', 'small-target', `"${label(el)}" is ${Math.round(r.height)}px tall (floor 24px)`);
    }
  }
  let tiny = 0, clipped = 0;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode; const el = t.parentElement;
    if (!el || seen.has(el) || !t.textContent.trim() || !visible(el)) continue;
    seen.add(el);
    if (el.closest('svg')) continue;                    // map labels scale with the SVG
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < 10.5 && tiny++ < 6) add('WARN', 'tiny-text', `"${t.textContent.trim().slice(0, 40)}" is ${fs}px (floor 11px)`);
    const s = getComputedStyle(el);
    if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 && !['auto', 'scroll'].includes(s.overflowX)
        && s.display !== 'inline' && s.textOverflow !== 'ellipsis' && clipped++ < 6)
      add('WARN', 'clipped-text', `"${t.textContent.trim().slice(0, 40)}" overflows its box (${el.scrollWidth} > ${el.clientWidth}px)`);
  }
  const fs = [...document.querySelectorAll('body *')].filter(visible).map(e => parseFloat(getComputedStyle(e).fontSize));
  // content height: where the page's content ends (the body stretches to the window, so
  // scrollHeight would never be under the viewport)
  let bottom = 0;
  for (const el of document.querySelectorAll('header, main > *')) bottom = Math.max(bottom, el.getBoundingClientRect().bottom + window.scrollY);
  return {findings: out, height: Math.ceil(bottom), width: doc.scrollWidth, controls: controls.length,
          median_font: fs.sort((a, b) => a - b)[Math.floor(fs.length / 2)] || 0};
}
"""


class Run:
    def __init__(self, args):
        self.args = args
        self.base = args.url.rstrip("/")
        self.out = Path(args.out)
        (self.out / "shots").mkdir(parents=True, exist_ok=True)
        self.budgets = json.loads((HERE / "budgets.json").read_text())
        self.results = []          # one per page × viewport × theme
        self.steps = []            # the play-through
        self.console = []          # (page label, text)
        self.started = time.time()

    # ------------------------------------------------------------------ helpers
    def watch(self, page, label_ref):
        page.on("console", lambda m: m.type == "error" and self.console.append((label_ref[0], m.text)))
        page.on("pageerror", lambda e: self.console.append((label_ref[0], f"uncaught: {e}")))
        page.on("response", lambda r: r.status >= 400 and not r.url.endswith("/favicon.ico")
                and self.console.append((label_ref[0], f"HTTP {r.status} {r.url}")))

    def step(self, page, name, fn):
        t = time.time()
        try:
            fn()
            ok, detail = True, ""
        except (PWError, AssertionError, TimeoutError) as exc:
            ok, detail = False, str(exc).splitlines()[0][:300]
        shot = f"shots/step-{len(self.steps) + 1:02d}.png"
        try:
            page.screenshot(path=str(self.out / shot))
        except PWError:
            shot = ""
        self.steps.append({"name": name, "ok": ok, "detail": detail, "shot": shot, "s": round(time.time() - t, 1)})
        print(("  ok  " if ok else "  FAIL ") + name + (f": {detail}" if detail else ""), flush=True)
        return ok

    def tick_now(self, page):
        before = page.locator("[data-tick]").first.get_attribute("data-tick")
        page.get_by_role("button", name=re.compile("Advance the clock")).click()
        for _ in range(40):
            page.wait_for_timeout(1000)
            page.reload()
            if page.locator("[data-tick]").first.get_attribute("data-tick") != before:
                return
        raise AssertionError("the tick did not advance within 40 s")

    # ------------------------------------------------------------------ 1. play-through
    def play(self, browser):
        ctx = browser.new_context(viewport={"width": 1366, "height": 768})
        page = ctx.new_page()
        label = ["play"]
        self.watch(page, label)
        email = self.args.email or f"ui-{int(time.time())}@example.test"
        pw = "ui-test passphrase 1"

        def signup():
            page.goto(self.base + "/signup")
            page.fill("#email", email)
            page.fill("#display_name", "UI Tester")
            page.fill("#password", pw)
            page.select_option("#birth_month", "5")
            page.fill("#birth_year", "1985")
            page.get_by_role("button", name="Create account").click()
            page.wait_for_load_state()
            assert "/found" in page.url or "/play" in page.url, (
                f"after sign-up the page is {page.url} (a server with SMTP needs email verification: "
                "run the UI suite against a stack without SMTP)")

        def found():
            if "/found" not in page.url:
                page.goto(self.base + "/found")
            page.fill("#name", f"UI Reach {int(time.time()) % 100000}")
            for k, v in ATTRS.items():
                page.fill(f"input[name=attr_{k}]", str(v))
            page.locator("label.fg-set").nth(4).click()
            page.get_by_role("button", name=re.compile("Found")).click()
            page.wait_for_load_state()
            self.tick_now(page)
            assert page.locator("#system-panel [data-home]").count(), "the home system panel is not shown after founding"

        def confirm_advice():
            page.goto(self.base + "/play")
            btn = page.locator("form[action$='/act/advice'] button").first
            assert btn.count(), "the advisor offered nothing to confirm"
            btn.click()
            page.wait_for_load_state()
            assert page.locator(".fg-flash--error").count() == 0, page.locator(".fg-flash--error").first.inner_text()

        def allocation():
            page.goto(self.base + "/governor")
            page.fill("input[name=expansion]", "35")
            page.fill("input[name=military]", "5")
            page.get_by_role("button", name=re.compile("Set allocation")).click()
            page.wait_for_load_state()
            assert page.locator(".fg-flash--ok").count(), "no confirmation after setting the allocation"

        def research():
            page.goto(self.base + "/research?tech=belt_extraction_rigs")
            page.locator("form[action$='/act/queue'] button").first.click()
            page.wait_for_load_state()
            assert page.locator(".fg-flash--error").count() == 0

        def ticks():
            for _ in range(self.args.ticks):
                self.tick_now(page)

        def survey():
            page.goto(self.base + "/play")
            send = page.locator("form[action$='/act/advice'] button", has_text=re.compile("Send|survey", re.I))
            if send.count():
                send.first.click()
                page.wait_for_load_state()
            assert page.locator(".fg-flash--error").count() == 0

        def map_click():
            page.goto(self.base + "/play")
            page.wait_for_selector(".fg-map__sys")
            box = page.locator(".fg-map__sys:not(.is-selected) .fg-map__dot").nth(5).bounding_box()
            assert box, "no unsurveyed star drawn on the map"
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)   # as a player clicks
            page.wait_for_timeout(1000)
            assert "Unsurveyed" in page.locator("#system-panel").inner_text(), "clicking a star did not open its panel"
            assert page.locator("#system-panel").inner_text().strip(), "the system panel is empty after a map click"

        def ask():
            page.goto(self.base + "/play")
            page.locator("details.fg-ask > summary").click()
            page.locator("textarea[name=question]").fill("How do I get more minerals?")
            page.locator("form[hx-post$='/advisor/ask'] button[type=submit]:not([name])").click()
            page.wait_for_selector(".fg-chat__a", timeout=30000)

        ok = self.step(page, "sign up", signup)
        ok = ok and self.step(page, "found a civilization and advance the clock", found)
        if ok:
            for name, fn in (("confirm an advisor suggestion", confirm_advice), ("set the allocation", allocation),
                             ("queue research", research), (f"advance {self.args.ticks} ticks", ticks),
                             ("send a survey", survey), ("select a star on the map", map_click),
                             ("ask the advisor", ask)):
                self.step(page, name, fn)
        self.storage = ctx.storage_state()
        ctx.close()
        return ok

    # ------------------------------------------------------------------ 2. page checks
    def pages(self, signed_in: bool):
        if not signed_in:
            return [("landing", "/"), ("sign-up", "/signup")]
        return [("galaxy", "/play"), ("system", "/play?system=__OTHER__"), ("governor", "/governor"),
                ("research", "/research"), ("research-detail", "/research?tech=orbital_survey_array"),
                ("dispatch", "/dispatch"), ("account", "/account"), ("admin", "/admin")]

    def check_all(self, browser, signed_in: bool):
        other = None
        for vp in self.args.viewports:
            w, h = (int(x) for x in vp.split("x"))
            for theme in self.args.themes:
                ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=theme,
                                          storage_state=self.storage if signed_in else None)
                page = ctx.new_page()
                label = [""]
                self.watch(page, label)
                for name, path in self.pages(signed_in):
                    if "__OTHER__" in path:
                        if other is None:
                            page.goto(self.base + "/api/v1/map")
                            data = json.loads(page.inner_text("body"))
                            other = next((s["id"] for s in data["systems"] if s.get("surveyed") and not s.get("mine")),
                                         data["systems"][0]["id"])
                        path = path.replace("__OTHER__", other)
                    label[0] = f"{name} {vp} {theme}"
                    n_console = len(self.console)
                    try:
                        resp = page.goto(self.base + path)
                        page.evaluate(f"localStorage.setItem('fg-theme', '{theme}')")
                        page.reload()
                        page.wait_for_load_state("networkidle")
                        page.wait_for_timeout(300)
                        res = page.evaluate(CHECKS_JS)
                        status = resp.status if resp else 0
                    except PWError as exc:
                        res, status = {"findings": [{"level": "FAIL", "check": "load", "detail": str(exc)[:200]}],
                                       "height": 0, "width": 0, "controls": 0, "median_font": 0}, 0
                    if path.startswith("/admin") and status == 403:
                        continue
                    for _, text in self.console[n_console:]:
                        kind = "csp" if "Content Security Policy" in text else "console"
                        res["findings"].append({"level": "FAIL", "check": kind, "detail": text[:240]})
                    budget = self.budgets.get(name, {}).get(f"{w}x{h}") or self.budgets.get(name, {}).get("default")
                    if budget and res["height"] > budget:
                        res["findings"].append({"level": "FAIL", "check": "density-budget",
                                                "detail": f"page is {res['height']}px tall; budget {budget}px at {w}x{h}"})
                    shot = f"shots/{name}-{vp}-{theme}.png"
                    page.screenshot(path=str(self.out / shot), full_page=True)
                    self.results.append({"page": name, "path": path, "viewport": vp, "theme": theme, "status": status,
                                         "height": res["height"], "controls": res["controls"],
                                         "median_font": res["median_font"], "budget": budget,
                                         "findings": res["findings"], "shot": shot})
                    worst = "FAIL" if any(f["level"] == "FAIL" for f in res["findings"]) else (
                        "WARN" if res["findings"] else "ok")
                    print(f"  {worst:4s} {name:16s} {vp:10s} {theme:5s} h={res['height']}px", flush=True)
                ctx.close()

    # ------------------------------------------------------------------ 3. report
    def report(self) -> int:
        fails = sum(1 for r in self.results for f in r["findings"] if f["level"] == "FAIL") + \
            sum(1 for s in self.steps if not s["ok"])
        warns = sum(1 for r in self.results for f in r["findings"] if f["level"] == "WARN")
        verdict = "PASS" if fails == 0 else "FAIL"
        summary = {"schema": "farglow-ui-summary/1", "verdict": verdict, "fails": fails, "warnings": warns,
                   "url": self.base, "started": datetime.fromtimestamp(self.started, timezone.utc).isoformat(),
                   "seconds": round(time.time() - self.started), "steps": self.steps, "pages": self.results}
        (self.out / "summary.json").write_text(json.dumps(summary, indent=2))
        e = html.escape
        rows = []
        for r in self.results:
            fs = "".join(f'<li class="{f["level"].lower()}"><b>{f["level"]}</b> {e(f["check"])}: {e(f["detail"])}</li>'
                         for f in r["findings"]) or '<li class="ok">no findings</li>'
            rows.append(f'<section><h3>{e(r["page"])} · {r["viewport"]} · {r["theme"]}</h3>'
                        f'<p class="meta">{e(r["path"])} · height {r["height"]}px'
                        f'{" / budget " + str(r["budget"]) + "px" if r["budget"] else ""} · {r["controls"]} controls · '
                        f'median font {r["median_font"]}px</p><ul>{fs}</ul>'
                        f'<a href="{r["shot"]}"><img src="{r["shot"]}" alt=""></a></section>')
        def step_li(st):
            link = f' · <a href="{st["shot"]}">screenshot</a>' if st["shot"] else ""
            detail = f": {e(st['detail'])}" if st["detail"] else ""
            word = "ok" if st["ok"] else "FAIL"
            return f'<li class="{word.lower()}"><b>{word}</b> {e(st["name"])} ({st["s"]} s){detail}{link}</li>'
        steps = "".join(step_li(st) for st in self.steps)
        page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Farglow UI test · {verdict}</title>
<style>body{{font:13px/1.4 system-ui,sans-serif;margin:16px;color:#141a22;background:#f3f4f1}}
h1{{font-size:18px}} section{{background:#fff;border:1px solid #d5d9de;border-radius:4px;padding:8px;margin:8px 0}}
h3{{margin:0;font-size:14px}} .meta{{color:#56606c;margin:2px 0 6px;font-family:monospace}} ul{{margin:0;padding-left:18px}}
.fail{{color:#b42318}} .warn{{color:#9a5b00}} .ok{{color:#1d7a46}} img{{max-width:420px;max-height:300px;border:1px solid #d5d9de;margin-top:6px}}
.verdict{{font-size:22px;font-weight:700}} .PASS{{color:#1d7a46}} .FAIL{{color:#b42318}}</style></head><body>
<h1>Farglow UI test · <span class="verdict {verdict}">{verdict}</span></h1>
<p class="meta">{e(self.base)} · {summary['started']} · {summary['seconds']} s · {fails} fail(s), {warns} warning(s)</p>
<h2>Play-through</h2><ul>{steps}</ul><h2>Screens</h2>{''.join(rows)}</body></html>"""
        (self.out / "report.html").write_text(page)
        print(f"\nUI test {verdict}: {fails} fail(s), {warns} warning(s). Report: {self.out / 'report.html'}")
        return 0 if verdict == "PASS" else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--url", required=True)
    p.add_argument("--out", default="ui-report")
    p.add_argument("--viewports", default="1366x768,1920x1080", type=lambda s: s.split(","))
    p.add_argument("--themes", default="light,dark", type=lambda s: s.split(","))
    p.add_argument("--ticks", type=int, default=4)
    p.add_argument("--email", default="")
    args = p.parse_args()
    run = Run(args)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        run.storage = None
        print("Public pages")
        run.check_all(browser, signed_in=False)
        print("Play-through")
        played = run.play(browser)
        if played:
            print("Game screens")
            run.check_all(browser, signed_in=True)
        browser.close()
    return run.report()


if __name__ == "__main__":
    sys.exit(main())
