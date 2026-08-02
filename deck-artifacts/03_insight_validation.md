# Artifact 3 — How insight quality was validated

Everything here is implemented in `validate.py` and `pass2_synthesize.py`; exact
thresholds and file/line references given. Numbers are from this run
(`data/validation.json`).

## 1. Triangulation rule (what counts, and why)

- **Rule (exact):** an item/theme/hypothesis is `triangulated` **iff it appears in
  ≥ 2 distinct sources.** Code: `validate.theme_evidence` → `"triangulated": len(srcs) >= 2`;
  `pass2_synthesize._evidence_for` → `"triangulated": len(sources) >= 2`.
- **Distinct sources** = distinct values of the `source` field, drawn from the four
  in this run: `app_store, play_store, reddit, youtube`.
- **Why ≥2:** a pattern seen only on, say, Play Store could be an artefact of that
  platform's reviewer population or its "most-recent" sort bias. Requiring a second
  independent source guards against single-channel artefacts. It is a deliberately
  low bar (2, not 3) because there are only 4 sources; it is a *floor*, not a
  strength measure — strength comes from item volume (below).

## 2. Distinct-item and distinct-source counting

For each theme (`validate.theme_evidence`): `evidence_items = # relevant items whose
themes[] contains the theme`; `n_sources = # distinct sources among those items`.
For each hypothesis (`pass2._evidence_for`): the LLM tags the hypothesis with
supporting vocab themes/signals; Python then counts **distinct relevant items whose
`themes ∩ supporting_themes` is non-empty OR whose `exploration_signal ∈
supporting_signals`**, and the distinct sources among them. Counting is on relevant
items only (`is_relevant=true`). Both are pure `set`/`len` operations — no LLM.

## 3. Confidence / strength tiers (exact thresholds)

Two tiers exist; **both use the same cutoffs** (items ≥15 / ≥6, always with ≥2 sources):

**Theme strength** (`validate.py`):
```
strong    if evidence_items >= 15 and n_sources >= 2
moderate  if evidence_items >= 6  and n_sources >= 2
weak      otherwise
```
**Hypothesis confidence** (`pass2._derive_confidence`):
```
high   if evidence_items >= 15 and n_sources >= 2
medium if evidence_items >= 6  and n_sources >= 2
low    otherwise
```
Hypothesis confidence is **derived deterministically in Python from the evidence
count** — the LLM does not set it. (The LLM proposes the hypothesis text and its
supporting themes; the tier is computed.)

## 4. Single-source flagging

`validate.py` builds `single_source_themes_flagged_low_confidence =
[theme for theme in per_theme_evidence if evidence_items > 0 and not triangulated]`
— i.e. any theme with evidence that lives in **only one source**. This run flags
exactly one: **`promo_drove_trial`** (1 item, 1 source). It is surfaced in the
Validation tab and report as lower-confidence.

## 5. no_signal & low_confidence rates — what they mean (this run)

From `data/validation.json` `coverage` (denominator = 2,282 tagged):
- **no_signal_pct = 84.6%** (1,930 items). The model found no explore/stuck/blocked
  cue. Most public feedback is about delivery/price/app, not category choice — see
  Artifact 8. This is a **coverage/honesty metric**, reported deliberately so the
  signal isn't overstated.
- **low_confidence_pct = 36.7%** (838 items). The **model's own** self-reported
  confidence was `low` (terse/ambiguous text). Confidence breakdown:
  `high 1,293 · medium 151 · low 838`.
- **ambiguity_rate_pct = 84.8%** = share of items that are `no_signal` **OR**
  `low_confidence`. It is the honest "how much of the corpus is uncertain" number.

> Caveat to state on the slide: the per-item `confidence` field is the LLM's
> *self-assessment*, not an independent check. The independent check is the manual
> sample (below) and the deterministic evidence counts.

## 6. Manual human-check

`validate.write_sample_csv` exports a **fixed 30-item random sample**
(`random.Random(SAMPLE_SEED=7)`, reproducible) with the AI tags plus blank
`HUMAN_*` / `AGREE_(Y/N)` columns. `score_validation.py` reads the filled file
(CSV or Excel) and writes `accuracy_rate` into `validation.json`. **This run:
100.0% (30/30) agreement** on the `AGREE` column. (Sample size is small — 30 —
so treat as a sanity check, not a precision estimate.)

## 7. Dedup & noise filtering (exact)

- **Merge dedup** (`merge.py`): drop text `< MIN_LEN = 8` chars (23 dropped this
  run); drop duplicate `id` (0); drop duplicate normalized text — whitespace-
  collapsed, lowercased (51 dropped). Total 74 dropped → 2,303 merged.
- **Relevance filter** (LLM `is_relevant`): 1,650 items marked off-topic and
  excluded from all barrier/segment aggregates. The count of filtered items is
  retained and reported (signal-to-noise honesty).
- **Vocab coercion** (`_coerce`): out-of-vocab tags discarded (noise can't enter
  aggregates).

## What is claimed vs actually implemented — honest check

| Claimed in report / UI | Implemented in code? |
|---|---|
| Distinct-item & distinct-source evidence counts | ✅ `validate.theme_evidence`, `pass2._evidence_for` |
| ≥2-source triangulation flag | ✅ exact `len(sources) >= 2` |
| Confidence/strength tiers from evidence volume | ✅ `_derive_confidence`, `theme_evidence.strength` |
| Single-source themes flagged | ✅ computed + surfaced |
| Coverage / ambiguity / no_signal / low_conf rates | ✅ `coverage_metrics` |
| 30-item human sample + accuracy write-back | ✅ `write_sample_csv` + `score_validation.py` |
| **Per-item confidence is an independent QA signal** | ⚠️ **No** — it is the LLM's self-report; only the manual sample and evidence counts are independent |
| **Inter-annotator / multi-model agreement on the same items** | ❌ **Not implemented** — five models tagged *different* items (rotation), never the same item twice, so there is no cross-model agreement measurement (see Artifact 7) |
