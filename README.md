# Blinkit Category-Exploration Discovery Engine

AI-powered review/feedback analysis pipeline that mines public user feedback about
**Blinkit** (India quick-commerce) to generate **hypotheses about why users don't
explore new product categories** — with evidence strength, source triangulation,
and a validation layer.

> **Framing:** every output is a *candidate barrier/driver with evidence strength* —
> a **hypothesis**, not a conclusion. These feed a downstream survey + user
> interviews. The tool is biased around the `exploration_signal` field and a
> barrier-focused theme vocabulary, not generic app complaints.

---

## What it does (3 layers)

1. **Multi-source scrapers** → normalized `data/raw_<source>.jsonl`
   - Apple App Store (India RSS feed) · Google Play (internal `batchexecute` RPC)
   - Reddit (Arctic Shift archive — Reddit's own JSON 403s from servers)
   - YouTube comments (official Data API v3, item-level topic filtering)
   - Complaint forums (Trustpilot/MouthShut) — **probed & dropped** (bot-walled /
     JS-rendered); the attempt is recorded in `data/source_probe.json` for honesty.
2. **Two-pass LLM analysis** (provider-agnostic: Groq primary, Gemini fallback)
   - **Pass 1** — per-item structured tags (`exploration_signal`, barrier `themes`,
     `user_segment_signals`, `job_to_be_done`, `is_relevant`, …). Batched, resumable,
     shuffle-before-limit, per-enum validated.
   - **Pass 2** — deterministic Python counts + one LLM call for clustering, quote
     selection, hypotheses, executive summary, category opportunities, and
     recommended experiments.
   - **Validation** — per-theme/hypothesis evidence counts, source triangulation,
     coverage/ambiguity rate, 30-item human-check CSV.
   - **Excel** — `blinkit_review_analysis.xlsx` (Tagged Reviews / Insights /
     Validation), screenshot-ready.
3. **Streamlit dashboard** (5 tabs) reading pre-computed files — deploys to
   Streamlit Community Cloud.

---

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in GROQ_API_KEY, GEMINI_API_KEY, YOUTUBE_API_KEY, ADMIN_PASSWORD

# Run the whole analysis pipeline (uses already-scraped data/raw_*.jsonl):
./run_all.sh                    # or: TAG_LIMIT=800 ./run_all.sh
./run_all.sh --scrape           # also re-scrape all sources first (slow)

# Launch the dashboard locally:
streamlit run app.py
```

Individual steps also run standalone:
`python -m scrapers.app_store` · `python merge.py` · `python pass1_tag.py --limit 400`
· `python pass2_synthesize.py` (`--rebuild` = recompute deterministic parts, no LLM)
· `python validate.py` · `python export_excel.py`.

---

## Providers, models & free-tier quotas (verified live)

The LLM client (`llm_client.py`) is provider-agnostic and uses the **same JSON
Schema** for both providers.

| Provider | Model | Notes |
|---|---|---|
| **Groq** (primary) | `llama-3.3-70b-versatile` (+ rotation pool) | Model IDs verified live against `/models` at startup — never hardcoded from memory. |
| **Gemini** (fallback) | `gemini-3.6-flash` | `gemini-2.0-flash` free tier is retired (`limit: 0`); 3.x-flash *thinks*, so the client gives extra output budget. |

**Groq free tier ≈ 100k tokens/day PER MODEL** (rolling window). The client
**rotates across models** (`llama-3.3-70b` → `gpt-oss-120b` → `gpt-oss-20b` →
`llama-3.1-8b`) as each hits its daily cap, then falls back to Gemini — so the full
~2,300-item dataset can be tagged for free in ~a day. Tagging is **resumable**
(re-run to continue). `run_all.sh` prints an estimated request count before the
LLM-heavy steps.

---

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub (the `data/` result files are committed on purpose so
   the deployed app can read them — only `.env` and logs are gitignored).
2. On [share.streamlit.io](https://share.streamlit.io) → **New app** → pick this
   repo/branch, main file `app.py`.
3. In **Advanced settings → Secrets**, add:
   ```toml
   GROQ_API_KEY   = "gsk_…"
   GEMINI_API_KEY = "…"
   YOUTUBE_API_KEY = "…"
   ADMIN_PASSWORD = "your-admin-pass"
   ```
4. Deploy. The dashboard reads pre-computed `data/*.json[l]`; the *Live pipeline*
   and *Try it live* tabs make one live LLM call each; the *Admin* tab (password-
   gated) can re-run the pipeline in a background thread.

> **Why not Vercel?** Streamlit is a long-running stateful server; Vercel is
> serverless and can't host it (nor run the admin re-run's long pipeline job).

---

## Controlled vocabularies

Single source of truth in [`vocab.py`](vocab.py). Barrier/driver **themes** (e.g.
`habit_lock_repetitive_buying`, `assortment_gap_missing_products`,
`dont_trust_quality_for_new_category`, `too_expensive_vs_alternatives`,
`positive_discovery_experience`), **segments** (e.g. `grocery_only_regular`,
`new_parent`, `pet_owner`, `gifting_occasion_buyer`), product **categories**, and
the four **exploration signals**: `explored_new_category`,
`wants_to_explore_but_blocked`, `stuck_in_routine`, `no_signal`.

---

## Outputs (all in `data/`)

`merged.jsonl` · `tagged.jsonl` · `synthesis.json` + `synthesis.md` ·
`validation.json` + `validation_sample.csv` · `blinkit_review_analysis.xlsx` ·
`last_run_metadata.json` · `source_probe.json` · rolling `pipeline.log`.
