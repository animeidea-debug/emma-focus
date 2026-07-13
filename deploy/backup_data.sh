#!/bin/sh
# ==============================================================================
# 💾 Emma Focus — 本地 SQLite 数据备份脚本 (CSV 格式)
#
# 迁移后直接备份容器内的 SQLite 数据库，不再调用 GAS API。
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

echo "[backup] 🚀 开始备份 ${TODAY}"

# 从容器内 SQLite 导出所有表为 CSV
DOCKER_CMD="/usr/bin/docker exec site_backend"
SQLITE_CMD="sqlite3 /app/data/poc.db"

# 需要导出的表
TABLES="evaluations activity_logs token_transactions redeem_items app_config"

for table in $TABLES; do
    $DOCKER_CMD sh -c "$SQLITE_CMD -header -csv \"SELECT * FROM $table;\"" > "${OUTPUT_DIR}/${table}.csv" 2>/dev/null
    if [ $? -eq 0 ] && [ -s "${OUTPUT_DIR}/${table}.csv" ]; then
        rows=$(wc -l < "${OUTPUT_DIR}/${table}.csv")
        echo "  ✅ ${table}.csv ($((rows - 1)) rows)"
    else
        echo "  ⚠️  ${table}.csv 为空或导出失败"
        echo "Date,Day_Type,Time_Start,Time_End,Focus_Blocks,Distractions,Eye_Rest_Minutes,Note,Absent" > "${OUTPUT_DIR}/${table}.csv"
    fi
done

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