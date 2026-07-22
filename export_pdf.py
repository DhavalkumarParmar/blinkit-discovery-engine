"""Findings PDF (WITH charts) → data/blinkit_findings_report.pdf

Keeps the visuals in the export: renders the key charts with matplotlib (no
system deps / no headless Chrome — works on Streamlit Cloud) and lays them out
in a reportlab PDF alongside the executive summary, opportunities, experiments,
quotes, and full hypotheses.

`build_pdf(...)` returns PDF bytes and is shared by this CLI and the dashboard's
sidebar download button.

Usage:  python export_pdf.py
Output: data/blinkit_findings_report.pdf
"""

import io
import json
import os

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_LEFT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import inch  # noqa: E402
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer,  # noqa: E402
                                Table, TableStyle)

from common import DATA_DIR, get_logger  # noqa: E402

log = get_logger("pdf")

SYNTH_PATH = os.path.join(DATA_DIR, "synthesis.json")
VALIDATION_PATH = os.path.join(DATA_DIR, "validation.json")
META_PATH = os.path.join(DATA_DIR, "last_run_metadata.json")
PDF_PATH = os.path.join(DATA_DIR, "blinkit_findings_report.pdf")

GREEN = "#0b6b3a"
RED = "#d73027"
BLUE = "#3a7bd5"
AMBER = "#f39c12"
SIGNAL_COLORS = {"explored_new_category": "#1a9850", "wants_to_explore_but_blocked": "#f39c12",
                 "stuck_in_routine": "#d73027", "no_signal": "#95a5a6"}
SENT_COLORS = {"positive": "#1a9850", "negative": "#d73027", "mixed": "#f39c12", "neutral": "#7f8c8d"}


# ── matplotlib chart → reportlab Image ──────────────────────────────

def _fig_to_img(fig, width_in=6.6):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    w, h = fig.get_size_inches()
    return Image(buf, width=width_in * inch, height=width_in * (h / w) * inch)


def _barh(labels, values, color, xlabel, fmt=None):
    fig, ax = plt.subplots(figsize=(9, max(2.2, 0.42 * len(labels))))
    y = range(len(labels))
    ax.barh(list(y), values, color=color)
    ax.set_yticks(list(y)); ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis(); ax.set_xlabel(xlabel, fontsize=9)
    for i, v in enumerate(values):
        ax.text(v, i, f" {fmt(v) if fmt else v}", va="center", fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return _fig_to_img(fig)


def _pie(labels, values, colorlist, title):
    fig, ax = plt.subplots(figsize=(5, 3.4))
    wedges, _texts, _auto = ax.pie(values, colors=colorlist, autopct="%1.1f%%",
                                   pctdistance=0.8, textprops={"fontsize": 8})
    ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=8, frameon=False)
    ax.set_title(title, fontsize=11, fontweight="bold")
    fig.tight_layout()
    return _fig_to_img(fig, width_in=5.4)


def _stacked(sources, series, colorlist, title):
    fig, ax = plt.subplots(figsize=(9, 3.2))
    import numpy as np
    bottom = np.zeros(len(sources))
    for (name, vals), col in zip(series.items(), colorlist):
        ax.bar(sources, vals, bottom=bottom, label=name, color=col)
        bottom += np.array(vals)
    ax.legend(fontsize=8, frameon=False)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return _fig_to_img(fig)


# ── PDF assembly ────────────────────────────────────────────────────

