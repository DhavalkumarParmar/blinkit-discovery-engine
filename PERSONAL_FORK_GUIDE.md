# PERSONAL_FORK_GUIDE.md

**Purpose:** hand this repo to a new Claude Code session and have it help you turn
this PM research tool into a **personal-use review analysis tool** for a completely
different subject.

Paste the prompt in §10 to start. Everything below is verified against the actual
code (file paths and line numbers are real as of this commit).

---

## 1. What you are inheriting

A working, end-to-end **review/feedback analysis pipeline**:

```
4 sources → scrape → merge+dedup → LLM per-item tagging → coerce to fixed vocab
          → deterministic aggregation → 1 LLM synthesis call → validation → reports + dashboard
```

It currently answers a Growth-PM question about Blinkit (why users don't explore new
product categories). **That subject is a thin configuration layer on top of a generic
engine.** The engine does not care what it is analysing.

Proven at real scale on the current run: 2,377 scraped → 2,303 merged → 2,282 tagged
→ 632 relevant, entirely on free LLM tiers, ~1h50m.

**What you get for free:** multi-source scrapers that survive rate limits, a
provider-agnostic LLM client with 4-model rotation + fallback, resumable batch
tagging, deduplication, deterministic counting (numbers can never be hallucinated),
a validation layer, and Markdown/PDF/Excel exports plus a Streamlit dashboard.

## 2. The three-layer mental model (most important section)

| Layer | Files | Touch it? |
|---|---|---|
| **ENGINE** — domain-agnostic plumbing | `common.py`, `llm_client.py`, `merge.py`, `pipeline.py` | ❌ **Don't.** Works for any subject. |
| **SCHEMA** — the *field names* of a tag | the keys in `pass1_tag.ITEM_SCHEMA`: `is_relevant`, `sentiment`, `themes`, `user_segment_signals`, `job_to_be_done`, `frustration_root_cause`, `mentions_category`, `exploration_signal`, `direct_quote`, `confidence` | ⚠️ **Carefully.** Field *names* are referenced across `validate.py`, `pass2_synthesize.py`, `export_*.py`, `app.py`. Renaming one means touching ~5 files. |
| **CONFIG** — the *values* + prompts + targets | `vocab.py`, the two `SYSTEM` prompts, scraper target IDs/queries | ✅ **Change freely.** This is where "Blinkit category exploration" lives. |

**The cheap path:** keep the field *names*, change only their *allowed values* and the
prompts. You get a completely different analysis tool while touching 4 files.
`themes` can mean anything; `exploration_signal` is just "the one categorical
verdict field" — reuse it as your primary axis and only rename it later if the name
bothers you.

## 3. Every change point, with exact locations

### 3a. Scraper targets — what you collect
| File | Line | Current | Change to |
|---|---|---|---|
| `scrapers/app_store.py` | 28 | `APP_ID = "960335206"` | your iOS app's ID (find via `https://itunes.apple.com/search?term=NAME&country=in&entity=software`) |
| `scrapers/play_store.py` | 32 | `PACKAGE = "com.grofers.customerapp"` | your Android package name (from the Play Store URL `?id=`) |
| `scrapers/reddit.py` | 38 | `SUBREDDITS = [...]` | subreddits relevant to your subject |
| `scrapers/reddit.py` | 45 | `TOPIC_HINTS = [...]` | keywords that flag relevance |
| `scrapers/youtube.py` | 39 | `QUERIES = [...]` | your video search queries |
| `scrapers/youtube.py` | 53 | `KEEP_KEYWORDS = [...]` | item-level filter for comments |
| `app.py` | 504 | `EXPLORE_KW = [...]` | keyword filter in the live-demo tab |

Also in `scrapers/reddit.py` and `scrapers/youtube.py`, the literal string
`"blinkit"` is used as the search term / item-level filter — grep and replace it.

**If your subject isn't an app** (a book, a restaurant, a hobby, a course), delete
`app_store.py` and `play_store.py` and keep Reddit + YouTube, or write one new
scraper following the same shape: fetch → `normalize()` → write
`data/raw_<source>.jsonl` with the 8 fields `id, source, date, rating, text, author,
url, scraped_at`. `merge.py` auto-discovers any `data/raw_*.jsonl`, so a new source
needs **zero** changes elsewhere.

