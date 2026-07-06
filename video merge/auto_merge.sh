#!/bin/sh

# 告诉容器去执行具体的合并任务，确保所有的 ffmpeg 调用都在容器内环境完成
docker exec tdarr_node sh -c '
    SOURCE_BASE="/mnt/source_videos"
    EXPORT_DIR="/mnt/export_videos"
    LOG_FILE="$EXPORT_DIR/merge_log.txt"
    mkdir -p "$EXPORT_DIR"

    # 初始化日志文件
    echo "=== [抗震全留痕完全体] 720P-30倍速-白昼时段流水线启动: $(date) ===" > "$LOG_FILE"
    
    # 建立索引
    find "$SOURCE_BASE" -type f -name "*.mp4" | sort > /tmp/all_files.txt
    grep -oE "2026[0-9]{4}" /tmp/all_files.txt | cut -c 1-8 | sort -u > /tmp/all_dates.txt

    while read -r d; do
        OUTPUT_FILE="$EXPORT_DIR/Xiaomi_Camera_${d}.mp4"
        if [ -f "$OUTPUT_FILE" ]; then continue; fi

        echo "[$(date)] 🚀 开始处理日期: $d (720P - 30倍速 - 强力抗震全留痕版)" | tee -a "$LOG_FILE"
        
        # 筛选当天的所有文件
        grep "$d" /tmp/all_files.txt > /tmp/temp_list_all.txt
        
        # 时段过滤（严格保留 09:00 至 22:59 白昼画面）
        grep -E "${d}(09|10|11|12|13|14|15|16|17|18|19|20|21|22)" /tmp/temp_list_all.txt > /tmp/temp_list.txt

        if [ ! -s /tmp/temp_list.txt ]; then
            echo "ℹ️ 日期 ${d} 在白昼时段无录像，跳过。" | tee -a "$LOG_FILE"
            continue
        fi

        # 校验循环
        > /tmp/list.txt
        while read -r file; do
            if ffprobe -v error -show_format "$file" < /dev/null > /dev/null 2>&1; then
                echo "file '\''$file'\''" >> /tmp/list.txt
            fi
        done < /tmp/temp_list.txt

        if [ -s /tmp/list.txt ]; then
            # ⏱️ 记录开始时间
            START_TIME=$(date +%s)

            # ===================================================================
            # ✨ 优化核心：
            # 1. +discardcorrupt -> 强丢损坏帧防死锁提前收工
            # 2. -loglevel warning -> 允许吐出所有的修复日志与异常判断记录
            # ===================================================================
            ffmpeg -y -loglevel warning -nostats -fflags +genpts+discardcorrupt -f concat -safe 0 -i /tmp/list.txt \
                -vf "scale=1280:720,format=nv12,setpts=0.033333*PTS" \
                -an -c:v h264_qsv -preset veryfast \
                "$OUTPUT_FILE" < /dev/null >> "$LOG_FILE" 2>&1
            
            FFMPEG_STATUS=$?

            # ⏱️ 记录结束时间并计算差值
            END_TIME=$(date +%s)
            ELAPSED_SECONDS=$((END_TIME - START_TIME))

            if [ $FFMPEG_STATUS -eq 0 ] && [ -s "$OUTPUT_FILE" ]; then
                echo "✅ 日期 $d 顺利出片！总体耗时: ${ELAPSED_SECONDS} 秒" | tee -a "$LOG_FILE"
            else
                echo "❌ 日期 $d 触发致命中断退出。状态码: $FFMPEG_STATUS | 耗时: ${ELAPSED_SECONDS} 秒" | tee -a "$LOG_FILE"
                # 💡 保留现场：取消了自动 rm，留着未拼完的视频方便去暴风影音或播放器看卡在几分几秒
            fi
            echo "--------------------------------------------------------" >> "$LOG_FILE"
        fi
    done < /tmp/all_dates.txt
    rm -f /tmp/all_files.txt /tmp/all_dates.txt /tmp/temp_list_all.txt /tmp/temp_list.txt /tmp/list.txt
'