def build_pdf(synth: dict, validation: dict, meta: dict) -> bytes:
    synth, validation, meta = synth or {}, validation or {}, meta or {}
    agg = synth.get("aggregates", {})
    counts = agg.get("counts", {})
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                            leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                            title="Blinkit Category-Exploration Findings")
    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=ss["Title"], fontSize=20, textColor=colors.HexColor(GREEN))
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=13, textColor=colors.HexColor(GREEN),
                        spaceBefore=12)
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=9.5, leading=13, alignment=TA_LEFT)
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.grey)
    quote = ParagraphStyle("quote", parent=body, fontSize=9.5, leftIndent=10, textColor=colors.HexColor("#123"),
                           borderColor=colors.HexColor("#12a150"), italic=True)
    E = []

    def para(txt, style=body):
        E.append(Paragraph(txt, style))

    # Title + framing
    para("Blinkit Category-Exploration — Findings Report", H1)
    para(f"Generated {synth.get('generated_at','')[:16]} · "
         f"{counts.get('relevant','—')} relevant of {counts.get('total_tagged','—')} tagged "
         f"({counts.get('relevant_pct','—')}%)", small)
    para(f"<i>{synth.get('framing','Hypotheses with evidence strength — not conclusions.')}</i>", small)
    E.append(Spacer(1, 8))

    # KPI table (colored)
    dist = {d["signal"]: d["count"] for d in agg.get("exploration_signal_distribution", [])}
    kdata = [[f"{meta.get('total_merged', counts.get('total_tagged','—'))}\nReviews collected",
              f"{counts.get('total_tagged','—')}\nAI-tagged",
              f"{counts.get('relevant','—')} · {counts.get('relevant_pct','—')}%\nRelevant"],
             [f"{dist.get('stuck_in_routine',0)}\nStuck in routine",
              f"{dist.get('wants_to_explore_but_blocked',0)}\nWant→explore, blocked",
              f"{dist.get('explored_new_category',0)}\nExplored new category"]]
    kt = Table(kdata, colWidths=[2.2 * inch] * 3, rowHeights=[0.7 * inch] * 2)
    kt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(GREEN)),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#12a150")),
        ("BACKGROUND", (2, 0), (2, 0), colors.HexColor(BLUE)),
        ("BACKGROUND", (0, 1), (0, 1), colors.HexColor(RED)),
        ("BACKGROUND", (1, 1), (1, 1), colors.HexColor(AMBER)),
        ("BACKGROUND", (2, 1), (2, 1), colors.HexColor("#1a9850")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 11), ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    E.append(kt)

    # Executive summary
    if synth.get("executive_summary"):
        para("Executive summary", H2)
        for e in synth["executive_summary"]:
            para(f"▸ {e}")

    # Barriers chart
    barriers = agg.get("barriers", [])[:10]
    if barriers:
        para("Top barriers to category exploration", H2)
        E.append(_barh([b["theme"] for b in barriers][::-1],
                       [b["pct_of_relevant"] for b in barriers][::-1], RED, "% of relevant items",
                       fmt=lambda v: f"{v}%"))

    # Exploration-signal + sentiment pies
    sd = [d for d in agg.get("exploration_signal_distribution", [])]
    if sd:
        para("Exploration-signal mix &amp; sentiment", H2)
        E.append(_pie([d["signal"].replace("_", " ") for d in sd], [d["count"] for d in sd],
                      [SIGNAL_COLORS.get(d["signal"], "#999") for d in sd], "Exploration signal"))
    snt = agg.get("sentiment_distribution", [])
    if snt:
        E.append(_pie([d["sentiment"] for d in snt], [d["count"] for d in snt],
                      [SENT_COLORS.get(d["sentiment"], "#999") for d in snt], "Sentiment (relevant)"))

    # Category mentions
    cm = agg.get("categories_mentioned", [])[:10]
    if cm:
        para("Categories users mention", H2)
        E.append(_barh([c["category"] for c in cm][::-1], [c["count"] for c in cm][::-1],
                       BLUE, "mentions"))

    # Signal by source (stacked)
    sbs = agg.get("signal_by_source", [])
    if sbs:
        para("Where exploration signal shows up (by source)", H2)
        series = {s.replace("_", " "): [r.get(s, 0) for r in sbs]
                  for s in ["explored_new_category", "wants_to_explore_but_blocked", "stuck_in_routine"]}
        E.append(_stacked([r["source"] for r in sbs], series,
                          [SIGNAL_COLORS["explored_new_category"],
                           SIGNAL_COLORS["wants_to_explore_but_blocked"],
                           SIGNAL_COLORS["stuck_in_routine"]], ""))

    # Segments
    para("Segments — locked-in vs. explorers", H2)
    for seg in synth.get("locked_in_segments", []):
        para(f"<b>🔁 {seg.get('segment')}</b> — {seg.get('traits','')}")
    for seg in synth.get("explorer_segments", []):
        para(f"<b>🧭 {seg.get('segment')}</b> — {seg.get('traits','')}")

    # Category opportunities
    if synth.get("category_opportunities"):
        para("Category-specific growth opportunities", H2)
        for co in synth["category_opportunities"]:
            para(f"<b>{co.get('category','').title()}</b> — barrier: {co.get('barrier','')} "
                 f"→ opportunity: {co.get('opportunity','')}")

    # Recommended experiments
    if synth.get("recommended_experiments"):
        para("Recommended experiments (to validate)", H2)
        for ex in synth["recommended_experiments"]:
            para(f"<b>{ex.get('lever','')}</b> (targets {ex.get('targets_barrier','')}): "
                 f"{ex.get('hypothesis','')}")

    # JTBD + unmet needs
    if synth.get("top_jobs_to_be_done"):
        para("Top jobs-to-be-done", H2)
        for j in synth["top_jobs_to_be_done"]:
            para(f"🎯 {j.get('job')} (~{j.get('approx_count')})")
    if synth.get("unmet_needs"):
        para("Top unmet needs", H2)
        for u in synth["unmet_needs"]:
            para(f"🔎 {u}")

    # Surprising
    if synth.get("surprising_insights"):
        para("Surprising / counter-intuitive", H2)
        for si in synth["surprising_insights"]:
            para(f"💡 {si}")

    # Quotes
    if synth.get("powerful_quotes"):
        para("Most powerful quotes", H2)
        for q in synth["powerful_quotes"]:
            para(f'“<i>{q.get("quote","")}</i>” — {q.get("source","")} · {q.get("attribution","")}', quote)

    # Hypotheses (full)
    para("Hypotheses (with evidence strength)", H2)
    for i, h in enumerate(synth.get("hypotheses", []), 1):
        tri = "✓ triangulated" if h.get("source_triangulated") else "⚠ single-source"
        para(f"<b>H{i}. {h.get('hypothesis','')}</b>")
        para(f"Confidence: <b>{h.get('confidence','—')}</b> · {h.get('evidence_items',0)} items "
             f"across {len(h.get('evidence_sources',[]))} sources "
             f"({', '.join(h.get('evidence_sources',[]))}) · {tri}", small)
        para(f"<i>{h.get('rationale','')}</i>", small)
        E.append(Spacer(1, 4))

    # Validation
    cov = validation.get("coverage", {})
    if cov:
        para("Validation — insight quality", H2)
        para(f"Relevant {cov.get('relevant_pct','—')}% · no_signal {cov.get('no_signal_pct','—')}% "
             f"· low-confidence {cov.get('low_confidence_pct','—')}% · ambiguity "
             f"{cov.get('ambiguity_rate_pct','—')}%", body)
        tev = [t for t in validation.get("per_theme_evidence", []) if t["evidence_items"] > 0][:12]
        if tev:
            tbl = [["Theme", "Kind", "Strength", "Items", "Src", "Tri"]] + [
                [t["theme"], t["kind"], t["strength"], t["evidence_items"], t["n_sources"],
                 "✓" if t["triangulated"] else "⚠"] for t in tev]
            vt = Table(tbl, colWidths=[2.4*inch, 0.7*inch, 0.9*inch, 0.6*inch, 0.5*inch, 0.4*inch])
            vt.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6fb")]),
            ]))
            E.append(Spacer(1, 4)); E.append(vt)

    para("<i>End of report — generated by the Blinkit Category-Exploration Discovery Engine. "
         "Hypotheses with evidence strength, to be validated by survey + interviews.</i>", small)

    doc.build(E)
    return buf.getvalue()


def main():
    def _load(p):
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        return {}
    pdf = build_pdf(_load(SYNTH_PATH), _load(VALIDATION_PATH), _load(META_PATH))
    with open(PDF_PATH, "wb") as f:
        f.write(pdf)
    log.info("Wrote %s (%d KB)", PDF_PATH, len(pdf) // 1024)


if __name__ == "__main__":
    main()
