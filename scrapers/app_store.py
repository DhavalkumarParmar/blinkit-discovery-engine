"""Apple App Store (India) review scraper for Blinkit.

Uses Apple's public RSS customer-reviews feed — no key, no scraping library:
  https://itunes.apple.com/in/rss/customerreviews/id=<APP_ID>/sortBy=mostRecent/page=N/json
The feed serves 50 reviews/page and caps at page 10 (=500 most recent), which
matches the 300-500 target.

App ID 960335206 verified live via the iTunes Search API
("Blinkit: Groceries & more", BLINK COMMERCE PRIVATE LIMITED).

Usage:  python -m scrapers.app_store [--pages 10] [--limit N]
Output: data/raw_app_store.jsonl  (normalized schema)
"""

import argparse
import datetime as dt
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import DATA_DIR, get_logger, write_jsonl

log = get_logger("scraper.app_store")

APP_ID = "960335206"
FEED = ("https://itunes.apple.com/in/rss/customerreviews/"
        f"id={APP_ID}/sortBy=mostRecent/page={{page}}/json")
APP_URL = f"https://apps.apple.com/in/app/id{APP_ID}?see-all=reviews"
OUT_PATH = os.path.join(DATA_DIR, "raw_app_store.jsonl")


def fetch_page(page: int) -> list[dict]:
    r = requests.get(FEED.format(page=page), timeout=30)
    if r.status_code != 200:
        log.warning("Page %d -> HTTP %d, stopping", page, r.status_code)
        return []
    entries = r.json().get("feed", {}).get("entry", [])
    # Page 1 sometimes includes the app itself as the first "entry" (no rating).
    return [e for e in entries if "im:rating" in e]


def normalize(e: dict, scraped_at: str) -> dict:
    title = e.get("title", {}).get("label", "").strip()
    body = e.get("content", {}).get("label", "").strip()
    text = f"{title}. {body}" if title and title.lower() not in body.lower() else body
    return {
        "id": f"appstore_{e['id']['label']}",
        "source": "app_store",
        "date": e.get("updated", {}).get("label", "")[:10],
        "rating": int(e["im:rating"]["label"]),
        "text": text,
        "author": e.get("author", {}).get("name", {}).get("label", ""),
        "url": APP_URL,  # Apple exposes no per-review permalink; link to reviews page
        "scraped_at": scraped_at,
    }


def scrape(max_pages: int = 10, limit: int | None = None) -> list[dict]:
    scraped_at = dt.datetime.now(dt.timezone.utc).isoformat()
    seen_ids: set[str] = set()
    items: list[dict] = []
    for page in range(1, max_pages + 1):
        entries = fetch_page(page)
        if not entries:
            log.info("Page %d empty — end of feed", page)
            break
        new = 0
        for e in entries:
            item = normalize(e, scraped_at)
            if item["id"] in seen_ids:
                continue  # duplicate across pages -> pagination not advancing
            seen_ids.add(item["id"])
            items.append(item)
            new += 1
        log.info("Page %d: %d entries, %d new (total %d)", page, len(entries), new, len(items))
        if new == 0:
            log.warning("Page %d returned only duplicates — pagination stopped advancing, aborting", page)
            break
        if limit and len(items) >= limit:
            items = items[:limit]
            break
        time.sleep(1)  # be polite
    return items


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=10)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    items = scrape(args.pages, args.limit)
    write_jsonl(OUT_PATH, items)
    log.info("Wrote %d reviews -> %s", len(items), OUT_PATH)
    if items:
        ratings = [i["rating"] for i in items]
        log.info("Date range %s .. %s | avg rating %.2f",
                 min(i["date"] for i in items), max(i["date"] for i in items),
                 sum(ratings) / len(ratings))
