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

echo ""
echo "============================================="
echo " 🚀 V2 监控视频合并开始 | $(date)"
echo "============================================="

echo ""
echo "⏳ 重启 tdarr_node 容器..."
docker restart tdarr_node 2>&1
sleep 10

echo "⏳ 清理容器临时文件..."
docker exec tdarr_node sh -c 'rm -rf /tmp/* 2>/dev/null; mkdir -p /tmp' 2>&1
echo "✅ 临时文件已清理"
echo ""

START_TS=$(date +%s)
TODAY=$(date +%Y%m%d)
ALL_SUCCESS=0
ALL_FAIL=0

pushover_notify "Video Merge V2" "🚀 V2 合并开始 | ${TODAY}"

# ----- 定义摄像头列表 -----
# 格式：CAMERA_NAME:SOURCE_DIR:RES:CODEC
CAMERAS="Study:/mnt/source_study:2160:hevc_qsv"

for camera_config in $CAMERAS; do
    CAMERA=$(echo "$camera_config" | cut -d: -f1)
    SOURCE=$(echo "$camera_config" | cut -d: -f2)
    RES=$(echo "$camera_config" | cut -d: -f3)
    CODEC=$(echo "$camera_config" | cut -d: -f4)

    echo ""
    echo "▶️ 正在处理【${CAMERA}】..."
    CAMERA="$CAMERA" SOURCE="$SOURCE" RES="$RES" CODEC="$CODEC" sh "$SCRIPT_DIR/merge_v2.sh"
    EXIT_CODE=$?

    RESULT_FILE="${NAS_DATA}/export_videos/result_v2_${CAMERA}.json"
    if [ -f "$RESULT_FILE" ]; then
        eval "$(cat "$RESULT_FILE" | sed 's/[{}"]//g; s/,/ /g' | awk '{for(i=1;i<=NF;i++){split($i,a,":"); if(a[1]=="success") S=a[2]; if(a[1]=="fail") F=a[2]}} END {print "S="S"; F="F}')"
        ALL_SUCCESS=$((ALL_SUCCESS + S))
        ALL_FAIL=$((ALL_FAIL + F))
        rm -f "$RESULT_FILE"
    fi

    if [ $EXIT_CODE -ne 0 ]; then
        pushover_notify "Video Merge V2" "⚠️ ${CAMERA} 异常 | ${TODAY}"
    else
        pushover_notify "Video Merge V2" "✅ ${CAMERA} 完成 | ${TODAY}"
    fi
done

# ----- 总计 -----
END_TS=$(date +%s)
ELAPSED=$(( (END_TS - START_TS) / 60 ))

pushover_notify "Video Merge V2" "🎉 V2 全部完成 | ${TODAY}
成功: ${ALL_SUCCESS}✅ 失败: ${ALL_FAIL}❌
耗时: ${ELAPSED}分钟"

echo ""
echo "============================================="
echo " ✅ V2 全部完成！"
echo "    成功: ${ALL_SUCCESS} / 失败: ${ALL_FAIL}"
echo "    耗时: ${ELAPSED}分钟"
echo "============================================="