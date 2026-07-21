"""Reddit scraper for Blinkit discussion — via the Arctic Shift archive mirror.

Reddit's own JSON endpoints 403 from servers (bot detection) and new API-app
creation is often denied, so we use Arctic Shift (a public Reddit archive):
  GET /api/posts/search?subreddit=..&query=blinkit&after=..&limit=100
  GET /api/comments/search?link_id=t3_<postid>&limit=..   (comments ON a post)

Learned from probing the API live:
- Posts search (`query=`) is fast and reliable.
- Comment BODY-search (`body=`) over big subreddits (r/india, r/bangalore) always
  returns 422 "Timeout. Maybe slow down a bit" — the server can't scan a whole
  sub's comment corpus for a substring. So we DON'T body-search comments.
- Instead we pull TOP-LEVEL comments directly from the Blinkit posts we already
  found (link_id search; top-level == parent_id starts with "t3_"). Those are
  on-topic by construction and cost one cheap request per post.
- Item-level filter: posts must contain "blinkit" in their own text (search is
  noisy). Comments inherit topicality from their Blinkit parent post.

Usage:  python -m scrapers.reddit [--limit N] [--per-sub 120] [--comment-posts 25]
Output: data/raw_reddit.jsonl  (normalized schema)
"""

import argparse
import datetime as dt
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import DATA_DIR, get_logger, write_jsonl

log = get_logger("scraper.reddit")

BASE = "https://arctic-shift.photon-reddit.com/api"
SUBREDDITS = ["bangalore", "india", "mumbai", "delhi", "IndianStreetBets", "QuickCommerce"]
OUT_PATH = os.path.join(DATA_DIR, "raw_reddit.jsonl")

AFTER = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=365)).strftime("%Y-%m-%d")
PAGE_LIMIT = 100
MAX_RETRIES = 4
MIN_COMMENT_LEN = 15
TOPIC_HINTS = ["categor", "only order", "always buy", "never tried", "discover",
               "recommend", "pet", "baby", "personal care", "same stuff", "explore",
               "assortment", "beauty", "pharma", "grocery", "snack", "cosmetic"]


_URL_RE = re.compile(r"https?://\S+")


def _is_substantive(text: str) -> bool:
    """True if the comment has real prose left after stripping URLs."""
    stripped = _URL_RE.sub("", text)
    words = re.findall(r"[A-Za-z]{2,}", stripped)
    return len(" ".join(words)) >= MIN_COMMENT_LEN and len(words) >= 3


def _get(endpoint: str, params: dict) -> list | None:
    """GET with retry/backoff on 422/429/5xx. Returns list, or None on hard fail."""
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=45)
        except (requests.Timeout, requests.ConnectionError) as e:
            log.warning("%s network error: %r", endpoint, e)
            time.sleep(min(2 ** attempt * 2, 20))
            continue
        if r.status_code == 200:
            return r.json().get("data") or []
        if r.status_code in (422, 429) or r.status_code >= 500:
            wait = min(2 ** attempt * 2, 20)
            log.warning("%s HTTP %d (%s) — retry in %ds", endpoint, r.status_code,
                        r.text[:50], wait)
            time.sleep(wait)
            continue
        log.warning("%s HTTP %d (%s) — giving up", endpoint, r.status_code, r.text[:80])
        return None
    return None


def _mk(obj: dict, kind: str, text: str, scraped_at: str) -> dict:
    ts = obj.get("created_utc")
    date = (dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d")
            if ts else "")
    permalink = obj.get("permalink") or ""
    url = f"https://reddit.com{permalink}" if permalink.startswith("/") else permalink
    return {
        "id": f"{kind}_{obj.get('id')}",
        "source": "reddit",
        "date": date,
        "rating": None,
        "text": text,
        "author": obj.get("author") or "",
        "url": url,
        "scraped_at": scraped_at,
        "_subreddit": obj.get("subreddit", ""),
    }


