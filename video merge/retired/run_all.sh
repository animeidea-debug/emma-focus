#!/bin/sh

# ==============================================================================
# 🚀 极空间监控合并总控脚本：串行排队执行
#
# crontab 22:45（由 root 配置）：
#   45 22 * * * /tmp/zfsv3/nvme14/13918962622/data/scripts/run_all.sh
#
# 执行顺序：
#   [1/2] 书房主机位（小米）720P
#   [2/2] 客厅 4K
#
# 可配置环境变量：
#   XIAOMI_RES       — 书房主机位分辨率 (默认 720)
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

# ========== 容器重启 + 临时文件清理 ==========
echo ""
echo "⏳ 重启 tdarr_node 容器（清除残留进程 + 新 volume mapping 生效）..."
docker restart tdarr_node 2>&1
if [ $? -eq 0 ]; then
    echo "✅ 容器重启成功"
else
    echo "⚠️ 容器重启失败，继续执行..."
fi
sleep 10

echo "⏳ 清理容器临时文件..."
docker exec tdarr_node sh -c 'rm -rf /tmp/* 2>/dev/null; mkdir -p /tmp' 2>&1
echo "✅ 临时文件已清理"
echo ""

START_TS=$(date +%s)
TODAY=$(date +%Y%m%d)

echo "================================================="
echo " 🚀 开始执行监控视频自动合并任务 | $(date)"
echo "================================================="

# ----- 辅助函数：读取进度文件并发送通知 -----
read_progress_and_notify() {
    CAMERA_NAME="$1"
    PROGRESS_FILE="$2"
    EXIT_CODE="$3"
    PREFIX="$4"  # 1/2 or 2/2

    TOTAL=0; DONE=0; SUCCESS=0; FAIL=0; CURRENT=""
    if [ -f "$PROGRESS_FILE" ]; then
        eval "$(cat "$PROGRESS_FILE" 2>/dev/null | sed 's/^/export /')"
        rm -f "$PROGRESS_FILE"
    fi
    # 也读 result JSON
    if [ "$CAMERA_NAME" = "书房主机位" ] && [ -f "${NAS_DATA}/export_videos/result_xiaomi.json" ]; then
        eval "$(cat ${NAS_DATA}/export_videos/result_xiaomi.json | sed 's/[{}"]//g; s/,/ /g' | awk '{for(i=1;i<=NF;i++){split($i,a,":"); if(a[1]=="success") XS=a[2]; if(a[1]=="fail") XF=a[2]}} END {print "SUCCESS="XS"; FAIL="XF}')"
        rm -f "${NAS_DATA}/export_videos/result_xiaomi.json"
    fi
    if [ "$CAMERA_NAME" = "客厅" ] && [ -f "${NAS_DATA}/export_videos_livingroom/result_livingroom.json" ]; then
        eval "$(cat ${NAS_DATA}/export_videos_livingroom/result_livingroom.json | sed 's/[{}"]//g; s/,/ /g' | awk '{for(i=1;i<=NF;i++){split($i,a,":"); if(a[1]=="success") LS=a[2]; if(a[1]=="fail") LF=a[2]}} END {print "SUCCESS="LS"; FAIL="LF}')"
        rm -f "${NAS_DATA}/export_videos_livingroom/result_livingroom.json"
    fi

    if [ $EXIT_CODE -ne 0 ]; then
        pushover_notify "Video Merge" "⚠️ [${PREFIX}] ${CAMERA_NAME} 异常 | ${TODAY}
成功: ${SUCCESS:-0} 天 ✅ | 失败: ${FAIL:-0} 天 ❌"
    elif [ "${TOTAL:-0}" -eq 0 ]; then
        pushover_notify "Video Merge" "✅ [${PREFIX}] ${CAMERA_NAME} 完成 | ${TODAY}
无需处理（全部已有成品）"
    else
        pushover_notify "Video Merge" "✅ [${PREFIX}] ${CAMERA_NAME} 完成 | ${TODAY}
成功: ${SUCCESS:-0}/${TOTAL} 天 ✅
失败: ${FAIL:-0} 天 ❌
最后处理: ${CURRENT:-}"
    fi
}

pushover_notify "Video Merge" "🚀 监控视频合并开始 | ${TODAY}
设备: 书房主机位(${XIAOMI_RES:-720}P) + 客厅(${LIVINGROOM_RES:-2160}P)"

# ========== [1/2] 书房主机位（小米）==========
echo ""
echo "▶️ [1/2] 正在启动【书房主机位】合并任务..."
sh "$SCRIPT_DIR/auto_merge.sh"
XIAOMI_EXIT=$?
XIAOMI_SUCCESS=0; XIAOMI_FAIL=0

