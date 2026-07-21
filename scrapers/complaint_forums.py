"""Complaint-forum probe (Trustpilot, MouthShut) — DROPPED source, documented.

Per the brief we ATTEMPT complaint forums and DROP any that don't yield
scrapable Blinkit signal, recording the outcome honestly (for signal-to-noise
reporting) rather than silently omitting them.

Findings from live probing (2026-07):
  - Trustpilot (blinkit.com / grofers.com): HTTP 403 — hard bot block.
  - MouthShut (blinkit-reviews-925738270): page exists, 18,632 ratings, avg
    1.56/5, BUT the review list is JS-rendered — no permalinks in raw HTML, no
    review-loading AJAX endpoint, and JSON-LD exposes only aggregateRating (no
    individual reviewBody). Individual review permalink pages DO render
    server-side, but cannot be enumerated without a headless browser, which
    would break the Streamlit-Cloud admin re-run (no Chromium there).

Decision: DROP the forum source. This module still runs the probe so the drop
is reproducible and evidenced. It writes data/source_probe.json and an (empty)
data/raw_forums.jsonl so the merge step sees a consistent set of raw_* files.

Usage:  python -m scrapers.complaint_forums
"""

import datetime as dt
import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import DATA_DIR, get_logger, write_jsonl

log = get_logger("scraper.forums")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
PROBE_PATH = os.path.join(DATA_DIR, "source_probe.json")
OUT_PATH = os.path.join(DATA_DIR, "raw_forums.jsonl")

TARGETS = [
    ("trustpilot", "https://www.trustpilot.com/review/blinkit.com"),
    ("mouthshut", "https://www.mouthshut.com/product-reviews/blinkit-reviews-925738270"),
]


def probe() -> dict:
    results = []
    for name, url in TARGETS:
        entry = {"forum": name, "url": url}
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
            entry["http_status"] = r.status_code
            body = r.text if r.status_code == 200 else ""
            # Is any individual Blinkit review body present in the raw HTML?
            entry["review_bodies_in_raw_html"] = (
                'itemprop="reviewBody"' in body or "/review/blinkit-review-" in body
            )
            if r.status_code == 403:
                entry["verdict"] = "blocked (403 bot wall)"
            elif r.status_code == 200 and not entry["review_bodies_in_raw_html"]:
                entry["verdict"] = "loads but reviews are JS-rendered (not scrapable via requests)"
            elif r.status_code == 200:
                entry["verdict"] = "scrapable"
            else:
                entry["verdict"] = f"unexpected HTTP {r.status_code}"
        except requests.RequestException as e:
            entry["http_status"] = None
            entry["verdict"] = f"request error: {e!r}"
        log.info("Probe %-11s -> %s", name, entry["verdict"])
        results.append(entry)

    scrapable = [r for r in results if r["verdict"] == "scrapable"]
    report = {
        "probed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "targets": results,
        "decision": ("DROPPED — no forum yielded scrapable Blinkit review bodies "
                     "via a browserless, deploy-safe scraper"
                     if not scrapable else "some forums scrapable"),
        "items_captured": 0,
    }
    return report


if __name__ == "__main__":
    report = probe()
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PROBE_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    write_jsonl(OUT_PATH, [])  # consistent empty raw file for the merge step
    log.info("Wrote probe report -> %s (decision: %s)", PROBE_PATH, report["decision"])
