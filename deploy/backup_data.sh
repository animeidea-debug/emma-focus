#!/bin/sh
# ==============================================================================
# 💾 Emma Focus — 数据备份脚本
#
# 在容器内执行全量备份，通过 volume mapping 自动输出到 NAS 宿主机。
# 不需要宿主机上的任何外部工具或 sudo 权限。
#
# 执行流程：
#   1. docker exec → 容器内 python3 /app/backup_data.py
#   2. Python 脚本在容器内创建一致性 SQLite 快照 + CSV 导出
#   3. 输出到 /app/backups/YYYYMMDD/
#   4. 通过 NAS 项目管理的专用 volume mapping 输出到宿主机集中备份目录
#
# cron: 0 8 * * * docker exec site_backend python3 /app/backup_data.py
#       0 20 * * * docker exec site_backend python3 /app/backup_data.py
#
# NAS 输出路径：
#   /tmp/zfsv3/nvme14/13918962622/data/backups/emma_data/YYYYMMDD/
#     ├── poc.db              # 完整 SQLite 数据库文件（一致性快照）
#     ├── evaluations.csv     # CSV 导出（可读性备用）
#     ├── activity_logs.csv
#     ├── token_transactions.csv
#     ├── redeem_items.csv
#     └── app_config.csv
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTAINER="site_backend"
EXIT_CODE=0

echo "============================================="
echo " 💾 Emma Focus — 数据备份"
echo "============================================="
echo ""

# 检查容器是否存在
if ! /usr/bin/docker ps --filter name="${CONTAINER}" --format "{{.Names}}" | grep -q "${CONTAINER}"; then
    echo -e "❌ 容器 ${CONTAINER} 未运行"
    echo "   请先启动容器: docker compose -p site up -d"
    exit 1
fi

echo "⏳ 在容器 ${CONTAINER} 内执行备份..."
echo ""

# 在容器内执行 Python 备份脚本
/usr/bin/docker exec "${CONTAINER}" python3 /app/backup_data.py
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 备份完成！"
else
    echo "❌ 备份执行异常（exit code: ${EXIT_CODE}）"
fi

# Pushover 通知：本地仓库路径或 NAS /scripts 同目录均支持。
NOTIFY_SCRIPT="${SCRIPT_DIR}/../video merge/notify.sh"
[ -f "$NOTIFY_SCRIPT" ] || NOTIFY_SCRIPT="${SCRIPT_DIR}/notify.sh"
if [ -f "$NOTIFY_SCRIPT" ]; then
    . "$NOTIFY_SCRIPT"
    TODAY=$(date +%Y%m%d)
    if [ $EXIT_CODE -eq 0 ]; then
        pushover_notify "Emma Focus Backup" "✅ 数据备份成功 | ${TODAY}
SQLite 快照与 CSV 已生成" 0 || true
    else
        pushover_notify "Emma Focus Backup" "⚠️ 数据备份失败 | ${TODAY}
退出码: ${EXIT_CODE}
日志: /tmp/nas-emma-backup.cron.log" 1 || true
    fi
fi

exit $EXIT_CODE
