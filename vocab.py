"""Controlled vocabularies — the single source of truth for every layer.

Biased around WHY users don't explore new categories (barriers/drivers), not
generic app complaints. Imported by pass1_tag, pass2_synthesize, validate, and
the Streamlit app so tags stay consistent everywhere.

Includes the two user-approved additions:
  - theme   `too_expensive_vs_alternatives`
  - segment `gifting_occasion_buyer`
"""

# Barriers to / drivers of category exploration.
THEMES = [
    "habit_lock_repetitive_buying",
    "unaware_category_exists",
    "dont_trust_quality_for_new_category",
    "price_uncertainty_new_category",
    "too_expensive_vs_alternatives",
    "no_reason_to_explore",
    "hard_to_discover_in_app",
    "search_only_finds_known_items",
    "poor_recommendations",
    "irrelevant_recommendations",
    "overwhelmed_too_many_options",
    "prefer_specialist_store_for_category",
    "assortment_gap_missing_products",
    "positive_discovery_experience",
    "cross_sell_worked",
    "promo_drove_trial",
    "fast_checkout_no_time_to_browse",
    "only_use_for_emergencies",
    "other",
]

USER_SEGMENTS = [
    "grocery_only_regular",
    "snack_beverage_buyer",
    "household_essentials_buyer",
    "multi_category_explorer",
    "new_parent",
    "pet_owner",
    "beauty_personal_care_user",
    "bulk_monthly_stockup",
    "daily_topup_buyer",
    "price_sensitive",
    "convenience_first",
    "first_time_user",
    "gifting_occasion_buyer",
]

CATEGORIES = [
    "grocery", "snacks", "dairy", "pet", "baby", "personal_care", "beauty",
    "electronics", "home", "pharma", "stationery", "gifting", "other",
]

EXPLORATION_SIGNALS = [
    "explored_new_category",
    "wants_to_explore_but_blocked",
    "stuck_in_routine",
    "no_signal",
]

SENTIMENTS = ["positive", "negative", "mixed", "neutral"]
CONFIDENCE = ["high", "medium", "low"]
