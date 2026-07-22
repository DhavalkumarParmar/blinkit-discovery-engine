"""Pipeline runner + process-global run state (used by the admin re-run tab).

State lives at MODULE level (imported once, not re-executed on Streamlit reruns)
so it is process-global, shared across all sessions/reruns — not session-scoped.

Each step is a subprocess that logs to data/pipeline.log through the shared
logger, so the admin tab just tails that file for a live view.
"""

import datetime as dt
import json
import os
import subprocess
import sys
import threading

from common import DATA_DIR, PROJECT_ROOT, get_logger

log = get_logger("pipeline")

METADATA_PATH = os.path.join(DATA_DIR, "last_run_metadata.json")

# Process-global state (NOT st.session_state).
PIPELINE_STATE: dict = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "current_step": None,
    "steps_done": [],
    "returncode": None,
    "error": None,
}
_LOCK = threading.Lock()

# Analysis steps (scraping is optional and slow, so it's off by default).
SCRAPE_STEPS = [
    ("scrape app store", [sys.executable, "-m", "scrapers.app_store", "--pages", "10"]),
    ("scrape play store", [sys.executable, "-m", "scrapers.play_store", "--max", "500"]),
    ("scrape reddit", [sys.executable, "-m", "scrapers.reddit"]),
    ("scrape youtube", [sys.executable, "-m", "scrapers.youtube"]),
    ("probe forums", [sys.executable, "-m", "scrapers.complaint_forums"]),
]


def analysis_steps(tag_limit: int) -> list:
    return [
        ("merge", [sys.executable, "merge.py"]),
        ("pass 1 tag", [sys.executable, "pass1_tag.py", "--limit", str(tag_limit), "--yes"]),
        ("pass 2 synthesize", [sys.executable, "pass2_synthesize.py"]),
        ("validate", [sys.executable, "validate.py"]),
        ("excel export", [sys.executable, "export_excel.py"]),
        ("findings report", [sys.executable, "export_report.py"]),
        ("findings pdf", [sys.executable, "export_pdf.py"]),
    ]


def _run_steps(steps: list):
    try:
        for name, cmd in steps:
            with _LOCK:
                PIPELINE_STATE["current_step"] = name
            log.info("=== pipeline step: %s ===", name)
            proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
            if proc.returncode != 0:
                log.error("Step %s FAILED (rc=%d): %s", name, proc.returncode,
                          (proc.stderr or proc.stdout)[-400:])
                with _LOCK:
                    PIPELINE_STATE["returncode"] = proc.returncode
                    PIPELINE_STATE["error"] = f"{name} failed"
                return
            with _LOCK:
                PIPELINE_STATE["steps_done"].append(name)
        with _LOCK:
            PIPELINE_STATE["returncode"] = 0
        _write_metadata()
        log.info("=== pipeline complete ===")
    finally:
        with _LOCK:
            PIPELINE_STATE["running"] = False
            PIPELINE_STATE["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            PIPELINE_STATE["current_step"] = None


def start_pipeline(scrape: bool = False, tag_limit: int = 400) -> bool:
    """Start the pipeline in a background thread. Returns False if already running."""
    with _LOCK:
        if PIPELINE_STATE["running"]:
            return False
        PIPELINE_STATE.update({"running": True, "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                               "finished_at": None, "current_step": None, "steps_done": [],
                               "returncode": None, "error": None})
    steps = (SCRAPE_STEPS if scrape else []) + analysis_steps(tag_limit)
    threading.Thread(target=_run_steps, args=(steps,), daemon=True).start()
    return True


def _write_metadata():
    """Write data/last_run_metadata.json from whatever result files exist."""
    from common import read_jsonl
    meta = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "per_source": {}}
    merged = read_jsonl(os.path.join(DATA_DIR, "merged.jsonl"))
    tagged = read_jsonl(os.path.join(DATA_DIR, "tagged.jsonl"))
    for it in merged:
        meta["per_source"][it["source"]] = meta["per_source"].get(it["source"], 0) + 1
    meta["total_merged"] = len(merged)
    meta["total_tagged"] = len(tagged)
    models = {}
    for it in tagged:
        m = it.get("tagged_by") or "unknown"
        models[m] = models.get(m, 0) + 1
    meta["tagged_by_model"] = models
    synth_path = os.path.join(DATA_DIR, "synthesis.json")
    if os.path.exists(synth_path):
        with open(synth_path, encoding="utf-8") as f:
            meta["llm_stats"] = json.load(f).get("llm_stats", {})
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return meta


if __name__ == "__main__":
    # CLI: run the analysis pipeline synchronously (no threads) — used by run_all.sh.
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scrape", action="store_true")
    ap.add_argument("--tag-limit", type=int, default=400)
    args = ap.parse_args()
    _run_steps((SCRAPE_STEPS if args.scrape else []) + analysis_steps(args.tag_limit))
