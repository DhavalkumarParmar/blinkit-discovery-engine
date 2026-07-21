"""Pass 2 — aggregate synthesis over the TAGGED data.

Division of labour (per the brief):
  - PYTHON computes every frequency/percentage DETERMINISTICALLY (barriers,
    exploration-signal distribution, segment/category counts, evidence counts).
  - The LLM (ONE call) does only what needs language understanding: cluster the
    free-text jobs-to-be-done + unmet needs, pick the most powerful quotes, and
    form 3-5 hypotheses. Each hypothesis is tagged BY THE MODEL with the vocab
    themes/signals that support it, so Python can then attach a deterministic
    evidence count + source-triangulation flag.

Everything is framed as hypotheses-with-evidence-strength, not conclusions.

Usage:  python pass2_synthesize.py [--context-items 120]
Output: data/synthesis.json + data/synthesis.md
"""

import argparse
import datetime as dt
import json
import os
from collections import Counter

from common import DATA_DIR, get_logger, read_jsonl
from llm_client import LLMClient
from vocab import DRIVER_THEMES, EXPLORATION_SIGNALS, THEMES, USER_SEGMENTS

log = get_logger("pass2")

TAGGED_PATH = os.path.join(DATA_DIR, "tagged.jsonl")
SYNTH_JSON = os.path.join(DATA_DIR, "synthesis.json")
SYNTH_MD = os.path.join(DATA_DIR, "synthesis.md")

# Signals/themes that indicate being LOCKED IN vs EXPLORING (for segment split).
LOCKED_SIGNALS = {"stuck_in_routine", "wants_to_explore_but_blocked"}
EXPLORE_SIGNALS = {"explored_new_category"}


# ── Deterministic aggregates ────────────────────────────────────────

def compute_aggregates(tagged: list[dict], relevant: list[dict]) -> dict:
    n_all, n_rel = len(tagged), len(relevant)

    def pct(n, d):
        return round(100 * n / d, 1) if d else 0.0

    # Theme frequency over RELEVANT items, split into BARRIERS vs DRIVERS
    # (exclude the catch-all "other").
    theme_counts = Counter(th for it in relevant for th in it["themes"])
    barriers = [{"theme": th, "count": c, "pct_of_relevant": pct(c, n_rel)}
                for th, c in theme_counts.most_common()
                if th != "other" and th not in DRIVER_THEMES]
    drivers = [{"theme": th, "count": c, "pct_of_relevant": pct(c, n_rel)}
               for th, c in theme_counts.most_common() if th in DRIVER_THEMES]

    # exploration_signal distribution over ALL tagged items.
    sig_counts = Counter(it["exploration_signal"] for it in tagged)
    signal_dist = [{"signal": s, "count": sig_counts.get(s, 0),
                    "pct_of_all": pct(sig_counts.get(s, 0), n_all)}
                   for s in EXPLORATION_SIGNALS]

    # Segment frequency, split into locked-in vs explorer populations.
    locked = Counter(seg for it in relevant if it["exploration_signal"] in LOCKED_SIGNALS
                     for seg in it["user_segment_signals"])
    explorer = Counter(seg for it in relevant if it["exploration_signal"] in EXPLORE_SIGNALS
                       for seg in it["user_segment_signals"])
    seg_overall = Counter(seg for it in relevant for seg in it["user_segment_signals"])

    cat_counts = Counter(c for it in relevant for c in it["mentions_category"] if c != "other")
    src_counts = Counter(it["source"] for it in relevant)

    return {
        "counts": {"total_tagged": n_all, "relevant": n_rel,
                   "irrelevant_filtered": n_all - n_rel,
                   "relevant_pct": pct(n_rel, n_all)},
        "barriers": barriers,
        "drivers": drivers,
        "exploration_signal_distribution": signal_dist,
        "segments_locked_in": [{"segment": s, "count": c} for s, c in locked.most_common()],
        "segments_explorers": [{"segment": s, "count": c} for s, c in explorer.most_common()],
        "segments_overall": [{"segment": s, "count": c} for s, c in seg_overall.most_common()],
        "categories_mentioned": [{"category": c, "count": n} for c, n in cat_counts.most_common()],
        "source_distribution": [{"source": s, "count": c} for s, c in src_counts.most_common()],
    }


