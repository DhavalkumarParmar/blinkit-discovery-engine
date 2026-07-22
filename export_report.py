"""Full findings report → data/blinkit_findings_report.md

Combines EVERYTHING (synthesis + validation + run metadata + dropped-source probe)
into one detailed, self-contained markdown report for the next project steps
(survey design + user interviews). No summarization, no truncation — every barrier,
theme, segment, quote, hypothesis, and evidence count is included.

`build_report(...)` is shared by this CLI and the Streamlit download button so the
downloaded file always matches the committed data.

Usage:  python export_report.py
Output: data/blinkit_findings_report.md
"""

import json
import os

from common import DATA_DIR, get_logger

log = get_logger("report")

SYNTH_PATH = os.path.join(DATA_DIR, "synthesis.json")
VALIDATION_PATH = os.path.join(DATA_DIR, "validation.json")
META_PATH = os.path.join(DATA_DIR, "last_run_metadata.json")
PROBE_PATH = os.path.join(DATA_DIR, "source_probe.json")
REPORT_PATH = os.path.join(DATA_DIR, "blinkit_findings_report.md")


def _table(headers: list[str], rows: list[list]) -> str:
    if not rows:
        return "_(none)_\n"
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |")
    return "\n".join(out) + "\n"


def build_report(synth: dict, validation: dict, meta: dict, probe: dict | None = None) -> str:
    synth = synth or {}
    validation = validation or {}
    meta = meta or {}
    agg = synth.get("aggregates", {})
    counts = agg.get("counts", {})
    L: list[str] = []

    def h(level, text):
        L.append(f"\n{'#' * level} {text}\n")

    # ── Title ──
    L.append("# Blinkit Category-Exploration — Full Findings Report")
    L.append(f"\n_Generated {synth.get('generated_at', '')[:16]}_")
    L.append(f"\n> **Framing:** {synth.get('framing', 'Hypotheses with evidence strength — not conclusions.')}")
    L.append("\n> These findings are **inputs to a survey and user interviews**, not final "
             "conclusions. Confidence and evidence counts show how far each item can currently "
             "be trusted.\n")
    L.append("\n**Contents:** run metadata · coverage · executive summary · exploration-signal "
             "funnel · barriers · drivers · sentiment · categories · signal by source/segment · "
             "segments · jobs-to-be-done · unmet needs · category opportunities · recommended "
             "experiments · surprising insights · quotes · hypotheses · validation · dropped sources · vocab appendix\n")

    # ── 1. Run metadata ──
    h(2, "1 · Run metadata")
    per_src = meta.get("per_source", {})
    L.append(_table(["Source", "Items (merged)"], [[k, v] for k, v in sorted(per_src.items())]))
    L.append(f"\n- **Total merged:** {meta.get('total_merged', counts.get('total_tagged', '—'))}")
    L.append(f"- **Total AI-tagged:** {meta.get('total_tagged', counts.get('total_tagged', '—'))}")
    if meta.get("tagged_by_model"):
        L.append("\n**Tagging load by model (free-tier rotation):**\n")
        L.append(_table(["Model", "Items tagged"],
                        [[k, v] for k, v in sorted(meta["tagged_by_model"].items(),
                                                   key=lambda x: -x[1])]))
    if synth.get("llm_stats"):
        L.append("\n**LLM request stats (last synthesis):** "
                 + ", ".join(f"{k}={v}" for k, v in synth["llm_stats"].items()
                             if not isinstance(v, dict)) + "\n")

    # ── 2. Coverage ──
    h(2, "2 · Coverage & signal-to-noise")
    cov = validation.get("coverage", {})
    L.append(_table(["Metric", "Value"], [
        ["Total tagged", cov.get("total_tagged", counts.get("total_tagged", "—"))],
        ["Category-relevant", f"{cov.get('relevant', counts.get('relevant', '—'))} "
                              f"({cov.get('relevant_pct', counts.get('relevant_pct', '—'))}%)"],
        ["Filtered as noise", cov.get("irrelevant_filtered", counts.get("irrelevant_filtered", "—"))],
        ["no_signal rate", f"{cov.get('no_signal_pct', '—')}%"],
        ["low_confidence rate", f"{cov.get('low_confidence_pct', '—')}%"],
        ["Ambiguity rate (no_signal or low_conf)", f"{cov.get('ambiguity_rate_pct', '—')}%"],
    ]))
    if cov.get("confidence_breakdown"):
        L.append("\n**Confidence breakdown:** "
                 + ", ".join(f"{k}: {v}" for k, v in cov["confidence_breakdown"].items()) + "\n")

    # ── 3. Executive summary ──
    if synth.get("executive_summary"):
        h(2, "3 · Executive summary")
        for e in synth["executive_summary"]:
            L.append(f"- {e}")

    # ── 4. Exploration-signal funnel ──
    h(2, "4 · Exploration-signal funnel")
    if synth.get("funnel"):
        L.append(_table(["Stage", "Count"], [[f["stage"], f["count"]] for f in synth["funnel"]]))
    L.append("\n**Distribution:**\n")
    L.append(_table(["Signal", "Count", "% of all tagged"],
                    [[d["signal"], d["count"], f'{d.get("pct_of_all", "—")}%']
                     for d in agg.get("exploration_signal_distribution", [])]))

    # ── 5. Barriers (ALL) ──
    h(2, "5 · Barriers to category exploration (all)")
    L.append(_table(["Barrier theme", "Items", "% of relevant"],
                    [[b["theme"], b["count"], f'{b["pct_of_relevant"]}%'] for b in agg.get("barriers", [])]))

    # ── 6. Drivers ──
    h(2, "6 · Drivers of exploration (what's working)")
    L.append(_table(["Driver theme", "Items", "% of relevant"],
                    [[d["theme"], d["count"], f'{d["pct_of_relevant"]}%'] for d in agg.get("drivers", [])]))

    # ── 7. Sentiment ──
    h(2, "7 · Sentiment distribution (relevant)")
    L.append(_table(["Sentiment", "Count"],
                    [[d["sentiment"], d["count"]] for d in agg.get("sentiment_distribution", [])]))

    # ── 8. Categories mentioned ──
    h(2, "8 · Categories users mention (all)")
    L.append(_table(["Category", "Mentions"],
                    [[c["category"], c["count"]] for c in agg.get("categories_mentioned", [])]))

    # ── 9. Signal by source ──
    h(2, "9 · Exploration signal by source")
    sbs = agg.get("signal_by_source", [])
    if sbs:
        keys = [k for k in sbs[0].keys() if k != "source"]
        L.append(_table(["Source"] + keys, [[r["source"]] + [r.get(k, 0) for k in keys] for r in sbs]))

    # ── 10. Signal by segment ──
    h(2, "10 · Exploration signal by segment")
    L.append(_table(["Segment", "Stuck/blocked", "Explored", "Total"],
                    [[r["segment"], r["stuck"], r["explored"], r["total"]]
                     for r in agg.get("signal_by_segment", [])]))

    # ── 11-13. Segments ──
    h(2, "11 · Segments most locked into repetitive buying")
    for seg in synth.get("locked_in_segments", []):
        L.append(f"- **{seg.get('segment')}** — {seg.get('traits', '')}")
    h(2, "12 · Segments most likely to explore")
    for seg in synth.get("explorer_segments", []):
        L.append(f"- **{seg.get('segment')}** — {seg.get('traits', '')}")
    h(2, "13 · All segments by frequency (relevant items)")
    L.append(_table(["Segment", "Count"],
                    [[s["segment"], s["count"]] for s in agg.get("segments_overall", [])]))

    # ── 14. JTBD ──
    h(2, "14 · Jobs-to-be-done (ranked)")
    L.append(_table(["Job-to-be-done", "Approx. count"],
                    [[j.get("job"), j.get("approx_count")] for j in synth.get("top_jobs_to_be_done", [])]))

    # ── 15. Unmet needs ──
    h(2, "15 · Unmet needs")
    for u in synth.get("unmet_needs", []):
        L.append(f"- {u}")

    # ── 16. Category opportunities ──
    h(2, "16 · Category-specific growth opportunities")
    for co in synth.get("category_opportunities", []):
        L.append(f"- **{co.get('category', '').title()}**  \n"
                 f"  - Barrier: {co.get('barrier', '')}  \n"
                 f"  - Opportunity: {co.get('opportunity', '')}")

    # ── 17. Recommended experiments ──
    h(2, "17 · Recommended experiments (to validate)")
    for ex in synth.get("recommended_experiments", []):
        L.append(f"- **{ex.get('lever', '')}** (targets: {ex.get('targets_barrier', '')})  \n"
                 f"  - Hypothesis to test: {ex.get('hypothesis', '')}")

    # ── 18. Surprising insights ──
    if synth.get("surprising_insights"):
        h(2, "18 · Surprising / counter-intuitive findings")
        for si in synth["surprising_insights"]:
            L.append(f"- {si}")

    # ── 19. Quotes (ALL) ──
    h(2, "19 · Most powerful quotes (with attribution)")
    for q in synth.get("powerful_quotes", []):
        L.append(f"> \"{q.get('quote', '')}\"  \n"
                 f"> — **{q.get('source', '')}** · {q.get('attribution', '')}\n")

    # ── 20. Hypotheses (FULL) ──
    h(2, "20 · Hypotheses (full detail with evidence)")
    for i, hyp in enumerate(synth.get("hypotheses", []), 1):
        tri = "✓ triangulated" if hyp.get("source_triangulated") else "⚠ single-source"
        L.append(f"\n### H{i}. {hyp.get('hypothesis', '')}")
        L.append(f"- **Confidence:** {hyp.get('confidence', '—')}")
        L.append(f"- **Evidence:** {hyp.get('evidence_items', 0)} items across "
                 f"{len(hyp.get('evidence_sources', []))} sources "
                 f"({', '.join(hyp.get('evidence_sources', []))}) — {tri}")
        if hyp.get("supporting_themes"):
            L.append(f"- **Supporting themes:** {', '.join(hyp['supporting_themes'])}")
        if hyp.get("supporting_signals"):
            L.append(f"- **Supporting signals:** {', '.join(hyp['supporting_signals'])}")
        L.append(f"- **Rationale:** {hyp.get('rationale', '')}")

    # ── 21. Validation detail ──
    h(2, "21 · Validation — insight quality")
    L.append(f"_{validation.get('purpose', '')}_\n")
    L.append("**Per-theme evidence (distinct items × sources):**\n")
    L.append(_table(["Theme", "Kind", "Strength", "Items", "Sources", "Triangulated"],
                    [[t["theme"], t["kind"], t["strength"], t["evidence_items"], t["n_sources"],
                      "✓" if t["triangulated"] else "⚠"]
                     for t in validation.get("per_theme_evidence", []) if t["evidence_items"] > 0]))
    if validation.get("per_hypothesis_validation"):
        L.append("\n**Per-hypothesis validation:**\n")
        L.append(_table(["Hypothesis", "Confidence", "Items", "Sources", "Triangulated"],
                        [[hv["hypothesis"][:80], hv["confidence"], hv["evidence_items"],
                          hv["n_sources"], "✓" if hv["source_triangulated"] else "⚠"]
                         for hv in validation["per_hypothesis_validation"]]))
    tri = validation.get("triangulation", {})
    if tri.get("single_source_themes_flagged_low_confidence"):
        L.append("\n**Single-source themes (flagged lower-confidence):** "
                 + ", ".join(tri["single_source_themes_flagged_low_confidence"]) + "\n")
    mc = validation.get("manual_check", {})
    acc = mc.get("accuracy_rate")
    L.append(f"\n**Manual accuracy check:** sample of {mc.get('sample_size', '—')} items — "
             + (f"**{acc}** agreement" if acc else "not yet filled in") + ".\n")
    if mc.get("accuracy_breakdown"):
        b = mc["accuracy_breakdown"]
        L.append(_table(["Check", "Result"], [
            ["AGREE column", f"{b.get('agree')} agree / {b.get('disagree')} disagree ({b.get('agree_rate_pct')}%)"],
            ["is_relevant agreement", f"{b.get('is_relevant_agreement_pct')}% ({b.get('is_relevant_checked')} checked)"],
            ["exploration_signal agreement", f"{b.get('exploration_signal_agreement_pct')}% ({b.get('exploration_signal_checked')} checked)"],
        ]))

    # ── 22. Dropped sources ──
    if probe:
        h(2, "22 · Dropped / attempted sources")
        L.append(f"_Decision: {probe.get('decision', '')}_\n")
        L.append(_table(["Forum", "HTTP", "Verdict"],
                        [[t.get("forum"), t.get("http_status"), t.get("verdict")]
                         for t in probe.get("targets", [])]))

    # ── Appendix: vocab ──
    h(2, "Appendix · Controlled vocabularies")
    try:
        from vocab import (BARRIER_THEMES, CATEGORIES, DRIVER_THEMES,
                           EXPLORATION_SIGNALS, USER_SEGMENTS)
        L.append(f"- **Barrier themes:** {', '.join(BARRIER_THEMES)}")
        L.append(f"- **Driver themes:** {', '.join(sorted(DRIVER_THEMES))}")
        L.append(f"- **User segments:** {', '.join(USER_SEGMENTS)}")
        L.append(f"- **Categories:** {', '.join(CATEGORIES)}")
        L.append(f"- **Exploration signals:** {', '.join(EXPLORATION_SIGNALS)}")
    except Exception:  # noqa: BLE001
        pass

    L.append("\n---\n_End of report. Generated by the Blinkit Category-Exploration Discovery Engine._")
    return "\n".join(L)


def main():
    def _load(p):
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        return {}
    report = build_report(_load(SYNTH_PATH), _load(VALIDATION_PATH), _load(META_PATH),
                          _load(PROBE_PATH) or None)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    log.info("Wrote %s (%d chars, %d lines)", REPORT_PATH, len(report), report.count("\n") + 1)


if __name__ == "__main__":
    main()
