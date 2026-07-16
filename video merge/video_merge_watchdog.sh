#!/bin/sh
# 22:05 运行：如果 22:00 视频合并任务没有写入启动标记，则主动报警。

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/notify.sh"

TODAY=$(date +%Y%m%d)
STATE_DIR="${VIDEO_MERGE_STATE_DIR:-/tmp/nas-video-merge-state}"
START_MARKER="${STATE_DIR}/${TODAY}.started"
ALERT_MARKER="${STATE_DIR}/${TODAY}.start-alerted"

mkdir -p "$STATE_DIR"

if [ -f "$START_MARKER" ]; then
    echo "[watchdog] 今日视频合并任务已启动"
    exit 0
fi

if [ -f "$ALERT_MARKER" ]; then
    echo "[watchdog] 今日未启动报警已发送，跳过重复通知"
    exit 0
fi

if pushover_notify "Video Merge" "🚨 视频合并任务未按时启动 | ${TODAY}
计划时间: 22:00
检查时间: $(date '+%H:%M')
请检查 cron、flock、Docker 与 NAS 状态" 1; then
    : > "$ALERT_MARKER"
fi