# 从容器中读取进度文件
docker exec tdarr_node sh -c 'cat /mnt/export_videos/progress_xiaomi.txt' > /tmp/progress_xiaomi_read.txt 2>/dev/null || true
read_progress_and_notify "书房主机位" "/tmp/progress_xiaomi_read.txt" "$XIAOMI_EXIT" "1/2"
# 从进度文件中提取具体数字给汇总用
if [ -f "/tmp/progress_xiaomi_read.txt" ]; then
    eval "$(cat /tmp/progress_xiaomi_read.txt 2>/dev/null | awk -F= '{print "XIAOMI_SUCCESS="$2}' | head -3)"
    rm -f /tmp/progress_xiaomi_read.txt
fi

# ========== [2/2] 客厅 4K ==========
echo ""
echo "▶️ [2/2] 正在启动【客厅】合并任务..."
sh "$SCRIPT_DIR/livingroom_auto_merge.sh"
LIVINGROOM_EXIT=$?
LR_SUCCESS=0; LR_FAIL=0

docker exec tdarr_node sh -c 'cat /mnt/export_videos_livingroom/progress_livingroom.txt' > /tmp/progress_livingroom_read.txt 2>/dev/null || true
read_progress_and_notify "客厅" "/tmp/progress_livingroom_read.txt" "$LIVINGROOM_EXIT" "2/2"
if [ -f "/tmp/progress_livingroom_read.txt" ]; then
    eval "$(cat /tmp/progress_livingroom_read.txt 2>/dev/null | awk -F= '{print "LR_SUCCESS="$2}' | head -3)"
    rm -f /tmp/progress_livingroom_read.txt
fi

# 后备：从 result JSON 读取（进度文件不存在时）
if [ $XIAOMI_SUCCESS -eq 0 ] && [ $XIAOMI_FAIL -eq 0 ]; then
    if [ -f "${NAS_DATA}/export_videos/result_xiaomi.json" ]; then
        eval "$(cat ${NAS_DATA}/export_videos/result_xiaomi.json | sed 's/[{}"]//g; s/,/ /g' | awk '{for(i=1;i<=NF;i++){split($i,a,":"); if(a[1]=="success") XS=a[2]; if(a[1]=="fail") XF=a[2]}} END {print "XIAOMI_SUCCESS="XS"; XIAOMI_FAIL="XF}')"
        rm -f "${NAS_DATA}/export_videos/result_xiaomi.json"
    fi
fi
if [ $LR_SUCCESS -eq 0 ] && [ $LR_FAIL -eq 0 ]; then
    if [ -f "${NAS_DATA}/export_videos_livingroom/result_livingroom.json" ]; then
        eval "$(cat ${NAS_DATA}/export_videos_livingroom/result_livingroom.json | sed 's/[{}"]//g; s/,/ /g' | awk '{for(i=1;i<=NF;i++){split($i,a,":"); if(a[1]=="success") LS=a[2]; if(a[1]=="fail") LF=a[2]}} END {print "LR_SUCCESS="LS"; LR_FAIL="LF}')"
        rm -f "${NAS_DATA}/export_videos_livingroom/result_livingroom.json"
    fi
fi

# ========== 总计 ==========
END_TS=$(date +%s)
ELAPSED_MIN=$(( (END_TS - START_TS) / 60 ))
ELAPSED_SEC=$(( (END_TS - START_TS) % 60 ))
TOTAL_SUCCESS=$(( XIAOMI_SUCCESS + LR_SUCCESS ))
TOTAL_FAIL=$(( XIAOMI_FAIL + LR_FAIL ))

pushover_notify "Video Merge" "🎉 全部完成 | ${TODAY}
书房主机位: ${XIAOMI_SUCCESS}✅ ${XIAOMI_FAIL}❌
客厅: ${LR_SUCCESS}✅ ${LR_FAIL}❌
总计: ${TOTAL_SUCCESS}✅ ${TOTAL_FAIL}❌
耗时: ${ELAPSED_MIN}分${ELAPSED_SEC}秒"

echo ""
echo "✅ 所有监控视频延时处理全部完毕！"
echo "🎉 结束时间: $(date) | 总耗时: ${ELAPSED_MIN}m${ELAPSED_SEC}s"
echo "📊 书房主机位: 成功 ${XIAOMI_SUCCESS} / 失败 ${XIAOMI_FAIL}"
echo "📊 客厅: 成功 ${LR_SUCCESS} / 失败 ${LR_FAIL}"
echo "================================================="