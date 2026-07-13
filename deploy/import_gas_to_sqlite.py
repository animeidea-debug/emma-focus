#!/usr/bin/env python3
"""
Emma Focus — GAS → SQLite 数据迁移脚本
=========================================
Usage: python3 import_gas_to_sqlite.py <export.json> [db_path]
Default db_path: /app/data/poc.db (inside container)
"""
import json
import sqlite3
import sys
import os
from datetime import datetime

DB_PATH = sys.argv[2] if len(sys.argv) > 2 else "/app/data/poc.db"

def ensure_tables(conn):
    """Create tables if they don't exist (mirrors poc_main.py init_db)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS evaluations (
            date TEXT PRIMARY KEY,
            day_type TEXT DEFAULT '',
            start_time TEXT DEFAULT '',
            end_time TEXT DEFAULT '',
            focus_blocks INTEGER DEFAULT 0,
            distractions INTEGER DEFAULT 0,
            eye_rest_minutes INTEGER DEFAULT 0,
            rating TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            note TEXT DEFAULT '',
            absent INTEGER DEFAULT 0,
            status TEXT DEFAULT 'gray',
            tokens_net INTEGER DEFAULT 0,
            bucket_focus INTEGER DEFAULT 0,
            bucket_coaching INTEGER DEFAULT 0,
            bucket_screen INTEGER DEFAULT 0,
            bucket_activity INTEGER DEFAULT 0,
            bucket_eyerest INTEGER DEFAULT 0,
            bucket_distraction INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            stage_name TEXT DEFAULT '',
            category TEXT DEFAULT '',
            duration INTEGER DEFAULT 0,
            start_time TEXT DEFAULT '',
            end_time TEXT DEFAULT '',
            note TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS tokens (
            silver_balance INTEGER DEFAULT 0,
            gold_balance INTEGER DEFAULT 0,
            exchange_rate INTEGER DEFAULT 5
        );
        CREATE TABLE IF NOT EXISTS token_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            description TEXT DEFAULT '',
            silver_delta INTEGER DEFAULT 0,
            gold_delta INTEGER DEFAULT 0,
            silver_balance INTEGER DEFAULT 0,
            gold_balance INTEGER DEFAULT 0,
            note TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS redeem_items (
            item_id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            description TEXT DEFAULT '',
            coin_type TEXT NOT NULL,
            cost INTEGER NOT NULL,
            active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS api_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            ip TEXT DEFAULT '',
            payload TEXT DEFAULT ''
        );
        INSERT OR IGNORE INTO tokens (silver_balance, gold_balance, exchange_rate) VALUES (0, 0, 5);
        INSERT OR IGNORE INTO app_config (key, value) VALUES ('exchange_rate', '5');
    """)
    conn.commit()

def load_json(path):
    with open(path) as f:
        raw = json.load(f)
    data = raw.get("data", raw)
    print(f"Loaded: {len(data.get('Timeline', []))} timeline rows")
    print(f"         {len(data.get('Evaluations', []))} evaluations")
    print(f"         {len(data.get('Activity_Logs', []))} activity logs")
    print(f"         {len(data.get('Transactions', []))} transactions")
    print(f"         {len(data.get('RedeemItems', []))} redeem items")
    print(f"         {len(data.get('AppConfig', []))} app configs")
    return data

def clear_db(conn):
    """清空所有表"""
    conn.executescript("""
        DELETE FROM evaluations;
        DELETE FROM activity_logs;
        DELETE FROM token_transactions;
        DELETE FROM redeem_items;
        DELETE FROM api_log;
        UPDATE tokens SET silver_balance=0, gold_balance=0, exchange_rate=5;
        DELETE FROM app_config;
        INSERT OR IGNORE INTO app_config (key, value) VALUES ('exchange_rate', '5');
    """)
    conn.commit()
    print("✅ 清空所有表完成")

