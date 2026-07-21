"""Pass 1 — per-item structured tagging via the LLM.

For each merged item, extract the structured tags defined in the brief (biased
around exploration_signal + barrier themes). Design goals:
  - Batch BATCH_SIZE items per LLM call (fewer requests, cheaper).
  - RESUMABLE: skip ids already present in data/tagged.jsonl on re-run.
  - Shuffle the merged dataset (fixed seed) BEFORE applying --limit, so a partial
    run samples across all sources, not just the first file.
  - Robust: a failed batch is logged and skipped (those items stay untagged and
    get picked up on the next run) — one error never kills the run.
  - Every enum is validated/coerced against vocab.py so downstream code can trust
    the tags.

Usage:  python pass1_tag.py [--limit 400] [--batch 8] [--yes]
Output: data/tagged.jsonl  (original fields + tags, one row per item)
"""

import argparse
import os
import random
import sys

from common import DATA_DIR, get_logger, read_jsonl, append_jsonl
from llm_client import LLMClient
from vocab import (CATEGORIES, CONFIDENCE, EXPLORATION_SIGNALS, SENTIMENTS,
                   THEMES, USER_SEGMENTS)

log = get_logger("pass1")

MERGED_PATH = os.path.join(DATA_DIR, "merged.jsonl")
TAGGED_PATH = os.path.join(DATA_DIR, "tagged.jsonl")
SHUFFLE_SEED = 42
BATCH_SIZE = 8
MAX_TEXT_CHARS = 800  # truncate long reviews/posts to control tokens

TAG_FIELDS = ["is_relevant", "sentiment", "themes", "user_segment_signals",
              "job_to_be_done", "frustration_root_cause", "mentions_category",
              "exploration_signal", "direct_quote", "confidence"]

# Per-item JSON Schema (standard lowercase types) wrapped in a batch envelope.
ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "is_relevant": {"type": "boolean"},
        "sentiment": {"type": "string", "enum": SENTIMENTS},
        "themes": {"type": "array", "items": {"type": "string", "enum": THEMES}},
        "user_segment_signals": {"type": "array", "items": {"type": "string", "enum": USER_SEGMENTS}},
        "job_to_be_done": {"type": "string"},
        "frustration_root_cause": {"type": "string"},
        "mentions_category": {"type": "array", "items": {"type": "string", "enum": CATEGORIES}},
        "exploration_signal": {"type": "string", "enum": EXPLORATION_SIGNALS},
        "direct_quote": {"type": "string"},
        "confidence": {"type": "string", "enum": CONFIDENCE},
    },
    "required": ["id", "is_relevant", "sentiment", "themes", "user_segment_signals",
                 "job_to_be_done", "frustration_root_cause", "mentions_category",
                 "exploration_signal", "direct_quote", "confidence"],
}
BATCH_SCHEMA = {
    "type": "object",
    "properties": {"results": {"type": "array", "items": ITEM_SCHEMA}},
    "required": ["results"],
}

SYSTEM = (
    "You are a product-research analyst studying why Blinkit (India quick-commerce) "
    "users stay locked into the SAME product categories and rarely explore NEW ones "
    "(pet, baby, personal care, beauty, electronics, home, pharma, etc.). "
    "You tag each user feedback item for category-EXPLORATION signal, not generic "
    "app complaints. Mark is_relevant=false when an item is a pure delivery/app/refund "
    "complaint with NO bearing on what categories users buy or why. "
    "exploration_signal is the most important field. Use ONLY the allowed enum values. "
    "job_to_be_done and frustration_root_cause: one short sentence each, in the user's "
    "voice. direct_quote: a verbatim snippet from the text, max 25 words. "
    "confidence reflects how clearly the text supports your tags (low if terse/ambiguous). "
    "Echo back each item's exact id."
)


