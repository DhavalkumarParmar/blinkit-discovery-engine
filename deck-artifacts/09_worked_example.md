# Artifact 9 — One item, end to end (a judgement call)

A real item from `data/tagged.jsonl`, chosen because it is **transliterated Hindi
(Hinglish)** *and* a genuine judgement call — not an obvious case. Everything below
is copied from the actual data / reconstructed with the real code.

## Step 0 — Raw scraped record (`data/merged.jsonl`)

```json
{
  "id": "youtube_UgxCiAyE-YxP1BpN5rV4AaABAg",
  "source": "youtube",
  "date": "2025-09-04",
  "rating": null,
  "text": "Jiomart karo sasta hai blinkit se aur local shop se",
  "author": "@SwaroopKubal1780",
  "url": "https://www.youtube.com/watch?v=1D_ERP231_0&lc=UgxCiAyE-YxP1BpN5rV4AaABAg"
}
```
Rough gloss (not in the pipeline — for the reader): *"Use Jiomart, it's cheaper than
Blinkit and cheaper than the local shop."*

## Step 1 — Cleaning (deterministic, `merge.py` + `pass1_tag._build_prompt`)

- Survived merge: length ≥ 8 chars, not a duplicate → kept.
- For the prompt, text is newline-stripped and truncated to `MAX_TEXT_CHARS=800`
  (here it's short, so unchanged). No translation, no transliteration — the raw
  Hinglish is sent as-is.

## Step 2 — The exact prompt sent (reconstructed via `_build_prompt`)

System message (`pass1_tag.SYSTEM`, verbatim — see Artifact 2 for the full text)
plus the embedded JSON schema, then this user message:

```
Tag each of the following feedback items. Return {"results": [...]} with one object per item, echoing its id.

- id="youtube_UgxCiAyE-YxP1BpN5rV4AaABAg" source=youtube: Jiomart karo sasta hai blinkit se aur local shop se
```

(In the real run this item was one of 8 in its batch; shown alone here.)

## Step 3 — The model's tag output (stored in `data/tagged.jsonl`, `tagged_by` = llama-3.3-70b-versatile)

```json
{
  "is_relevant": true,
  "sentiment": "negative",
  "themes": ["price_uncertainty_new_category"],
  "user_segment_signals": ["price_sensitive"],
  "job_to_be_done": "Compare prices with other stores",
  "frustration_root_cause": "Blinkit is expensive",
  "mentions_category": ["grocery"],
  "exploration_signal": "wants_to_explore_but_blocked",
  "direct_quote": "Jiomart karo sasta",
  "confidence": "high"
}
```

Then `_coerce` ran: every enum here is valid vocab, so nothing was changed or
dropped; free-text fields were within length limits.

## Step 4 — How it rolled up

- `is_relevant=true` → counted in the **632 relevant** (not the 1,650 filtered).
- `exploration_signal=wants_to_explore_but_blocked` → one of the **111** in that
  bucket, and one of the **352** that "carry exploration signal" in the funnel.
- `themes=["price_uncertainty_new_category"]` → **+1 to that theme's count**, which
  totals **93 items (14.7% of relevant)** across sources — the #2 barrier overall.
- `user_segment_signals=["price_sensitive"]` → +1 to that segment's tally.
- Because this theme reaches 93 items across ≥2 sources, it clears the `strong`
  strength threshold (≥15 items, ≥2 sources) in `validate.py`.

## Why this is a judgement call (the honest part)

The comment never says "I want to try a new category." It's a **price put-down**
("Jiomart is cheaper"). The model made two defensible-but-debatable leaps:

1. It tagged `exploration_signal = wants_to_explore_but_blocked` — reading "I'd buy,
   but the price pushes me to a competitor" as *intent blocked by price*. A stricter
   reading is that this is simply a **price complaint / competitor preference** with
   no exploration intent at all (i.e. arguably `no_signal`).
2. It applied `price_uncertainty_new_category` even though the comment is about
   Blinkit's general pricing, not specifically *new-category* pricing.

Both are reasonable, and `confidence=high` is arguably over-confident for a 9-word
transliterated line. This single item won't move the analysis, but it illustrates
the real risk at scale: **price/competitor complaints can inflate the
"blocked-by-price" barrier** if the model leans toward exploration readings. It's
exactly the kind of edge the downstream survey should disambiguate — and a reason
the per-item `confidence` is the model's *self*-assessment, not ground truth
(Artifact 3).
