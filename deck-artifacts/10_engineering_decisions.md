# Artifact 10 — Engineering decisions & trade-offs

What was chosen, rejected, cut, and what's next. All grounded in the actual code.

## Chosen (and why)

| Decision | Why | Trade-off accepted |
|---|---|---|
| **Direct public APIs/feeds, no scraping libraries** (App Store RSS, Play `batchexecute` RPC, Arctic Shift for Reddit, YouTube Data API) | Scraping libs silently break against changed markup; APIs are stable and testable | More per-source code; each endpoint reverse-engineered once |
| **Flat JSONL files, no database** | Zero infra; every stage's output is inspectable and diff-able; deployable app just reads committed files | Not built for concurrent writes or millions of rows |
| **Closed controlled vocab + deterministic counting; LLM only for 2 stages** | Numbers can't be hallucinated; tags are aggregatable and cross-model comparable | Can't surface a truly novel, unanticipated barrier (→ `other`) |
| **Multi-model Groq rotation → Gemini fallback** | Tags the full 2,282-item corpus on **free tiers** by using each model's separate daily bucket | Mixed-model corpus with no per-model quality control (Artifact 7) |
| **Resumable, cached, shuffle-before-limit tagging** | Survives daily caps / crashes; a partial run samples across all sources, not just the first file | State lives in the append-only `tagged.jsonl` |
| **Live `/models` verification at startup** | A deprecated model ID fails loudly, never silently | One extra startup call |
| **Streamlit (Community Cloud)** for the UI | Free, deploys in minutes, runs the live/admin pipeline tabs (persistent process) | Less design control than a bespoke frontend |
| **matplotlib + reportlab for the PDF** | Pure-Python; runs on Streamlit Cloud | Charts are re-drawn in matplotlib, not reused from Plotly |

## Rejected

| Rejected | In favour of | Reason |
|---|---|---|
| `google-play-scraper` and similar libraries | Direct `batchexecute` RPC | Popular scraping libs are frequently broken/unmaintained against current markup |
| LinkedIn, Twitter/X, TikTok as sources | Skipped | Auth walls / anti-scraping; out of scope |
| Trustpilot & MouthShut | Dropped after a live probe | Trustpilot 403s; MouthShut reviews are JS-rendered — not scrapable browserlessly (`source_probe.json`) |
| Next.js on Vercel for a "nicer" dashboard | Streamlit | Vercel is serverless — it **cannot** run the hours-long pipeline or the admin re-run; would have forced dropping those tabs |
| `kaleido` (Plotly→PNG) for the PDF | matplotlib | kaleido needs headless Chrome, unreliable on Streamlit Cloud (verified it fails there) |
| Gemini 2.0-flash (first choice) | Gemini 3.6-flash | 2.0-flash free tier is retired (`limit: 0`); verified live |

## Cut for time / known incomplete

- **Verbatim-quote verification** — quotes aren't substring-checked against source.
- **Cross-model agreement / second-opinion tagging** — each item tagged once.
- **Language detection / handling** — Hinglish works by luck of the LLM, unmeasured.
- **Token / cost / runtime logging** — not instrumented (Artifact 4).
- **Full corpus** — 2,282 of 2,303 tagged; 21 items (1 failed batch + skips) never
  back-filled before this snapshot.
- **Forum sources** — dropped rather than solved with a headless browser (which
  would break the free, deploy-safe constraint).

## What I'd build next, with more budget

1. **Close the validation gaps (highest value, cheapest):** substring-verify quotes;
   re-tag a ~100-item gold set with each model + humans to get per-model accuracy;
   add a second-opinion pass on the 838 low-confidence items.
2. **Instrument cost/tokens/runtime** so free-tier headroom and any paid spend are
   measured, not asserted.
3. **Feed the survey loop the brief requires:** export the top barriers as survey
   items and interview screeners; ingest survey results to *size* each barrier on a
   representative sample (fixing the vocal-minority bias in Artifact 8).
4. **Weight or stratify the sample** instead of taking source volume as-is (Reddit is
   40% only because it scraped easily).
5. **Broaden sources** with a compliant headless-browser worker (run offline, not on
   Streamlit Cloud) to add complaint forums and regional-language content.
6. **Language pipeline:** detect + optionally translate regional text, and penalise
   confidence on low-resource languages.
