"""Dev tool: smoke-test every dashboard page in a real browser and save screenshots to docs/screenshots/.

Requires: pip install playwright  (uses the installed Microsoft Edge or Chrome; or run `playwright install chromium`)
Usage:    streamlit run app.py   (in another terminal), then  python scripts/capture_screenshots.py [--url http://localhost:8501]
Exits non-zero if any page shows a Streamlit exception.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["", "signals", "events", "stress-lab", "evaluation", "data"]


def launch(p):
    for channel in ("msedge", "chrome", None):
        try:
            return p.chromium.launch(channel=channel) if channel else p.chromium.launch()
        except Exception:
            continue
    sys.exit("No Chromium-based browser found. Run: playwright install chromium")


def wait_idle(page) -> None:
    page.wait_for_selector("[data-testid='stApp']", timeout=60_000)
    page.wait_for_timeout(1500)
    for _ in range(120):  # Streamlit shows a status widget while a script run is in progress
        if page.locator("[data-testid='stStatusWidget']").count() == 0:
            break
        page.wait_for_timeout(500)
    page.wait_for_timeout(2500)  # let Plotly finish drawing


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8501")
    ap.add_argument("--out", default=str(ROOT / "docs" / "screenshots"))
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    failures = []
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={"width": args.width, "height": args.height}, device_scale_factor=1.25)
        for name in PAGES:
            page.goto(f"{args.url}/{name}")
            wait_idle(page)
            errs = page.locator("[data-testid='stException']")
            if errs.count():
                failures.append((name, errs.first.inner_text()[:600]))
            label = name or "overview"
            page.screenshot(path=str(out / f"{label}_fold.png"))
            # Streamlit scrolls inside its own container, so grow the viewport to capture the whole page
            h = page.evaluate("document.querySelector('[data-testid=\"stMain\"]').scrollHeight")
            page.set_viewport_size({"width": args.width, "height": max(args.height, int(h) + 40)})
            page.wait_for_timeout(2500)
            page.screenshot(path=str(out / f"{label}.png"))
            page.set_viewport_size({"width": args.width, "height": args.height})
            print(f"{label}: {'EXCEPTION' if errs.count() else 'ok'} (height {h})")
        browser.close()
    for name, msg in failures:
        print(f"\n--- {name} ---\n{msg}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
