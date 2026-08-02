# Artifact 8 — Sampling & bias limitations (pre-empting the obvious challenge)

Grounded in the real source mix for this run (`last_run_metadata.json`):
Reddit 913 · Play Store 500 · App Store 479 · YouTube 411 (total 2,303).

## What the four sources over- and under-represent

| Source | Over-represents | Under-represents |
|---|---|---|
| **Reddit (913, 40% of corpus)** | Metro, English-literate, younger, opinionated users; deal-hunters and price-comparers (r/IndianStreetBets is finance-minded); people with a grievance or a hot take | Non-urban users, older users, anyone who doesn't use Reddit (most customers) |
| **Play Store (500)** | Motivated reviewers — disproportionately the very angry (the "most-recent" sort skewed heavily negative when scraped); Android users | Satisfied silent users; iOS users |
| **App Store (479)** | iOS users (higher-income skew in India); reviewers at the extremes | Android-majority India; the indifferent middle |
| **YouTube (411)** | People who watch quick-commerce/haul/comparison videos and comment — already engaged with the *topic* of shopping apps | Everyone who consumes but doesn't comment; non-topic viewers |

**Cross-cutting skews (all four):** smartphone-owning, digitally engaged, willing to
post publicly, and writing in English or transliterated Hindi. This is a **vocal-
minority, metro, digitally-fluent** sample — not a representative cross-section of
Blinkit's monthly active customers.

## Why 84.6% no_signal is expected, not alarming

- Public reviews and comments are overwhelmingly about **delivery, service, refunds,
  app bugs, and price** — not reflections on *category choice*. Almost nobody writes
  "I never try new categories on Blinkit." So the honest expectation is that the
  large majority of items carry **no exploration signal** — and 84.6% (1,930/2,282)
  is exactly that.
- It is reported **on purpose** as a coverage metric so the signal isn't overstated.
  The value of the pipeline is precisely that it **finds the 15.3% (352 items) that
  do carry a directional signal** in a large, noisy corpus, and quantifies them by
  theme and source — rather than cherry-picking a few quotes.
- A *low* no_signal rate would actually be the red flag — it would suggest the
  relevance filter was too loose and letting generic complaints masquerade as
  category insight.

## Which segments are inferred, not self-reported

**All of them.** `user_segment_signals` (e.g. `new_parent`, `pet_owner`,
`price_sensitive`) are the **LLM's inference from the text** — e.g. "new_parent"
because the person mentions diapers. There is:
- no account/demographic data, no age/gender/location beyond the source subreddit,
- no purchase history, no basket data, no confirmation the person is who the text implies.

So segment counts are **directional hypotheses about who is saying what**, not a
census. Treat "top locked-in segment = grocery_only_regular" as *"the text most
often reads like a grocery-only regular,"* not a measured population share.

## What the pipeline structurally cannot see

- **Actual behaviour.** It sees *stated* behaviour and *intent*, never real
  purchases. "wants_to_explore_but_blocked" is a stated wish, not a tracked drop-off.
- **The silent majority.** Everyone who churned, or shops narrowly, without ever
  posting. By definition invisible here.
- **Blinkit's own data.** In-app search logs, category impression/CTR, funnel
  telemetry, assortment/price ground truth — none of it. The barriers are what users
  *say*, not what instrumentation would show.
- **Causality.** It can say `hard_to_discover_in_app` co-occurs with non-exploration;
  it cannot prove discovery friction *causes* it.
- **Recency/representativeness of volume.** Reddit is 40% of the corpus purely
  because it was the easiest to scrape at volume — not because Reddit reflects 40% of
  customers. Source mix is a scraping artefact, not a weighting.

## The one-line defense for the deck

> "This is a **hypothesis-generation** instrument on a vocal, metro, digitally-
> engaged public sample. It surfaces and quantifies candidate barriers with evidence
> strength; it is explicitly **not** a representative measurement of the customer
> base. That's why the next steps are a representative **survey** (to size the
> barriers) and **interviews** (to test causality) — the barriers here are the
> screener input, not the answer."
