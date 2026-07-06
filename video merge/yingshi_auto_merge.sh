#!/bin/sh

# ===================================================================
# ✨ 路径完美对齐 + 强力抗震全留痕完全体版（萤石专用 1080P）
# ===================================================================
docker exec tdarr_node sh -c '
    # 容器内映射的绝对路径
    SOURCE_BASE="/mnt/source_videos_yingshi"
    EXPORT_DIR="/mnt/export_videos_yingshi"
    
    # ✨ 路径对齐：因为容器内 /tmp 已经是挂载的 temp_workspace，直接使用 /tmp 即可
    WORK_TMP="/tmp"

    mkdir -p "$EXPORT_DIR"
    LOG_FILE="$EXPORT_DIR/yingshi_merge.log"

    # 初始化总日志
    echo "=== [抗震全留痕版] 萤石监控1080P-30倍速流水线启动: $(date) ===" > "$LOG_FILE"

    # 扫描深度变短，正则完美匹配包含年份的目录
    find "$SOURCE_BASE" -type d -regextype posix-extended -regex ".*/[0-9]{4}/[0-9]{2}/[0-9]{2}" | sort -u > /tmp/ys_dates.txt

    while read -r d_path; do
        # 提取类似 2026/07/03 并压缩成 20260703
        DATE_STR=$(echo "$d_path" | grep -oE "[0-9]{4}/[0-9]{2}/[0-9]{2}" | sed '\''s/\///g'\'')
        OUTPUT_FILE="$EXPORT_DIR/Ezviz_60x_1080P_${DATE_STR}.mp4"
        
        # 检测是否已存在成品
        if [ -f "$OUTPUT_FILE" ]; then
            echo "[$(date)] ⏩ 跳过日期 ${DATE_STR}: 成品已存在。" >> "$LOG_FILE"
            continue
        fi

        # 提取当前日期下的有效小时目录
        find "$d_path" -maxdepth 1 -type d -name "[0-9][0-9]" | sort > /tmp/ys_hours.txt
        HOUR_LIST_FILE="$WORK_TMP/list_of_hours_ys_${DATE_STR}.txt"
        > "$HOUR_LIST_FILE"

        while read -r hour_dir; do
            HOUR_VAL=$(basename "$hour_dir")
            H=$(echo "$HOUR_VAL" | sed '\''s/^0*//'\'')
            
            # 时段过滤（严格保留 09:00 至 22:59 白昼画面，排除深夜凌晨无效录像）
            if [ -z "$H" ] || [ "$H" -lt 9 ] || [ "$H" -gt 22 ]; then continue; fi
            
            echo "[$(date)] 🚀 正在处理萤石日期 ${DATE_STR} 的第 ${HOUR_VAL} 时段 (30倍速-抗震全留痕清洗)" >> "$LOG_FILE"
            
            # 收集当前小时内的所有原始视频片段并写入临时列表文件
            find "$hour_dir" -type f -name "*.mp4" | sort | sed "s/^/file '\''/;s/$/'\''/" > "$WORK_TMP/list_ys_${DATE_STR}_${HOUR_VAL}.txt"
            
            HOUR_OUT="$WORK_TMP/temp_hour_ys_${DATE_STR}_${HOUR_VAL}.mp4"
            
            if [ -s "$WORK_TMP/list_ys_${DATE_STR}_${HOUR_VAL}.txt" ]; then
                # ⏱️ 记录时段起始时间戳
                START_TIME=$(date +%s)
                
                # ===================================================================
                # ✨ 终极硬解硬编优化点：
                # 1. +discardcorrupt  -> 遭遇极其严重的畸变宏块时强行丢帧，逼迫解码器向下推
                # 2. -loglevel warning -> 允许在 yingshi_merge.log 记录所有的丢帧判定与修复日志
                # ===================================================================
                ffmpeg -y -loglevel warning -nostats -fflags +genpts+discardcorrupt -f concat -safe 0 \
                    -i "$WORK_TMP/list_ys_${DATE_STR}_${HOUR_VAL}.txt" \
                    -vf "scale=1920:1080,format=nv12,setpts=0.033333*PTS" \
                    -an -c:v h264_qsv -preset veryfast \
                    "$HOUR_OUT" < /dev/null >> "$LOG_FILE" 2>&1
                
                FFMPEG_STATUS=$?
                
                # ⏱️ 计算耗时
                END_TIME=$(date +%s)
                ELAPSED_SECONDS=$((END_TIME - START_TIME))
                
                if [ $FFMPEG_STATUS -eq 0 ] && [ -s "$HOUR_OUT" ]; then
                    echo "file '\''$HOUR_OUT'\''" >> "$HOUR_LIST_FILE"
                    echo "✅ 时段 ${HOUR_VAL}:00 处理成功！耗时: ${ELAPSED_SECONDS} 秒" >> "$LOG_FILE"
                else
                    echo "❌ 时段 ${HOUR_VAL}:00 触发致命中断退出。状态码: $FFMPEG_STATUS | 耗时: ${ELAPSED_SECONDS} 秒" >> "$LOG_FILE"
                    # 💡 保留现场：取消自动 rm，方便去 temp_workspace 直接查看残缺的片段
                fi
                echo "--------------------------------------------------------" >> "$LOG_FILE"
            fi
        done < /tmp/ys_hours.txt

        # ===================================================================
        # 🎉 日终无损秒级大缝合（在容器内直接 copy 合并）
        # ===================================================================
        if [ -s "$HOUR_LIST_FILE" ]; then
            echo "[$(date)] 🏁 正在进行白昼时段无损秒级大缝合..." >> "$LOG_FILE"
            ffmpeg -y -loglevel warning -nostats -f concat -safe 0 -i "$HOUR_LIST_FILE" \
                -c copy "$OUTPUT_FILE" < /dev/null >> "$LOG_FILE" 2>&1
            
            if [ $? -eq 0 ] && [ -s "$OUTPUT_FILE" ]; then
                echo "🎉 🎉 🎉 萤石日期 ${DATE_STR} 30倍速容器版延时视频合成成功！" >> "$LOG_FILE"
            else
                echo "❌ 日期 ${DATE_STR} 最终缝合失败。" >> "$LOG_FILE"
                # 💡 保留现场：不删最终残片
            fi
        fi
        
        # 清理当前日期的临时缓存中间件（在物理 temp_workspace 中自动擦除）
        rm -f "$WORK_TMP"/temp_hour_ys_${DATE_STR}_*.mp4 "$WORK_TMP"/list_ys_${DATE_STR}_*.txt "$HOUR_LIST_FILE"
    done < /tmp/ys_dates.txt

    # 最终大打扫
    rm -f /tmp/ys_dates.txt /tmp/ys_hours.txt
    echo "=== 萤石所有历史积压日期处理完毕！ ===" >> "$LOG_FILE"
'