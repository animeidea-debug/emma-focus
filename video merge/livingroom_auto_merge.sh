#!/bin/sh

# ==============================================================================
# 🎥 客厅小米摄像头 4K 30 倍速延时合并脚本（低优先级）
#
# 功能：从容器内 /mnt/source_videos_livingroom 读取原始 MP4 片段，
#       文件名格式：00_YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4
#       按日期聚合 → 筛选 09:00-22:59 白昼时段 → ffmpeg 30 倍速合成
#       输出到 /mnt/export_videos_livingroom/
#
# 可配置变量（可在 run_all.sh 中 export 覆盖）：
#   LIVINGROOM_RES  — 输出分辨率 (默认 2160 = 4K)
#   MAX_LOG_SIZE    — 日志轮转阈值 (默认 10485760 = 10MB)
# ==============================================================================

# ---------- 可配置变量（可被外部 export 覆盖） ----------
LIVINGROOM_RES="${LIVINGROOM_RES:-2160}"
MAX_LOG_SIZE="${MAX_LOG_SIZE:-10485760}"  # 10 MB

# 通过环境变量注入容器
docker exec -e LIVINGROOM_RES="$LIVINGROOM_RES" -e MAX_LOG_SIZE="$MAX_LOG_SIZE" -e TEST_MODE="$TEST_MODE" -e CAMERA_NAME="livingroom" tdarr_node sh -c '
    SOURCE_BASE="/mnt/source_videos_livingroom"
    EXPORT_DIR="/mnt/export_videos_livingroom"
    if [ "$TEST_MODE" = "true" ]; then
        EXPORT_DIR="/mnt/export_videos_test/${CAMERA_NAME}"
    fi
    mkdir -p "$EXPORT_DIR"
    LOG_FILE="$EXPORT_DIR/livingroom_merge.log"
    RESULT_FILE="$EXPORT_DIR/result_livingroom.json"

    # ----- 日志轮转 -----
    if [ -f "$LOG_FILE" ]; then
        SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat --format=%s "$LOG_FILE" 2>/dev/null || echo 0)
        if [ "$SIZE" -gt "${MAX_LOG_SIZE}" ]; then
            mv "$LOG_FILE" "${LOG_FILE}.old"
            echo "[LOG_ROTATE] 日志超过 ${MAX_LOG_SIZE}B，已重命名" > "$LOG_FILE"
        fi
    fi

    RESOLUTION="${LIVINGROOM_RES}"
    SCALE="-2:${RESOLUTION}"
    echo "=== [客厅] ${RESOLUTION}P-30x-流水线启动: $(date) ===" >> "$LOG_FILE"
    echo "配置: 分辨率=${RESOLUTION}p | 日志轮转阈值=${MAX_LOG_SIZE}B" >> "$LOG_FILE"

    find "$SOURCE_BASE" -maxdepth 1 -type f -name "*.mp4" | sort > /tmp/lr_all_files.txt
    # 只提取文件名中第一个日期（起始时间戳），避免跨日期视频被误分到两个日期
    sed "s|.*/||" /tmp/lr_all_files.txt | cut -d_ -f2 | grep -oE "2026[0-9]{4}" | sort -u > /tmp/lr_all_dates.txt

    if [ "$TEST_MODE" = "true" ]; then
        head -1 /tmp/lr_all_dates.txt > /tmp/lr_dates_tmp.txt && mv /tmp/lr_dates_tmp.txt /tmp/lr_all_dates.txt
        echo "🧪 测试模式: 仅处理 1 个日期" >> "$LOG_FILE"
    fi

    LR_SUCCESS=0
    LR_FAIL=0

    # 提取最新日期（用于跳过未录完的不完整日期）
    LATEST_DATE_LR=$(tail -1 /tmp/lr_all_dates.txt)

    while read -r d; do
        OUTPUT_FILE="$EXPORT_DIR/LivingRoom_4K_${d}.mp4"
        # 0字节文件视为无效，重新生成
        if [ -f "$OUTPUT_FILE" ] && [ -s "$OUTPUT_FILE" ]; then
            echo "[skip] $d 成品已存在，跳过。" >> "$LOG_FILE"
            continue
        fi

        echo "[$(date)] 🚀 开始处理日期: $d (${RESOLUTION}P - 30x)" >> "$LOG_FILE"

        grep "${d}" /tmp/lr_all_files.txt > /tmp/lr_temp_list.txt

        # ⏭️ 如果是最新日期且尚无下午录像（13:00-22:59），跳过等待明天补全
        if [ "$d" = "$LATEST_DATE_LR" ] && [ "$TEST_MODE" != "true" ]; then
            if ! grep -qE "_2026${d}(1[3-9]|2[0-2])[0-9]{4}_" /tmp/lr_temp_list.txt; then
                echo "ℹ️ 最新日期 ${d} 尚无下午录像（13:00-22:59），跳过（待明日补全）。" >> "$LOG_FILE"
                continue
            fi
        fi
        if [ ! -s /tmp/lr_temp_list.txt ]; then
            echo "ℹ️ 日期 ${d} 无录像，跳过。" >> "$LOG_FILE"
            continue
        fi

        > /tmp/lr_daytime_list.txt
        while read -r file; do
            basename "$file" | grep -qE "^[0-9]+_2026[0-9]{4}(0[9-9]|1[0-9]|2[0-2])[0-9]{4}_" && echo "$file" >> /tmp/lr_daytime_list.txt
        done < /tmp/lr_temp_list.txt

        if [ ! -s /tmp/lr_daytime_list.txt ]; then
            echo "ℹ️ 日期 ${d} 在白昼时段无录像，跳过。" >> "$LOG_FILE"
            continue
        fi

        > /tmp/lr_list.txt
        while read -r file; do
            if ffprobe -v error -show_format "$file" < /dev/null > /dev/null 2>&1; then
                echo "file '"'"'$file'"'"'" >> /tmp/lr_list.txt
            fi
        done < /tmp/lr_daytime_list.txt

        if [ ! -s /tmp/lr_list.txt ]; then
            echo "ℹ️ 日期 ${d} 无有效视频，跳过。" >> "$LOG_FILE"
            continue
        fi

        if [ "$TEST_MODE" = "true" ] && [ -s /tmp/lr_list.txt ]; then
            head -2 /tmp/lr_list.txt > /tmp/lr_trim.txt && mv /tmp/lr_trim.txt /tmp/lr_list.txt
        fi

        FFMPEG_STATUS=1
        ATTEMPT=1
        MAX_ATTEMPTS=2
        START_TIME=$(date +%s)

        while [ $ATTEMPT -le $MAX_ATTEMPTS ] && [ $FFMPEG_STATUS -ne 0 ]; do
            if [ $ATTEMPT -gt 1 ]; then
                echo "🔁 第 ${ATTEMPT} 次重试..." >> "$LOG_FILE"
            fi

            ffmpeg -y -loglevel warning -nostats -fflags +genpts+discardcorrupt -f concat -safe 0 -i /tmp/lr_list.txt \
                -vf "scale=${SCALE},format=nv12,setpts=0.033333*PTS" \
                -an -c:v hevc_qsv -preset veryfast -r 20 \
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
                LR_SUCCESS=$((LR_SUCCESS + 1))
            else
                ATTEMPT=$((ATTEMPT + 1))
            fi
        done

        if [ $FFMPEG_STATUS -ne 0 ] || [ ! -s "$OUTPUT_FILE" ]; then
            END_TIME=$(date +%s)
            ELAPSED=$((END_TIME - START_TIME))
            echo "❌ 日期 $d 触发中断。尝试次数: $((ATTEMPT-1)) | 耗时: ${ELAPSED}s" >> "$LOG_FILE"
            LR_FAIL=$((LR_FAIL + 1))
        fi
        echo "--------------------------------------------------------" >> "$LOG_FILE"
    done < /tmp/lr_all_dates.txt

    rm -f /tmp/lr_all_files.txt /tmp/lr_all_dates.txt /tmp/lr_temp_list.txt /tmp/lr_daytime_list.txt /tmp/lr_list.txt

    TOTAL=$((LR_SUCCESS + LR_FAIL))
    echo "=== [客厅] 全部处理完毕！成功: ${LR_SUCCESS} 天 | 失败: ${LR_FAIL} 天 ===" >> "$LOG_FILE"
    echo "{\"success\":$LR_SUCCESS,\"fail\":$LR_FAIL,\"total\":$TOTAL,\"name\":\"客厅\"}" > "$RESULT_FILE"
    # 确保 run_all.sh 可以删除 result JSON
    chmod 644 "$RESULT_FILE"
'
LR_EXIT=$?
exit $LR_EXIT