### 3b. `vocab.py` — the controlled vocabularies (the heart)
Replace the list contents, keep the variable names:
- `THEMES` (19) — what you're categorising. Currently exploration barriers/drivers.
- `DRIVER_THEMES` (3) — the positive subset; `BARRIER_THEMES` derives automatically.
- `USER_SEGMENTS` (13) — who is speaking.
- `CATEGORIES` (13) — sub-topics mentioned.
- `EXPLORATION_SIGNALS` (4) — **the primary verdict axis.**
- `SENTIMENTS`, `CONFIDENCE` — leave alone; universally useful.

### 3c. The two prompts
- `pass1_tag.py:66` `SYSTEM` — per-item tagging instructions. Rewrite entirely for
  your subject and say plainly what makes an item `is_relevant=false`.
- `pass2_synthesize.py:183` `SYSTEM` — the synthesis persona/output. Currently
  "Growth PM at Blinkit… hypotheses with evidence strength". For personal use this
  is usually the biggest rewrite (see §5).

### 3d. Output names & branding
`export_report.py`, `export_pdf.py`, `export_excel.py` write
`data/blinkit_*` — rename the path constants (and the matching one in `app.py`, which
reads the xlsx for the download button). Dashboard copy lives in `app.py` (hero text,
titles — 12 "Blinkit" references).

## 4. The minimum viable fork (~1 hour)

1. Rewrite `vocab.py` lists for your subject.
2. Rewrite both `SYSTEM` prompts.
3. Point the scrapers at your targets; delete the ones that don't apply.
4. Rename the `blinkit_*` output files.
5. `rm -rf data/*.jsonl data/*.json data/*.csv data/*.xlsx data/*.pdf data/*.md` to
   clear the previous run's results, then run the pipeline.

Do **not** rename schema fields on the first pass. Get one clean run first, then
rename if you still want to.

## 5. Personal use ≠ PM use: what to strip

This tool carries research-rigor scaffolding that exists because it fed a survey and
stakeholder deck. For personal use, most of it is overhead:

| Feature | Keep? | Why |
|---|---|---|
| Multi-source scraping, dedup, tagging, aggregation | ✅ keep | This is the actual tool |
| Sentiment + themes + your verdict axis | ✅ keep | Core output |
| Excel / Markdown export | ✅ keep | Useful anywhere |
| Streamlit dashboard | ✅ keep | Nice for browsing your own results |
| `user_segment_signals` | 🔸 probably drop | "Who is speaking" matters for PM segmentation; for personal use you usually only care *what* was said. Set to `[]` and ignore. |
| Hypotheses + evidence counts + confidence tiers (`pass2`) | 🔸 simplify | Built to survive stakeholder challenge. For yourself, "top 5 themes + best quotes + a summary" is enough. |
| `validate.py`, `score_validation.py`, the 30-item human check | 🔸 optional | Insight-quality proof for a graded deliverable. Skip unless you want to trust the numbers hard. |
| `deck-artifacts/`, `CONTEXT.md`, `ARCHITECTURE.md` | ❌ delete | PM-project artifacts. Irrelevant to you. |
| "hypotheses not conclusions" framing everywhere | ❌ drop | Say what the reviews say. |

**A good personal-use Pass 2** is a much smaller prompt: top N themes with counts, the
strongest quotes, a plain-English summary, and a recommendation. Delete
`recommended_experiments`, `category_opportunities`, `surprising_insights` from
`SYNTH_SCHEMA` if you don't want them.

## 6. Worked example — "should I buy this thing?"

Say you want to analyse reviews of a product/app before buying:

- `THEMES` → `build_quality`, `battery_life`, `value_for_money`,
  `customer_support`, `reliability`, `ease_of_use`, `missing_features`,
  `shipping_issues`, `works_as_advertised`, `other`
- `DRIVER_THEMES` → `{works_as_advertised, ease_of_use}` (the positives)
- `EXPLORATION_SIGNALS` → rename conceptually to a **verdict**:
  `would_recommend`, `mixed`, `would_not_recommend`, `no_signal`
