#!/bin/sh
# ==============================================================================
# 💾 Emma Focus — Google Sheets 数据备份脚本
#
# 每天 08:00 执行（由 crontab 调度），将 Google Spreadsheet 所有数据表
# 导出为 JSON 并保存到 NAS 本地目录。
#
# cron: 0 8 * * * /tmp/zfsv3/nvme14/13918962622/data/scripts/backup_data.sh
#
# 依赖：
#   - GAS 已部署最新版本（包含 exportAll action）
#   - curl 可用
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_BASE="/tmp/zfsv3/nvme14/13918962622/data/backups/emma_data"
mkdir -p "$BACKUP_BASE"

TODAY=$(date +%Y%m%d)
OUTPUT_FILE="${BACKUP_BASE}/emma_data_${TODAY}.json"
API_TOKEN="emma2026_secure"

# GAS 部署 ID（从 clasp 读取）
GAS_DEPLOY_ID=""
if [ -f "${SCRIPT_DIR}/../gas/.clasp.json" ]; then
    GAS_DEPLOY_ID=$(cat "${SCRIPT_DIR}/../gas/.clasp.json" | python3 -c "import sys,json; print(json.load(sys.stdin).get('scriptId',''))" 2>/dev/null)
fi

if [ -z "$GAS_DEPLOY_ID" ]; then
    echo "[backup] ⚠️ 无法获取 GAS Script ID" >&2
    exit 1
fi

GAS_URL="https://script.google.com/macros/s/${GAS_DEPLOY_ID}/exec"

echo "[backup] 🚀 开始备份 ${TODAY}"
echo "[backup] 请求 URL: ${GAS_URL}?action=exportAll&token=..."

# 调用 GAS API 导出全部数据
HTTP_CODE=$(curl -s -o "$OUTPUT_FILE" -w "%{http_code}" \
    --connect-timeout 15 --max-time 60 \
    "${GAS_URL}?action=exportAll&token=${API_TOKEN}" 2>&1)

if [ "$HTTP_CODE" = "200" ] && [ -s "$OUTPUT_FILE" ]; then
    # 验证 JSON 有效性
    if python3 -c "import json; json.load(open('$OUTPUT_FILE'))" 2>/dev/null; then
        FILE_SIZE=$(ls -lh "$OUTPUT_FILE" | awk '{print $5}')
        echo "[backup] ✅ 备份成功！文件: ${OUTPUT_FILE} (${FILE_SIZE})"

        # 关联通知
        if [ -f "${SCRIPT_DIR}/../video merge/notify.sh" ]; then
            . "${SCRIPT_DIR}/../video merge/notify.sh"
            pushover_notify "Emma Focus" "✅ 数据备份成功 | ${TODAY}
文件: ${FILE_SIZE}" 2>/dev/null || true
        fi
    else
        echo "[backup] ❌ 返回的 JSON 无效" >&2
        rm -f "$OUTPUT_FILE"
        exit 1
    fi
else
    echo "[backup] ❌ 备份失败 (HTTP ${HTTP_CODE})" >&2
    rm -f "$OUTPUT_FILE"
    exit 1
fi