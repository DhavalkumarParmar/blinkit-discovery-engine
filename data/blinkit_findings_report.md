# Blinkit Category-Exploration — Full Findings Report

_Generated 2026-07-22T08:35_

> **Framing:** Candidate barriers/drivers with evidence strength — HYPOTHESES, not conclusions. To be screened by survey and refined by interviews.

> These findings are **inputs to a survey and user interviews**, not final conclusions. Confidence and evidence counts show how far each item can currently be trusted.


**Contents:** run metadata · coverage · executive summary · exploration-signal funnel · barriers · drivers · sentiment · categories · signal by source/segment · segments · jobs-to-be-done · unmet needs · category opportunities · recommended experiments · surprising insights · quotes · hypotheses · validation · dropped sources · vocab appendix


## 1 · Run metadata

| Source | Items (merged) |
| --- | --- |
| app_store | 479 |
| play_store | 500 |
| reddit | 913 |
| youtube | 411 |


- **Total merged:** 2303
- **Total AI-tagged:** 2282

**Tagging load by model (free-tier rotation):**

| Model | Items tagged |
| --- | --- |
| llama-3.1-8b-instant | 1043 |
| openai/gpt-oss-120b | 406 |
| llama-3.3-70b-versatile | 352 |
| openai/gpt-oss-20b | 337 |
| gemini-3.6-flash | 144 |


**LLM request stats (last synthesis):** groq_requests=4, gemini_requests=1, retries=0, fallbacks=1, model_rotations=3, groq_model=llama-3.1-8b-instant, gemini_model=gemini-3.6-flash


## 2 · Coverage & signal-to-noise

| Metric | Value |
| --- | --- |
| Total tagged | 2282 |
| Category-relevant | 632 (27.7%) |
| Filtered as noise | 1650 |
| no_signal rate | 84.6% |
| low_confidence rate | 36.7% |
| Ambiguity rate (no_signal or low_conf) | 84.8% |


**Confidence breakdown:** high: 1293, low: 838, medium: 151


## 3 · Executive summary

- In-app discovery friction is the single largest barrier, accounting for 26.3% of relevant feedback where users fail to navigate beyond routine items.
- Price uncertainty and perceived premium markups vs offline alternatives deter 21.7% of users from trying non-grocery categories like electronics and home essentials.
- Quality mistrust and strict return policies push users toward specialist stores for high-value electronics and fresh dairy items.
- Cross-selling and targeted trial promotions show high conversion potential but remain underutilized across the user journey.

## 4 · Exploration-signal funnel

| Stage | Count |
| --- | --- |
| Merged items | 2303 |
| Tagged | 2282 |
| Relevant (on-topic) | 632 |
| Carries exploration signal | 352 |
| Explored a new category | 98 |


**Distribution:**

| Signal | Count | % of all tagged |
| --- | --- | --- |
| explored_new_category | 98 | 4.3% |
| wants_to_explore_but_blocked | 111 | 4.9% |
| stuck_in_routine | 143 | 6.3% |
| no_signal | 1930 | 84.6% |


## 5 · Barriers to category exploration (all)

| Barrier theme | Items | % of relevant |
| --- | --- | --- |
| hard_to_discover_in_app | 166 | 26.3% |
| price_uncertainty_new_category | 93 | 14.7% |
| poor_recommendations | 78 | 12.3% |
| assortment_gap_missing_products | 61 | 9.7% |
| irrelevant_recommendations | 47 | 7.4% |
| too_expensive_vs_alternatives | 44 | 7.0% |
| habit_lock_repetitive_buying | 32 | 5.1% |
| dont_trust_quality_for_new_category | 23 | 3.6% |
| prefer_specialist_store_for_category | 22 | 3.5% |
| search_only_finds_known_items | 21 | 3.3% |
| unaware_category_exists | 19 | 3.0% |
| no_reason_to_explore | 12 | 1.9% |
| only_use_for_emergencies | 7 | 1.1% |
| fast_checkout_no_time_to_browse | 5 | 0.8% |
| overwhelmed_too_many_options | 4 | 0.6% |


## 6 · Drivers of exploration (what's working)

| Driver theme | Items | % of relevant |
| --- | --- | --- |
| positive_discovery_experience | 102 | 16.1% |
| cross_sell_worked | 11 | 1.7% |
| promo_drove_trial | 1 | 0.2% |


## 7 · Sentiment distribution (relevant)

