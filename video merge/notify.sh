#!/bin/sh
# ==============================================================================
# Pushover 通知辅助脚本 — 无明文密码版本
#
# 被 run_all.sh / auto_merge.sh / merge_v2.sh 等脚本 source 使用
#
# 凭证来源（优先级从高到低）：
#   1. .env 文件（与 notify.sh 同目录，不在 git 中）
#   2. 环境变量 PUSHOVER_NAS_TOKEN / PUSHOVER_NAS_USER
#
# .env 文件格式（复制自 .env.example 并填入实际值）：
#   export PUSHOVER_NAS_TOKEN=your_token_here
#   export PUSHOVER_NAS_USER=your_user_key_here
#
# ⚠️ Token 仅存于 NAS 上的 .env 文件（已 gitignored），不进 git。
#    其他机器首次使用前，需在 NAS 上创建 .env 文件或设置环境变量。
# ==============================================================================

# 显式环境变量优先于 .env，便于 cron/临时运行覆盖配置。
_EXPLICIT_PUSHOVER_TOKEN="${PUSHOVER_NAS_TOKEN:-}"
_EXPLICIT_PUSHOVER_USER="${PUSHOVER_NAS_USER:-}"
_ENV_FILE="$(cd "$(dirname "$0")" && pwd)/.env"
if [ -f "$_ENV_FILE" ]; then
    . "$_ENV_FILE"
fi

PUSHOVER_NAS_TOKEN="${_EXPLICIT_PUSHOVER_TOKEN:-${PUSHOVER_NAS_TOKEN:-}}"
PUSHOVER_NAS_USER="${_EXPLICIT_PUSHOVER_USER:-${PUSHOVER_NAS_USER:-}}"
unset _EXPLICIT_PUSHOVER_TOKEN _EXPLICIT_PUSHOVER_USER

# ---------------------------------------------------------------------------
# pushover_notify — 发送通知（使用 NAS Task App Token）
# 参数: $1 = title, $2 = message, $3 = priority（默认 0，可用 1 表示高优先级）
# ---------------------------------------------------------------------------
pushover_notify() {
    title="$1"
    message="$2"
    priority="${3:-0}"
    sound="${4:-${PUSHOVER_SOUND:-}}"
    log_file="${PUSHOVER_LOG_FILE:-/tmp/nas-notifications.jsonl}"

    if [ -z "$PUSHOVER_NAS_TOKEN" ] || [ -z "$PUSHOVER_NAS_USER" ]; then
        echo "[notify] ⚠️ Pushover 凭证未配置，跳过通知" >&2
        return 1
    fi

    response_file=$(mktemp "/tmp/pushover-response.XXXXXX") || return 1
    extra_args=""
    [ -n "$sound" ] && extra_args="--data-urlencode sound=$sound"
    [ "$priority" = "2" ] && extra_args="$extra_args --data-urlencode retry=60 --data-urlencode expire=3600"
    # shellcheck disable=SC2086
    if curl --silent --show-error --fail -X POST \
        --connect-timeout 5 --max-time 15 --retry 3 --retry-delay 2 \
        --retry-all-errors \
        https://api.pushover.net/1/messages.json \
        --data-urlencode "token=$PUSHOVER_NAS_TOKEN" \
        --data-urlencode "user=$PUSHOVER_NAS_USER" \
        --data-urlencode "title=$title" \
        --data-urlencode "message=$message" \
        --data-urlencode "priority=$priority" $extra_args \
        > "$response_file"; then
        if ! grep -q '"status"[[:space:]]*:[[:space:]]*1' "$response_file"; then
            echo "[notify] ❌ API 响应未确认成功: $title" >&2
            printf '{"time":"%s","title":"%s","result":"api_error"}\n' "$(date -Iseconds)" "$title" >> "$log_file"
            rm -f "$response_file"
            return 1
        fi
        request_id=$(sed -n 's/.*"request"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$response_file" | head -1)
        rm -f "$response_file"
        printf '{"time":"%s","title":"%s","priority":%s,"result":"sent","request":"%s"}\n' "$(date -Iseconds)" "$title" "$priority" "$request_id" >> "$log_file"
        echo "[notify] ✅ 已发送: $title (request=$request_id)"
        return 0
    else
        status=$?
    fi

    echo "[notify] ❌ 发送失败: $title (curl=$status)" >&2
    printf '{"time":"%s","title":"%s","priority":%s,"result":"curl_error","code":%s}\n' "$(date -Iseconds)" "$title" "$priority" "$status" >> "$log_file"
    rm -f "$response_file"
    return "$status"
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
