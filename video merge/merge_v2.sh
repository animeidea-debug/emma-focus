#!/bin/sh
# ==============================================================================
# 🎥 新一代统一延时合并脚本
#
# 参数化设计，通过环境变量配置处理哪个摄像头：
#   CAMERA    — 房间英文名，用于输出文件名（如 Study / LivingRoom）
#   SOURCE    — 容器内源目录路径（如 /mnt/source_study）
#   RES       — 输出分辨率 (默认 2160)
#   CODEC     — 编码器 (默认 hevc_qsv)
#
# 用法：
#   CAMERA=Study SOURCE=/mnt/source_study sh merge_v2.sh
#
# 输出到 /mnt/export_videos/{CAMERA}_{YYYYMMDD}.mp4
# 使用容器内部 /tmp（不依赖 temp_workspace volume）
# ==============================================================================

# ---------- 参数（可通过环境变量覆盖）----------
CAMERA="${CAMERA:?必须设置 CAMERA 环境变量}"
SOURCE_DIR="${SOURCE:?必须设置 SOURCE 环境变量}"
RESOLUTION="${RES:-2160}"
CODEC="${CODEC:-hevc_qsv}"
MAX_LOG_SIZE="${MAX_LOG_SIZE:-10485760}"

# ---------- 引入通知 ----------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/notify.sh"

