#!/bin/bash
# Poll the producer-owned Study ready manifest, then create one local candidate.
# This script never submits to Emma Focus and never receives the parent PIN.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
DATE_SELECTOR="${1:-today}"
if [ "$DATE_SELECTOR" = "today" ]; then
  DATE_VALUE="$(date +%Y-%m-%d)"
elif [[ "$DATE_SELECTOR" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  DATE_VALUE="$DATE_SELECTOR"
else
  echo "❌ Date must be today or YYYY-MM-DD: $DATE_SELECTOR" >&2
  exit 2
fi
DATE_COMPACT="$(printf '%s' "$DATE_VALUE" | tr -d '-')"

: "${EMMA_VIDEO_DIR:?Set EMMA_VIDEO_DIR to the study-room exported-video directory}"
: "${EMMA_REVIEW_MODEL:?Set EMMA_REVIEW_MODEL to the local vision model directory}"

VENV_PY="${EMMA_REVIEW_PYTHON:-$PROJECT_ROOT/.venv-emma-review/bin/python3}"
WAIT_SECONDS="${EMMA_REVIEW_WAIT_SECONDS:-5400}"
POLL_SECONDS="${EMMA_REVIEW_POLL_SECONDS:-60}"
OUTPUT_ROOT="${EMMA_REVIEW_OUTPUT_ROOT:-$EMMA_VIDEO_DIR/.emma-review}"
RESULT="$OUTPUT_ROOT/$DATE_VALUE/result_pipeline.json"
SOURCE_VIDEO="$EMMA_VIDEO_DIR/Study_${DATE_COMPACT}.mp4"
READY_REPORT="${TMPDIR:-/tmp}/emma-ready-${DATE_COMPACT}.json"
STARTED_AT="$(date +%s)"

notify_parent() {
  title="$1"
  message="$2"
  priority="${3:-0}"
  if [ "${EMMA_REVIEW_PUSHOVER:-1}" != "1" ]; then
    return 0
  fi
  PUSHOVER_ENV_FILE="$PROJECT_ROOT/video merge/.env"
  export PUSHOVER_ENV_FILE
  # shellcheck source=/dev/null
  . "$PROJECT_ROOT/video merge/notify.sh"
  pushover_notify "$title" "$message" "$priority" "${EMMA_REVIEW_SOUND:-}" || {
    echo "⚠️ Candidate state is valid, but Pushover delivery failed." >&2
    return 0
  }
}

case "$WAIT_SECONDS:$POLL_SECONDS" in
  *[!0-9:]*|0:*|*:0)
    echo "❌ Wait and poll values must be positive integer seconds." >&2
    exit 2
    ;;
esac

echo "⏳ Waiting for Study_${DATE_COMPACT}.ready.json (up to ${WAIT_SECONDS}s)..."
while ! "$VENV_PY" "$PROJECT_ROOT/skills/emma-review/scripts/emma_review.py" \
  ready "$DATE_VALUE" --video-dir "$EMMA_VIDEO_DIR" >"$READY_REPORT" 2>&1; do
  elapsed=$(( $(date +%s) - STARTED_AT ))
  if [ "$elapsed" -ge "$WAIT_SECONDS" ]; then
    last_reason="$(tail -n 1 "$READY_REPORT" 2>/dev/null || true)"
    notify_parent "Emma Review 未启动" \
      "⚠️ ${DATE_VALUE} 书房视频在 22:30–00:00 内未 ready。请检查 Video Merge 或挂载。${last_reason:+\n$last_reason}" 1
    echo "❌ Timed out waiting for producer-confirmed ready manifest." >&2
    exit 1
  fi
  sleep "$POLL_SECONDS"
done

if "$VENV_PY" "$PROJECT_ROOT/skills/emma-review/scripts/emma_review.py" \
  candidate-status "$RESULT" --video "$SOURCE_VIDEO" \
  --expected-date "$DATE_VALUE" >/dev/null 2>&1; then
  echo "✅ Matching pending_review candidate already exists; skipping analysis."
  exit 0
fi

export EMMA_REVIEW_OUTPUT_ROOT="$OUTPUT_ROOT"
if bash "$PROJECT_ROOT/run_tonight.sh" "$DATE_VALUE"; then
  summary="$($VENV_PY "$PROJECT_ROOT/skills/emma-review/scripts/emma_review.py" \
    summary "$RESULT" --expected-date "$DATE_VALUE")"
  notify_parent "Emma Review 待审核" \
    "✅ ${DATE_VALUE} 书房候选分析完成\n${summary}\n状态：待家长复核，未自动入库" 0
  echo "✅ $summary"
else
  status=$?
  notify_parent "Emma Review 分析失败" \
    "❌ ${DATE_VALUE} 书房视频已 ready，但候选分析失败（exit=${status}）。生产数据未修改。" 1
  exit "$status"
fi
