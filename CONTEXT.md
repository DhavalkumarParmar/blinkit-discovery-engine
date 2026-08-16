# CONTEXT.md — primer for a fresh session

Read this first. It orients a new Claude Code session (or a new human) on what this
repo is, what it deliberately is **not**, what's genuinely broken or missing, and
what a v2 should improve. Every number here is from the committed data files.

---

## 1. What this is

An **AI-powered review/feedback analysis pipeline** built for a Growth PM use case at
Blinkit (India quick-commerce). It mines public user feedback from four sources and
produces **hypotheses about why users don't explore new product categories** — with
evidence counts, source triangulation, and confidence tiers.

**The strategic question it serves:** why do users stay locked into the same
categories (groceries, snacks) and rarely try new ones (pet, baby, beauty,
electronics, pharma)?

**Critical framing:** the output is **candidate barriers with evidence strength, not
conclusions.** It is a hypothesis-generation instrument whose output feeds a
downstream survey (to size barriers on a representative sample) and user interviews
(to test causality). Anything that presents it as measurement is a misuse.

## 2. Current live state (as committed, one full run)

| Stage | Count |
|---|---:|
| Raw scraped | 2,377 |
| Merged (after dedup) | 2,303 |
| AI-tagged | 2,282 |
| Relevant (`is_relevant=true`) | 632 (27.7%) |
| Filtered as noise | 1,650 |
| Carries exploration signal | 352 |
| Explored a new category | 98 |

Sources: Reddit 913 · Play Store 500 · App Store 479 · YouTube 411.
Coverage: 84.6% `no_signal` · 36.7% low-confidence · 84.8% ambiguity rate.
Manual spot-check: 100% agreement on a 30-item sample (small — a sanity check, not a
precision estimate).
Top barrier: `hard_to_discover_in_app` (166 items, 26.3% of relevant).
Top driver: `positive_discovery_experience` (102, 16.1%).

Tagged by 5 models via rotation: `llama-3.1-8b-instant` 1,043 · `openai/gpt-oss-120b`
406 · `llama-3.3-70b-versatile` 352 · `openai/gpt-oss-20b` 337 · `gemini-3.6-flash` 144.
Tagging run: 495 Groq requests, 253 retries, 3 model rotations, 0 Gemini fallbacks,
≈1h50m wall-clock. **Cost: $0 (free tiers) — but tokens/cost/runtime are NOT
instrumented; the runtime figure is derived from log timestamps.**

## 3. Architecture in one paragraph

Nine stages; the LLM touches only two of them.
`sources → scrapers → merge/dedup → [LLM] Pass-1 per-item tagging → coerce to
controlled vocab → aggregation → [LLM] Pass-2 synthesis → validation → reports/UI`.

**The core invariant:** every number that appears in any output is computed in Python
(`compute_aggregates`, `validate.py`). The LLM does per-item tagging and, in one
call, language-only work (clustering JTBDs, selecting quotes, wording hypotheses).
Each hypothesis the LLM writes must cite controlled-vocab themes, whose supporting
evidence is then **counted deterministically**. This is why evidence counts cannot be
hallucinated. Full diagram: `ARCHITECTURE.md` and `deck-artifacts/01_architecture.svg`.

## 4. Key design decisions (and what was rejected)

| Decision | Rejected alternative | Why |
|---|---|---|
| Direct public APIs/feeds | Scraping libraries (`google-play-scraper` etc.) | Libraries silently break against changed markup |
| Closed controlled vocabulary | Free-form tags | Free-form tags don't aggregate; closed vocab is enforced by `_coerce` and is comparable across models |
| Deterministic counting, LLM for language only | Asking the LLM for numbers | Numbers can't be hallucinated |
| Multi-model Groq rotation → Gemini fallback | Single model / paid tier | Each model has its own daily token bucket; tags the full corpus on free tiers |
| Flat JSONL, no database | Postgres/SQLite | Zero infra; every stage's output is inspectable and diffable |
| Streamlit on Community Cloud | Next.js on Vercel | Vercel is serverless — cannot run the hours-long pipeline or admin re-run |
| matplotlib + reportlab for PDF | `kaleido` (Plotly→PNG) | kaleido needs headless Chrome; unreliable on Streamlit Cloud (verified failing) |

## 5. Deliberately out of scope (don't "fix" these)

- **Trustpilot & MouthShut** — probed and dropped on evidence (Trustpilot 403s;
  MouthShut reviews are JS-rendered). Recorded in `data/source_probe.json`. Adding
  them requires a headless browser, which breaks the free/deploy-safe constraint.
- **LinkedIn / Twitter-X / TikTok** — auth walls and anti-scraping.
- **A database** — flat files are the design, not a shortcut.
- **Per-visitor pipeline runs** — the deployed app reads pre-computed committed files
  by design.

## 6. Known gaps — the real v2 backlog

These are honest, verified gaps, not speculation (see
`deck-artifacts/06_failure_modes.md` and `10_engineering_decisions.md`):

1. **No verbatim-quote verification.** The prompt asks for a verbatim snippet, but
   nothing checks the returned `direct_quote` actually appears in the source text. A
   paraphrase or fabrication would pass into a slide. *Cheapest high-value fix:
   substring-check in `_coerce`.*
2. **No cross-model agreement.** Rotation means each item was tagged **once** by
   whichever model was active — never the same item twice. So there is **no measured
   quality delta** between the 70B and 8B models, and no inter-model reliability
   number. Any claim that bigger models tag better here is unsupported.