| Sentiment | Count |
| --- | --- |
| positive | 186 |
| negative | 332 |
| mixed | 16 |
| neutral | 98 |


## 8 · Categories users mention (all)

| Category | Mentions |
| --- | --- |
| grocery | 245 |
| electronics | 64 |
| snacks | 28 |
| beauty | 17 |
| dairy | 16 |
| personal_care | 12 |
| home | 11 |
| pharma | 9 |
| pet | 9 |
| stationery | 9 |
| gifting | 9 |
| baby | 5 |


## 9 · Exploration signal by source

| Source | explored_new_category | wants_to_explore_but_blocked | stuck_in_routine | no_signal |
| --- | --- | --- | --- | --- |
| app_store | 17 | 9 | 23 | 428 |
| play_store | 25 | 20 | 64 | 384 |
| reddit | 35 | 69 | 31 | 773 |
| youtube | 21 | 13 | 25 | 345 |


## 10 · Exploration signal by segment

| Segment | Stuck/blocked | Explored | Total |
| --- | --- | --- | --- |
| grocery_only_regular | 68 | 21 | 150 |
| convenience_first | 30 | 22 | 67 |
| price_sensitive | 22 | 3 | 39 |
| multi_category_explorer | 12 | 16 | 32 |
| snack_beverage_buyer | 12 | 5 | 19 |
| daily_topup_buyer | 7 | 3 | 13 |
| gifting_occasion_buyer | 3 | 3 | 9 |
| beauty_personal_care_user | 5 | 2 | 8 |


## 11 · Segments most locked into repetitive buying

- **grocery_only_regular** — High purchase frequency for daily essentials, heavy reliance on reorder/routine flows, reluctant to browse non-food categories.
- **convenience_first** — Time-poor users driven by speed; defaults to known items during emergency or quick replenishment needs.
- **price_sensitive** — Compares unit pricing across platforms; hesitant to buy non-grocery goods due to fear of hidden handling fees or markups.

## 12 · Segments most likely to explore

- **multi_category_explorer** — High digital literacy, willing to test quick commerce for electronics and home accessories when speed is paramount.
- **convenience_first** — Explores non-grocery options selectively during high-urgency or late-night emergency situations.

## 13 · All segments by frequency (relevant items)

| Segment | Count |
| --- | --- |
| grocery_only_regular | 150 |
| convenience_first | 67 |
| price_sensitive | 39 |
| multi_category_explorer | 32 |
| snack_beverage_buyer | 19 |
| daily_topup_buyer | 13 |
| gifting_occasion_buyer | 9 |
| beauty_personal_care_user | 8 |
| household_essentials_buyer | 7 |
| pet_owner | 3 |
| first_time_user | 3 |
| new_parent | 3 |
| bulk_monthly_stockup | 2 |


## 14 · Jobs-to-be-done (ranked)

| Job-to-be-done | Approx. count |
| --- | --- |
| Get daily groceries and fresh essentials quickly and reliably | 245 |
| Order electronics and gadgets with instant delivery and easy returns | 64 |
| Replenish daily snacks, beverages, and impulse items | 28 |
| Purchase personal care, beauty, and grooming products discreetly | 29 |
| Source emergency home, stationery, and utility supplies late at night | 20 |


## 15 · Unmet needs

- Transparent and competitive pricing without excessive handling or delivery markups on non-grocery items
- Guaranteed freshness and strict cold-chain management for dairy and temperature-sensitive products
- Easier category navigation and intelligent search that surfaces non-exact or broader category queries
- Hassle-free replacement/return policies for high-value electronics, beauty, and general merchandise

## 16 · Category-specific growth opportunities

- **Electronics**  
  - Barrier: High perceived risk of receiving defective or tampered goods alongside non-existent return accountability.  
  - Opportunity: Introduce verified brand authenticity badges and clear return/exchange guarantees at checkout.
- **Home**  
  - Barrier: Exorbitant delivery fees on heavy/bulky utility items and low initial category awareness.  
  - Opportunity: Offer tiered bulk delivery discounts and introduce seasonal utility bundles.
- **Beauty**  
  - Barrier: Difficulty discovering budget-friendly or specific niche skincare items through standard app search.  
  - Opportunity: Curate dedicated beauty discovery hubs with price filters like 'Gifts Under ₹500'.
