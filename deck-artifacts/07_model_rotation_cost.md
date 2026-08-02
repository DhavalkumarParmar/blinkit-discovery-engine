# Artifact 7 — Model rotation & cost strategy

From `llm_client.py` and the run metadata. The honest headline: rotation is a
**cost/throughput** mechanism to stay on free tiers, **not** a quality-tuning
mechanism, and **no cross-model quality comparison was run.**

## Why multiple models across free tiers

Groq's free tier caps **tokens-per-day per model** (verified live: llama-3.3-70b
returned a "tokens per day (TPD)" 429 mid-run). Each model ID has its **own daily
bucket**. So instead of stopping when one model's daily budget is spent, the client
rotates to the next model — multiplying free daily throughput enough to tag the
whole 2,282-item corpus in one day at $0.

Rotation pool (from code, ordered "best-quality first" per the comment):
```
GROQ_ROTATION = ["llama-3.3-70b-versatile",   # rotation order 1
                 "openai/gpt-oss-120b",        # 2
                 "openai/gpt-oss-20b",          # 3
                 "llama-3.1-8b-instant"]        # 4
# then fallback provider: gemini-3.6-flash
```

## How rotation & fallback are triggered (exact)

1. **Startup:** `verify_groq_model()` hits the live `/models` endpoint and keeps
   only active IDs from the pool (a deprecated ID can never be used silently).
2. **Per call:** use the first non-exhausted model (`_next_groq_model`).
3. **Daily-cap 429** (body contains `per day`/`tpd`/`rpd`) **or 413**: mark that
   model exhausted, `model_rotations += 1`, move to the next model **immediately
   (no backoff)** — waiting wouldn't help a *daily* cap.
4. **Per-minute 429 / 5xx / timeout:** retry the *same* model with exponential
   backoff `min(2^attempt·2, 60)`s (honoring `Retry-After`), up to `MAX_RETRIES=5`.
5. **All 4 Groq models exhausted → Gemini fallback** (`fallbacks += 1`). Gemini
   gets extra output budget (`max(max_tokens·2, 8192)`) because 3.x-flash is a
   thinking model.
6. **Both providers fail → `LLMError`**; the batch is skipped and the run is
   **resumable** (re-run next day; buckets roll over on a 24h window).

## What actually happened (this run)

Tagging (2,282 items) split across models — `tagged_by_model`:

| Rotation order | Model | Items tagged | Share |
|---:|---|---:|---:|
| 1 | llama-3.3-70b-versatile | 352 | 15.4% |
| 2 | openai/gpt-oss-120b | 406 | 17.8% |
| 3 | openai/gpt-oss-20b | 337 | 14.8% |
| 4 | llama-3.1-8b-instant | **1,043** | **45.7%** |
| fallback | gemini-3.6-flash | 144 | 6.3% |

Tagging: **3 model rotations, 0 Gemini fallbacks** (Groq rotation alone carried it;
the 144 Gemini items came from an earlier partial run, not the main rotation run).
Note the biggest share went to the **smallest** model (8b, 46%) — because it has the
largest daily bucket, so it absorbed the most volume once the larger models capped.

## The quality trade-off — stated honestly

- **Larger vs smaller:** all pool models share a 131k context window and JSON mode,
  so the schema/prompt fit identically. The *intended* trade-off is that the larger
  models (70b, gpt-oss-120b) give better nuance on ambiguous/transliterated text,
  and the pool is **ordered largest-first** so the best models are used until their
  buckets run out. In practice the smallest model (8b) still did ~46% of tagging.
- **Was tagging quality ever compared across models? No.** There is no A/B in the
  code or data: each item was tagged **once by whichever model was active**, never
  the same item by two models. So there is **no measured quality delta** between,
  say, 70b and 8b on this corpus. Any claim that "the big models are more accurate
  here" would be unsupported.
- **What we *do* know:** the single independent accuracy signal is the 30-item
  manual check (100% agreement), but that sample mixes models and isn't stratified
  by model, so it can't attribute quality per model either.

## Cost

- **$0 measured** — entirely on free tiers by design. **No token or dollar figure is
  logged** (Artifact 4). The strategy is "stay free via rotation," not "minimize a
  tracked spend."

## The obvious follow-up (for Artifact 10)

To make a defensible quality claim: re-tag a fixed ~100-item gold sample with each
model, measure agreement vs the human labels per model, and either pin the highest-
accuracy affordable model or keep rotation but report the per-model accuracy.
