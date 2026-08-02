# Artifact 6 — Failure modes: what the pipeline handles, and the gaps

"Handled?" and "How the code handles it" are from the actual source. **Likelihood
and Impact are my estimates** (not measured) — labelled so you can challenge them.
Legend: ✅ handled · ◑ partial / delegated to LLM with no guardrail · ❌ known gap.

| Failure mode | Likelihood | Impact | How the code handles it | If it fires |
|---|---|---|---|---|
| **API rate limit (429, per-minute)** | High | Med | ✅ `llm_client._backoff_sleep`: exponential `min(2^attempt·2, 60)`s, honors `Retry-After` (cap 120s); `MAX_RETRIES=5` | Retries; 253 retries / 256 429s occurred this run and it still completed |
| **Daily token cap (429 "per day"/TPD)** | High (free tier) | Med | ✅ detected by substring `per day/tpd/rpd`; rotates to next Groq model immediately (no wait), then Gemini | Seamless model rotation; 3 rotations this run |
| **Model unavailable / deprecated ID** | Low | High | ✅ `verify_groq_model()` checks the **live `/models`** endpoint at startup; refuses any ID not active | Raises at startup with the list of live models; never silently uses a dead model |
| **Malformed LLM JSON** | Med | Med | ✅ `_extract_json` strips ``` fences, grabs outer `{...}`/`[...]`; unparseable → `LLMError` | Batch logged as failed and skipped; **resumable** (re-run tags the rest) — no crash |
| **Tag outside controlled vocab** | Med | High | ✅ `_coerce` drops invalid enum values, substitutes safe defaults, filters lists to vocab | Bad tag discarded; aggregates stay clean |
| **Hallucinated / mismatched item id in batch** | Low | Med | ✅ tagger matches results by `id` (`by_id.get`); unmatched dropped | That result is discarded; its item stays untagged and is retried next run |
| **Whole batch throws** | Low | Med | ✅ `except Exception` per batch → log + continue; append-per-batch cache | Only that batch's 8 items are skipped; run continues (1 failed batch this run) |
| **Payload too large (413)** | Low | Med | ✅ 413 → `ProviderExhausted` → Gemini (larger context) | Falls back to Gemini for that call (happened in synthesis) |
| **Gemini thinking-token truncation** | Med | Med | ✅ `out_budget = max(max_tokens·2, 8192)` reserves headroom | Enough budget for reasoning + JSON; avoids cut-off output |
| **Network timeout / connection drop** | Med | Low | ✅ `TIMEOUT_S=120`; retry on `Timeout`/`ConnectionError` with backoff | Retried up to 5×, then rotates/falls back |
| **Both providers exhausted** | Med (heavy day) | High | ✅ raises `LLMError("All providers failed")`; batch skipped; **resumable next day** | Partial tagging; you re-run tomorrow (buckets are rolling 24h) — this is by design |
| **Trustpilot bot-wall (403)** | Certain | Low | ✅ probed in `complaint_forums.py`; recorded in `source_probe.json`; source dropped | Source excluded; documented, not silently missing |
| **MouthShut JS-rendered reviews** | Certain | Low | ✅ probed; raw HTML has no review bodies → dropped | Source excluded; documented |
| **Scraper library silently broken** | — | — | ✅ avoided by design: no scraping libraries; direct public APIs/feeds only | N/A |
| **Pagination limit / stall** | Med | Low | ✅ App Store hard-caps at page 10 (=500); all scrapers dedup by id and **abort if a page returns only duplicates** | Stops cleanly at the real end; won't loop |
| **Reddit body-search timeout (422)** | High (big subs) | Low | ✅ known: comment body-search 422s on large subs → switched to per-post `link_id` comments; retry on 422/429/5xx | Comments fetched via post threads instead; documented in `reddit.py` |
| **YouTube quota exceeded** | Med | Med | ✅ `QuotaExceeded` caught; stops with partial data | Returns what it collected; ~1,100 of 10,000 units used, so headroom exists |
| **Duplicate content across pages/sources** | High | Low | ✅ dedup by `id` + normalized (lowercased, whitespace-collapsed) text in `merge.py` | 51 text-dupes removed this run |
| **Non-English / transliterated (Hinglish) text** | High (Indian sources) | Med | ◑ **No language detection/translation in code** — delegated entirely to the LLM | Usually tagged fine (worked example is Hinglish), but **no guardrail**; a mis-read is silent |
| **Sarcasm / ambiguity** | Med | Med | ◑ delegated to LLM; only signal is the self-reported `confidence=low` (36.7% of items) | Ambiguous items flagged low-confidence but **not corrected or reviewed** |
| **Hallucinated free-text (quote not verbatim / invented JTBD)** | Med | Med | ❌ **Gap:** `direct_quote`/`job_to_be_done`/`frustration_root_cause` are **not verified against source text**; only length-truncated | An invented or paraphrased "verbatim" quote could reach a slide unchecked |
| **Same item tagged differently by different models** | — | Med | ❌ **Gap:** rotation means each item is tagged once by one model; **no re-tag / cross-model agreement check** exists | No measure of model-to-model consistency (see Artifact 7) |

## The gaps, stated plainly (so you're not caught out)

1. **No verbatim-quote verification.** The prompt asks for a verbatim snippet, but
   nothing checks the returned `direct_quote` actually appears in the source text.
   A paraphrase or fabrication would pass. → Easy fix: substring-check quotes in
   `_coerce`.
2. **No language handling.** Transliterated Hindi/regional text is tagged only
   because the LLM happens to understand it; there's no detection, no translation,
   no confidence penalty for non-English. Quality on regional-language items is
   unmeasured.
3. **No cross-model agreement.** Five models tagged the corpus, but never the same
   item twice, so there is no inter-model reliability number. The 100%/30 manual
   check is the only independent accuracy signal, and 30 is small.
4. **`is_relevant` and all tags rest on a single model's judgement per item.** No
   second opinion, no adjudication of the 838 low-confidence items.