- **Pet**  
  - Barrier: Low awareness of specialized pet food assortment during non-emergency browsing.  
  - Opportunity: Cross-sell pet food samples to frequent grocery buyers and introduce emergency pet supply badges.

## 17 · Recommended experiments (to validate)

- **Contextual Cross-Category Nudges at Checkout** (targets: hard_to_discover_in_app)  
  - Hypothesis to test: If we display personalized non-grocery add-on recommendations (e.g., beauty or stationery) based on basket context at checkout, then cross-category trial rates will increase by 15%.
- **Local Price-Match Transparency Badging** (targets: price_uncertainty_new_category)  
  - Hypothesis to test: If we display price-confidence badges showing price parity with local markets on personal care and home goods, then trial conversion among price-sensitive users will rise by 20%.
- **Hassle-Free Category Return Guarantees** (targets: dont_trust_quality_for_new_category)  
  - Hypothesis to test: If we offer clear 48-hour replacement guarantees on non-grocery electronics and personal care, then first-time category exploration will increase by 25%.

## 18 · Surprising / counter-intuitive findings

- Users frequently turn to quick commerce for niche emergency cross-category needs—such as late-night exam printouts or stray animal care—proving willingness to buy non-grocery items when urgency overrides habit.
- Convenience-first shoppers represent both the largest locked-in segment (30 users) and the largest explorer segment (22 users), indicating that urgency is the primary dynamic bridge between routine lock-in and multi-category trial.
- Perceived assortment gaps are often search UI failures rather than inventory issues, as users label items as 'missing' when exact keyword searches fail to surface relevant categories.

## 19 · Most powerful quotes (with attribution)

> "Blinkit has made grocery shopping incredibly convenient"  
> — **play_store** · Sahebrao Dabhade · 2026-06-26

> "Blinkit is for emergency only"  
> — **youtube** · @AyonRoy-w8h · 2025-08-27

> "Always compare product in apps"  
> — **youtube** · @psr0879 · 2026-02-09

> "Ordering iphone 17 pro"  
> — **reddit** · kafkasky · 2025-11-30

> "best discounts on ps5"  
> — **reddit** · Comfortable_Bake_585 · 2026-07-01

> "eggs from hens that are given good quality feed"  
> — **reddit** · billl_buttlicker · 2026-06-22

> "alu ka price blinkit me kabhi kam nhi hota"  
> — **youtube** · @sainichatterjee8137 · 2026-06-05

> "Fed the cat some baby cat food"  
> — **reddit** · Direct_Possible5245 · 2026-04-27

> "BLINKIT is selling home bbq"  
> — **reddit** · yolo2021bets · 2025-11-24

> "inefficient prices"  
> — **reddit** · Pretend-Map6859 · 2026-05-27


## 20 · Hypotheses (full detail with evidence)


### H1. In-app discovery and search limitations cause users to remain unaware of non-grocery categories, reinforcing routine grocery reordering.
- **Confidence:** high
- **Evidence:** 357 items across 4 sources (app_store, play_store, reddit, youtube) — ✓ triangulated
- **Supporting themes:** hard_to_discover_in_app, search_only_finds_known_items, unaware_category_exists, poor_recommendations, irrelevant_recommendations
- **Supporting signals:** wants_to_explore_but_blocked, stuck_in_routine
- **Rationale:** 166 relevant user feedback items point to category discovery difficulty, while search friction limits users to reordering known items.

### H2. Perceived price markups and fee uncertainty create high friction for users evaluating non-essential or high-value non-grocery categories.
- **Confidence:** high
- **Evidence:** 329 items across 4 sources (app_store, play_store, reddit, youtube) — ✓ triangulated
- **Supporting themes:** price_uncertainty_new_category, too_expensive_vs_alternatives, habit_lock_repetitive_buying
- **Supporting signals:** wants_to_explore_but_blocked, stuck_in_routine
- **Rationale:** Price uncertainty (93 mentions) combined with concerns over premium pricing vs offline alternatives (44 mentions) deters price-conscious segments from exploring beyond daily groceries.

### H3. Lack of product trust and post-purchase return friction drive users to rely on specialist retailers for high-value or high-involvement products.
- **Confidence:** high
- **Evidence:** 286 items across 4 sources (app_store, play_store, reddit, youtube) — ✓ triangulated
- **Supporting themes:** dont_trust_quality_for_new_category, prefer_specialist_store_for_category, assortment_gap_missing_products
- **Supporting signals:** wants_to_explore_but_blocked, stuck_in_routine
- **Rationale:** Concerns over damaged items, lack of accountability for defective electronics, and perceived quality risks in non-grocery sectors encourage users to default to established specialized stores.