def _evidence_for(themes: list[str], signals: list[str], relevant: list[dict]) -> dict:
    """Deterministic evidence count for a hypothesis: distinct items + sources
    whose themes/signal intersect the hypothesis's supporting tags."""
    tset, sset = set(themes or []), set(signals or [])
    hits = [it for it in relevant
            if (tset & set(it["themes"])) or (it["exploration_signal"] in sset)]
    sources = sorted({it["source"] for it in hits})
    return {"evidence_items": len(hits), "evidence_sources": sources,
            "n_sources": len(sources), "triangulated": len(sources) >= 2}


def _derive_confidence(ev: dict) -> str:
    """Confidence from evidence VOLUME + source CONSISTENCY (deterministic)."""
    n, s = ev["evidence_items"], ev["n_sources"]
    if n >= 15 and s >= 2:
        return "high"
    if n >= 6 and s >= 2:
        return "medium"
    return "low"


# ── LLM synthesis (language-understanding parts only) ───────────────

SYNTH_SCHEMA = {
    "type": "object",
    "properties": {
        "locked_in_segments": {"type": "array", "items": {"type": "object", "properties": {
            "segment": {"type": "string"}, "traits": {"type": "string"}},
            "required": ["segment", "traits"]}},
        "explorer_segments": {"type": "array", "items": {"type": "object", "properties": {
            "segment": {"type": "string"}, "traits": {"type": "string"}},
            "required": ["segment", "traits"]}},
        "top_jobs_to_be_done": {"type": "array", "items": {"type": "object", "properties": {
            "job": {"type": "string"}, "approx_count": {"type": "integer"}},
            "required": ["job", "approx_count"]}},
        "unmet_needs": {"type": "array", "items": {"type": "string"}},
        "powerful_quotes": {"type": "array", "items": {"type": "object", "properties": {
            "quote": {"type": "string"}, "source": {"type": "string"},
            "attribution": {"type": "string"}}, "required": ["quote", "source", "attribution"]}},
        "hypotheses": {"type": "array", "items": {"type": "object", "properties": {
            "hypothesis": {"type": "string"},
            "supporting_themes": {"type": "array", "items": {"type": "string", "enum": THEMES}},
            "supporting_signals": {"type": "array", "items": {"type": "string", "enum": EXPLORATION_SIGNALS}},
            "rationale": {"type": "string"}},
            "required": ["hypothesis", "supporting_themes", "supporting_signals", "rationale"]}},
    },
    "required": ["locked_in_segments", "explorer_segments", "top_jobs_to_be_done",
                 "unmet_needs", "powerful_quotes", "hypotheses"],
}

SYSTEM = (
    "You are a Growth PM at Blinkit synthesizing tagged user feedback to explain "
    "WHY users stay locked into the same product categories and rarely explore new "
    "ones. You are given deterministic aggregate counts plus per-item tags and "
    "quotes (NOT raw text). Produce a synthesis framed as HYPOTHESES WITH EVIDENCE "
    "STRENGTH, not conclusions (a survey + interviews will validate them). "
    "Cluster the free-text jobs-to-be-done and unmet needs into themes. Select the "
    "10 MOST POWERFUL verbatim quotes from the candidates provided (keep them "
    "verbatim, include their source+attribution). Give 3-5 hypotheses about the "
    "barriers to category exploration; for EACH, list the supporting_themes and "
    "supporting_signals (from the controlled vocab) that back it, so evidence can be "
    "counted. Use only allowed enum values for those tag lists."
)


