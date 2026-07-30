#!/bin/bash
# Emma Review local candidate runner.
#
# Usage:
#   EMMA_VIDEO_DIR="/path/to/export_videos/书房" \
#   EMMA_REVIEW_MODEL="/path/to/Qwen2.5-VL-7B-Instruct-4bit" \
#   sh run_tonight.sh [YYYY-MM-DD]
#
# The source directory must contain both Study_YYYYMMDD.mp4 and its matching
# .ready/Study_YYYYMMDD.ready.json manifest. Historical videos are rejected by
# default; set EMMA_ALLOW_LEGACY_STABLE=1 only after parent confirmation.
#
# This script only produces a local pending_review candidate. It never receives
# a parent PIN and never writes to the production API or database.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
DATE_VALUE="${1:-$(date +%Y-%m-%d)}"
DATE_COMPACT="$(printf '%s' "$DATE_VALUE" | tr -d '-')"

: "${EMMA_VIDEO_DIR:?Set EMMA_VIDEO_DIR to the study-room exported-video directory}"
: "${EMMA_REVIEW_MODEL:?Set EMMA_REVIEW_MODEL to the local vision model directory}"

VENV_PY="${EMMA_REVIEW_PYTHON:-$PROJECT_ROOT/.venv-emma-review/bin/python3}"
CACHE_ROOT="${EMMA_REVIEW_CACHE_DIR:-/tmp/emma-tonight}"
OUTPUT_ROOT="${EMMA_REVIEW_OUTPUT_ROOT:-$CACHE_ROOT/.emma-review}"
SOURCE_VIDEO="$EMMA_VIDEO_DIR/Study_${DATE_COMPACT}.mp4"
SOURCE_READY="$EMMA_VIDEO_DIR/.ready/Study_${DATE_COMPACT}.ready.json"
LOCAL_VIDEO="$CACHE_ROOT/Study_${DATE_COMPACT}.mp4"
LOCAL_READY="$CACHE_ROOT/.ready/Study_${DATE_COMPACT}.ready.json"
OUTPUT_DIR="$OUTPUT_ROOT/$DATE_VALUE"
OUTPUT="$OUTPUT_DIR/result_pipeline.json"

if [ ! -x "$VENV_PY" ]; then
  echo "❌ Emma Review Python environment is not executable: $VENV_PY" >&2
  exit 1
fi

if [ ! -d "$EMMA_REVIEW_MODEL" ]; then
  echo "❌ Local model directory not found: $EMMA_REVIEW_MODEL" >&2
  exit 1
fi

if [ ! -f "$SOURCE_VIDEO" ]; then
  echo "❌ Ready video not found: $SOURCE_VIDEO" >&2
  exit 1
fi

ALLOW_LEGACY=0
if [ "${EMMA_ALLOW_LEGACY_STABLE:-0}" = "1" ]; then
  ALLOW_LEGACY=1
elif [ ! -f "$SOURCE_READY" ]; then
  echo "❌ Producer ready manifest not found: $SOURCE_READY" >&2
  echo "   Wait for Video Merge completion, or set EMMA_ALLOW_LEGACY_STABLE=1" >&2
  echo "   only for a parent-confirmed historical video." >&2
  exit 1
fi

mkdir -p "$CACHE_ROOT/.ready" "$OUTPUT_DIR"

if [ ! -f "$LOCAL_VIDEO" ] || [ "$SOURCE_VIDEO" -nt "$LOCAL_VIDEO" ]; then
  echo "📋 Copying video to local cache..."
  cp "$SOURCE_VIDEO" "$LOCAL_VIDEO"
fi

if [ "$ALLOW_LEGACY" -eq 0 ]; then
  cp "$SOURCE_READY" "$LOCAL_READY"
fi

PIPELINE_ARGS=(
  --date "$DATE_VALUE"
  --video "$LOCAL_VIDEO"
  --model "$EMMA_REVIEW_MODEL"
  --interval 4.0
  --resize 640
  --batch-size 5
  --similarity 0.95
  --max-similar-gap 12.0
  --mode describe
  --output "$OUTPUT"
)
if [ "$ALLOW_LEGACY" -eq 1 ]; then
  PIPELINE_ARGS+=(--allow-legacy-stable)
fi

echo "============================================================"
echo " Emma Review candidate — $DATE_VALUE"
echo "============================================================"
"$VENV_PY" "$PROJECT_ROOT/skills/emma-review/scripts/emma_pipeline.py" \
  "${PIPELINE_ARGS[@]}"

echo ""
echo "✅ Candidate created"
echo "   Result: $OUTPUT"
echo "   Review: ${OUTPUT%.json}.review.json"
echo "   Next: review and correct it in Admin; do not submit automatically."