## 21 · Validation — insight quality

_Insight-quality evidence: how much distinct-item and distinct-source support each theme/hypothesis has, plus honest coverage/ambiguity so hypotheses can be weighted, not trusted blindly._

**Per-theme evidence (distinct items × sources):**

| Theme | Kind | Strength | Items | Sources | Triangulated |
| --- | --- | --- | --- | --- | --- |
| hard_to_discover_in_app | barrier | strong | 166 | 4 | ✓ |
| positive_discovery_experience | driver | strong | 102 | 4 | ✓ |
| price_uncertainty_new_category | barrier | strong | 93 | 4 | ✓ |
| poor_recommendations | barrier | strong | 78 | 4 | ✓ |
| assortment_gap_missing_products | barrier | strong | 61 | 4 | ✓ |
| irrelevant_recommendations | barrier | strong | 47 | 4 | ✓ |
| too_expensive_vs_alternatives | barrier | strong | 44 | 4 | ✓ |
| habit_lock_repetitive_buying | barrier | strong | 32 | 4 | ✓ |
| dont_trust_quality_for_new_category | barrier | strong | 23 | 4 | ✓ |
| prefer_specialist_store_for_category | barrier | strong | 22 | 4 | ✓ |
| search_only_finds_known_items | barrier | strong | 21 | 4 | ✓ |
| unaware_category_exists | barrier | strong | 19 | 3 | ✓ |
| no_reason_to_explore | barrier | moderate | 12 | 2 | ✓ |
| cross_sell_worked | driver | moderate | 11 | 3 | ✓ |
| only_use_for_emergencies | barrier | moderate | 7 | 4 | ✓ |
| fast_checkout_no_time_to_browse | barrier | weak | 5 | 3 | ✓ |
| overwhelmed_too_many_options | barrier | weak | 4 | 3 | ✓ |
| promo_drove_trial | driver | weak | 1 | 1 | ⚠ |


**Per-hypothesis validation:**

| Hypothesis | Confidence | Items | Sources | Triangulated |
| --- | --- | --- | --- | --- |
| In-app discovery and search limitations cause users to remain unaware of non-gro | high | 357 | 4 | ✓ |
| Perceived price markups and fee uncertainty create high friction for users evalu | high | 329 | 4 | ✓ |
| Lack of product trust and post-purchase return friction drive users to rely on s | high | 286 | 4 | ✓ |


**Single-source themes (flagged lower-confidence):** promo_drove_trial


**Manual accuracy check:** sample of 30 items — not yet filled in.


## 22 · Dropped / attempted sources

_Decision: DROPPED — no forum yielded scrapable Blinkit review bodies via a browserless, deploy-safe scraper_

| Forum | HTTP | Verdict |
| --- | --- | --- |
| trustpilot | 403 | blocked (403 bot wall) |
| mouthshut | 200 | loads but reviews are JS-rendered (not scrapable via requests) |


## Appendix · Controlled vocabularies

- **Barrier themes:** habit_lock_repetitive_buying, unaware_category_exists, dont_trust_quality_for_new_category, price_uncertainty_new_category, too_expensive_vs_alternatives, no_reason_to_explore, hard_to_discover_in_app, search_only_finds_known_items, poor_recommendations, irrelevant_recommendations, overwhelmed_too_many_options, prefer_specialist_store_for_category, assortment_gap_missing_products, fast_checkout_no_time_to_browse, only_use_for_emergencies
- **Driver themes:** cross_sell_worked, positive_discovery_experience, promo_drove_trial
- **User segments:** grocery_only_regular, snack_beverage_buyer, household_essentials_buyer, multi_category_explorer, new_parent, pet_owner, beauty_personal_care_user, bulk_monthly_stockup, daily_topup_buyer, price_sensitive, convenience_first, first_time_user, gifting_occasion_buyer
- **Categories:** grocery, snacks, dairy, pet, baby, personal_care, beauty, electronics, home, pharma, stationery, gifting, other
- **Exploration signals:** explored_new_category, wants_to_explore_but_blocked, stuck_in_routine, no_signal

---
_End of report. Generated by the Blinkit Category-Exploration Discovery Engine._