"""Blinkit Category-Exploration Discovery Engine — Streamlit dashboard.

Reads PRE-COMPUTED result files (data/*.json[l]); it does NOT run the full
pipeline per visitor. Five tabs:
  1. Insights (default)  2. Validation  3. Live pipeline (tiny live demo)
  4. Try it live         5. Admin re-run (password-gated)

Deploy: Streamlit Community Cloud. Set GROQ_API_KEY / GEMINI_API_KEY /
ADMIN_PASSWORD in the app's Secrets (see README).
"""

import json
import os
import random
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Blinkit Category-Exploration Engine",
                   page_icon="🛒", layout="wide", initial_sidebar_state="expanded")

# Bridge Streamlit Cloud secrets → os.environ so llm_client (os.getenv) works.
for _k in ("GROQ_API_KEY", "GEMINI_API_KEY", "YOUTUBE_API_KEY", "ADMIN_PASSWORD",
           "LLM_PROVIDER", "GROQ_MODEL", "GEMINI_MODEL"):
    try:
        if _k in st.secrets and not os.getenv(_k):
            os.environ[_k] = str(st.secrets[_k])
    except Exception:
        pass

from common import DATA_DIR, LOG_PATH, read_jsonl  # noqa: E402

SYNTH_PATH = os.path.join(DATA_DIR, "synthesis.json")
VALIDATION_PATH = os.path.join(DATA_DIR, "validation.json")
TAGGED_PATH = os.path.join(DATA_DIR, "tagged.jsonl")
META_PATH = os.path.join(DATA_DIR, "last_run_metadata.json")

# ── Colors ──────────────────────────────────────────────────────────
SENTIMENT_COLOR = {"positive": "#1a9850", "negative": "#d73027",
                   "mixed": "#f39c12", "neutral": "#7f8c8d"}
SIGNAL_COLOR = {"explored_new_category": "#1a9850",
                "wants_to_explore_but_blocked": "#f39c12",
                "stuck_in_routine": "#d73027", "no_signal": "#95a5a6"}
SIGNAL_LABEL = {"explored_new_category": "✅ Explored new category",
                "wants_to_explore_but_blocked": "🚧 Wants to explore — blocked",
                "stuck_in_routine": "🔁 Stuck in routine", "no_signal": "· no signal"}
CONF_COLOR = {"high": "#1a9850", "medium": "#f39c12", "low": "#d73027"}

CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1250px;}
.hero {background: linear-gradient(100deg,#0b6b3a,#12a150); color:#fff;
  padding:22px 26px; border-radius:14px; margin-bottom:6px;}
.hero h1 {margin:0; font-size:1.7rem;}
.hero p {margin:6px 0 0; opacity:.92; font-size:.95rem;}
.pill {display:inline-block; padding:3px 10px; margin:2px 4px 2px 0; border-radius:999px;
  font-size:.72rem; font-weight:600; background:#eef2f7; color:#274; border:1px solid #dce3ec;}
.badge {display:inline-block; padding:4px 12px; border-radius:999px; color:#fff;
  font-size:.75rem; font-weight:700;}
.card {background:#fff; border:1px solid #e6e9ef; border-radius:12px; padding:16px 18px;
  margin-bottom:12px; box-shadow:0 1px 3px rgba(20,40,80,.05);}
.qcard {border-left:4px solid #12a150; background:#f8fbf9; padding:12px 16px;
  border-radius:8px; margin-bottom:10px;}
.qcard .q {font-size:1.02rem; color:#123; font-style:italic;}
.qcard .a {font-size:.78rem; color:#678; margin-top:6px;}
.seg-card {background:#fff;border:1px solid #e6e9ef;border-radius:12px;padding:14px 16px;height:100%;}
.seg-card h4 {margin:0 0 6px; color:#0b6b3a;}
.hyp {background:#fff;border:1px solid #e6e9ef;border-left:5px solid #12a150;
  border-radius:10px;padding:14px 18px;margin-bottom:12px;}
.hyp .meta {font-size:.8rem;color:#556;margin-top:6px;}
.jtbd {background:#f3f6fb;border-radius:8px;padding:8px 14px;margin-bottom:6px;font-size:.92rem;}
small.muted{color:#889;}
/* KPI cards */
.kpi {border-radius:14px; padding:16px 18px; color:#fff; height:100%;
  box-shadow:0 2px 8px rgba(20,40,80,.10);}
.kpi .v {font-size:2.0rem; font-weight:800; line-height:1.05;}
.kpi .l {font-size:.80rem; font-weight:600; opacity:.95; margin-top:4px;}
.kpi .s {font-size:.72rem; opacity:.85; margin-top:2px;}
.opp {background:#fff;border:1px solid #e6e9ef;border-top:4px solid #12a150;border-radius:12px;
  padding:14px 16px;height:100%;}
.opp h4{margin:0 0 4px;color:#0b6b3a;text-transform:capitalize;}
.opp .b{font-size:.8rem;color:#b03030;}
.exp {background:#fffdf5;border:1px solid #f0e4c0;border-left:4px solid #e0a800;border-radius:10px;
  padding:12px 15px;margin-bottom:10px;}
.exp .lv{font-weight:700;color:#7a5c00;}
.surprise{background:#f4f0fb;border-left:4px solid #7c4dff;border-radius:10px;padding:10px 15px;margin-bottom:8px;}
.exec{background:linear-gradient(180deg,#f6fbf8,#eef7f1);border:1px solid #d5e8dc;
  border-radius:10px;padding:11px 16px;margin-bottom:8px;font-size:1.0rem;color:#0d3a24;}
.exec b{color:#0b6b3a;}
/* vertical left-side nav */
section[data-testid="stSidebar"] {background:#0b2e1e; min-width:250px;}
section[data-testid="stSidebar"] * {color:#eaf5ee;}
section[data-testid="stSidebar"] .stRadio label {font-size:1.02rem; padding:8px 6px;}
.sidenav-title{font-size:1.15rem;font-weight:800;color:#fff;padding:6px 4px 2px;}
.sidenav-sub{font-size:.78rem;color:#9fd3b4;padding:0 4px 12px;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ── Loaders (small files; reloaded each run so admin re-run reflects live) ──
def load_json(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def badge(text, color):
    return f'<span class="badge" style="background:{color}">{text}</span>'


def pills(items, kind="theme"):
    return "".join(f'<span class="pill">{i}</span>' for i in items) or '<small class="muted">—</small>'


def kpi(col, value, label, sub="", color="#12a150"):
    col.markdown(f'<div class="kpi" style="background:{color}"><div class="v">{value}</div>'
                 f'<div class="l">{label}</div><div class="s">{sub}</div></div>',
                 unsafe_allow_html=True)


def donut(labels, values, colors, height=270):
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.58,
                           marker_colors=colors, sort=False,
                           textinfo="label+percent", textposition="outside"))
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10),
                      showlegend=False)
    return fig


def render_tags(tags: dict):
    """Shared renderer for a single item's Pass-1 tags (live tabs)."""
    sig = tags.get("exploration_signal", "no_signal")
    sent = tags.get("sentiment", "neutral")
    c1, c2, c3 = st.columns([1.4, 1, 1])
    c1.markdown(badge(SIGNAL_LABEL.get(sig, sig), SIGNAL_COLOR.get(sig, "#888")),
                unsafe_allow_html=True)
    c2.markdown(badge(sent, SENTIMENT_COLOR.get(sent, "#888")), unsafe_allow_html=True)
    c3.markdown(badge(f"relevant: {tags.get('is_relevant')}",
                      "#1a9850" if tags.get("is_relevant") else "#95a5a6"),
                unsafe_allow_html=True)
    st.markdown("**Themes:** " + pills(tags.get("themes", [])), unsafe_allow_html=True)
    if tags.get("user_segment_signals"):
        st.markdown("**Segments:** " + pills(tags["user_segment_signals"]), unsafe_allow_html=True)
    if tags.get("mentions_category"):
        st.markdown("**Categories:** " + pills(tags["mentions_category"]), unsafe_allow_html=True)
    if tags.get("job_to_be_done"):
        st.markdown(f'<div class="qcard"><div class="q">JTBD: “{tags["job_to_be_done"]}”</div>'
                    f'<div class="a">confidence: {tags.get("confidence","?")} · '
                    f'tagged by {tags.get("tagged_by","?")}</div></div>', unsafe_allow_html=True)


# ═══════════════════ VERTICAL LEFT-SIDE NAVIGATION ══════════════════
st.sidebar.markdown('<div class="sidenav-title">🛒 Discovery Engine</div>'
                    '<div class="sidenav-sub">Blinkit category-exploration barriers</div>',
                    unsafe_allow_html=True)
PAGES = ["📊 Insights", "🔬 Validation", "⚡ Live pipeline", "🧪 Try it live", "🔐 Admin"]
page = st.sidebar.radio("Navigate", PAGES, label_visibility="collapsed")


# ─────────────────────────── 1. INSIGHTS ───────────────────────────
if page == "📊 Insights":
    s = load_json(SYNTH_PATH)
    if not s:
        st.warning("No synthesis yet. Run the pipeline (see Admin tab).")
    else:
        a = s["aggregates"]; c = a["counts"]
        meta = load_json(META_PATH) or {}
        srcs = ", ".join(sorted(meta.get("per_source", {}).keys())) or "4 sources"
        st.markdown(f"""<div class="hero"><h1>🛒 Why don't Blinkit users explore new categories?</h1>
          <p>Last analyzed {s['generated_at'][:10]} · {c['relevant']} relevant of {c['total_tagged']}
          tagged items ({c['relevant_pct']}%) from {srcs} · {c['irrelevant_filtered']} filtered as noise</p></div>""",
          unsafe_allow_html=True)
        st.caption("⚠️ " + s["framing"])

        # ── KPI CARD ROW ──────────────────────────────────────────
        dist = {d["signal"]: d for d in a["exploration_signal_distribution"]}
        n_src = len(meta.get("per_source", {})) or len(a.get("source_distribution", []))
        merged_n = next((f["count"] for f in s.get("funnel", []) if f["stage"] == "Merged items"),
                        c["total_tagged"])
        r1 = st.columns(3)
        kpi(r1[0], f'{merged_n:,}', "Reviews collected", f'across {n_src} sources', "#0b6b3a")
        kpi(r1[1], f'{c["total_tagged"]:,}', "AI-tagged items", "two-pass LLM analysis", "#12a150")
        kpi(r1[2], f'{c["relevant"]} · {c["relevant_pct"]}%', "Category-relevant",
            f'{c["irrelevant_filtered"]} filtered as noise', "#3a7bd5")
        st.write("")
        r2 = st.columns(3)
        kpi(r2[0], dist.get("stuck_in_routine", {}).get("count", 0), "🔁 Stuck in routine",
            "same categories, repeat buys", "#d73027")
        kpi(r2[1], dist.get("wants_to_explore_but_blocked", {}).get("count", 0),
            "🚧 Want to explore — blocked", "intent exists, friction stops it", "#f39c12")
        kpi(r2[2], dist.get("explored_new_category", {}).get("count", 0), "✅ Explored new category",
            "actually crossed over", "#1a9850")

        # ── EXECUTIVE SUMMARY ─────────────────────────────────────
        if s.get("executive_summary"):
            st.subheader("Executive summary")
            for e in s["executive_summary"]:
                st.markdown(f'<div class="exec">▸ {e}</div>', unsafe_allow_html=True)

        # ── FUNNEL + SIGNAL DONUT ─────────────────────────────────
        fc1, fc2 = st.columns([1.3, 1])
        with fc1:
            st.subheader("From raw feedback → exploration signal")
            fn = s.get("funnel", [])
            if fn:
                ff = go.Figure(go.Funnel(y=[f["stage"] for f in fn], x=[f["count"] for f in fn],
                                         marker_color=["#0b6b3a", "#12a150", "#3a7bd5", "#f39c12", "#1a9850"],
                                         textinfo="value+percent initial"))
                ff.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(ff, width="stretch")
        with fc2:
            st.subheader("Exploration-signal mix")
            sd = a["exploration_signal_distribution"]
            st.plotly_chart(donut([d["signal"].replace("_", " ") for d in sd],
                                  [d["count"] for d in sd],
                                  [SIGNAL_COLOR[d["signal"]] for d in sd], height=300),
                            width="stretch")

        # ── BARRIERS + CATEGORY MENTIONS ──────────────────────────
        bc1, bc2 = st.columns(2)
        with bc1:
            st.subheader("Top barriers to exploration")
            bars = a["barriers"][:8][::-1]
            fig = go.Figure(go.Bar(x=[b["pct_of_relevant"] for b in bars], y=[b["theme"] for b in bars],
                orientation="h", marker_color="#d73027",
                text=[f'{b["pct_of_relevant"]}% ({b["count"]})' for b in bars], textposition="auto"))
            fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10),
                              xaxis_title="% of relevant", plot_bgcolor="#fff")
            st.plotly_chart(fig, width="stretch")
        with bc2:
            st.subheader("Which categories users talk about")
            cm = a.get("categories_mentioned", [])[:8][::-1]
            if cm:
                figc = go.Figure(go.Bar(x=[m["count"] for m in cm], y=[m["category"] for m in cm],
                    orientation="h", marker_color="#3a7bd5",
                    text=[m["count"] for m in cm], textposition="auto"))
                figc.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="#fff")
                st.plotly_chart(figc, width="stretch")

        # ── SENTIMENT DONUT + SIGNAL BY SOURCE + DRIVERS ──────────
        sc1, sc2 = st.columns([1, 1.3])
        with sc1:
            st.subheader("Sentiment (relevant)")
            snt = a.get("sentiment_distribution", [])
            if snt:
                st.plotly_chart(donut([d["sentiment"] for d in snt], [d["count"] for d in snt],
                                      [SENTIMENT_COLOR[d["sentiment"]] for d in snt], height=260),
                                width="stretch")
        with sc2:
            st.subheader("Where exploration signal shows up (by source)")
            sbs = a.get("signal_by_source", [])
            if sbs:
                figs = go.Figure()
                for sig in ["explored_new_category", "wants_to_explore_but_blocked",
                            "stuck_in_routine"]:
                    figs.add_bar(name=sig.replace("_", " "), x=[r["source"] for r in sbs],
                                 y=[r.get(sig, 0) for r in sbs], marker_color=SIGNAL_COLOR[sig])
                figs.update_layout(barmode="stack", height=260, margin=dict(l=10, r=10, t=10, b=10),
                                   legend=dict(orientation="h", y=-0.2), plot_bgcolor="#fff")
                st.plotly_chart(figs, width="stretch")

        st.subheader("What's working (drivers of exploration)")
        dcols = st.columns(3)
        for i, d in enumerate(a.get("drivers", [])[:3]):
            kpi(dcols[i], f'{d["count"]}', f'✅ {d["theme"]}', f'{d["pct_of_relevant"]}% of relevant', "#1a9850")

        # ── CATEGORY OPPORTUNITIES ────────────────────────────────
        if s.get("category_opportunities"):
            st.subheader("Category-specific growth opportunities")
            ocols = st.columns(len(s["category_opportunities"]))
            for i, co in enumerate(s["category_opportunities"]):
                ocols[i].markdown(f'<div class="opp"><h4>{co["category"]}</h4>'
                                  f'<div class="b">⛔ {co["barrier"]}</div>'
                                  f'<div style="margin-top:6px">🚀 {co["opportunity"]}</div></div>',
                                  unsafe_allow_html=True)

        st.subheader("Segments: locked-in vs. natural explorers")
        cols = st.columns(2)
        with cols[0]:
            st.markdown("**🔁 Most locked into repetitive buying**")
            for seg in s["locked_in_segments"]:
                st.markdown(f'<div class="seg-card"><h4>{seg["segment"]}</h4>{seg["traits"]}</div>',
                            unsafe_allow_html=True)
        with cols[1]:
            st.markdown("**🧭 Most likely to explore**")
            for seg in s["explorer_segments"]:
                st.markdown(f'<div class="seg-card"><h4>{seg["segment"]}</h4>{seg["traits"]}</div>',
                            unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Top jobs-to-be-done")
            for j in s["top_jobs_to_be_done"]:
                st.markdown(f'<div class="jtbd">🎯 {j["job"]} <small class="muted">(~{j["approx_count"]})</small></div>',
                            unsafe_allow_html=True)
        with c2:
            st.subheader("Top unmet needs")
            for u in s["unmet_needs"]:
                st.markdown(f'<div class="jtbd">🔎 {u}</div>', unsafe_allow_html=True)

        if s.get("recommended_experiments"):
            st.subheader("Recommended experiments to drive exploration")
            st.caption("Levers to TEST — framed as hypotheses for the downstream survey/experiments, not asserted wins.")
            for ex in s["recommended_experiments"]:
                st.markdown(f'<div class="exp"><span class="lv">🧪 {ex["lever"]}</span> '
                            f'<small class="muted">(targets: {ex["targets_barrier"]})</small><br>{ex["hypothesis"]}</div>',
                            unsafe_allow_html=True)

        if s.get("surprising_insights"):
            st.subheader("Surprising / counter-intuitive")
            for si in s["surprising_insights"]:
                st.markdown(f'<div class="surprise">💡 {si}</div>', unsafe_allow_html=True)

        st.subheader("Most powerful quotes")
        qc = st.columns(2)
        for i, q in enumerate(s["powerful_quotes"]):
            with qc[i % 2]:
                st.markdown(f'<div class="qcard"><div class="q">“{q["quote"]}”</div>'
                            f'<div class="a">— {q["source"]} · {q["attribution"]}</div></div>',
                            unsafe_allow_html=True)

        st.subheader("Hypotheses (with evidence strength)")
        for i, h in enumerate(s["hypotheses"], 1):
            tri = "✓ triangulated" if h["source_triangulated"] else "⚠ single-source"
            st.markdown(
                f'<div class="hyp">{badge(h["confidence"].upper(), CONF_COLOR.get(h["confidence"],"#888"))} '
                f'<b>H{i}. {h["hypothesis"]}</b>'
                f'<div class="meta">{h["evidence_items"]} items · {len(h.get("evidence_sources",[]))} sources '
                f'({", ".join(h.get("evidence_sources",[]))}) · {tri}<br>{h.get("rationale","")}</div></div>',
                unsafe_allow_html=True)


# ─────────────────────────── 2. VALIDATION ─────────────────────────
elif page == "🔬 Validation":
    v = load_json(VALIDATION_PATH)
    if not v:
        st.warning("No validation data yet.")
    else:
        st.subheader("Insight-quality validation")
        st.caption(v["purpose"])
        cov = v["coverage"]
        m = st.columns(4)
        m[0].metric("Relevant (signal)", f'{cov["relevant_pct"]}%', f'{cov["relevant"]} items')
        m[1].metric("No-signal rate", f'{cov["no_signal_pct"]}%')
        m[2].metric("Low-confidence", f'{cov["low_confidence_pct"]}%')
        m[3].metric("Ambiguity rate", f'{cov["ambiguity_rate_pct"]}%')

        acc = v["manual_check"].get("accuracy_rate")
        st.info(f"🧑‍🔬 Manual accuracy check: sample of {v['manual_check']['sample_size']} items "
                f"(`{v['manual_check']['sample_file']}`) — "
                + (f"**{acc}** agreement" if acc is not None else "accuracy not yet filled in "
                   "(fill HUMAN_ columns in the sample CSV)."))

        st.subheader("Per-hypothesis evidence & triangulation")
        hyp = v.get("per_hypothesis_validation", [])
        if hyp:
            df = pd.DataFrame([{"Hypothesis": h["hypothesis"][:90], "Confidence": h["confidence"],
                                "Evidence items": h["evidence_items"], "# sources": h["n_sources"],
                                "Triangulated": "✓" if h["source_triangulated"] else "⚠ single-source"}
                               for h in hyp])
            st.dataframe(df, width="stretch", hide_index=True)

        st.subheader("Per-theme evidence strength")
        tdf = pd.DataFrame([{"Theme": t["theme"], "Kind": t["kind"], "Strength": t["strength"],
                             "Items": t["evidence_items"], "Sources": t["n_sources"],
                             "Triangulated": "✓" if t["triangulated"] else "⚠"}
                            for t in v["per_theme_evidence"] if t["evidence_items"] > 0])
        st.dataframe(tdf, width="stretch", hide_index=True)
        ss = v["triangulation"]["single_source_themes_flagged_low_confidence"]
        if ss:
            st.warning("Single-source themes flagged lower-confidence: " + ", ".join(ss))


# ───────────────────────── 3. LIVE PIPELINE ────────────────────────
elif page == "⚡ Live pipeline":
    st.subheader("⚡ Live pipeline demo — a few fresh reviews, tagged in real time")
    st.caption("Fetches 5 fresh App Store reviews and tags each with one live LLM call. "
               "This is a demo of the mechanism on a tiny sample — it does NOT run the full pipeline.")
    if st.button("▶️ Run live demo", key="livebtn"):
        try:
            from scrapers.app_store import fetch_page, normalize
            from llm_client import LLMClient
            from pass1_tag import tag_one_item
            import datetime as dt
            with st.spinner("Fetching fresh reviews…"):
                raw = fetch_page(1)[:12]
                sa = dt.datetime.now(dt.timezone.utc).isoformat()
                items = [normalize(e, sa) for e in raw]
                items = [i for i in items if len(i["text"]) > 25][:5]
            client = LLMClient()
            client.verify_groq_model()
            rollup = {}
            for it in items:
                with st.container():
                    st.markdown(f'<div class="card"><b>{it["source"]}</b> · {it["date"]} · '
                                f'★{it["rating"]}<br>{it["text"][:280]}</div>', unsafe_allow_html=True)
                    with st.spinner("Tagging live…"):
                        tags = tag_one_item(client, it)
                    render_tags(tags)
                    sig = tags["exploration_signal"]
                    rollup[sig] = rollup.get(sig, 0) + 1
                    st.divider()
            st.success("Roll-up of this mini-batch → " +
                       " · ".join(f"{SIGNAL_LABEL.get(k,k)}: {n}" for k, n in rollup.items()))
            st.caption("At scale, these tags aggregate into the Insights tab's barriers, "
                       "segments, and hypotheses.")
        except Exception as e:  # noqa: BLE001
            st.error(f"Live demo failed: {e}")


# ─────────────────────────── 4. TRY IT LIVE ────────────────────────
elif page == "🧪 Try it live":
    SAMPLES = [
        "I only ever order milk and bread on Blinkit, never knew they even sold pet food.",
        "Tried ordering a birthday gift and some makeup — surprisingly they had a good range!",
        "Blinkit is only for emergencies, I still go to the local store for fresh vegetables.",
        "Wanted to buy baby diapers but the brand I trust wasn't available, so I used Amazon.",
        "Their prices on electronics feel higher than Amazon, so I never try those categories here.",
    ]
    st.subheader("🧪 Try it live — paste a review, get structured tags")
    st.caption("Makes ONE live Pass-1 call and renders the structured output.")
    cols = st.columns(5)
    for i, s_txt in enumerate(SAMPLES):
        if cols[i].button(f"Sample {i+1}", key=f"s{i}"):
            st.session_state["try_text"] = s_txt
    text = st.text_area("Review text", value=st.session_state.get("try_text", ""), height=110,
                        placeholder="Paste any Blinkit review or comment…")
    if st.button("🔍 Analyze", type="primary") and text.strip():
        try:
            from llm_client import LLMClient
            from pass1_tag import tag_one_item
            import datetime as dt
            client = LLMClient()
            client.verify_groq_model()
            item = {"id": "live", "source": "user_input", "date": dt.date.today().isoformat(),
                    "rating": None, "text": text.strip()}
            with st.spinner("Tagging…"):
                tags = tag_one_item(client, item)
            render_tags(tags)
            if tags.get("direct_quote"):
                st.markdown(f'> “{tags["direct_quote"]}”')
        except Exception as e:  # noqa: BLE001
            st.error(f"Analysis failed: {e}")


# ─────────────────────────── 5. ADMIN ──────────────────────────────
elif page == "🔐 Admin":
    st.subheader("🔐 Admin — re-run the pipeline")
    pw_real = os.getenv("ADMIN_PASSWORD", "")
    pw = st.text_input("Admin password", type="password")
    if not pw_real:
        st.warning("ADMIN_PASSWORD not set in environment/secrets.")
    elif pw != pw_real:
        st.info("Enter the admin password to access pipeline controls.")
    else:
        from pipeline import PIPELINE_STATE, start_pipeline
        st.success("Authenticated.")
        c1, c2 = st.columns(2)
        scrape = c1.checkbox("Also re-scrape all sources (slow, may hit quotas)", value=False)
        tag_limit = c2.number_input("Pass-1 tag limit", 50, 3000, 400, step=50)
        if st.button("🚀 Run pipeline now", type="primary", disabled=PIPELINE_STATE["running"]):
            if start_pipeline(scrape=scrape, tag_limit=int(tag_limit)):
                st.toast("Pipeline started")
            else:
                st.warning("Already running.")
        state = PIPELINE_STATE
        if state["running"]:
            st.info(f"⏳ Running — current step: **{state['current_step']}** · "
                    f"done: {', '.join(state['steps_done']) or '—'}")
        elif state["returncode"] == 0:
            st.success(f"✅ Last run complete: {', '.join(state['steps_done'])}")
        elif state["returncode"]:
            st.error(f"❌ Last run failed at: {state.get('error')}")
        st.markdown("**Live log tail** (data/pipeline.log)")
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, encoding="utf-8") as f:
                lines = f.readlines()[-40:]
            st.code("".join(lines), language="log")
        if st.button("🔄 Refresh log / status"):
            st.rerun()
