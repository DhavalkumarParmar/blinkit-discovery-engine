#!/usr/bin/env bash
# End-to-end pipeline runner for the Blinkit Category-Exploration Discovery Engine.
#
# Usage:
#   ./run_all.sh                 # analysis only (merge → tag → synth → validate → excel)
#   ./run_all.sh --scrape        # also re-scrape all sources first (slow, hits quotas)
#   TAG_LIMIT=800 ./run_all.sh   # tag more items (default 400; resumable across runs)
#
# Reads keys from .env. Safe to re-run: scraping dedupes, tagging skips already-tagged
# ids. Prints an estimated request count before the LLM-heavy steps.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-.venv/bin/python}"
[ -x "$PY" ] || PY="python3"
TAG_LIMIT="${TAG_LIMIT:-400}"

echo "════════════════════════════════════════════════════════════"
echo " Blinkit Discovery Engine — full pipeline"
echo " python: $PY | tag limit: $TAG_LIMIT"
echo "════════════════════════════════════════════════════════════"

if [ "${1:-}" = "--scrape" ]; then
  echo "▶ Scraping all sources (App Store, Play Store, Reddit, YouTube, forums)…"
  echo "  ⚠ YouTube uses ~1,100 of 10,000 daily quota units; others are keyless."
  $PY -m scrapers.app_store --pages 10
  $PY -m scrapers.play_store --max 500
  $PY -m scrapers.reddit
  $PY -m scrapers.youtube
  $PY -m scrapers.complaint_forums
fi

echo "▶ [1/5] Merging raw sources → data/merged.jsonl"
$PY merge.py

MERGED=$($PY -c "from common import read_jsonl; print(len(read_jsonl('data/merged.jsonl')))")
N_BATCH=$(( (TAG_LIMIT + 7) / 8 ))
echo "▶ [2/5] Pass 1 tagging (limit $TAG_LIMIT of $MERGED merged items)"
echo "  ⚠ QUOTA: ~$N_BATCH LLM requests. Groq free tier ≈100k tokens/day PER MODEL;"
echo "    the client rotates models + falls back to Gemini. Resumable if it stops."
$PY pass1_tag.py --limit "$TAG_LIMIT" --yes

echo "▶ [3/5] Pass 2 synthesis (1 LLM request)"
$PY pass2_synthesize.py

echo "▶ [4/5] Validation + human-check sample"
$PY validate.py

echo "▶ [5/5] Excel export + run metadata"
$PY export_excel.py
$PY -c "from pipeline import _write_metadata; _write_metadata()"

echo "════════════════════════════════════════════════════════════"
echo " ✅ Done. Outputs in data/:"
echo "   synthesis.json/.md · validation.json · validation_sample.csv"
echo "   blinkit_review_analysis.xlsx · last_run_metadata.json"
echo " Launch the dashboard:  streamlit run app.py"
echo "════════════════════════════════════════════════════════════"
