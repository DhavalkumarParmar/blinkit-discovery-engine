"""YouTube comment scraper for Blinkit / quick-commerce shopping habits.

Uses the official YouTube Data API v3 (key in YOUTUBE_API_KEY).

Quota (per Google): 10,000 units/day.
  - search.list          = 100 units each
  - commentThreads.list  =   1 unit  each (up to 100 comments/page)
Default run ≈ len(QUERIES)*100 + (#videos * pages) ≈ ~1,100 units. Well under cap.

Search results are NOISY (videos may be tangential), so we FILTER AT THE ITEM
LEVEL: a comment is kept only if it mentions "blinkit" or a category/exploration
topic keyword — not merely because the video title matched. (Brief's lesson.)

Usage:  python -m scrapers.youtube [--limit N] [--max-videos 60] [--comment-pages 2]
Output: data/raw_youtube.jsonl  (normalized schema)
"""

import argparse
import datetime as dt
import os
import sys
import time

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import DATA_DIR, get_logger, write_jsonl

load_dotenv()
log = get_logger("scraper.youtube")

API = "https://www.googleapis.com/youtube/v3"
KEY = os.getenv("YOUTUBE_API_KEY", "")
OUT_PATH = os.path.join(DATA_DIR, "raw_youtube.jsonl")

# Queries chosen to surface shopping-habit / category-exploration content, not
# generic "how to order" tutorials.
QUERIES = [
    "blinkit shopping habits",
    "blinkit vs local shop",
    "blinkit quick commerce review",
    "blinkit haul what i order",
    "quick commerce india category",
    "blinkit gadgets electronics",
    "blinkit beauty personal care",
    "blinkit pet baby products",
    "zepto blinkit instamart comparison",
    "quick commerce changing shopping behaviour india",
]

# Item-level relevance filter: keep a comment only if it hits one of these.
KEEP_KEYWORDS = [
    "blinkit", "quick commerce", "quick-commerce", "q-commerce",
    "categor", "only order", "always buy", "always order", "never tried",
    "never buy", "discover", "recommend", "same stuff", "same thing",
    "explore", "assortment", "pet", "baby", "personal care", "beauty",
    "cosmetic", "electronic", "gadget", "pharma", "medicine", "grocery",
    "snack", "stopped going", "local shop", "kirana",
]
MAX_RETRIES = 4
YEAR_AGO = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=365))


class QuotaExceeded(Exception):
    pass


def _get(endpoint: str, params: dict) -> dict | None:
    params = {**params, "key": KEY}
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(f"{API}/{endpoint}", params=params, timeout=30)
        except (requests.Timeout, requests.ConnectionError) as e:
            log.warning("%s network error: %r", endpoint, e)
            time.sleep(min(2 ** attempt * 2, 20))
            continue
        if r.status_code == 200:
            return r.json()
        body = r.text[:200]
        if "quotaExceeded" in body or "dailyLimitExceeded" in body:
            raise QuotaExceeded(body)
        if r.status_code == 429 or r.status_code >= 500:
            wait = min(2 ** attempt * 2, 20)
            log.warning("%s HTTP %d — retry in %ds", endpoint, r.status_code, wait)
            time.sleep(wait)
            continue
        # 403 with commentsDisabled etc.: skip this video, don't crash
        log.warning("%s HTTP %d (%s)", endpoint, r.status_code, body)
        return None
    return None


def search_videos(query: str, max_results: int = 15) -> list[str]:
    data = _get("search", {"part": "snippet", "q": query, "type": "video",
                           "maxResults": max_results, "regionCode": "IN",
                           "relevanceLanguage": "en", "order": "relevance"})
    if not data:
        return []
    return [it["id"]["videoId"] for it in data.get("items", []) if "videoId" in it.get("id", {})]


def _keep(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in KEEP_KEYWORDS)


def fetch_comments(video_id: str, pages: int, scraped_at: str) -> list[dict]:
    items: list[dict] = []
    token = None
    for _ in range(pages):
        params = {"part": "snippet", "videoId": video_id, "maxResults": 100,
                  "order": "relevance", "textFormat": "plainText"}
        if token:
            params["pageToken"] = token
        data = _get("commentThreads", params)
        if not data:
            break
        for it in data.get("items", []):
            s = it["snippet"]["topLevelComment"]["snippet"]
            text = (s.get("textDisplay") or "").strip()
            if not text or not _keep(text):  # item-level topic filter
                continue
            published = s.get("publishedAt", "")
            try:
                pub_dt = dt.datetime.fromisoformat(published.replace("Z", "+00:00"))
                if pub_dt < YEAR_AGO:
                    continue  # last-12-months window
            except ValueError:
                pass
            items.append({
                "id": f"youtube_{it['snippet']['topLevelComment']['id']}",
                "source": "youtube",
                "date": published[:10],
                "rating": None,
                "text": text,
                "author": s.get("authorDisplayName", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}"
                       f"&lc={it['snippet']['topLevelComment']['id']}",
                "scraped_at": scraped_at,
            })
        token = data.get("nextPageToken")
        if not token:
            break
    return items


def scrape(max_videos: int = 60, comment_pages: int = 2, limit: int | None = None) -> list[dict]:
    if not KEY:
        raise RuntimeError("YOUTUBE_API_KEY not set")
    scraped_at = dt.datetime.now(dt.timezone.utc).isoformat()
    video_ids: list[str] = []
    seen_v: set[str] = set()
    for q in QUERIES:
        try:
            for vid in search_videos(q):
                if vid not in seen_v:
                    seen_v.add(vid)
                    video_ids.append(vid)
        except QuotaExceeded:
            log.warning("Quota exceeded during search — proceeding with %d videos found", len(video_ids))
            break
        log.info("Query %-45s -> %d unique videos so far", q[:45], len(video_ids))
        time.sleep(0.3)
    video_ids = video_ids[:max_videos]
    log.info("Collected %d unique videos; fetching comments ...", len(video_ids))

    all_items: dict[str, dict] = {}
    for i, vid in enumerate(video_ids, 1):
        try:
            for c in fetch_comments(vid, comment_pages, scraped_at):
                all_items[c["id"]] = c
        except QuotaExceeded:
            log.warning("Quota exceeded during comments — stopping with %d items", len(all_items))
            break
        if i % 10 == 0:
            log.info("  video %d/%d, %d relevant comments so far", i, len(video_ids), len(all_items))
        time.sleep(0.2)
        if limit and len(all_items) >= limit:
            break
    items = list(all_items.values())
    return items[:limit] if limit else items


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-videos", type=int, default=60)
    ap.add_argument("--comment-pages", type=int, default=2)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    items = scrape(args.max_videos, args.comment_pages, args.limit)
    write_jsonl(OUT_PATH, items)
    log.info("Wrote %d youtube comments -> %s", len(items), OUT_PATH)
    if items:
        dates = [i["date"] for i in items if i["date"]]
        log.info("Date range %s .. %s", min(dates), max(dates))
