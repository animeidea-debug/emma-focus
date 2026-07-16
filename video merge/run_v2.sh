#!/bin/sh
# ==============================================================================
# 🚀 新一代监控合并总控脚本
#
# 按顺序处理各摄像头，串行执行。
# 输出到 /mnt/export_videos/{CAMERA}_{YYYYMMDD}.mp4
#
# 用法：sh run_v2.sh
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/notify.sh"

NAS_DATA="/tmp/zfsv3/nvme14/13918962622/data"
STATE_DIR="${VIDEO_MERGE_STATE_DIR:-/tmp/nas-video-merge-state}"
TODAY=$(date +%Y%m%d)
START_TS=$(date +%s)

mkdir -p "$STATE_DIR"

echo ""
echo "============================================="
echo " 🚀 V2 监控视频合并开始 | $(date)"
echo "============================================="

echo ""
echo "⏳ 重启 tdarr_node 容器..."
if ! docker restart tdarr_node 2>&1; then
    pushover_notify "Video Merge" "🚨 视频合并启动失败 | ${TODAY}
阶段: 重启 tdarr_node
请立即检查 Docker/NAS" 1 siren || true
    exit 1
fi
sleep 10

echo "⏳ 清理容器临时文件..."
if ! docker exec tdarr_node sh -c 'rm -rf /tmp/* 2>/dev/null; mkdir -p /tmp' 2>&1; then
    pushover_notify "Video Merge" "🚨 视频合并启动失败 | ${TODAY}
阶段: 清理 tdarr_node 临时目录" 1 siren || true
    exit 1
fi
echo "✅ 临时文件已清理"
echo ""

ALL_SUCCESS=0
ALL_FAIL=0

: > "${STATE_DIR}/${TODAY}.started"
rm -f "${STATE_DIR}/${TODAY}.start-alerted"
pushover_notify "Video Merge" "🚀 视频合并总任务已启动 | ${TODAY}
计划: 书房 → 客厅
tdarr_node 已重启并完成临时目录清理" 0 pushover || true

# ----- 定义摄像头列表 -----
# 格式：CAMERA_NAME:SOURCE_DIR:RES:CODEC:MAX_HOUR:SPEED:LABEL
CAMERAS="Study:/mnt/source_study:720:hevc_qsv:21:30:书房 LivingRoom:/mnt/source_videos_livingroom:2160:hevc_qsv:23:15:客厅"

for camera_config in $CAMERAS; do
    CAMERA=$(echo "$camera_config" | cut -d: -f1)
    SOURCE=$(echo "$camera_config" | cut -d: -f2)
    RES=$(echo "$camera_config" | cut -d: -f3)
    CODEC=$(echo "$camera_config" | cut -d: -f4)
    MAX_HOUR=$(echo "$camera_config" | cut -d: -f5)
    SPEED=$(echo "$camera_config" | cut -d: -f6)
    LABEL=$(echo "$camera_config" | cut -d: -f7)
    CAMERA_START_TS=$(date +%s)

    echo ""
    echo "▶️ 正在处理【${LABEL}】(${SPEED}x 白昼 09-${MAX_HOUR}时)..."

    if ! docker exec tdarr_node sh -c "test -d '$SOURCE' && command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null && find '$SOURCE' -maxdepth 1 -type f -name '*.mp4' | grep -q ."; then
        echo "❌ ${LABEL} 启动前检查失败"
        ALL_FAIL=$((ALL_FAIL + 1))
        pushover_notify "Video Merge" "🚨 ${LABEL}视频未能启动 | ${TODAY}
检查项: 源目录、MP4 输入、ffmpeg/ffprobe
请检查摄像头挂载与 tdarr_node" 1 siren || true
        continue
    fi

    pushover_notify "Video Merge" "▶️ ${LABEL}视频合并已启动 | ${TODAY}
源: ${CAMERA}
参数: ${RES}p / ${SPEED}x / 截止 ${MAX_HOUR}:00" 0 pushover || true

    CAMERA="$CAMERA" SOURCE="$SOURCE" RES="$RES" CODEC="$CODEC" MAX_HOUR="$MAX_HOUR" SPEED="$SPEED" CAMERA_LABEL="$LABEL" sh "$SCRIPT_DIR/merge_v2.sh"
    EXIT_CODE=$?

    RESULT_FILE="${NAS_DATA}/export_videos/result_v2_${CAMERA}.json"
    S=0
    F=0
    if [ -f "$RESULT_FILE" ]; then
        eval "$(cat "$RESULT_FILE" | sed 's/[{}"]//g; s/,/ /g' | awk '{for(i=1;i<=NF;i++){split($i,a,":"); if(a[1]=="success") S=a[2]; if(a[1]=="fail") F=a[2]}} END {print "S="S"; F="F}')"
        rm -f "$RESULT_FILE"
    else
        F=1
    fi

    ALL_SUCCESS=$((ALL_SUCCESS + S))
    ALL_FAIL=$((ALL_FAIL + F))
    CAMERA_ELAPSED=$(( ($(date +%s) - CAMERA_START_TS) / 60 ))

    if [ $EXIT_CODE -ne 0 ] && [ "$F" -eq 0 ]; then
        F=1
        ALL_FAIL=$((ALL_FAIL + 1))
    fi

    if [ "$F" -gt 0 ] || [ $EXIT_CODE -ne 0 ]; then
        pushover_notify "Video Merge" "⚠️ ${LABEL}视频合并异常 | ${TODAY}
成功: ${S} 失败: ${F}
耗时: ${CAMERA_ELAPSED} 分钟
日志: merge_v2_${CAMERA}.log" 1 siren || true
    else
        pushover_notify "Video Merge" "✅ ${LABEL}视频合并完成 | ${TODAY}
成功: ${S} 失败: 0
耗时: ${CAMERA_ELAPSED} 分钟" 0 magic || true
    fi
done

# ----- 总计 -----
END_TS=$(date +%s)
ELAPSED=$(( (END_TS - START_TS) / 60 ))

: > "${STATE_DIR}/${TODAY}.finished"

if [ "$ALL_FAIL" -gt 0 ]; then
    pushover_notify "Video Merge" "⚠️ 视频合并部分失败 | ${TODAY}
成功: ${ALL_SUCCESS} 失败: ${ALL_FAIL}
总耗时: ${ELAPSED} 分钟
请检查摄像头通知与合并日志" 1 siren || true
    FINAL_EXIT=1
else
    pushover_notify "Video Merge" "🎉 视频合并全部完成 | ${TODAY}
成功: ${ALL_SUCCESS} 失败: 0
总耗时: ${ELAPSED} 分钟" 0 magic || true
    FINAL_EXIT=0
fi

echo ""
echo "============================================="
exit "$FINAL_EXIT"
echo " ✅ V2 全部完成！"
echo "    成功: ${ALL_SUCCESS} / 失败: ${ALL_FAIL}"
echo "    耗时: ${ELAPSED}分钟"
echo "============================================="