def build_llm_prompt(agg: dict, relevant: list[dict], quote_candidates: list[dict],
                     context_items: int) -> str:
    items = relevant[:context_items]
    compact = [{"source": it["source"], "signal": it["exploration_signal"],
                "themes": it["themes"], "segments": it["user_segment_signals"],
                "categories": it["mentions_category"], "jtbd": it["job_to_be_done"],
                "root_cause": it["frustration_root_cause"]} for it in items]
    return (
        "DETERMINISTIC AGGREGATES (already counted — do not recount):\n"
        + json.dumps({k: agg[k] for k in ["counts", "barriers",
             "exploration_signal_distribution", "segments_locked_in",
             "segments_explorers", "categories_mentioned"]}, indent=1)
        + f"\n\nTAGGED RELEVANT ITEMS (tags only, n={len(compact)}):\n"
        + json.dumps(compact, ensure_ascii=False)
        + f"\n\nQUOTE CANDIDATES (choose the 10 most powerful, keep verbatim):\n"
        + json.dumps(quote_candidates, ensure_ascii=False)
        + "\n\nReturn the synthesis JSON."
    )


def synthesize(context_items: int = 120) -> dict:
    tagged = read_jsonl(TAGGED_PATH)
    if not tagged:
        raise RuntimeError("No tagged.jsonl — run pass1_tag.py first.")
    relevant = [it for it in tagged if it.get("is_relevant")]
    log.info("Synthesizing over %d relevant / %d tagged items", len(relevant), len(tagged))

    agg = compute_aggregates(tagged, relevant)

    # Quote candidates: relevant, non-empty quote, prefer high confidence.
    cand = sorted([it for it in relevant if (it.get("direct_quote") or "").strip()],
                  key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["confidence"], 3))
    quote_candidates = [{"quote": it["direct_quote"], "source": it["source"],
                         "attribution": (it.get("author") or "anon") + " · " + (it.get("date") or ""),
                         "signal": it["exploration_signal"]} for it in cand[:40]]

    client = LLMClient()
    log.warning("QUOTA ESTIMATE: 1 LLM request for synthesis.")
    llm = client.generate_json(build_llm_prompt(agg, relevant, quote_candidates, context_items),
                               SYNTH_SCHEMA, system=SYSTEM, max_tokens=4096)

    # Attach DETERMINISTIC evidence counts + confidence to each hypothesis.
    hypotheses = []
    for h in llm.get("hypotheses", []):
        ev = _evidence_for(h.get("supporting_themes"), h.get("supporting_signals"), relevant)
        hypotheses.append({
            "hypothesis": h["hypothesis"],
            "supporting_themes": [t for t in h.get("supporting_themes", []) if t in THEMES],
            "supporting_signals": [s for s in h.get("supporting_signals", []) if s in EXPLORATION_SIGNALS],
            "rationale": h.get("rationale", ""),
            "evidence_items": ev["evidence_items"],
            "evidence_sources": ev["evidence_sources"],
            "source_triangulated": ev["triangulated"],
            "confidence": _derive_confidence(ev),
        })
    hypotheses.sort(key=lambda x: x["evidence_items"], reverse=True)

    synthesis = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "framing": ("Candidate barriers/drivers with evidence strength — HYPOTHESES, "
                    "not conclusions. To be screened by survey and refined by interviews."),
        "aggregates": agg,
        "locked_in_segments": llm.get("locked_in_segments", [])[:3],
        "explorer_segments": llm.get("explorer_segments", [])[:3],
        "top_jobs_to_be_done": llm.get("top_jobs_to_be_done", [])[:5],
        "unmet_needs": llm.get("unmet_needs", [])[:5],
        "powerful_quotes": llm.get("powerful_quotes", [])[:10],
        "hypotheses": hypotheses,
        "llm_stats": client.stats,
    }
    return synthesis


# ── Markdown rendering ──────────────────────────────────────────────

