"""Score the human-check sample and write the accuracy rate into validation.json.

Workflow:
  1. Open data/validation_sample.csv and, for each row, fill the blank columns:
       HUMAN_is_relevant            (true/false)
       HUMAN_exploration_signal     (one of the 4 exploration_signal values)
       AGREE_(Y/N)                  (Y if the AI tags look right, N otherwise)
       NOTES                        (optional)
  2. Run:  python score_validation.py
  3. It computes the agreement rate and writes it into
     data/validation.json → manual_check → accuracy_rate (+ a breakdown).
  4. Commit & push so the deployed dashboard's Validation tab shows it.

No LLM, no network — pure local scoring.
"""

import csv
import datetime as dt
import json
import os

from common import DATA_DIR, get_logger

log = get_logger("score")

SAMPLE_CSV = os.path.join(DATA_DIR, "validation_sample.csv")
VALIDATION_JSON = os.path.join(DATA_DIR, "validation.json")

_TRUE = {"true", "t", "yes", "y", "1", "relevant"}
_FALSE = {"false", "f", "no", "n", "0", "irrelevant"}
_AGREE = {"y", "yes", "agree", "1", "true", "✓"}
_DISAGREE = {"n", "no", "disagree", "0", "false", "✗", "x"}


def _to_bool(v: str):
    v = (v or "").strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    return None  # unfilled / unrecognized


def score() -> dict | None:
    if not os.path.exists(SAMPLE_CSV):
        log.error("No %s — run validate.py first.", SAMPLE_CSV)
        return None

    with open(SAMPLE_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        log.error("Sample CSV is empty.")
        return None

    total = len(rows)
    agree_y = agree_n = 0
    rel_checked = rel_match = 0
    sig_checked = sig_match = 0

    for r in rows:
        # 1) explicit AGREE column
        a = (r.get("AGREE_(Y/N)") or "").strip().lower()
        if a in _AGREE:
            agree_y += 1
        elif a in _DISAGREE:
            agree_n += 1

        # 2) field-level agreement (only where the human filled a value)
        h_rel = _to_bool(r.get("HUMAN_is_relevant"))
        if h_rel is not None:
            rel_checked += 1
            ai_rel = _to_bool(str(r.get("is_relevant")))
            if h_rel == ai_rel:
                rel_match += 1

        h_sig = (r.get("HUMAN_exploration_signal") or "").strip().lower()
        if h_sig:
            sig_checked += 1
            if h_sig == (r.get("exploration_signal") or "").strip().lower():
                sig_match += 1

    n_agree_reviewed = agree_y + agree_n
    if n_agree_reviewed == 0 and rel_checked == 0 and sig_checked == 0:
        log.warning("No rows filled in yet — fill HUMAN_/AGREE columns in %s first. "
                    "Leaving accuracy_rate unchanged.", SAMPLE_CSV)
        return None

    def rate(match, n):
        return round(100 * match / n, 1) if n else None

    agree_pct = rate(agree_y, n_agree_reviewed)
    rel_pct = rate(rel_match, rel_checked)
    sig_pct = rate(sig_match, sig_checked)

    # Headline accuracy: prefer the explicit AGREE column; else fall back to the
    # exploration_signal field agreement (the most important field), else is_relevant.
    if agree_pct is not None:
        headline = f"{agree_pct}% ({agree_y}/{n_agree_reviewed})"
    elif sig_pct is not None:
        headline = f"{sig_pct}% ({sig_match}/{sig_checked}) on exploration_signal"
    else:
        headline = f"{rel_pct}% ({rel_match}/{rel_checked}) on is_relevant"

    breakdown = {
        "sample_size": total,
        "rows_reviewed_agree_column": n_agree_reviewed,
        "agree": agree_y, "disagree": agree_n,
        "agree_rate_pct": agree_pct,
        "is_relevant_agreement_pct": rel_pct,
        "is_relevant_checked": rel_checked,
        "exploration_signal_agreement_pct": sig_pct,
        "exploration_signal_checked": sig_checked,
        "scored_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    return {"headline": headline, "breakdown": breakdown}


def write_into_validation(result: dict):
    if not os.path.exists(VALIDATION_JSON):
        log.error("No %s — run validate.py first.", VALIDATION_JSON)
        return
    with open(VALIDATION_JSON, encoding="utf-8") as f:
        v = json.load(f)
    v.setdefault("manual_check", {})
    v["manual_check"]["accuracy_rate"] = result["headline"]
    v["manual_check"]["accuracy_breakdown"] = result["breakdown"]
    with open(VALIDATION_JSON, "w", encoding="utf-8") as f:
        json.dump(v, f, indent=2, ensure_ascii=False)
    log.info("Wrote accuracy_rate = %s into %s", result["headline"], VALIDATION_JSON)


if __name__ == "__main__":
    res = score()
    if res:
        b = res["breakdown"]
        log.info("Manual-check accuracy: %s", res["headline"])
        log.info("  AGREE column: %d agree / %d disagree (%s%%)",
                 b["agree"], b["disagree"], b["agree_rate_pct"])
        log.info("  is_relevant agreement: %s%% (%d checked)",
                 b["is_relevant_agreement_pct"], b["is_relevant_checked"])
        log.info("  exploration_signal agreement: %s%% (%d checked)",
                 b["exploration_signal_agreement_pct"], b["exploration_signal_checked"])
        write_into_validation(res)
        print("\n✅ Done. Commit data/validation.json and push so the dashboard updates.")
    else:
        print("\nNothing scored. Fill the HUMAN_/AGREE columns in "
              "data/validation_sample.csv, then re-run.")
