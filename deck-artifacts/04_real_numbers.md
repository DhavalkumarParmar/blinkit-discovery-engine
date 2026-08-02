# Artifact 4 — Real numbers from the pipeline

Every figure is from the committed data/output files or the tagging log. Sources
named per line. Where the code does **not** log something, it says so.

## Items per source

**Raw scraped** (`data/raw_*.jsonl`, line counts):

| Source | Raw scraped | After merge/dedup (`last_run_metadata.json`) | Dropped in merge |
|--------|------:|------:|------:|
| App Store | 500 | 479 | 21 |
| Play Store | 500 | 500 | 0 |
| Reddit | 957 | 913 | 44 |
| YouTube | 420 | 411 | 9 |
| Trustpilot / MouthShut | 0 | 0 | — (dropped source, see Artifact 6) |
| **Raw total (ex-forums)** | **2,377** | **2,303 merged** | **74** |

## Stage totals

| Metric | Value | Source |
|---|---:|---|
| Merged total | 2,303 | `merged.jsonl` / metadata |
| Tagged total | 2,282 | `tagged.jsonl` / metadata |
| Relevant (`is_relevant=true`) | 632 (27.7%) | `validation.json` |
| Filtered as noise (`is_relevant=false`) | 1,650 | `validation.json` |
| Carries exploration signal | 352 | `synthesis.json` funnel |
| Explored a new category | 98 | `synthesis.json` |

## Drops at each stage, and why

| Stage | In → Out | Dropped | Cause (from code) |
|---|---|---:|---|
| Scrape → Merge | 2,377 → 2,303 | 74 | `merge.py`: 23 text `<8 chars`; 51 duplicate normalized text; 0 duplicate id |
| Merge → Tagged | 2,303 → 2,282 | 21 | 1 failed LLM batch (8 items) + ~13 id-mismatch/skips in the batch tagger; resumable (not re-run before this snapshot) |
| Tagged → Relevant | 2,282 → 632 | 1,650 | LLM `is_relevant=false` — off-topic delivery/app/refund complaints |
| Relevant → Signal | 632 → 352 | 280 | `exploration_signal=no_signal` among relevant items |
| Signal → Explored | 352 → 98 | 254 | `stuck_in_routine` (143) + `wants_to_explore_but_blocked` (111) |

## Per-model tagging counts (final, per item — `last_run_metadata.json → tagged_by_model`)

| Model | Items tagged | Share |
|---|---:|---:|
| llama-3.1-8b-instant | 1,043 | 45.7% |
| openai/gpt-oss-120b | 406 | 17.8% |
| llama-3.3-70b-versatile | 352 | 15.4% |
| openai/gpt-oss-20b | 337 | 14.8% |
| gemini-3.6-flash (fallback) | 144 | 6.3% |
| **Total** | **2,282** | 100% |

## LLM call stats — two separate figures, don't conflate them

**A. The big tagging run** (from `data/pipeline.log` / `pass1_full.log`, the
`Pass 1 done` line for the 1,911-item run):
- Groq requests: **495** · Gemini requests: **0**
- Retries: **253** · Fallbacks to Gemini: **0** · Model rotations: **3**
- Rate-limit / 429 events logged during tagging: **256**
- Per-model batches that run: 70b 13 · gpt-oss-120b 51 · gpt-oss-20b 43 · 8b 131
- Interpretation: all four Groq models' *daily token buckets* were worked through
  by rotation (3 rotations); Gemini was **not** needed for tagging (0 fallbacks).

**B. The last synthesis run** (`last_run_metadata.json → llm_stats`) — this is
**only Pass 2**, not tagging:
- Groq requests: 4 · Gemini requests: 1 · Retries: 0 · Fallbacks: 1 · Rotations: 3
- (The synthesis prompt is large; it rotated all 4 Groq models — each daily-capped
  at that moment — and fell back to Gemini once, which succeeded.)

> ⚠️ The `groq_models_used` field in `last_run_metadata.json` is `{}` because it
> reflects only the (fallback) synthesis call. The authoritative per-model tagging
> split is `tagged_by_model` above.

## Runtime

- **Not logged as a metric.** The code records no wall-clock, per-stage duration.
- **Derivable from log timestamps** for the big tagging run:
  `06:44:11 → 08:34:06` = **≈ 1h 50m** for 1,911 newly-tagged items
  (**≈ 3.5 s/item**, dominated by rate-limit backoff — 253 retries / 256 429s, not
  model latency).

## Cost and tokens

- **Not logged, not computed anywhere in the code.** There is no token counter and
  no cost calculation. Do **not** put a cost/token figure on a slide as if measured.
- **What is true and can be said:** the entire run was completed on **free tiers**
  (Groq per-model daily buckets + Gemini free tier); the design goal in code is to
  stay within free limits via rotation. `pass1_tag.py` truncates item text to
  `MAX_TEXT_CHARS = 800` to control token use, and batches 8 items/call. An actual
  token/cost number would require re-running with logging added (see Artifact 10).