def search_posts(sub: str, per_sub: int, scraped_at: str) -> list[dict]:
    """Paginate Blinkit posts in one subreddit, oldest-cursor via created_utc."""
    collected: dict[str, dict] = {}
    before = None
    page = 0
    while len(collected) < per_sub:
        page += 1
        params = {"subreddit": sub, "query": "blinkit", "after": AFTER,
                  "limit": PAGE_LIMIT, "sort": "desc"}
        if before:
            params["before"] = before
        raw = _get("posts/search", params)
        if not raw:
            break
        new = 0
        oldest = None
        for p in raw:
            oldest = p.get("created_utc") or oldest
            title = (p.get("title") or "").strip()
            body = (p.get("selftext") or "").strip()
            if body in ("[deleted]", "[removed]"):
                body = ""
            text = f"{title}. {body}".strip(". ").strip() if body else title
            if not text or "blinkit" not in text.lower():
                continue
            item = _mk(p, "reddit_post", text, scraped_at)
            if item["id"] not in collected:
                collected[item["id"]] = item
                new += 1
        log.info("  r/%s posts page %d: %d raw, %d new (total %d)",
                 sub, page, len(raw), new, len(collected))
        if not oldest or len(raw) < PAGE_LIMIT:
            break
        nxt = oldest - 1
        if before is not None and nxt >= before:
            break
        before = nxt
        time.sleep(1.2)
    return list(collected.values())


def fetch_top_comments(post_id: str, sub: str, scraped_at: str,
                       max_comments: int = 15) -> list[dict]:
    """Top-level comments on one post (parent_id == t3_<postid>)."""
    raw = _get("comments/search",
               {"link_id": f"t3_{post_id}", "limit": 100, "sort": "desc"})
    if not raw:
        return []
    out = []
    for c in raw:
        if not str(c.get("parent_id", "")).startswith("t3_"):
            continue  # keep only top-level
        body = (c.get("body") or "").strip()
        if body in ("[deleted]", "[removed]") or not _is_substantive(body):
            continue
        c.setdefault("subreddit", sub)
        out.append(_mk(c, "reddit_comment", body, scraped_at))
        if len(out) >= max_comments:
            break
    return out


def scrape(per_sub: int = 120, comment_posts: int = 25, limit: int | None = None) -> list[dict]:
    scraped_at = dt.datetime.now(dt.timezone.utc).isoformat()
    all_items: dict[str, dict] = {}
    for sub in SUBREDDITS:
        log.info("Subreddit r/%s ...", sub)
        posts = search_posts(sub, per_sub, scraped_at)
        for p in posts:
            all_items[p["id"]] = p
        # pull top-level comments from the most-recent Blinkit posts (bounded budget)
        n_comments = 0
        for p in posts[:comment_posts]:
            post_id = p["id"].replace("reddit_post_", "")
            for c in fetch_top_comments(post_id, sub, scraped_at):
                if c["id"] not in all_items:
                    all_items[c["id"]] = c
                    n_comments += 1
            time.sleep(0.8)
        log.info("r/%s -> %d posts + %d top-level comments (running total %d)",
                 sub, len(posts), n_comments, len(all_items))
        if limit and len(all_items) >= limit:
            break
    items = list(all_items.values())
    for it in items:
        blob = it["text"].lower()
        it["_topic_hint"] = any(h in blob for h in TOPIC_HINTS)
    return items[:limit] if limit else items


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-sub", type=int, default=120)
    ap.add_argument("--comment-posts", type=int, default=25)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    items = scrape(args.per_sub, args.comment_posts, args.limit)
    write_jsonl(OUT_PATH, items)
    log.info("Wrote %d reddit items -> %s", len(items), OUT_PATH)
    if items:
        n_hint = sum(1 for i in items if i.get("_topic_hint"))
        n_comments = sum(1 for i in items if i["id"].startswith("reddit_comment_"))
        by_sub: dict[str, int] = {}
        for i in items:
            by_sub[i["_subreddit"]] = by_sub.get(i["_subreddit"], 0) + 1
        dates = [i["date"] for i in items if i["date"]]
        log.info("Date range %s .. %s | %d comments | %d/%d topic-hinted | by sub: %s",
                 min(dates), max(dates), n_comments, n_hint, len(items), by_sub)
