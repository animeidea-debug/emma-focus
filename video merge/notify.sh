#!/bin/sh
# ==============================================================================
# Pushover 通知辅助脚本
# 被 run_all.sh / auto_merge.sh / yingshi_auto_merge.sh source 使用
# 通过 curl 直接调用 Pushover API，无需依赖 MCP 服务
# ==============================================================================

PUSHOVER_TOKEN="agp3kp2fyxyfgw1rkgacn3gp9q2d11"
PUSHOVER_USER="u52wpbjtdoxg19wxah39ahe5g34eqp"

pushover_notify() {
    title="$1"
    message="$2"
    curl -s -X POST https://api.pushover.net/1/messages.json \
        --data-urlencode "token=$PUSHOVER_TOKEN" \
        --data-urlencode "user=$PUSHOVER_USER" \
        --data-urlencode "title=$title" \
        --data-urlencode "message=$message" \
        > /dev/null 2>&1
}

# 格式化秒数为 mm:ss
format_duration() {
    secs=$1
    m=$(( secs / 60 ))
    s=$(( secs % 60 ))
    printf "%02d:%02d" "$m" "$s"
}

# 获取视频文件大小 (友好格式)
get_file_size() {
    ls -lh "$1" 2>/dev/null | awk '{print $5}'
}

# 获取视频时长（秒）
get_video_duration_sec() {
    ffprobe -v error -show_entries format=duration -of csv=p=0 "$1" 2>/dev/null || echo "0"
}