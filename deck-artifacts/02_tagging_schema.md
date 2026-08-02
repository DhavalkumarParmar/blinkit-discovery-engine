# Artifact 2 — Tagging schema & controlled vocabularies (verbatim)

All lists copied exactly from `vocab.py`. The system prompt is copied exactly
from `pass1_tag.py` (`SYSTEM`).

## Controlled vocabularies (from `vocab.py`)

**Barrier themes** (15) — `BARRIER_THEMES`, i.e. `THEMES` minus drivers minus `other`:
```
habit_lock_repetitive_buying
unaware_category_exists
dont_trust_quality_for_new_category
price_uncertainty_new_category
too_expensive_vs_alternatives
no_reason_to_explore
hard_to_discover_in_app
search_only_finds_known_items
poor_recommendations
irrelevant_recommendations
overwhelmed_too_many_options
prefer_specialist_store_for_category
assortment_gap_missing_products
fast_checkout_no_time_to_browse
only_use_for_emergencies
```

**Driver themes** (3) — `DRIVER_THEMES`:
```
positive_discovery_experience
cross_sell_worked
promo_drove_trial
```

Plus the catch-all `other`. (Full `THEMES` list = 15 barriers + 3 drivers + `other` = 19.)

**User segments** (13) — `USER_SEGMENTS`:
```
grocery_only_regular          snack_beverage_buyer
household_essentials_buyer    multi_category_explorer
new_parent                    pet_owner
beauty_personal_care_user     bulk_monthly_stockup
daily_topup_buyer             price_sensitive
convenience_first             first_time_user
gifting_occasion_buyer
```

**Categories** (13) — `CATEGORIES`:
```
grocery  snacks  dairy  pet  baby  personal_care  beauty
electronics  home  pharma  stationery  gifting  other
```

**Exploration signals** (4) — `EXPLORATION_SIGNALS` (the core field of the whole tool):
```
explored_new_category
wants_to_explore_but_blocked
stuck_in_routine
no_signal
```

**Sentiment** (4): `positive · negative · mixed · neutral`
**Confidence** (3): `high · medium · low`

> Note in the source: `too_expensive_vs_alternatives` (theme) and
> `gifting_occasion_buyer` (segment) are documented as two user-approved additions
> to the original brief's draft vocabulary.

## The full per-item output schema (from `pass1_tag.py`)

Each item returns exactly these fields (enums validated against the vocab above):
`is_relevant` (bool), `sentiment`, `themes[]`, `user_segment_signals[]`,
`job_to_be_done` (≤300 chars), `frustration_root_cause` (≤300 chars),
`mentions_category[]`, `exploration_signal`, `direct_quote` (≤25 words),
`confidence`.

## The system prompt used for tagging (verbatim, `pass1_tag.SYSTEM`)

```
You are a product-research analyst studying why Blinkit (India quick-commerce)
users stay locked into the SAME product categories and rarely explore NEW ones
(pet, baby, personal care, beauty, electronics, home, pharma, etc.). You tag each
user feedback item for category-EXPLORATION signal, not generic app complaints.
Mark is_relevant=false when an item is a pure delivery/app/refund complaint with
NO bearing on what categories users buy or why. exploration_signal is the most
important field. Use ONLY the allowed enum values. job_to_be_done and
frustration_root_cause: one short sentence each, in the user's voice. direct_quote:
a verbatim snippet from the text, max 25 words. confidence reflects how clearly the
text supports your tags (low if terse/ambiguous). Echo back each item's exact id.
```

The schema itself (JSON Schema with lowercase types and enum lists) is also
embedded into every request, appended to the system message by the LLM client, so
the same schema drives both Groq and Gemini.

## Why the vocabulary is closed, not free-form

1. **Counts must be aggregatable.** All frequencies and %s are computed in Python
   by exact string match against these lists (`compute_aggregates`). Free-form tags
   don't group — "hard to find in app", "discovery is bad", "couldn't locate it"
   would each be a count of 1. A closed set makes `hard_to_discover_in_app = 166`
   a real, defensible number.
2. **Enforced, not hoped-for.** `_coerce()` drops any value not in the vocab and
   substitutes a safe default (`sentiment→neutral`, `exploration_signal→no_signal`,
   `confidence→low`, empty `themes→["other"]`). So a model that invents a tag can
   never pollute the aggregates — the tag is discarded. (See Artifact 3/6.)
3. **Cross-provider / cross-model consistency.** Five different models tagged this
   corpus (Artifact 4). A closed vocab is the only way their outputs are directly
   comparable and mergeable.
4. **Bias toward the research question.** The theme list is deliberately about
   *barriers to and drivers of exploration*, not generic app quality. This forces
   the analysis onto the strategic question and is why generic complaints land in
   `other` / `is_relevant=false` rather than inventing new "delivery" themes.

**Trade-off (state honestly):** a closed vocab cannot surface a barrier nobody
anticipated — a genuinely novel theme collapses into `other` (which itself is 4
items among relevant here). Mitigation in the data: `other` is tracked, and Pass 2
hypotheses can still describe patterns the fixed themes miss.