def to_markdown(s: dict) -> str:
    a = s["aggregates"]
    c = a["counts"]
    L = ["# Blinkit Category-Exploration Synthesis",
         f"\n_Generated {s['generated_at'][:16]} · {c['relevant']} relevant of "
         f"{c['total_tagged']} tagged items ({c['relevant_pct']}%) · "
         f"{c['irrelevant_filtered']} filtered as noise_",
         f"\n> {s['framing']}\n",
         "## Top barriers to category exploration"]
    for b in a["barriers"][:5]:
        L.append(f"- **{b['theme']}** — {b['count']} items ({b['pct_of_relevant']}% of relevant)")
    L.append("\n## What's working (drivers of exploration)")
    for d in a.get("drivers", [])[:3]:
        L.append(f"- **{d['theme']}** — {d['count']} items ({d['pct_of_relevant']}% of relevant)")
    L.append("\n## Exploration-signal distribution")
    for d in a["exploration_signal_distribution"]:
        L.append(f"- {d['signal']}: {d['count']} ({d['pct_of_all']}%)")
    L.append("\n## Segments most locked into repetitive buying")
    for seg in s["locked_in_segments"]:
        L.append(f"- **{seg['segment']}** — {seg['traits']}")
    L.append("\n## Segments most likely to explore")
    for seg in s["explorer_segments"]:
        L.append(f"- **{seg['segment']}** — {seg['traits']}")
    L.append("\n## Top jobs-to-be-done")
    for j in s["top_jobs_to_be_done"]:
        L.append(f"- {j['job']} (~{j['approx_count']})")
    L.append("\n## Top unmet needs")
    for u in s["unmet_needs"]:
        L.append(f"- {u}")
    L.append("\n## Most powerful quotes")
    for q in s["powerful_quotes"]:
        L.append(f"> \"{q['quote']}\"  \n  — {q['source']}, {q['attribution']}")
    L.append("\n## Hypotheses (with evidence strength)")
    for i, h in enumerate(s["hypotheses"], 1):
        tri = "✓ triangulated" if h["source_triangulated"] else "⚠ single-source"
        L.append(f"\n**H{i}. {h['hypothesis']}**  \n"
                 f"Confidence: **{h['confidence']}** · {h['evidence_items']} items across "
                 f"{len(h['evidence_sources'])} sources ({', '.join(h['evidence_sources'])}) · {tri}  \n"
                 f"_{h['rationale']}_")
    return "\n".join(L)


def rebuild_from_existing() -> dict:
    """Recompute the DETERMINISTIC parts (aggregates, hypothesis evidence) from
    tagged.jsonl and re-render, reusing the LLM-derived narrative already in
    synthesis.json. No LLM call — regenerate deterministic output for free."""
    if not os.path.exists(SYNTH_JSON):
        raise RuntimeError("No existing synthesis.json to rebuild from — run without --rebuild first.")
    with open(SYNTH_JSON, encoding="utf-8") as f:
        prev = json.load(f)
    tagged = read_jsonl(TAGGED_PATH)
    relevant = [it for it in tagged if it.get("is_relevant")]
    agg = compute_aggregates(tagged, relevant)
    hypotheses = []
    for h in prev.get("hypotheses", []):
        ev = _evidence_for(h.get("supporting_themes"), h.get("supporting_signals"), relevant)
        hypotheses.append({**h, "evidence_items": ev["evidence_items"],
                           "evidence_sources": ev["evidence_sources"],
                           "source_triangulated": ev["triangulated"],
                           "confidence": _derive_confidence(ev)})
    hypotheses.sort(key=lambda x: x["evidence_items"], reverse=True)
    prev.update({"aggregates": agg, "hypotheses": hypotheses,
                 "rebuilt_at": dt.datetime.now(dt.timezone.utc).isoformat()})
    return prev


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--context-items", type=int, default=120)
    ap.add_argument("--rebuild", action="store_true",
                    help="recompute deterministic parts + re-render from existing "
                         "synthesis.json (no LLM call)")
    args = ap.parse_args()

    s = rebuild_from_existing() if args.rebuild else synthesize(args.context_items)
    with open(SYNTH_JSON, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
    with open(SYNTH_MD, "w", encoding="utf-8") as f:
        f.write(to_markdown(s))
    log.info("Wrote %s + %s", SYNTH_JSON, SYNTH_MD)
    log.info("Hypotheses: %d | quotes: %d | barriers: %d",
             len(s["hypotheses"]), len(s["powerful_quotes"]), len(s["aggregates"]["barriers"]))