3. **No language handling.** Transliterated Hindi/Hinglish is common in the corpus
   and is tagged only because the LLM happens to understand it. No detection, no
   translation, no confidence penalty. Quality on regional-language items is
   unmeasured.
4. **`confidence` is the LLM's self-report**, not an independent QA signal. The 838
   low-confidence items are never adjudicated or re-reviewed.
5. **No token/cost/runtime instrumentation.**
6. **Manual validation sample is only 30 items.**
7. **Source mix is a scraping artefact.** Reddit is 40% of the corpus because it
   scraped easily, not because it reflects 40% of customers. No weighting/stratification.
8. **21 items never tagged** (1 failed batch + id-mismatch skips); the tagger is
   resumable but wasn't re-run before the snapshot.

## 7. Sampling bias — state this before anyone challenges it

The corpus is a **vocal, metro, digitally-fluent minority**: people who post publicly,
in English or transliterated Hindi, on app stores / Reddit / YouTube. It
over-represents complainers and deal-hunters; it under-represents the silent
majority, non-urban and older users. All `user_segment_signals` (e.g. `new_parent`,
`pet_owner`) are **LLM-inferred from text, never self-reported** — there is no
demographic or purchase data.

**Why 84.6% `no_signal` is expected, not alarming:** public reviews are overwhelmingly
about delivery, refunds, price and app bugs — almost nobody spontaneously writes
about category choice. The pipeline's value is finding and quantifying the 15% that
*do* carry signal. A *low* no_signal rate would be the red flag (relevance filter too
loose). Full treatment: `deck-artifacts/08_sampling_bias.md`.

## 8. Reading order for a fresh session

| Order | File | Why |
|---|---|---|
| 1 | `CONTEXT.md` (this) | Orientation |
| 2 | `ARCHITECTURE.md` | System design + ASCII flow |
| 3 | `vocab.py` | The controlled vocabularies — the heart of the method |
| 4 | `llm_client.py` | Provider abstraction, rotation, fallback, retries |
| 5 | `pass1_tag.py` | Per-item tagging: prompt, schema, `_coerce` |
| 6 | `pass2_synthesize.py` | Deterministic aggregation + the single synthesis call |
| 7 | `validate.py` | Evidence, triangulation, coverage thresholds |
| 8 | `deck-artifacts/` | 10 artifacts incl. failure modes, decisions, real numbers |

Runnable entry points: `run_all.sh` (full pipeline), `merge.py`, `pass1_tag.py
--limit N`, `pass2_synthesize.py [--rebuild]`, `validate.py`, `score_validation.py`,
`export_report.py`, `export_pdf.py`, `export_excel.py`, `app.py` (Streamlit).
Secrets in `.env` (see `.env.example`); `.venv` is not committed.

---

## 9. Forward intent — why a new session is being opened

**Goal:** compare this tool against similar open-source review/feedback-analysis
tools on GitHub, then design an advanced v2 for future projects.

### Axes to compare rival tools on

Use these consistently so the comparison is structured, not anecdotal:

1. **Source coverage & acquisition** — how many sources; official APIs vs scraping;
   how they handle blocks, pagination, and rate limits; is acquisition resumable?
2. **Tagging method** — closed controlled vocabulary vs free-form/topic-modelling vs
   embeddings+clustering. Is the taxonomy enforced or merely requested?
3. **Determinism of numbers** — are counts computed in code, or produced by the LLM?
   (This repo's central claim; a good benchmark question for any rival.)
4. **Validation rigor** — evidence counting, triangulation, inter-annotator or
   cross-model agreement, human spot-checks, coverage/ambiguity reporting.
5. **Cost & model strategy** — single model vs rotation vs paid; is cost measured?
6. **Robustness** — retries, backoff, provider fallback, malformed-output handling,
   resumability.
7. **Output layer** — dashboard, exports, shareability, whether findings are framed
   as hypotheses vs asserted conclusions.
8. **Bias handling** — does the tool acknowledge sampling bias, or present a vocal
   minority as representative?
9. **Extensibility** — how hard to add a source, a taxonomy, another provider?

### What "advanced v2" should mean (informed by §6)

Priority order, cheapest-highest-value first:
1. Close the **validation gaps**: verbatim-quote verification; a gold-set re-tagged by
   every model *and* humans to produce per-model accuracy; second-opinion pass on
   low-confidence items.
2. **Instrument** tokens, cost, and runtime.
3. **Language pipeline**: detect/translate regional text; penalise confidence on
   low-resource languages.
4. **Close the research loop**: export barriers as survey items + interview
   screeners; ingest survey results to *size* each barrier representatively.
5. **Weight or stratify** the sample instead of accepting scrape-driven source mix.
6. **Generalise beyond Blinkit**: make the vocabulary, sources, and research question
   config-driven so the same engine serves any product/company.

### Setting up the comparison workspace

Clone this repo and the tools you're comparing as **siblings under one parent
folder**, then start the session from the **parent** so all repos are readable:

```bash
mkdir ~/review-tools-comparison && cd ~/review-tools-comparison
git clone https://github.com/DhavalkumarParmar/blinkit-discovery-engine
git clone <rival-tool-1>
git clone <rival-tool-2>
cd ~/review-tools-comparison && claude      # start from the PARENT
```

Claude Code reads the whole tree under its working directory, so starting from the
parent lets it read and compare every repo. For tools you only need to *survey*
(not run), the session can fetch the README/source from GitHub directly instead of
cloning.