def import_data(conn, data):
    # 1. Import Timeline → evaluations table
    timeline = data.get("Timeline", [])
    for row in timeline:
        d = row.get("Date", "")
        day_type = row.get("Day_Type", "")
        start_t = row.get("Time_Start", "00:00") or "00:00"
        end_t = row.get("Time_End", "00:00") or "00:00"
        fb = int(row.get("Focus_Blocks", 0) or 0)
        dist = int(row.get("Distractions", 0) or 0)
        eye = int(row.get("Eye_Rest_Minutes", 0) or 0)
        note = str(row.get("Note", "") or "")
        absent = 1 if (str(row.get("Absent", "")).lower() == "true" or row.get("Absent") == "true") else 0
        category = str(row.get("Category", "") or "")

        # Compute status from category
        status = "gray" if absent else ("green" if fb >= 2 and dist <= 1 else "amber")
        if category == "不在场":
            absent = 1
            status = "gray"

        conn.execute("""
            INSERT OR REPLACE INTO evaluations
            (date, day_type, start_time, end_time, focus_blocks, distractions,
             eye_rest_minutes, note, absent, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (d, day_type, start_t, end_t, fb, dist, eye, note, absent,
              "gray" if absent else "green"))

    print(f"✅ 导入 {len(timeline)} 条 Timeline → evaluations")

    # 2. Import Evaluations → update rating, summary, tokens_net
    evals = data.get("Evaluations", [])
    for row in evals:
        d = row.get("Date", "")
        summary = str(row.get("Summary", "") or "")
        rating = str(row.get("Rating", "") or "")
        tokens_net = int(row.get("Tokens_Net", 0) or 0)

        existing = conn.execute("SELECT * FROM evaluations WHERE date=?", (d,)).fetchone()
        if existing:
            conn.execute("""
                UPDATE evaluations SET summary=?, rating=?, tokens_net=?
                WHERE date=?
            """, (summary, rating, tokens_net, d))
        else:
            conn.execute("""
                INSERT INTO evaluations (date, summary, rating, tokens_net, status)
                VALUES (?, ?, ?, ?, 'green')
            """, (d, summary, rating, tokens_net))

    print(f"✅ 导入 {len(evals)} 条 Evaluations")

    # 3. Import Activity_Logs
    logs = data.get("Activity_Logs", [])
    for row in logs:
        d = row.get("Date", "")
        stage = str(row.get("Stage_Name", "") or "")
        category = str(row.get("Category", "") or "")
        duration = int(row.get("Duration", 0) or 0)
        start_t = str(row.get("Start_Time", "") or "")
        end_t = str(row.get("End_Time", "") or "")
        note = str(row.get("Note", "") or "")

        conn.execute("""
            INSERT INTO activity_logs (date, stage_name, category, duration, start_time, end_time, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (d, stage, category, duration, start_t, end_t, note))

    print(f"✅ 导入 {len(logs)} 条 Activity_Logs")

    # 4. Import Transactions
    txns = data.get("Transactions", [])
    for row in txns:
        d = row.get("Date", "")
        ttype = str(row.get("Type", "") or "")
        desc = str(row.get("Description", "") or "")
        s_delta = int(row.get("Silver_Delta", 0) or 0)
        g_delta = int(row.get("Gold_Delta", 0) or 0)
        s_bal = int(row.get("Silver_Balance", 0) or 0)
        g_bal = int(row.get("Gold_Balance", 0) or 0)
        note = str(row.get("Note", "") or "")

        conn.execute("""
            INSERT INTO token_transactions (date, type, description, silver_delta, gold_delta, silver_balance, gold_balance, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (d, ttype, desc, s_delta, g_delta, s_bal, g_bal, note))

    print(f"✅ 导入 {len(txns)} 条 Transactions")

    # 5. Calculate final balances from transactions
    last_txn = conn.execute("""
        SELECT silver_balance, gold_balance FROM token_transactions
        ORDER BY id DESC LIMIT 1
    """).fetchone()
    if last_txn:
        conn.execute("UPDATE tokens SET silver_balance=?, gold_balance=?",
                     (last_txn["silver_balance"], last_txn["gold_balance"]))

    # 6. Import RedeemItems
    items = data.get("RedeemItems", [])
    for row in items:
        conn.execute("""
            INSERT OR REPLACE INTO redeem_items (item_id, label, description, coin_type, cost, active, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            row.get("ItemId", ""),
            row.get("Label", ""),
            str(row.get("Description", "") or ""),
            row.get("CoinType", "silver"),
            int(row.get("Cost", 1) or 1),
            1 if (str(row.get("Active", "")).lower() == "true" or row.get("Active") == "true") else 0,
            int(row.get("Sort", 0) or 0)
        ))
    print(f"✅ 导入 {len(items)} 条 RedeemItems")

    # 7. Import AppConfig
    configs = data.get("AppConfig", [])
    for row in configs:
        key = str(row.get("Key", "") or "")
        val = str(row.get("Value", "") or "")
        if key and val:
            conn.execute("INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)", (key, val))
            if key == "exchange_rate":
                conn.execute("UPDATE tokens SET exchange_rate=?", (int(val),))
    print(f"✅ 导入 {len(configs)} 条 AppConfig")

    conn.commit()

def verify(conn):
    """Verify import counts"""
    tables = [
        ("evaluations", "evaluations"),
        ("activity_logs", "activity_logs"),
        ("token_transactions", "token_transactions"),
        ("redeem_items", "redeem_items"),
    ]
    print("\n=== 数据验证 ===")
    for name, table in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {name}: {count} 条")

    t = conn.execute("SELECT silver_balance, gold_balance, exchange_rate FROM tokens LIMIT 1").fetchone()
    if t:
        print(f"  tokens: 银币={t['silver_balance']}, 金币={t['gold_balance']}, 汇率={t['exchange_rate']}")

    cfg = conn.execute("SELECT value FROM app_config WHERE key='exchange_rate'").fetchone()
    if cfg:
        print(f"  app_config exchange_rate: {cfg['value']}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 import_gas_to_sqlite.py <export.json> [db_path]")
        sys.exit(1)

    json_path = sys.argv[1]
    data = load_json(json_path)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    ensure_tables(conn)
    clear_db(conn)
    import_data(conn, data)
    verify(conn)

    conn.close()
    print("\n✅ 数据迁移完成！")

if __name__ == "__main__":
    main()