def _coerce(raw: dict, original: dict) -> dict:
    """Validate/coerce one LLM result against the vocab; merge with original fields."""
    def clean_list(vals, allowed):
        out = [v for v in (vals or []) if v in allowed]
        return list(dict.fromkeys(out))  # dedupe, keep order

    sentiment = raw.get("sentiment")
    sentiment = sentiment if sentiment in SENTIMENTS else "neutral"
    signal = raw.get("exploration_signal")
    signal = signal if signal in EXPLORATION_SIGNALS else "no_signal"
    conf = raw.get("confidence")
    conf = conf if conf in CONFIDENCE else "low"
    quote = (raw.get("direct_quote") or "").strip()
    quote = " ".join(quote.split()[:25])

    tags = {
        "is_relevant": bool(raw.get("is_relevant", False)),
        "sentiment": sentiment,
        "themes": clean_list(raw.get("themes"), THEMES) or ["other"],
        "user_segment_signals": clean_list(raw.get("user_segment_signals"), USER_SEGMENTS),
        "job_to_be_done": (raw.get("job_to_be_done") or "").strip()[:300],
        "frustration_root_cause": (raw.get("frustration_root_cause") or "").strip()[:300],
        "mentions_category": clean_list(raw.get("mentions_category"), CATEGORIES),
        "exploration_signal": signal,
        "direct_quote": quote,
        "confidence": conf,
    }
    return {**original, **tags}


def _build_prompt(batch: list[dict]) -> str:
    lines = ["Tag each of the following feedback items. Return "
             '{"results": [...]} with one object per item, echoing its id.\n']
    for it in batch:
        text = (it.get("text") or "").replace("\n", " ").strip()[:MAX_TEXT_CHARS]
        rating = it.get("rating")
        rating_str = f" (star rating: {rating})" if rating is not None else ""
        lines.append(f'- id="{it["id"]}" source={it["source"]}{rating_str}: {text}')
    return "\n".join(lines)


def tag(limit: int | None = None, batch_size: int = BATCH_SIZE, assume_yes: bool = False):
    merged = read_jsonl(MERGED_PATH)
    if not merged:
        log.error("No merged.jsonl — run merge.py first.")
        return
    random.Random(SHUFFLE_SEED).shuffle(merged)  # shuffle BEFORE limit
    if limit:
        merged = merged[:limit]

    already = {t["id"] for t in read_jsonl(TAGGED_PATH)}
    todo = [it for it in merged if it["id"] not in already]
    if not todo:
        log.info("All %d selected items already tagged — nothing to do.", len(merged))
        return

    n_batches = (len(todo) + batch_size - 1) // batch_size
    log.info("Selected %d items (%d already tagged). To tag: %d in %d batches of %d.",
             len(merged), len(already), len(todo), n_batches, batch_size)
    log.warning("QUOTA ESTIMATE: ~%d LLM requests (batches). Groq free tier is "
                "token-limited; if it 429s it auto-falls back to Gemini and the "
                "run is resumable (re-run to continue).", n_batches)
    if not assume_yes:
        resp = input("Proceed? [y/N] ").strip().lower()
        if resp != "y":
            log.info("Aborted by user.")
            return

    client = LLMClient()
    if client.groq_key:
        client.verify_groq_model()

    tagged_count = failed_batches = 0
    for bi in range(0, len(todo), batch_size):
        batch = todo[bi:bi + batch_size]
        by_id = {it["id"]: it for it in batch}
        try:
            out = client.generate_json(_build_prompt(batch), BATCH_SCHEMA,
                                       system=SYSTEM, max_tokens=4096)
            results = out.get("results", []) if isinstance(out, dict) else []
        except Exception as e:  # noqa: BLE001 — never let one batch kill the run
            log.warning("Batch %d/%d failed (%s) — will retry on next run",
                        bi // batch_size + 1, n_batches, str(e)[:120])
            failed_batches += 1
            continue

        matched = 0
        for r in results:
            orig = by_id.get(r.get("id"))
            if orig is None:
                continue  # hallucinated / mismatched id
            append_jsonl(TAGGED_PATH, _coerce(r, orig))
            matched += 1
            tagged_count += 1
        log.info("Batch %d/%d: %d/%d items tagged (running total %d) | reqs g:%d gem:%d",
                 bi // batch_size + 1, n_batches, matched, len(batch), tagged_count,
                 client.stats["groq_requests"], client.stats["gemini_requests"])

    log.info("Pass 1 done. Newly tagged: %d | failed batches: %d | stats: %s",
             tagged_count, failed_batches, client.stats)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--batch", type=int, default=BATCH_SIZE)
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = ap.parse_args()
    tag(args.limit, args.batch, args.yes)