docker exec -e CAMERA="$CAMERA" -e SOURCE_DIR="$SOURCE_DIR" -e RESOLUTION="$RESOLUTION" -e CODEC="$CODEC" -e MAX_LOG_SIZE="$MAX_LOG_SIZE" -e TEST_MODE="$TEST_MODE" tdarr_node sh -c '
    OUTPUT_BASE="/mnt/export_videos"
    LOG_FILE="${OUTPUT_BASE}/merge_v2_${CAMERA}.log"
    RESULT_FILE="${OUTPUT_BASE}/result_v2_${CAMERA}.json"

    if [ "$TEST_MODE" = "true" ]; then
        OUTPUT_BASE="/mnt/export_videos_test/${CAMERA}"
        mkdir -p "$OUTPUT_BASE"
        LOG_FILE="${OUTPUT_BASE}/merge_v2_${CAMERA}.log"
        RESULT_FILE="${OUTPUT_BASE}/result_v2_${CAMERA}.json"
    fi

    # ----- 日志轮转 -----
    if [ -f "$LOG_FILE" ]; then
        SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat --format=%s "$LOG_FILE" 2>/dev/null || echo 0)
        if [ "$SIZE" -gt "${MAX_LOG_SIZE}" ]; then
            mv "$LOG_FILE" "${LOG_FILE}.old"
            echo "[LOG_ROTATE] 日志超过 ${MAX_LOG_SIZE}B，已重命名" > "$LOG_FILE"
        fi
    fi

    # vpp_qsv 需要显式宽高，根据分辨率计算 16:9 宽度
    VPP_H="${RESOLUTION}"
    VPP_W=$(( ${RESOLUTION} * 16 / 9 ))
    echo "VPP尺寸: ${VPP_W}x${VPP_H}" >> "$LOG_FILE"

    echo "=== [${CAMERA}] ${RESOLUTION}P-30x-流水线启动: $(date) ===" >> "$LOG_FILE"
    echo "配置: 源=${SOURCE_DIR} 分辨率=${RESOLUTION}p 编码=${CODEC} 日志轮转=${MAX_LOG_SIZE}B" >> "$LOG_FILE"

    # ----- 扫描源文件 -----
    ALL_FILES_TMP="/tmp/v2_all_${CAMERA}.txt"
    DATES_TMP="/tmp/v2_dates_${CAMERA}.txt"

    find "$SOURCE_DIR" -maxdepth 1 -type f -name "*.mp4" | sort > "$ALL_FILES_TMP"

    # 统一日期提取：兼容两种文件名格式
    #   新款: 00_YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4
    #   旧款: YYYYMMDDHHMMSS.mp4
    while IFS= read -r fpath; do
        fname=$(basename "$fpath")
        # 优先取第一个下划线后的日期段（新款格式）
        date_candidate=$(echo "$fname" | sed "s|.*/||" | cut -d_ -f2 2>/dev/null)
        if echo "$date_candidate" | grep -qE "^2026[0-9]{4}"; then
            echo "$date_candidate" | grep -oE "2026[0-9]{4}" | cut -c1-8
        else
            # 旧款格式：直接取文件名中的日期
            echo "$fname" | grep -oE "2026[0-9]{4}" | head -1
        fi
    done < "$ALL_FILES_TMP" | sort -u > "$DATES_TMP"

    if [ "$TEST_MODE" = "true" ]; then
        head -1 "$DATES_TMP" > "${DATES_TMP}.tmp" && mv "${DATES_TMP}.tmp" "$DATES_TMP"
        echo "🧪 测试模式: 仅处理 1 个日期" >> "$LOG_FILE"
    fi

    SUCCESS=0
    FAIL=0
    LATEST_DATE=$(tail -1 "$DATES_TMP")

    while read -r d; do
        OUTPUT_FILE="${OUTPUT_BASE}/${CAMERA}_${d}.mp4"

        # 跳过已有成品（0字节视为无效）
        if [ -f "$OUTPUT_FILE" ] && [ -s "$OUTPUT_FILE" ]; then
            echo "[skip] ${d} 成品已存在，跳过。" >> "$LOG_FILE"
            continue
        fi

        echo "[$(date)] 🚀 开始处理 ${CAMERA} 日期 ${d} (${RESOLUTION}P - 30x)" >> "$LOG_FILE"

        # 提取该日期的所有文件
        grep "$d" "$ALL_FILES_TMP" > "/tmp/v2_day_${CAMERA}_${d}.txt"

        # ⏭️ 最新日期跳过不完整的
        if [ "$d" = "$LATEST_DATE" ] && [ "$TEST_MODE" != "true" ]; then
            # 检查是否有下午录像（文件名第2段中的小时13-22）
            if ! grep -qE "(1[3-9]|2[0-2])[0-9]{4}_" "/tmp/v2_day_${CAMERA}_${d}.txt" 2>/dev/null && \
               ! grep -qE "${d}(1[3-9]|2[0-2])" "/tmp/v2_day_${CAMERA}_${d}.txt" 2>/dev/null; then
                echo "ℹ️ 最新日期 ${d} 尚无下午录像（13:00-22:59），跳过（待明日补全）。" >> "$LOG_FILE"
                rm -f "/tmp/v2_day_${CAMERA}_${d}.txt"
                continue
            fi
        fi

        if [ ! -s "/tmp/v2_day_${CAMERA}_${d}.txt" ]; then
            echo "ℹ️ 日期 ${d} 无录像，跳过。" >> "$LOG_FILE"
            rm -f "/tmp/v2_day_${CAMERA}_${d}.txt"
            continue
        fi

        # 白昼时段过滤 09:00-22:59
        > "/tmp/v2_daytime_${CAMERA}_${d}.txt"
        while IFS= read -r fpath; do
            fname=$(basename "$fpath")
            # 新款格式: 00_YYYYMMDDHHMMSS_... → 从第二段提取小时
            hour_part=$(echo "$fname" | cut -d_ -f2 | grep -oE "^2026[0-9]{4}([0-9]{2})" | sed "s/^2026[0-9]\{4\}//")
            if [ -z "$hour_part" ]; then
                # 旧款格式: 直接从文件名提取 HH
                hour_part=$(echo "$fname" | grep -oE "^2026[0-9]{4}([0-9]{2})" | sed "s/^2026[0-9]\{4\}//")
            fi
            H=$(echo "$hour_part" | sed "s/^0*//")
            if [ -n "$H" ] && [ "$H" -ge 9 ] && [ "$H" -le 22 ]; then
                echo "$fpath" >> "/tmp/v2_daytime_${CAMERA}_${d}.txt"
            fi
        done < "/tmp/v2_day_${CAMERA}_${d}.txt"

        if [ ! -s "/tmp/v2_daytime_${CAMERA}_${d}.txt" ]; then
            echo "ℹ️ 日期 ${d} 在白昼时段无录像，跳过。" >> "$LOG_FILE"
            rm -f "/tmp/v2_day_${CAMERA}_${d}.txt" "/tmp/v2_daytime_${CAMERA}_${d}.txt"
            continue
        fi

        # 校验有效文件，生成 concat list
        > "/tmp/v2_list_${CAMERA}_${d}.txt"
        while IFS= read -r file; do
            if ffprobe -v error -show_format "$file" < /dev/null > /dev/null 2>&1; then
                echo "file '"'"'$file'"'"'" >> "/tmp/v2_list_${CAMERA}_${d}.txt"
            fi
        done < "/tmp/v2_daytime_${CAMERA}_${d}.txt"

        if [ ! -s "/tmp/v2_list_${CAMERA}_${d}.txt" ]; then
            echo "ℹ️ 日期 ${d} 无有效视频，跳过。" >> "$LOG_FILE"
            rm -f "/tmp/v2_day_${CAMERA}_${d}.txt" "/tmp/v2_daytime_${CAMERA}_${d}.txt" "/tmp/v2_list_${CAMERA}_${d}.txt"
            continue
        fi

        if [ "$TEST_MODE" = "true" ] && [ -s "/tmp/v2_list_${CAMERA}_${d}.txt" ]; then
            head -2 "/tmp/v2_list_${CAMERA}_${d}.txt" > "/tmp/v2_list_${CAMERA}_${d}.trim" && mv "/tmp/v2_list_${CAMERA}_${d}.trim" "/tmp/v2_list_${CAMERA}_${d}.txt"
        fi

        # ----- ffmpeg 编码 -----
        FFMPEG_STATUS=1
        ATTEMPT=1
        MAX_ATTEMPTS=2
        START_TIME=$(date +%s)

        while [ $ATTEMPT -le $MAX_ATTEMPTS ] && [ $FFMPEG_STATUS -ne 0 ]; do
            if [ $ATTEMPT -gt 1 ]; then
                echo "🔁 第 ${ATTEMPT} 次重试..." >> "$LOG_FILE"
            fi

            ffmpeg -y -hwaccel qsv -hwaccel_output_format qsv -loglevel warning -nostats -fflags +genpts+discardcorrupt \
                -f concat -safe 0 \
                -i "/tmp/v2_list_${CAMERA}_${d}.txt" \
                -vf "vpp_qsv=w=${VPP_W}:h=${VPP_H},setpts=0.033333*PTS" \
                -an -c:v "${CODEC}" -preset veryfast -r 20 \
                "$OUTPUT_FILE" < /dev/null >> "$LOG_FILE" 2>&1

            FFMPEG_STATUS=$?
            if [ $FFMPEG_STATUS -eq 0 ] && [ -s "$OUTPUT_FILE" ]; then
                END_TIME=$(date +%s)
                ELAPSED=$((END_TIME - START_TIME))
                FILE_SIZE=$(ls -lh "$OUTPUT_FILE" 2>/dev/null | awk "{print \$5}")
                DUR_SEC=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUTPUT_FILE" 2>/dev/null || echo 0)
                DUR_MIN=$(( ${DUR_SEC%.*} / 60 ))
                DUR_SEC_REM=$(( ${DUR_SEC%.*} % 60 ))
                DUR_FMT=$(printf "%02d:%02d" "$DUR_MIN" "$DUR_SEC_REM")
                echo "✅ ${CAMERA} ${d} 出片！尝试: $ATTEMPT | 耗时: ${ELAPSED}s | 文件: ${FILE_SIZE} | 时长: ${DUR_FMT}" >> "$LOG_FILE"
                SUCCESS=$((SUCCESS + 1))
            else
                ATTEMPT=$((ATTEMPT + 1))
            fi
        done

        if [ $FFMPEG_STATUS -ne 0 ] || [ ! -s "$OUTPUT_FILE" ]; then
            END_TIME=$(date +%s)
            ELAPSED=$((END_TIME - START_TIME))
            echo "❌ ${CAMERA} ${d} 中断。尝试: $((ATTEMPT-1)) | 耗时: ${ELAPSED}s" >> "$LOG_FILE"
            FAIL=$((FAIL + 1))
        fi

        # 清理临时文件
        rm -f "/tmp/v2_day_${CAMERA}_${d}.txt" "/tmp/v2_daytime_${CAMERA}_${d}.txt" "/tmp/v2_list_${CAMERA}_${d}.txt"
        echo "--------------------------------------------------------" >> "$LOG_FILE"
    done < "$DATES_TMP"

    rm -f "$ALL_FILES_TMP" "$DATES_TMP"

    TOTAL=$((SUCCESS + FAIL))
    echo "=== [${CAMERA}] 全部处理完毕！成功: ${SUCCESS} 天 | 失败: ${FAIL} 天 ===" >> "$LOG_FILE"
    echo "{\"success\":$SUCCESS,\"fail\":$FAIL,\"total\":$TOTAL,\"name\":\"${CAMERA}\"}" > "$RESULT_FILE"
    chmod 644 "$RESULT_FILE"
'
EXIT_CODE=$?
exit $EXIT_CODE