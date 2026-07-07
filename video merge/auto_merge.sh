#!/bin/sh

# ==============================================================================
# 🎥 小米摄像头 720P 30 倍速延时合并脚本
# 
# 功能：从容器内 /mnt/source_videos 读取原始 MP4 片段，
#       按日期聚合 → 筛选 09:00-22:59 白昼时段 → 校验 → ffmpeg 30 倍速合成
#
# 可配置变量（可在 run_all.sh 中 export 覆盖）：
#   XIAOMI_RES    — 输出分辨率 (默认 720)
#   MAX_LOG_SIZE  — 日志轮转阈值 (默认 10485760 = 10MB)
# ==============================================================================

# ---------- 可配置变量（可被外部 export 覆盖） ----------
XIAOMI_RES="${XIAOMI_RES:-720}"
MAX_LOG_SIZE="${MAX_LOG_SIZE:-10485760}"  # 10 MB

# 通过环境变量注入容器，避免双引号 sh -c 导致转义错误
docker exec -e XIAOMI_RES="$XIAOMI_RES" -e MAX_LOG_SIZE="$MAX_LOG_SIZE" -e TEST_MODE="$TEST_MODE" -e CAMERA_NAME="xiaomi" tdarr_node sh -c '
    SOURCE_BASE="/mnt/source_videos"
    EXPORT_DIR="/mnt/export_videos"
    if [ "$TEST_MODE" = "true" ]; then
        EXPORT_DIR="/mnt/export_videos_test/${CAMERA_NAME}"
    fi
    mkdir -p "$EXPORT_DIR"
    LOG_FILE="$EXPORT_DIR/merge_log.txt"

    # ----- 日志轮转：超过 10MB 自动重命名 -----
    if [ -f "$LOG_FILE" ]; then
        SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat --format=%s "$LOG_FILE" 2>/dev/null || echo 0)
        if [ "$SIZE" -gt "${MAX_LOG_SIZE}" ]; then
            mv "$LOG_FILE" "${LOG_FILE}.old"
            echo "[LOG_ROTATE] 日志超过 ${MAX_LOG_SIZE}B，已重命名为 merge_log.txt.old" > "$LOG_FILE"
        fi
    fi

    RESOLUTION="${XIAOMI_RES}"
    SCALE="${RESOLUTION}:${RESOLUTION}"
    echo "=== [Xiaomi] ${RESOLUTION}P-30x-白昼时段流水线启动: $(date) ===" >> "$LOG_FILE"
    echo "配置: 分辨率=${RESOLUTION}p | 日志轮转阈值=${MAX_LOG_SIZE}B" >> "$LOG_FILE"

    # 建立索引
    find "$SOURCE_BASE" -type f -name "*.mp4" | sort > /tmp/all_files.txt
    grep -oE "2026[0-9]{4}" /tmp/all_files.txt | cut -c 1-8 | sort -u > /tmp/all_dates.txt

    # 测试模式：只处理 2 个日期
    if [ "$TEST_MODE" = "true" ]; then
        head -2 /tmp/all_dates.txt > /tmp/all_dates_tmp.txt && mv /tmp/all_dates_tmp.txt /tmp/all_dates.txt
        echo "🧪 测试模式: 仅处理前 2 个日期" >> "$LOG_FILE"
    fi

    XIAOMI_SUCCESS=0
    XIAOMI_FAIL=0

    while read -r d; do
        OUTPUT_FILE="$EXPORT_DIR/Xiaomi_Camera_${d}.mp4"
        if [ -f "$OUTPUT_FILE" ]; then
            echo "[skip] $d 成品已存在，跳过。" >> "$LOG_FILE"
            continue
        fi

        echo "[$(date)] 🚀 开始处理日期: $d (${RESOLUTION}P - 30x)" >> "$LOG_FILE"
        
        grep "$d" /tmp/all_files.txt > /tmp/temp_list_all.txt
        grep -E "${d}(09|10|11|12|13|14|15|16|17|18|19|20|21|22)" /tmp/temp_list_all.txt > /tmp/temp_list.txt

        if [ ! -s /tmp/temp_list.txt ]; then
            echo "ℹ️ 日期 ${d} 在白昼时段无录像，跳过。" >> "$LOG_FILE"
            continue
        fi

        # 校验循环
        > /tmp/list.txt
        while read -r file; do
            if ffprobe -v error -show_format "$file" < /dev/null > /dev/null 2>&1; then
                echo "file '"'"'$file'"'"'" >> /tmp/list.txt
            fi
        done < /tmp/temp_list.txt

        if [ ! -s /tmp/list.txt ]; then
            echo "ℹ️ 日期 ${d} 无有效视频片段，跳过。" >> "$LOG_FILE"
            continue
        fi

        # 测试模式：只取前 2 个片段，加速验证
        if [ "$TEST_MODE" = "true" ] && [ -s /tmp/list.txt ]; then
            head -2 /tmp/list.txt > /tmp/list_trim.txt && mv /tmp/list_trim.txt /tmp/list.txt
            echo "🧪 测试模式: 仅处理 2 个片段" >> "$LOG_FILE"
        fi

        # ----- ffmpeg 执行（带 2 次重试） -----
        FFMPEG_STATUS=1
        ATTEMPT=1
        MAX_ATTEMPTS=2
        START_TIME=$(date +%s)

        while [ $ATTEMPT -le $MAX_ATTEMPTS ] && [ $FFMPEG_STATUS -ne 0 ]; do
            if [ $ATTEMPT -gt 1 ]; then
                echo "🔁 第 ${ATTEMPT} 次重试..." >> "$LOG_FILE"
            fi

            ffmpeg -y -loglevel warning -nostats -fflags +genpts+discardcorrupt -f concat -safe 0 -i /tmp/list.txt \
                -vf "scale=${SCALE},format=nv12,setpts=0.033333*PTS" \
                -an -c:v h264_qsv -preset veryfast \
                "$OUTPUT_FILE" < /dev/null >> "$LOG_FILE" 2>&1

            FFMPEG_STATUS=$?
            if [ $FFMPEG_STATUS -eq 0 ] && [ -s "$OUTPUT_FILE" ]; then
                END_TIME=$(date +%s)
                ELAPSED=$((END_TIME - START_TIME))
                FILE_SIZE=$(ls -lh "$OUTPUT_FILE" 2>/dev/null | awk '"'"'{print $5}'"'"')
                DUR_SEC=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUTPUT_FILE" 2>/dev/null || echo 0)
                DUR_MIN=$(( ${DUR_SEC%.*} / 60 ))
                DUR_SEC_REM=$(( ${DUR_SEC%.*} % 60 ))
                DUR_FMT=$(printf "%02d:%02d" "$DUR_MIN" "$DUR_SEC_REM")

                echo "✅ 日期 $d 顺利出片！尝试次数: $ATTEMPT | 耗时: ${ELAPSED}s | 文件: ${FILE_SIZE} | 时长: ${DUR_FMT}" >> "$LOG_FILE"
                XIAOMI_SUCCESS=$((XIAOMI_SUCCESS + 1))
            else
                ATTEMPT=$((ATTEMPT + 1))
            fi
        done

        if [ $FFMPEG_STATUS -ne 0 ] || [ ! -s "$OUTPUT_FILE" ]; then
            END_TIME=$(date +%s)
            ELAPSED=$((END_TIME - START_TIME))
            echo "❌ 日期 $d 触发中断。尝试次数: $((ATTEMPT-1)) | 耗时: ${ELAPSED}s" >> "$LOG_FILE"
            XIAOMI_FAIL=$((XIAOMI_FAIL + 1))
        fi
        echo "--------------------------------------------------------" >> "$LOG_FILE"
    done < /tmp/all_dates.txt

    rm -f /tmp/all_files.txt /tmp/all_dates.txt /tmp/temp_list_all.txt /tmp/temp_list.txt /tmp/list.txt

    TOTAL=$((XIAOMI_SUCCESS + XIAOMI_FAIL))
    echo "=== [Xiaomi] 全部处理完毕！成功: ${XIAOMI_SUCCESS} 天 | 失败: ${XIAOMI_FAIL} 天 ===" >> "$LOG_FILE"
    echo "{\"success\":$XIAOMI_SUCCESS,\"fail\":$XIAOMI_FAIL,\"total\":$TOTAL}" > /tmp/xiaomi_result.json
'
XIAOMI_EXIT=$?

# 读取结果
if [ -f /tmp/xiaomi_result.json ]; then
    XIAOMI_SUMMARY=$(cat /tmp/xiaomi_result.json)
    rm -f /tmp/xiaomi_result.json
else
    XIAOMI_SUMMARY='{"success":0,"fail":0,"total":0}'
fi

exit $XIAOMI_EXIT