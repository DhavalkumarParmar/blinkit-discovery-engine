# System Architecture

The Blinkit Category-Exploration Discovery Engine is a flat-file pipeline (no DB,
no framework) that turns public feedback into **evidence-weighted hypotheses** about
why users don't explore new categories. Data flows left→right; every stage writes a
file in `data/` so the next stage — and the deployed dashboard — can read it.

## End-to-end data flow

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│                     LAYER 1 · MULTI-SOURCE SCRAPERS  (scrapers/)                    │
│                                                                                    │
│  Apple App Store ─ RSS feed ────────►  raw_app_store.jsonl   (500)                 │
│  Google Play ──── batchexecute RPC ─►  raw_play_store.jsonl  (500)                 │
│  Reddit ───────── Arctic Shift API ─►  raw_reddit.jsonl      (913)  ← JSON 403s   │
│  YouTube ──────── Data API v3 ──────►  raw_youtube.jsonl     (411)    from servers │
│  Trustpilot / MouthShut ────────────►  source_probe.json    (DROPPED: bot-walled/ │
│  LinkedIn / X / TikTok  ── excluded                            JS-rendered)        │
│         │  item-level keyword filter · dedupe · pagination verified                │
└─────────┼──────────────────────────────────────────────────────────────────────┘
          ▼
   ┌─────────────┐   merge.py    normalize to 8 fields, drop noise/dupes
   │ merge.py    ├────────────►  data/merged.jsonl   (2,303 items)
   └─────────────┘               id · source · date · rating · text · author · url · scraped_at
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                     LAYER 2 · TWO-PASS AI ANALYSIS                                  │
│                                                                                    │
│   PASS 1  pass1_tag.py  ── per-item structured tags (batches of 8, RESUMABLE) ──┐  │
│      shuffle→limit · skip tagged ids · per-enum validated                        │  │
│      exploration_signal · themes(barriers) · segments · JTBD · is_relevant ...   │  │
│                                              │                                    │  │
│                                              ▼                                    │  │
│                                    data/tagged.jsonl  (2,282)                     │  │
│                                              │                                    │  │
│   PASS 2  pass2_synthesize.py  ◄─────────────┘                                   │  │
│      ┌───────────────────────────┐      ┌──────────────────────────────────┐    │  │
│      │ PYTHON (deterministic)    │      │ LLM (1 call · language only)      │    │  │
│      │ barriers% · signal dist   │  +   │ cluster JTBDs · pick quotes ·     │    │  │
│      │ segment/category counts   │      │ hypotheses(+supporting themes) ·  │    │  │
│      │ per-hypothesis evidence   │      │ exec summary · cat opportunities ·│    │  │
│      │ funnel · triangulation    │      │ experiments · surprising insights │    │  │
│      └───────────────────────────┘      └──────────────────────────────────┘    │  │
│                       └──────────────┬────────────────┘                          │  │
│                                      ▼                                            │  │
│                    data/synthesis.json  +  synthesis.md                           │  │
│                                      │                                            │  │
│   VALIDATE  validate.py  ◄───────────┤   evidence depth · source triangulation · │  │
│      data/validation.json            │   coverage/ambiguity · 30-item human CSV   │  │
│      data/validation_sample.csv      │                                            │  │
│                                      ▼                                            │  │
│   EXPORT  export_excel.py ──►  data/blinkit_review_analysis.xlsx  (3 tabs)        │  │
│   META    ──►  data/last_run_metadata.json  (counts · models · rotation mix)      │  │
└──────────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│               LAYER 3 · STREAMLIT DASHBOARD  (app.py)  — reads pre-computed files   │
│                                                                                    │
│   📊 Insights  · 🔬 Validation  · ⚡ Live pipeline  · 🧪 Try it live  · 🔐 Admin    │
│                                       │ live tabs → 1 LLM call    │ password-gated  │
│                                       ▼                           ▼                 │
│                            data/*.json[l]  (committed)     pipeline.py (bg thread)  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## The provider-agnostic LLM client (`llm_client.py`)

Every LLM call (Pass 1, Pass 2, live tabs) goes through one client with the **same
JSON Schema** for both providers. Groq model IDs are verified live against `/models`
at startup — never hardcoded from memory.

```text
   generate_json(prompt, schema)
            │
            ▼
   ┌─────────────────── GROQ (primary) ───────────────────┐      each model has its
   │  llama-3.3-70b ─cap?─► gpt-oss-120b ─cap?─►           │      OWN ~100k tok/day
   │  gpt-oss-20b ─cap?─► llama-3.1-8b ─cap?──────────────┐│      bucket → rotating
   │  (daily-cap 429 / 413 too-large ⇒ rotate, no wait)   ││      multiplies free tier
   └──────────────────────────────────────────────────────┘│
            │ all Groq models exhausted                     │
            ▼                                               │
   ┌─────────────── GEMINI (fallback) ──────────────┐      │
   │  gemini-3.6-flash (thinking model → +budget)    │      │
   │  retry w/ exponential backoff on 429/5xx        │      │
   └─────────────────────────────────────────────────┘      │
            │                                                │
            ▼                                                ▼
      structured JSON  ◄── retries · Retry-After honored · per-model usage counted
```

## Design principles

- **Hypotheses, not conclusions** — outputs are candidate barriers/drivers with
  evidence strength; a survey + interviews validate them downstream.
- **Numbers are deterministic** — all counts/percentages computed in Python; the LLM
  is used only where language understanding is required. Evidence counts can't be
  hallucinated.
- **Resumable & cached** — every stage writes to `data/`; Pass 1 skips already-tagged
  ids so large runs span days or model buckets safely.
- **Free-tier native** — per-model Groq rotation + Gemini fallback tag the full
  ~2,300-item dataset for free; quota estimates print before heavy steps.
- **Flat files, committed** — `data/` is versioned so the deployed dashboard reads
  pre-computed results and never scrapes/synthesizes per visitor.

## File map

```text
scrapers/            app_store · play_store · reddit · youtube · complaint_forums
common.py            logging (console + rolling data/pipeline.log) · JSONL helpers
vocab.py             controlled vocab: themes(barriers/drivers) · segments · signals
llm_client.py        Groq rotation pool + Gemini fallback · live model verify
merge.py             raw_*.jsonl → merged.jsonl
pass1_tag.py         per-item tagging (batched · resumable) → tagged.jsonl
pass2_synthesize.py  deterministic counts + 1 LLM call → synthesis.json/.md
validate.py          evidence/triangulation/coverage → validation.json + sample.csv
score_validation.py  read filled sample.csv → write accuracy_rate into validation.json
export_excel.py      → blinkit_review_analysis.xlsx (3 tabs)
export_report.py     → blinkit_findings_report.md (full report; sidebar download)
pipeline.py          admin re-run orchestration · process-global state · metadata
app.py               Streamlit dashboard (6 tabs) · reads data/
run_all.sh           one-command pipeline (merge→tag→synth→validate→excel)
```