- `CATEGORIES` → the product aspects you care about
- `USER_SEGMENTS` → `[]` or usage types (`power_user`, `casual`, `first_time`)
- Pass-1 `SYSTEM` → "You analyse product reviews for someone deciding whether to buy
  X. Mark `is_relevant=false` for reviews about shipping/seller issues that say
  nothing about the product itself…"
- Pass-2 `SYSTEM` → "Summarise for a buyer: top complaints with counts, top praises,
  deal-breakers, and a verdict."

Same engine. Same commands. Completely different tool.

Other viable subjects: a game/film/book's reception, a course or bootcamp, a city or
travel destination, a piece of software you maintain, a competitor's app.

## 7. Setup and running

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add GROQ_API_KEY, GEMINI_API_KEY, YOUTUBE_API_KEY

python -m scrapers.reddit      # run scrapers individually first, verify output
python merge.py
python pass1_tag.py --limit 100 --yes    # start small!
python pass2_synthesize.py
python export_report.py
streamlit run app.py
```
`run_all.sh` runs the whole chain. **Always test with `--limit 20` before a full run.**

Key flags: `pass1_tag.py --limit N` (caps items; shuffles first so you sample across
sources), `--yes` (skip the quota confirmation), `pass2_synthesize.py --rebuild`
(recompute deterministic parts with **no LLM call**).

## 8. Cost and quota reality (verified live)

- **Groq free tier caps tokens-per-day, per model.** `llama-3.3-70b-versatile` is
  ~100k tokens/day. The client rotates through 4 models (each has its own bucket)
  before falling back to Gemini. Rotation is why 2,282 items were tagged free in a day.
- **Gemini `2.0-flash` free tier is retired** (`limit: 0`). Use `gemini-3.6-flash`.
  It's a *thinking* model — reasoning tokens eat the output budget, which is why the
  client sets `max_output_tokens = max(max_tokens*2, 8192)`.
- **Tagging is resumable**: `pass1_tag.py` skips ids already in `data/tagged.jsonl`.
  Hit a daily cap → re-run tomorrow, it continues.
- Rough scale: ~2,300 items ≈ 290 batches of 8. Budget a day on free tiers.
- **Nothing logs tokens or cost.** Add it if you care.

## 9. Known gaps you are inheriting

1. **Quotes are not verified.** The model returns a `direct_quote` but nothing checks
   it actually appears in the source text. Cheapest high-value fix: substring-check
   inside `pass1_tag._coerce`.
2. **Each item is tagged once, by whichever model was active.** No cross-model
   agreement, so there's no measured quality difference between the 70B and 8B models.
3. **No language handling.** Transliterated/non-English text works only because the
   LLM copes. No detection, no confidence penalty.
4. **`confidence` is the model's self-report**, not an independent signal.
5. **Sampling bias is real**: public reviews over-represent people with strong
   opinions. Fine for personal use — just don't read percentages as population truth.
6. A high `no_signal` rate is normal (84.6% here). Most public text isn't about your
   specific question. That's the filter working, not a bug.

## 10. Prompt to paste into the new session

> I'm forking this repo into a personal-use review analysis tool. Read
> `PERSONAL_FORK_GUIDE.md` first, then `vocab.py`, `pass1_tag.py`, and
> `pass2_synthesize.py`.
>
> **My subject:** `<what you're analysing>`
> **The question I want answered:** `<e.g. "should I buy this / what do people
> actually complain about / how is it received">`
> **Sources available:** `<app store / play store / reddit / youtube / other>`
>
> Following §4 (minimum viable fork) and §5 (strip the PM scaffolding):
> 1. Propose new `vocab.py` lists for my subject and explain each choice.
> 2. Rewrite both `SYSTEM` prompts.
> 3. Update the scraper targets, deleting scrapers that don't apply.
> 4. Rename the `blinkit_*` outputs and clear the old `data/` results.
> 5. Run end-to-end on ~20 items and show me the tagged output before scaling.
>
> Don't rename schema field names on the first pass. Ask me before deleting the
> validation layer.
