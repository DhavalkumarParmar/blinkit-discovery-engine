"""Insight-validation layer — deterministic, no LLM.

The brief requires demonstrating INSIGHT QUALITY, not just insights. This
computes, from the tagged data + synthesis:

  1. Per-theme evidence: how many DISTINCT items, across how many DISTINCT
     sources, support each theme. (2 reviews = weak; 40 across 3 sources = strong.)
  2. Source-triangulation flag: does the theme/hypothesis appear in >=2
     independent sources? Single-source insights are flagged lower-confidence.
  3. Coverage / ambiguity rate: what % of items the model marked no_signal or
     low-confidence — so coverage can be reported honestly.
  4. A 30-item human-check sample (data/validation_sample.csv) with AI tags +
     blank columns to eyeball agreement and report an approximate accuracy rate.

Usage:  python validate.py [--sample-size 30]
Output: data/validation.json + data/validation_sample.csv
"""

import argparse
import csv
import datetime as dt
import json
import os
import random
from collections import Counter

from common import DATA_DIR, get_logger, read_jsonl
from vocab import BARRIER_THEMES, DRIVER_THEMES

log = get_logger("validate")

TAGGED_PATH = os.path.join(DATA_DIR, "tagged.jsonl")
SYNTH_PATH = os.path.join(DATA_DIR, "synthesis.json")
VALIDATION_JSON = os.path.join(DATA_DIR, "validation.json")
SAMPLE_CSV = os.path.join(DATA_DIR, "validation_sample.csv")
SAMPLE_SEED = 7


def theme_evidence(relevant: list[dict]) -> list[dict]:
    rows = []
    for theme in BARRIER_THEMES + sorted(DRIVER_THEMES):
        hits = [it for it in relevant if theme in it["themes"]]
        srcs = sorted({it["source"] for it in hits})
        rows.append({
            "theme": theme,
            "kind": "driver" if theme in DRIVER_THEMES else "barrier",
            "evidence_items": len(hits),
            "n_sources": len(srcs),
            "sources": srcs,
            "triangulated": len(srcs) >= 2,
            "strength": ("strong" if len(hits) >= 15 and len(srcs) >= 2
                         else "moderate" if len(hits) >= 6 and len(srcs) >= 2
                         else "weak"),
        })
    return sorted(rows, key=lambda r: r["evidence_items"], reverse=True)


def coverage_metrics(tagged: list[dict]) -> dict:
    n = len(tagged)
    def pct(c):
        return round(100 * c / n, 1) if n else 0.0
    no_signal = sum(1 for it in tagged if it["exploration_signal"] == "no_signal")
    low_conf = sum(1 for it in tagged if it["confidence"] == "low")
    relevant = sum(1 for it in tagged if it.get("is_relevant"))
    # "uncertain" = model gave no exploration signal OR low confidence.
    uncertain = sum(1 for it in tagged
                    if it["exploration_signal"] == "no_signal" or it["confidence"] == "low")
    return {
        "total_tagged": n,
        "relevant": relevant,
        "relevant_pct": pct(relevant),
        "irrelevant_filtered": n - relevant,
        "no_signal_pct": pct(no_signal),
        "low_confidence_pct": pct(low_conf),
        "ambiguity_rate_pct": pct(uncertain),
        "confidence_breakdown": dict(Counter(it["confidence"] for it in tagged)),
    }


def write_sample_csv(tagged: list[dict], size: int) -> int:
    rng = random.Random(SAMPLE_SEED)
    sample = rng.sample(tagged, min(size, len(tagged)))
    cols = ["id", "source", "date", "text", "is_relevant", "exploration_signal",
            "sentiment", "themes", "user_segment_signals", "mentions_category",
            "job_to_be_done", "confidence", "direct_quote",
            # blank columns for the human reviewer:
            "HUMAN_is_relevant", "HUMAN_exploration_signal", "AGREE_(Y/N)", "NOTES"]
    with open(SAMPLE_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for it in sample:
            row = dict(it)
            row["text"] = (it.get("text") or "").replace("\n", " ")[:300]
            for lst in ("themes", "user_segment_signals", "mentions_category"):
                row[lst] = ", ".join(it.get(lst) or [])
            row.update({"HUMAN_is_relevant": "", "HUMAN_exploration_signal": "",
                        "AGREE_(Y/N)": "", "NOTES": ""})
            w.writerow(row)
    return len(sample)


def validate(sample_size: int = 30) -> dict:
    tagged = read_jsonl(TAGGED_PATH)
    if not tagged:
        raise RuntimeError("No tagged.jsonl — run pass1_tag.py first.")
    relevant = [it for it in tagged if it.get("is_relevant")]

    themes = theme_evidence(relevant)
    coverage = coverage_metrics(tagged)

    # Pull hypothesis validation straight from synthesis (already deterministic).
    hyp_val = []
    if os.path.exists(SYNTH_PATH):
        with open(SYNTH_PATH, encoding="utf-8") as f:
            synth = json.load(f)
        for h in synth.get("hypotheses", []):
            hyp_val.append({
                "hypothesis": h["hypothesis"],
                "evidence_items": h.get("evidence_items", 0),
                "n_sources": len(h.get("evidence_sources", [])),
                "sources": h.get("evidence_sources", []),
                "source_triangulated": h.get("source_triangulated", False),
                "confidence": h.get("confidence", "low"),
            })

    n_sample = write_sample_csv(tagged, sample_size)

    single_source_themes = [t["theme"] for t in themes
                            if t["evidence_items"] > 0 and not t["triangulated"]]

    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "purpose": ("Insight-quality evidence: how much distinct-item and "
                    "distinct-source support each theme/hypothesis has, plus honest "
                    "coverage/ambiguity so hypotheses can be weighted, not trusted blindly."),
        "coverage": coverage,
        "per_theme_evidence": themes,
        "per_hypothesis_validation": hyp_val,
        "triangulation": {
            "distinct_sources": sorted({it["source"] for it in tagged}),
            "n_sources": len({it["source"] for it in tagged}),
            "single_source_themes_flagged_low_confidence": single_source_themes,
        },
        "manual_check": {
            "sample_size": n_sample,
            "sample_file": os.path.relpath(SAMPLE_CSV, DATA_DIR),
            "accuracy_rate": None,  # fill in after eyeballing the CSV
            "instructions": ("Open validation_sample.csv, fill HUMAN_is_relevant / "
                             "HUMAN_exploration_signal / AGREE_(Y/N), then compute "
                             "accuracy = #AGREE / sample_size and record it here."),
        },
    }
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample-size", type=int, default=30)
    args = ap.parse_args()

    report = validate(args.sample_size)
    with open(VALIDATION_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log.info("Wrote %s + %s", VALIDATION_JSON, SAMPLE_CSV)
    c = report["coverage"]
    log.info("Coverage: relevant %.1f%% | no_signal %.1f%% | low_conf %.1f%% | ambiguity %.1f%%",
             c["relevant_pct"], c["no_signal_pct"], c["low_confidence_pct"], c["ambiguity_rate_pct"])
    log.info("Single-source (lower-confidence) themes: %s",
             report["triangulation"]["single_source_themes_flagged_low_confidence"])
