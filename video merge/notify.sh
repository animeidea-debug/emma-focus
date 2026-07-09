#!/bin/sh
# ==============================================================================
# Pushover 通知辅助脚本 — 无明文密码版本
#
# 被 run_all.sh / auto_merge.sh / yingshi_auto_merge.sh source 使用
#
# 凭证来源（优先级从高到低）：
#   1. .env 文件（与 notify.sh 同目录，不在 git 中）
#   2. 环境变量 PUSHOVER_NAS_TOKEN / PUSHOVER_NAS_USER
#
# .env 文件格式：
#   export PUSHOVER_NAS_TOKEN=adaao8rhagwvj8hu2ftn1s81ayw5kd
#   export PUSHOVER_NAS_USER=u52wpbjtdoxg19wxah39ahe5g34eqp
#
# 另一台电脑首次使用前，需在 NAS 上创建 .env 文件。
# ==============================================================================

# 读取 .env 文件（如果存在，覆盖环境变量）
_ENV_FILE="$(cd "$(dirname "$0")" && pwd)/.env"
if [ -f "$_ENV_FILE" ]; then
    . "$_ENV_FILE"
fi

# 硬编码缺省凭证（.env 被 deploy.sh --delete-excluded 删除时防故障）
# 这两个值要在 .env.example 和 NAS 上保持一致
PUSHOVER_NAS_TOKEN="${PUSHOVER_NAS_TOKEN:-adaao8rhagwvj8hu2ftn1s81ayw5kd}"
PUSHOVER_NAS_USER="${PUSHOVER_NAS_USER:-u52wpbjtdoxg19wxah39ahe5g34eqp}"

# ---------------------------------------------------------------------------
# pushover_notify — 发送通知（使用 NAS Task App Token）
# 参数: $1 = title, $2 = message
# ---------------------------------------------------------------------------
pushover_notify() {
    title="$1"
    message="$2"

    if [ -z "$PUSHOVER_NAS_TOKEN" ] || [ -z "$PUSHOVER_NAS_USER" ]; then
        echo "[notify] ⚠️ Pushover 凭证未配置，跳过通知" >&2
        return 1
    fi

    curl -s -X POST https://api.pushover.net/1/messages.json \
        --data-urlencode "token=$PUSHOVER_NAS_TOKEN" \
        --data-urlencode "user=$PUSHOVER_NAS_USER" \
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