#!/bin/sh
# ==============================================================================
# 💾 Emma Focus — Google Sheets 数据备份脚本 (CSV 格式)
#
# 每天 08:00 执行，将 Google Spreadsheet 所有数据表导出为 CSV 文件。
#
# cron: 0 8 * * * /tmp/zfsv3/nvme14/13918962622/data/scripts/backup_data.sh
#
# 输出目录（NAS 宿主机）：
#   /tmp/zfsv3/nvme14/13918962622/data/backups/emma_data/YYYYMMDD/
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_BASE="/mnt/backups/emma_data"
TODAY=$(date +%Y%m%d)
OUTPUT_DIR="${BACKUP_BASE}/${TODAY}"
mkdir -p "$OUTPUT_DIR"

API_TOKEN="emma2026_secure"

# GAS 部署 ID（@28，含 exportAll action）
GAS_DEPLOY_ID="AKfycbwdRAkRUJpNDD94-yf5tfPgM5j9LlIMiRfqUjamj7M1peDq7awf7d7XADfnkeFZ8F2E-w"
GAS_URL="https://script.google.com/macros/s/${GAS_DEPLOY_ID}/exec"

echo "[backup] 🚀 开始备份 ${TODAY}"

# 获取 JSON 数据
JSON_FILE="/tmp/emma_backup_${TODAY}.json"
HTTP_CODE=$(curl -sL -o "$JSON_FILE" -w "%{http_code}" \
    --connect-timeout 15 --max-time 60 \
    "${GAS_URL}?action=exportAll&token=${API_TOKEN}" 2>&1)

if [ "$HTTP_CODE" != "200" ] || [ ! -s "$JSON_FILE" ]; then
    echo "[backup] ❌ GAS API 返回 HTTP ${HTTP_CODE}" >&2
    rm -f "$JSON_FILE"
    exit 1
fi

# 验证 JSON 并生成 CSV
python3 -c "
import json, csv, os

with open('${JSON_FILE}') as f:
    raw = json.load(f)

data = raw.get('data', raw)
output_dir = '${OUTPUT_DIR}'

for table_name, rows in data.items():
    if not rows or not isinstance(rows, list):
        continue
    headers = list(rows[0].keys())
    csv_path = os.path.join(output_dir, f'{table_name}.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as out:
        w = csv.writer(out)
        w.writerow(headers)
        for row in rows:
            w.writerow([str(row.get(h, '')).replace('\n', ' ') for h in headers])
    print(f'  ✅ {table_name}.csv ({len(rows)} rows)')
" 2>&1

rm -f "$JSON_FILE"

# 统计
TOTAL_FILES=$(ls "$OUTPUT_DIR"/*.csv 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "$OUTPUT_DIR" 2>/dev/null | awk '{print $1}')

echo "[backup] ✅ 备份完成！目录: ${OUTPUT_DIR}"
echo "[backup]    文件: ${TOTAL_FILES} 个 CSV | 大小: ${TOTAL_SIZE}"

# Pushover 通知
if [ -f "${SCRIPT_DIR}/../video merge/notify.sh" ]; then
    . "${SCRIPT_DIR}/../video merge/notify.sh"
    pushover_notify "Emma Focus" "✅ 数据备份成功 | ${TODAY}
${TOTAL_FILES} 个 CSV | ${TOTAL_SIZE}" 2>/dev/null || true
fi