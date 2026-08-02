# Deck artifacts — index

Raw artifacts extracted from the Blinkit review-analysis codebase. Every number is
from the repo's committed data/output or the tagging log, or reconstructed by
re-running the code — none from memory. Where the code doesn't record something
(cost, tokens, runtime, cross-model quality), the artifact says so explicitly.

Diagrams are colourblind-safe (Okabe-Ito **blue = code, orange = LLM**; no
red/green carrying meaning), ≥14px text, no gradients, high-contrast for PDF.

| # | Artifact | File(s) | Candidate slide | Strength |
|---|----------|---------|-----------------|----------|
| 1 | Pipeline architecture | `01_architecture.md`, `01_architecture.svg` | **"How it works" 1-slider** | ★★★ strongest — brief explicitly requires it |
| 5 | Funnel (raw → explored) | `05_funnel.md`, `05_funnel.svg` | The product story in one visual | ★★★ strongest — funnel beats the table in the report |
| 3 | Insight-quality validation | `03_insight_validation.md` | "How we know the insights hold up" | ★★★ strong — separately graded; has exact thresholds + honest gaps |
| 4 | Real numbers | `04_real_numbers.md` | Appendix / "by the numbers" | ★★★ strong — the factual backbone every other slide cites |
| 8 | Sampling & bias limits | `08_sampling_bias.md` | "What this can and can't tell us" | ★★★ strong — pre-empts the obvious challenge; has the one-line defense |
| 2 | Tagging schema (verbatim) | `02_tagging_schema.md` | Methodology / appendix | ★★ solid — proves rigor; closed-vocab rationale |
| 6 | Failure modes & gaps | `06_failure_modes.md` | Risk/robustness appendix | ★★ solid — names the gaps honestly (quote-verification, language, cross-model) |
| 7 | Model rotation & cost | `07_model_rotation_cost.md` | "How we ran it for $0" | ★★ solid — good story; honest that no quality A/B was done |
| 9 | Worked example (Hinglish, judgement call) | `09_worked_example.md` | Methodology "show, don't tell" | ★★ solid — one vivid end-to-end trace; surfaces a real edge case |
| 10 | Engineering decisions | `10_engineering_decisions.md` | Appendix / "what's next" | ★★ solid — chosen/rejected/cut/next |

## Suggested top 5 for a tight deck
1. **#1 Architecture** — the required 1-slider.
2. **#5 Funnel** — the story: 2,303 → 98 explored, with the drops.
3. **#3 Validation** — insight quality is separately graded; lead with the exact
   thresholds and the 100%/30 manual check, and own the gaps.
4. **#8 Sampling/bias** — the pre-emptive defense (vocal-minority sample →
   hypotheses, not measurement).
5. **#4 Real numbers** — the backbone appendix everything else cites.

## Headline numbers (for quick reference, all from the repo)
- **2,377 raw scraped → 2,303 merged → 2,282 tagged → 632 relevant (27.7%) → 352
  carry signal → 98 explored a new category.** 1,650 filtered as noise.
- Sources: Reddit 913 · Play Store 500 · App Store 479 · YouTube 411 (Trustpilot &
  MouthShut probed and dropped).
- Tagged by 5 models (rotation): 8b 1,043 · gpt-oss-120b 406 · 70b 352 · gpt-oss-20b
  337 · gemini-3.6-flash 144. Tagging run: 495 Groq requests, 253 retries, 3
  rotations, 0 Gemini fallbacks, ≈1h50m.
- Coverage: 84.6% no_signal · 36.7% low-confidence · 84.8% ambiguity. Manual check
  100% (30/30). One single-source theme flagged (`promo_drove_trial`).
- Top barrier: `hard_to_discover_in_app` (166 items, 26.3% of relevant). Top driver:
  `positive_discovery_experience` (102, 16.1%).

## Honesty ledger (things the code does NOT do — repeated here so nothing slips)
- No cost / token / runtime logging (runtime only derivable from log timestamps).
- No verbatim-quote verification against source text.
- No cross-model agreement / second-opinion tagging (each item tagged once).
- No language detection/handling; per-item `confidence` is the LLM's self-report.
- Segments are LLM-inferred from text, never self-reported; sample is a vocal,
  metro, digitally-engaged minority, not representative.
