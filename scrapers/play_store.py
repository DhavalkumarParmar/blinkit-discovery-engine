"""Google Play Store (India) review scraper for Blinkit.

Does NOT use the `google-play-scraper` library (frequently broken / unmaintained
per hard experience). Instead calls Google's own internal `batchexecute` RPC
directly with `requests` — verified live to return 40 reviews/page with a working
pagination token.

Blinkit package id: com.grofers.customerapp (verified on the live details page).

Response quirk: the RPC body is prefixed with `)]}'` and is doubly JSON-encoded
(the useful payload is a JSON string nested inside the outer envelope).

Usage:  python -m scrapers.play_store [--max 500] [--limit N]
Output: data/raw_play_store.jsonl  (normalized schema)
"""

import argparse
import datetime as dt
import json
import os
import sys
import time
from urllib.parse import urlencode

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import DATA_DIR, get_logger, write_jsonl

log = get_logger("scraper.play_store")

PACKAGE = "com.grofers.customerapp"
RPC_URL = "https://play.google.com/_/PlayStoreUi/data/batchexecute"
APP_URL = f"https://play.google.com/store/apps/details?id={PACKAGE}&hl=en&gl=IN"
OUT_PATH = os.path.join(DATA_DIR, "raw_play_store.jsonl")

PAGE_SIZE = 40           # max the RPC returns per call
SORT_NEWEST = 2          # [2,1,...] -> sort=newest
HEADERS = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}


def _build_body(token: str | None) -> str:
    """Build the f.req form payload for one page (token=None for first page)."""
    count_block = [PAGE_SIZE, None, token]
    inner = [None, None, [SORT_NEWEST, 1, count_block, None, []], [PACKAGE, 7]]
    envelope = [[["UsvDTd", json.dumps(inner), None, "generic"]]]
    return urlencode({"f.req": json.dumps(envelope)})


def fetch_page(token: str | None) -> tuple[list, str | None]:
    """Return (raw_reviews, next_token). Empty list + None on failure/end."""
    params = {"rpcids": "UsvDTd", "hl": "en", "gl": "IN"}
    try:
        r = requests.post(f"{RPC_URL}?{urlencode(params)}", headers=HEADERS,
                          data=_build_body(token), timeout=30)
    except (requests.Timeout, requests.ConnectionError) as e:
        log.warning("Network error fetching page: %r", e)
        return [], None
    if r.status_code != 200:
        log.warning("RPC -> HTTP %d, stopping", r.status_code)
        return [], None
    try:
        body = r.text[r.text.find("\n") + 1:]        # strip )]}' prefix line
        envelope = json.loads(body)
        payload = json.loads(envelope[0][2])          # doubly-encoded
        reviews = payload[0] or []
        next_token = payload[-1][-1] if payload[-1] else None
        return reviews, next_token
    except (json.JSONDecodeError, IndexError, TypeError) as e:
        log.warning("Failed to parse RPC response: %r", e)
        return [], None


def normalize(rv: list, scraped_at: str) -> dict | None:
    try:
        review_id = rv[0]
        author = rv[1][0] if rv[1] else ""
        rating = int(rv[2]) if rv[2] is not None else None
        text = (rv[4] or "").strip()
        ts = rv[5][0] if rv[5] else None
        date = dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d") if ts else ""
    except (IndexError, TypeError, ValueError):
        return None
    if not text:
        return None
    return {
        "id": f"playstore_{review_id}",
        "source": "play_store",
        "date": date,
        "rating": rating,
        "text": text,
        "author": author,
        "url": APP_URL,   # Play exposes no stable per-review permalink
        "scraped_at": scraped_at,
    }


def scrape(max_reviews: int = 500, limit: int | None = None) -> list[dict]:
    target = min(max_reviews, limit) if limit else max_reviews
    scraped_at = dt.datetime.now(dt.timezone.utc).isoformat()
    seen_ids: set[str] = set()
    items: list[dict] = []
    token: str | None = None
    page = 0
    while len(items) < target:
        page += 1
        raw, token = fetch_page(token)
        if not raw:
            log.info("Page %d empty — end of reviews", page)
            break
        new = 0
        for rv in raw:
            item = normalize(rv, scraped_at)
            if item is None or item["id"] in seen_ids:
                continue
            seen_ids.add(item["id"])
            items.append(item)
            new += 1
        log.info("Page %d: %d raw, %d new (total %d)", page, len(raw), new, len(items))
        if new == 0:
            log.warning("Page %d only duplicates — pagination not advancing, aborting", page)
            break
        if token is None:
            log.info("No further pagination token — reached end")
            break
        time.sleep(1)  # be polite
    return items[:target]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=500)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    items = scrape(args.max, args.limit)
    write_jsonl(OUT_PATH, items)
    log.info("Wrote %d reviews -> %s", len(items), OUT_PATH)
    if items:
        ratings = [i["rating"] for i in items if i["rating"] is not None]
        log.info("Date range %s .. %s | avg rating %.2f",
                 min(i["date"] for i in items), max(i["date"] for i in items),
                 sum(ratings) / len(ratings) if ratings else 0)
