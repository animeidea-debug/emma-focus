#!/bin/sh

# ==============================================================================
# 🎥 萤石摄像头 1080P 30 倍速延时合并脚本
#
# 功能：从容器内 /mnt/source_videos_yingshi 读取原始 MP4 片段，
#       按日期聚合 → 筛选 09:00-22:59 白昼时段 → 每小时间隔合成 →
#       → 日终无损拼接 → 最终 1080P 30 倍速延时视频
#
# 可配置变量（可在 run_all.sh 中 export 覆盖）：
#   YINGSHI_RES   — 输出分辨率 (默认 1080)
#   MAX_LOG_SIZE  — 日志轮转阈值 (默认 10485760 = 10MB)
# ==============================================================================

# ---------- 可配置变量（可被外部 export 覆盖） ----------
YINGSHI_RES="${YINGSHI_RES:-1080}"
MAX_LOG_SIZE="${MAX_LOG_SIZE:-10485760}"  # 10 MB

# 引入通知辅助
SCRIPT_DIR_YS="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR_YS/notify.sh"

docker exec -e YINGSHI_RES="$YINGSHI_RES" -e MAX_LOG_SIZE="$MAX_LOG_SIZE" -e TEST_MODE="$TEST_MODE" -e CAMERA_NAME="yingshi" tdarr_node sh -c "
    SOURCE_BASE=\"/mnt/source_videos_yingshi\"
    WORK_TMP=\"/tmp\"
    EXPORT_DIR=\"/mnt/export_videos_yingshi\"
    if [ \"\$TEST_MODE\" = \"true\" ]; then
        EXPORT_DIR=\"/mnt/export_videos_test/\${CAMERA_NAME}\"
    fi
    mkdir -p \"\$EXPORT_DIR\"
    LOG_FILE=\"\$EXPORT_DIR/yingshi_merge.log\"
    RESULT_FILE=\"\$EXPORT_DIR/result_yingshi.json\"

    # ----- 日志轮转：超过 10MB 自动重命名 -----
    if [ -f \"\$LOG_FILE\" ]; then
        SIZE=\$(stat -f%z \"\$LOG_FILE\" 2>/dev/null || stat --format=%s \"\$LOG_FILE\" 2>/dev/null || echo 0)
        if [ \"\$SIZE\" -gt ${MAX_LOG_SIZE} ]; then
            mv \"\$LOG_FILE\" \"\${LOG_FILE}.old\"
            echo \"[LOG_ROTATE] 日志超过 ${MAX_LOG_SIZE}B，已重命名为 yingshi_merge.log.old\" > \"\$LOG_FILE\"
        fi
    fi

    RESOLUTION=${YINGSHI_RES}
    SCALE=\"-2:\${RESOLUTION}\"
    echo \"=== [Yingshi] \${RESOLUTION}P-30x-白昼时段流水线启动: \$(date) ===\" >> \"\$LOG_FILE\"
    echo \"配置: 分辨率=\${RESOLUTION}p | 日志轮转阈值=${MAX_LOG_SIZE}B\" >> \"\$LOG_FILE\"

    # 扫描深度变短，正则完美匹配包含年份的目录
    find \"\$SOURCE_BASE\" -type d -regextype posix-extended -regex \".*/[0-9]{4}/[0-9]{2}/[0-9]{2}\" | sort -u > /tmp/ys_dates.txt

    # 测试模式：只处理 1 个日期
    if [ \"\$TEST_MODE\" = \"true\" ]; then
        head -1 /tmp/ys_dates.txt > /tmp/ys_dates_tmp.txt && mv /tmp/ys_dates_tmp.txt /tmp/ys_dates.txt
        echo \"🧪 测试模式: 仅处理 1 个日期\" >> \"\$LOG_FILE\"
    fi

    YINGSHI_SUCCESS=0
    YINGSHI_FAIL=0

    while read -r d_path; do
        # 提取类似 2026/07/03 并压缩成 20260703
        DATE_STR=\$(echo \"\$d_path\" | grep -oE \"[0-9]{4}/[0-9]{2}/[0-9]{2}\" | sed 's/\\///g')
        OUTPUT_FILE=\"\$EXPORT_DIR/Ezviz_60x_1080P_\${DATE_STR}.mp4\"
        
        # 检测是否已存在成品
        if [ -f \"\$OUTPUT_FILE\" ]; then
            echo \"[\$(date)] ⏩ 跳过日期 \${DATE_STR}: 成品已存在。\" >> \"\$LOG_FILE\"
            continue
        fi

        # 提取当前日期下的有效小时目录
        find \"\$d_path\" -maxdepth 1 -type d -name \"[0-9][0-9]\" | sort > /tmp/ys_hours.txt
        HOUR_LIST_FILE=\"\$WORK_TMP/list_of_hours_ys_\${DATE_STR}.txt\"
        > \"\$HOUR_LIST_FILE\"

        while read -r hour_dir; do
            HOUR_VAL=\$(basename \"\$hour_dir\")
            H=\$(echo \"\$HOUR_VAL\" | sed 's/^0*//')

            # 时段过滤（严格保留 09:00 至 22:59 白昼画面）
            if [ -z \"\$H\" ] || [ \"\$H\" -lt 9 ] || [ \"\$H\" -gt 22 ]; then continue; fi

            echo \"[\$(date)] 🚀 正在处理萤石日期 \${DATE_STR} 的第 \${HOUR_VAL} 时段 (30倍速-抗震全留痕清洗)\" >> \"\$LOG_FILE\"

            # 收集当前小时内的所有原始视频片段
            find \"\$hour_dir\" -type f -name \"*.mp4\" | sort | sed \"s/^/file '/;s/$/'/\" > \"\$WORK_TMP/list_ys_\${DATE_STR}_\${HOUR_VAL}.txt\"

            HOUR_OUT=\"\$WORK_TMP/temp_hour_ys_\${DATE_STR}_\${HOUR_VAL}.mp4\"

            if [ -s \"\$WORK_TMP/list_ys_\${DATE_STR}_\${HOUR_VAL}.txt\" ]; then
                # 测试模式：只取前 2 个片段
                if [ \"\$TEST_MODE\" = \"true\" ]; then
                    head -2 \"\$WORK_TMP/list_ys_\${DATE_STR}_\${HOUR_VAL}.txt\" > \"\${WORK_TMP}/list_ys_\${DATE_STR}_\${HOUR_VAL}.trim\" && mv \"\${WORK_TMP}/list_ys_\${DATE_STR}_\${HOUR_VAL}.trim\" \"\$WORK_TMP/list_ys_\${DATE_STR}_\${HOUR_VAL}.txt\"
                fi
                # ----- ffmpeg 执行（带 2 次重试） -----
                FFMPEG_STATUS=1
                ATTEMPT=1
                MAX_ATTEMPTS=2
                START_TIME=\$(date +%s)

                while [ \$ATTEMPT -le \$MAX_ATTEMPTS ] && [ \$FFMPEG_STATUS -ne 0 ]; do
                    if [ \$ATTEMPT -gt 1 ]; then
                        echo \"🔁 第 \${ATTEMPT} 次重试...\" >> \"\$LOG_FILE\"
                    fi

                    ffmpeg -y -loglevel warning -nostats -fflags +genpts+discardcorrupt -f concat -safe 0 \
                        -i \"\$WORK_TMP/list_ys_\${DATE_STR}_\${HOUR_VAL}.txt\" \
                        -vf \"scale=\${SCALE},format=nv12,setpts=0.033333*PTS\" \
                        -an -c:v h264_qsv -preset veryfast \
                        \"\$HOUR_OUT\" < /dev/null >> \"\$LOG_FILE\" 2>&1

                    FFMPEG_STATUS=\$?
                    if [ \$FFMPEG_STATUS -eq 0 ] && [ -s \"\$HOUR_OUT\" ]; then
                        END_TIME=\$(date +%s)
                        ELAPSED=\$((END_TIME - START_TIME))
                        echo \"file '\$HOUR_OUT'\" >> \"\$HOUR_LIST_FILE\"
                        echo \"✅ 时段 \${HOUR_VAL}:00 处理成功！尝试次数: \$ATTEMPT | 耗时: \${ELAPSED}s\" >> \"\$LOG_FILE\"
                    else
                        ATTEMPT=\$((ATTEMPT + 1))
                    fi
                done

                if [ \$FFMPEG_STATUS -ne 0 ] || [ ! -s \"\$HOUR_OUT\" ]; then
                    END_TIME=\$(date +%s)
                    ELAPSED=\$((END_TIME - START_TIME))
                    echo \"❌ 时段 \${HOUR_VAL}:00 触发中断。尝试次数: \$((ATTEMPT-1)) | 耗时: \${ELAPSED}s\" >> \"\$LOG_FILE\"
                fi
                echo \"--------------------------------------------------------\" >> \"\$LOG_FILE\"
            fi
        done < /tmp/ys_hours.txt

        # 测试模式：只取前 2 个成功处理的时段
        if [ \"\$TEST_MODE\" = \"true\" ] && [ -s \"\$HOUR_LIST_FILE\" ]; then
            head -2 \"\$HOUR_LIST_FILE\" > \"\${HOUR_LIST_FILE}.trim\" && mv \"\${HOUR_LIST_FILE}.trim\" \"\$HOUR_LIST_FILE\"
            echo \"🧪 测试模式: 仅缝合 2 个时段\" >> \"\$LOG_FILE\"
        fi

        # ===================================================================
        # 🎉 日终无损秒级大缝合
        # ===================================================================
        if [ -s \"\$HOUR_LIST_FILE\" ]; then
            echo \"[\$(date)] 🏁 正在进行白昼时段无损秒级大缝合...\" >> \"\$LOG_FILE\"
            START_TIME=\$(date +%s)
            ffmpeg -y -loglevel warning -nostats -f concat -safe 0 -i \"\$HOUR_LIST_FILE\" \
                -c copy \"\$OUTPUT_FILE\" < /dev/null >> \"\$LOG_FILE\" 2>&1

            if [ \$? -eq 0 ] && [ -s \"\$OUTPUT_FILE\" ]; then
                END_TIME=\$(date +%s)
                ELAPSED=\$((END_TIME - START_TIME))
                FILE_SIZE=\$(ls -lh \"\$OUTPUT_FILE\" 2>/dev/null | awk '{print \$5}')
                DUR_SEC=\$(ffprobe -v error -show_entries format=duration -of csv=p=0 \"\$OUTPUT_FILE\" 2>/dev/null || echo 0)
                DUR_MIN=\$(( \${DUR_SEC%.*} / 60 ))
                DUR_SEC_REM=\$(( \${DUR_SEC%.*} % 60 ))
                DUR_FMT=\$(printf \"%02d:%02d\" \"\$DUR_MIN\" \"\$DUR_SEC_REM\")
                echo \"🎉 萤石日期 \${DATE_STR} 合成成功！耗时: \${ELAPSED}s | 文件: \${FILE_SIZE} | 时长: \${DUR_FMT}\" >> \"\$LOG_FILE\"
                YINGSHI_SUCCESS=\$((YINGSHI_SUCCESS + 1))
            else
                echo \"❌ 日期 \${DATE_STR} 最终缝合失败。\" >> \"\$LOG_FILE\"
                YINGSHI_FAIL=\$((YINGSHI_FAIL + 1))
            fi
        else
            echo \"ℹ️ 日期 \${DATE_STR} 无成功处理的小时片段，跳过。\" >> \"\$LOG_FILE\"
        fi

        # 清理当前日期的临时文件
        rm -f \"\$WORK_TMP\"/temp_hour_ys_\${DATE_STR}_*.mp4 \"\$WORK_TMP\"/list_ys_\${DATE_STR}_*.txt \"\$HOUR_LIST_FILE\"
    done < /tmp/ys_dates.txt

    # 最终打扫
    rm -f /tmp/ys_dates.txt /tmp/ys_hours.txt

    TOTAL=\$((YINGSHI_SUCCESS + YINGSHI_FAIL))
    echo \"=== [书房辅机位] 全部处理完毕！成功: \${YINGSHI_SUCCESS} 天 | 失败: \${YINGSHI_FAIL} 天 ===\" >> \"\$LOG_FILE\"
    echo \"{\\\"success\\\":\$YINGSHI_SUCCESS,\\\"fail\\\":\$YINGSHI_FAIL,\\\"total\\\":\$TOTAL,\\\"name\\\":\\\"书房辅机位\\\"}\" > \"\$RESULT_FILE\"
"
YINGSHI_EXIT=$?
exit $YINGSHI_EXIT
