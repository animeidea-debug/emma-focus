#!/bin/sh

# ==============================================================================
# 🚀 极空间监控合并总控脚本：串行排队执行
#
# crontab 22:45（由 root 配置）：
#   45 22 * * * /tmp/zfsv3/nvme14/13918962622/data/scripts/run_all.sh
#
# 执行顺序：
#   [1/3] 书房主机位（小米）720P
#   [2/3] 书房辅机位（萤石）1080P
#   [3/3] 客厅 4K
#
# 可配置环境变量：
#   XIAOMI_RES       — 书房主机位分辨率 (默认 720)
#   YINGSHI_RES      — 书房辅机位分辨率 (默认 1080)
#   LIVINGROOM_RES   — 客厅分辨率 (默认 2160)
#   MAX_LOG_SIZE     — 日志轮转阈值 (默认 10485760)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/notify.sh"

# NAS 数据根目录
NAS_DATA="/tmp/zfsv3/nvme14/13918962622/data"

# ----- 自检：检查 .env 是否存在（仅警告，notify.sh 内置缺省凭证）-----
if [ ! -f "${SCRIPT_DIR}/.env" ]; then
    echo "[WARN] .env 文件缺失，将使用 notify.sh 内置缺省凭证（与 .env.example 相同）" >&2
fi

START_TS=$(date +%s)
TODAY=$(date +%Y%m%d)

echo "================================================="
echo " 🚀 开始执行监控视频自动合并任务 | $(date)"
echo "================================================="

pushover_notify "Video Merge" "🚀 监控视频合并开始 | ${TODAY}
设备: 书房主机位(${XIAOMI_RES:-720}P) + 书房辅机位(${YINGSHI_RES:-1080}P) + 客厅(${LIVINGROOM_RES:-2160}P)"

# ========== [1/3] 书房主机位（小米）==========
echo ""
echo "▶️ [1/3] 正在启动【书房主机位】合并任务..."
sh "$SCRIPT_DIR/auto_merge.sh"
XIAOMI_EXIT=$?

XIAOMI_SUCCESS=0; XIAOMI_FAIL=0
if [ -f "${NAS_DATA}/export_videos/result_xiaomi.json" ]; then
    eval "$(cat ${NAS_DATA}/export_videos/result_xiaomi.json | sed 's/[{}"]//g; s/,/ /g' | awk '{for(i=1;i<=NF;i++){split($i,a,":"); if(a[1]=="success") XS=a[2]; if(a[1]=="fail") XF=a[2]}} END {print "XIAOMI_SUCCESS="XS"; XIAOMI_FAIL="XF}')"
    rm -f "${NAS_DATA}/export_videos/result_xiaomi.json"
fi

if [ $XIAOMI_EXIT -ne 0 ]; then
    pushover_notify "Video Merge" "⚠️ 书房主机位合并异常 | ${TODAY}
成功: ${XIAOMI_SUCCESS} 天 | 失败: ${XIAOMI_FAIL} 天"
else
    pushover_notify "Video Merge" "✅ 书房主机位合并完成 | ${TODAY}
成功: ${XIAOMI_SUCCESS} 天 | 失败: ${XIAOMI_FAIL} 天"
fi

# ========== [2/3] 书房辅机位（萤石）==========
echo ""
echo "▶️ [2/3] 正在启动【书房辅机位】合并任务..."
sh "$SCRIPT_DIR/yingshi_auto_merge.sh"
YINGSHI_EXIT=$?

YINGSHI_SUCCESS=0; YINGSHI_FAIL=0
if [ -f "${NAS_DATA}/export_videos_yingshi/result_yingshi.json" ]; then
    eval "$(cat ${NAS_DATA}/export_videos_yingshi/result_yingshi.json | sed 's/[{}"]//g; s/,/ /g' | awk '{for(i=1;i<=NF;i++){split($i,a,":"); if(a[1]=="success") YS=a[2]; if(a[1]=="fail") YF=a[2]}} END {print "YINGSHI_SUCCESS="YS"; YINGSHI_FAIL="YF}')"
    rm -f "${NAS_DATA}/export_videos_yingshi/result_yingshi.json"
fi

if [ $YINGSHI_EXIT -ne 0 ]; then
    pushover_notify "Video Merge" "⚠️ 书房辅机位合并异常 | ${TODAY}
成功: ${YINGSHI_SUCCESS} 天 | 失败: ${YINGSHI_FAIL} 天"
else
    pushover_notify "Video Merge" "✅ 书房辅机位合并完成 | ${TODAY}
成功: ${YINGSHI_SUCCESS} 天 | 失败: ${YINGSHI_FAIL} 天"
fi

# ========== [3/3] 客厅 4K ==========
echo ""
echo "▶️ [3/3] 正在启动【客厅】合并任务..."
sh "$SCRIPT_DIR/livingroom_auto_merge.sh"
LIVINGROOM_EXIT=$?

LR_SUCCESS=0; LR_FAIL=0
if [ -f "${NAS_DATA}/export_videos_livingroom/result_livingroom.json" ]; then
    eval "$(cat ${NAS_DATA}/export_videos_livingroom/result_livingroom.json | sed 's/[{}"]//g; s/,/ /g' | awk '{for(i=1;i<=NF;i++){split($i,a,":"); if(a[1]=="success") LS=a[2]; if(a[1]=="fail") LF=a[2]}} END {print "LR_SUCCESS="LS"; LR_FAIL="LF}')"
    rm -f "${NAS_DATA}/export_videos_livingroom/result_livingroom.json"
fi

if [ $LIVINGROOM_EXIT -ne 0 ]; then
    pushover_notify "Video Merge" "⚠️ 客厅4K合并异常 | ${TODAY}
成功: ${LR_SUCCESS} 天 | 失败: ${LR_FAIL} 天"
else
    pushover_notify "Video Merge" "✅ 客厅4K合并完成 | ${TODAY}
成功: ${LR_SUCCESS} 天 | 失败: ${LR_FAIL} 天"
fi

# ========== 总计 ==========
END_TS=$(date +%s)
ELAPSED_MIN=$(( (END_TS - START_TS) / 60 ))
ELAPSED_SEC=$(( (END_TS - START_TS) % 60 ))
TOTAL_SUCCESS=$(( XIAOMI_SUCCESS + YINGSHI_SUCCESS + LR_SUCCESS ))
TOTAL_FAIL=$(( XIAOMI_FAIL + YINGSHI_FAIL + LR_FAIL ))

pushover_notify "Video Merge" "🎉 全部完成 | ${TODAY}
书房主机位: ${XIAOMI_SUCCESS}✅ ${XIAOMI_FAIL}❌
书房辅机位: ${YINGSHI_SUCCESS}✅ ${YINGSHI_FAIL}❌
客厅: ${LR_SUCCESS}✅ ${LR_FAIL}❌
总计: ${TOTAL_SUCCESS}✅ ${TOTAL_FAIL}❌
耗时: ${ELAPSED_MIN}分${ELAPSED_SEC}秒"

echo ""
echo "✅ 所有监控视频延时处理全部完毕！"
echo "🎉 结束时间: $(date) | 总耗时: ${ELAPSED_MIN}m${ELAPSED_SEC}s"
echo "📊 书房主机位: 成功 ${XIAOMI_SUCCESS} / 失败 ${XIAOMI_FAIL}"
echo "📊 书房辅机位: 成功 ${YINGSHI_SUCCESS} / 失败 ${YINGSHI_FAIL}"
echo "📊 客厅: 成功 ${LR_SUCCESS} / 失败 ${LR_FAIL}"
echo "================================================="