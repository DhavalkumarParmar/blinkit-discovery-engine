"""Merge all raw_<source>.jsonl files into one normalized data/merged.jsonl.

Deterministic (no LLM). Steps:
  1. Read every data/raw_*.jsonl.
  2. Keep only the canonical schema fields, dropping internal `_`-prefixed
     helper fields (e.g. _subreddit, _topic_hint) the scrapers added.
  3. Drop empty/whitespace-only text and too-short items (< MIN_LEN chars).
  4. Dedupe by `id` (and by normalized text, to catch cross-source repost dupes).
  5. Write data/merged.jsonl + print a per-source count table.

Usage:  python merge.py
"""

import glob
import os
import re

from common import DATA_DIR, get_logger, read_jsonl, write_jsonl

log = get_logger("merge")

MERGED_PATH = os.path.join(DATA_DIR, "merged.jsonl")
SCHEMA = ["id", "source", "date", "rating", "text", "author", "url", "scraped_at"]
MIN_LEN = 8  # drop trivial one-word noise like "Nice", "ok"


def _norm_text(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip().lower()


def merge() -> list[dict]:
    raw_files = sorted(glob.glob(os.path.join(DATA_DIR, "raw_*.jsonl")))
    by_id: dict[str, dict] = {}
    seen_text: set[str] = set()
    per_source_raw: dict[str, int] = {}
    dropped_short = dropped_dup_id = dropped_dup_text = 0

    for path in raw_files:
        items = read_jsonl(path)
        src_name = os.path.basename(path)[4:-6]  # raw_<x>.jsonl -> <x>
        per_source_raw[src_name] = len(items)
        for it in items:
            clean = {k: it.get(k) for k in SCHEMA}
            text = (clean.get("text") or "").strip()
            if len(text) < MIN_LEN:
                dropped_short += 1
                continue
            _id = clean.get("id")
            if not _id or _id in by_id:
                dropped_dup_id += 1
                continue
            nt = _norm_text(text)
            if nt in seen_text:
                dropped_dup_text += 1
                continue
            seen_text.add(nt)
            by_id[_id] = clean

    merged = list(by_id.values())
    # stable order: source, then date
    merged.sort(key=lambda x: (x["source"], x.get("date") or ""))

    log.info("Raw files: %s", {os.path.basename(p): per_source_raw[os.path.basename(p)[4:-6]]
                               for p in raw_files})
    log.info("Dropped -> short:%d, dup_id:%d, dup_text:%d",
             dropped_short, dropped_dup_id, dropped_dup_text)
    by_src_merged: dict[str, int] = {}
    for m in merged:
        by_src_merged[m["source"]] = by_src_merged.get(m["source"], 0) + 1
    log.info("Merged per-source: %s", by_src_merged)
    log.info("TOTAL merged items: %d", len(merged))
    return merged


if __name__ == "__main__":
    merged = merge()
    write_jsonl(MERGED_PATH, merged)
    log.info("Wrote %d items -> %s", len(merged), MERGED_PATH)
