#!/usr/bin/env python3
"""
Emma Focus — 数据备份脚本（容器内执行版）

直接在容器内运行，不需要宿主机任何工具。
输出到 /app/backups/YYYYMMDD/。
该目录由 NAS 项目的生产 Compose 显式映射到宿主机集中备份目录。

用法（容器内）：
    python3 /app/backup_data.py

用法（宿主机）：
    docker exec site_backend python3 /app/backup_data.py
    
NAS 输出目录：
    /tmp/zfsv3/nvme14/13918962622/data/backups/emma_data/YYYYMMDD/
      ├── poc.db              # 完整 SQLite 数据库文件（一致性快照）
      ├── evaluations.csv     # CSV 导出
      ├── activity_logs.csv
      ├── token_transactions.csv
      ├── redeem_items.csv
      └── app_config.csv
"""

import sqlite3
import csv
import os
import io
import re
import sys
from datetime import datetime, timedelta

# 数据库路径（容器内）
DB_PATH = os.environ.get("EMMA_DB_PATH", "/app/data/poc.db")
# 生产 Compose 显式设置同一值；环境变量也用于隔离测试和恢复演练。
BACKUP_BASE = os.environ.get("EMMA_BACKUP_BASE", "/app/backups")

# 需要导出的表
TABLES = ["evaluations", "activity_logs", "token_transactions", "redeem_items", "app_config"]

# 各表的 CSV header（用于空表回退）
TABLE_HEADERS = {
    "evaluations": "Date,Day_Type,Time_Start,Time_End,Focus_Blocks,Distractions,Eye_Rest_Minutes,Note,Absent",
    "activity_logs": "ID,Date,Stage_Name,Category,Duration,Start_Time,End_Time,Note",
    "token_transactions": "ID,Date,Type,Description,Silver_Delta,Gold_Delta,Silver_Balance,Gold_Balance,Note",
    "redeem_items": "Item_ID,Label,Description,Coin_Type,Cost,Active,Sort_Order",
    "app_config": "Key,Value",
}


def backup_database(conn, dest):
    """Create a consistent snapshot of the database"""
    temp_dest = dest + ".tmp"
    if os.path.exists(temp_dest):
        os.remove(temp_dest)
    backup = sqlite3.connect(temp_dest)
    try:
        conn.backup(backup)
    finally:
        backup.close()
    os.replace(temp_dest, dest)
    size = os.path.getsize(dest)
    return size


def export_table_to_csv(conn, table_name):
    """Export a single table as CSV string"""
    try:
        cur = conn.execute(f"SELECT * FROM [{table_name}]")
        rows = cur.fetchall()
        if not rows:
            return None
        headers = [d[0] for d in cur.description]
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(headers)
        for r in rows:
            w.writerow([str(v) if v is not None else "" for v in r])
        result = buf.getvalue()
        buf.close()
        return result
    except Exception as e:
        print(f"  ⚠️  导出 {table_name} 失败: {e}")
        return None


def clean_old_backups(backup_base, days=30):
    """Remove backups older than `days` days"""
    cutoff = datetime.now() - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y%m%d")
    count = 0
    if not os.path.isdir(backup_base):
        return count
    for entry in os.listdir(backup_base):
        dirpath = os.path.join(backup_base, entry)
        if not re.fullmatch(r"\d{8}", entry):
            continue
        try:
            datetime.strptime(entry, "%Y%m%d")
        except ValueError:
            continue
        if os.path.isdir(dirpath) and entry < cutoff_str:
            import shutil
            shutil.rmtree(dirpath)
            print(f"  🗑️  删除 {entry}")
            count += 1
    return count


def main():
    today = datetime.now().strftime("%Y%m%d")
    now = datetime.now().strftime("%H%M%S")
    output_dir = os.path.join(BACKUP_BASE, today)

    if not os.path.isfile(DB_PATH):
        raise FileNotFoundError(f"数据库不存在: {DB_PATH}")

    print(f"[backup] 🚀 开始备份 {today} {now}")
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # ----- 1. 一致性 SQLite 快照 -----
    print("")
    print("[backup] 📦 备份完整数据库文件...")
    
    snapshot_path = os.path.join(output_dir, "poc.db")
    conn = sqlite3.connect(DB_PATH)
    try:
        size = backup_database(conn, snapshot_path)
        print(f"  ✅ poc.db 备份完成 ({size // 1024}K)")
    except Exception as e:
        print(f"  ❌ 数据库备份失败: {e}")
        conn.close()
        return 1
    
    # ----- 2. CSV 导出 -----
    print("")
    print("[backup] 📄 导出 CSV...")
    
    csv_ok = 0
    csv_fail = 0
    
    for table in TABLES:
        csv_content = export_table_to_csv(conn, table)
        csv_path = os.path.join(output_dir, f"{table}.csv")
        
        if csv_content:
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                f.write(csv_content)
            lines = csv_content.count("\n")
            print(f"  ✅ {table}.csv ({lines} lines)")
            csv_ok += 1
        else:
            # 写入空 header
            header = TABLE_HEADERS.get(table, "")
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                f.write(header + "\n")
            print(f"  ⚠️  {table}.csv 为空")
            csv_fail += 1
    
    conn.close()
    
    # ----- 3. 清理 30 天前的旧备份 -----
    print("")
    print("[backup] 🧹 清理 30 天前的旧备份...")
    purge_count = clean_old_backups(BACKUP_BASE)
    if purge_count == 0:
        print("  无旧备份需清理")
    
    # ----- 统计 -----
    total_db_size = 0
    total_csv_size = 0
    for fname in os.listdir(output_dir):
        fpath = os.path.join(output_dir, fname)
        if os.path.isfile(fpath):
            sz = os.path.getsize(fpath)
            if fname == "poc.db" or fname.startswith("poc.db"):
                total_db_size += sz
            else:
                total_csv_size += sz
    
    print("")
    print("=============================================")
    print(f" ✅ 备份完成！")
    print(f"    目录: {output_dir}")
    print(f"    DB:   {total_db_size // 1024}K")
    print(f"    CSV:  {total_csv_size // 1024}K ({csv_ok} 表成功)")
    print("=============================================")
    
    print("")
    print(f" 📍 持久化输出: {output_dir}/")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[backup] ❌ 备份失败: {exc}", file=sys.stderr)
        sys.exit(1)
