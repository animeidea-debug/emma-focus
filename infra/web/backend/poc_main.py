"""
Emma Focus — 完整本地后端 (FastAPI + SQLite)
============================================
Full replacement for GAS backend. All business logic ported from emma_focus_api.gs.

Endpoints:
  GET  /api/poc/dashboard?ym=       — Dashboard data (replaces GAS getDashboard)
  GET  /api/poc/charts              — Chart data (replaces GAS getCharts)
  GET  /api/poc/tokens              — Token balance + transactions (replaces GAS getTokens)
  GET  /api/poc/redeem-items        — Redeem shop items (replaces GAS getRedeemItems)
  GET  /api/poc/exchange-rate       — Exchange rate (replaces GAS getExchangeRate)
  GET  /api/poc/logs?date=&limit=   — Daily activity logs (replaces GAS getLogs)
  GET  /api/poc/health              — Health check
  POST /api/poc/evaluate            — Submit day evaluation (replaces GAS doPost single)
  POST /api/poc/batch-write         — Batch write days (replaces GAS batch)
  POST /api/poc/redeem              — Redeem item (replaces GAS actionRedeem)
  POST /api/poc/bonus               — Manual bonus (replaces GAS actionBonus)
  POST /api/poc/exchange            — Coin exchange (replaces GAS actionExchange)
  POST /api/poc/mark-absent         — Mark day absent (replaces GAS actionMarkAbsent)
  POST /api/poc/upsert-redeem-item  — Admin upsert single item
  POST /api/poc/upsert-redeem-items — Admin batch upsert items
  POST /api/poc/set-exchange-rate   — Admin set exchange rate
  POST /api/poc/seed-dummy          — PoC only: seed test data

Database: /app/data/poc.db (standalone, separate from site.db)
"""

from fastapi import FastAPI, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import os
import json
from datetime import datetime, timedelta

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_PATH = "/app/data/poc.db"
os.makedirs("/app/data", exist_ok=True)

router = APIRouter(prefix="/api/poc")

# ─── Category → Bucket mapping (mirrors GAS) ───────────────────────────────
CATEGORY_BUCKETS = {
    "Focus":        {"bucket": "focus",       "color": "#3b82f6"},
    "Coaching":     {"bucket": "coaching",    "color": "#a855f7"},
    "Screen":       {"bucket": "screen",      "color": "#f59e0b"},
    "Activity":     {"bucket": "activity",    "color": "#06b6d4"},
    "Distraction":  {"bucket": "distraction", "color": "#ef4444"},
    "Eye Rest":     {"bucket": "eyerest",     "color": "#22c55e"}
}
NEUTRAL_COLOR = "#9ca3af"

BUCKET_TO_CARD = {
    "focus":       "study",
    "coaching":    "coaching",
    "screen":      "screen",
    "activity":    "study",
    "eyerest":     None,
    "distraction": "waste",
    "neutral":     "waste"
}

TOKEN_START_DATE = "2026-06-27"

def bucket_for(category):
    hit = CATEGORY_BUCKETS.get(category)
    if hit:
        return hit["bucket"]
    return "neutral"

# ─── Database ───────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
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
    conn.close()

init_db()

# ─── Helpers ────────────────────────────────────────────────────────────────

def log_action(action: str, ip: str = "", payload: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO api_log (timestamp, action, ip, payload) VALUES (?, ?, ?, ?)",
                     (datetime.now().isoformat(), action, ip, str(payload)[:200]))
        conn.commit()
        conn.close()
    except Exception:
        pass

def today_iso():
    return datetime.now().strftime("%Y-%m-%d")

def shift_date(date_str: str, delta: int) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    d += timedelta(days=delta)
    return d.strftime("%Y-%m-%d")

def parse_date_safe(val):
    """Safely parse a date string, return datetime or None."""
    if not val:
        return None
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None

def iso_week_bounds(date_str: str):
    """Return (monday, sunday, weekTag) for the ISO week containing date_str."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    dow = (d.weekday() + 1) % 7  # Monday=0
    monday = d - timedelta(days=dow)
    sunday = monday + timedelta(days=6)
    fmt = lambda x: x.strftime("%Y-%m-%d")
    return fmt(monday), fmt(sunday), fmt(monday)[5:] + "~" + fmt(sunday)[5:]

def rebuild_balances(conn):
    """Rebuild silver_balance/gold_balance from transactions >= TOKEN_START_DATE."""
    rows = conn.execute("""
        SELECT silver_delta, gold_delta, date
        FROM token_transactions
        WHERE date >= ?
        ORDER BY id ASC
    """, (TOKEN_START_DATE,)).fetchall()
    s_bal, g_bal = 0, 0
    for r in rows:
        s_bal += r["silver_delta"] or 0
        g_bal += r["gold_delta"] or 0
    # Update balance fields in transactions
    conn.execute("""
        UPDATE token_transactions
        SET silver_balance = (
            SELECT COALESCE(SUM(silver_delta), 0) FROM token_transactions t2
            WHERE t2.id <= token_transactions.id AND t2.date >= ?
        ), gold_balance = (
            SELECT COALESCE(SUM(gold_delta), 0) FROM token_transactions t2
            WHERE t2.id <= token_transactions.id AND t2.date >= ?
        )
    """, (TOKEN_START_DATE, TOKEN_START_DATE))
    return s_bal, g_bal

def get_tokens_data(conn):
    """Return {silverBalance, goldBalance, transactions} matching GAS format."""
    t = conn.execute("SELECT silver_balance, gold_balance, exchange_rate FROM tokens LIMIT 1").fetchone()
    s_bal = t["silver_balance"] if t else 0
    g_bal = t["gold_balance"] if t else 0
    rate = t["exchange_rate"] if t else 5

    txns = conn.execute("""
        SELECT * FROM token_transactions
        WHERE date >= ?
        ORDER BY id DESC LIMIT 200
    """, (TOKEN_START_DATE,)).fetchall()

    # Also compute actual balances from transactions
    actual_s, actual_g = rebuild_balances(conn)
    # Sync tokens table
    conn.execute("UPDATE tokens SET silver_balance=?, gold_balance=?", (actual_s, actual_g))

    transactions = []
    for r in txns:
        transactions.append({
            "date": r["date"],
            "type": r["type"],
            "description": r["description"],
            "silverDelta": r["silver_delta"] or 0,
            "goldDelta": r["gold_delta"] or 0,
            "silverBalance": r["silver_balance"] or 0,
            "goldBalance": r["gold_balance"] or 0,
            "note": r["note"] or ""
        })

    return {
        "silverBalance": actual_s,
        "goldBalance": actual_g,
        "transactions": transactions
    }

def status_from_rating(rating: str, absent: bool, blocks: int, dist: int) -> str:
    if absent:
        return "gray"
    if rating:
        if "🟢" in rating:
            return "green"
        if "🟡" in rating:
            return "amber"
        if "🔴" in rating:
            return "red"
        if "⚪" in rating:
            return "gray"
    if blocks == 0 or dist > 3:
        return "red"
    if blocks >= 2 and dist <= 1:
        return "green"
    return "amber"

# ─── Build Dashboard (mirrors GAS buildDashboard) ───────────────────────────

def build_dashboard(conn, ym: str = ""):
    """Returns dashboard data matching GAS getDashboard format."""
    timeline_rows = conn.execute("SELECT * FROM evaluations ORDER BY date").fetchall()
    logs_rows = conn.execute("SELECT * FROM activity_logs").fetchall()

    # Data range
    min_date, max_date = None, None
    for r in timeline_rows:
        d = r["date"]
        if d:
            if not min_date or d < min_date:
                min_date = d
            if not max_date or d > max_date:
                max_date = d

    data_range = {}
    if min_date and max_date:
        data_range = {
            "minYM": min_date[:7],
            "maxYM": max_date[:7],
            "minDate": min_date,
            "maxDate": max_date
        }

    if not ym and max_date:
        ym = max_date[:7]

    # Build days dict
    days = {}
    for r in timeline_rows:
        d = r["date"]
        if ym and d[:7] != ym:
            continue

        bm = {
            "focus": r["bucket_focus"] or 0,
            "coaching": r["bucket_coaching"] or 0,
            "screen": r["bucket_screen"] or 0,
            "activity": r["bucket_activity"] or 0,
            "eyerest": r["bucket_eyerest"] or 0,
            "distraction": r["bucket_distraction"] or 0
        }

        # Add activity_logs durations to bucketMinutes
        day_logs = [l for l in logs_rows if l["date"] == d]
        for l in day_logs:
            b = bucket_for(l["category"])
            dur = l["duration"] or 0
            bm[b] = bm.get(b, 0) + dur

        absent = bool(r["absent"])
        days[d] = {
            "date": d,
            "dayType": r["day_type"] or "",
            "startTime": r["start_time"] or "",
            "endTime": r["end_time"] or "",
            "focusBlocks": r["focus_blocks"] or 0,
            "distractions": r["distractions"] or 0,
            "eyeRestMinutes": r["eye_rest_minutes"] or 0,
            "rating": r["rating"] or "",
            "summary": r["summary"] or "",
            "note": r["note"] or "",
            "absent": absent,
            "status": status_from_rating(r["rating"] or "", absent, r["focus_blocks"] or 0, r["distractions"] or 0),
            "tokensNet": r["tokens_net"] or 0,
            "bucketMinutes": bm
        }

    # ── Compute month summary (ym-filtered) ──
    month_tokens = 0
    m_focus = m_activity = m_coaching = m_screen = m_waste = 0
    m_seen = set()
    m_days = m_workdays = m_weekends = 0

    for r in timeline_rows:
        d = r["date"]
        if ym and d[:7] != ym:
            continue
        if not d or d in m_seen:
            continue
        m_seen.add(d)
        absent = bool(r["absent"])
        if not absent:
            parsed = parse_date_safe(d)
            if parsed:
                dow = parsed.weekday()
                m_days += 1
                if dow >= 5:
                    m_weekends += 1
                else:
                    m_workdays += 1
        if d >= TOKEN_START_DATE:
            month_tokens += r["tokens_net"] or 0

    for l in logs_rows:
        d = l["date"]
        if ym and d[:7] != ym:
            continue
        dur = l["duration"] or 0
        b = bucket_for(l["category"])
        slot = BUCKET_TO_CARD.get(b)
        if slot == "study":
            if b == "focus":
                m_focus += dur
            elif b == "activity":
                m_activity += dur
        elif slot == "coaching":
            m_coaching += dur
        elif slot == "screen":
            m_screen += dur
        elif slot == "waste":
            m_waste += dur

    month_summary = {
        "totalDays": m_days,
        "workdays": m_workdays,
        "weekends": m_weekends,
        "totalTokens": month_tokens,
        "studyHours": round((m_focus + m_activity) / 60, 1),
        "focusHours": round(m_focus / 60, 1),
        "activityHours": round(m_activity / 60, 1),
        "coachingHours": round(m_coaching / 60, 1),
        "screenHours": round(m_screen / 60, 1),
        "wasteHours": round(m_waste / 60, 1)
    }

    # ── Compute full summary (all time, no ym filter) ──
    full_tokens = 0
    f_focus = f_activity = f_coaching = f_screen = f_waste = 0
    f_seen = set()
    f_days = f_workdays = f_weekends = 0

    for r in timeline_rows:
        d = r["date"]
        if not d or d in f_seen:
            continue
        f_seen.add(d)
        absent = bool(r["absent"])
        if not absent:
            parsed = parse_date_safe(d)
            if parsed:
                dow = parsed.weekday()
                f_days += 1
                if dow >= 5:
                    f_weekends += 1
                else:
                    f_workdays += 1
        if d >= TOKEN_START_DATE:
            full_tokens += r["tokens_net"] or 0

    for l in logs_rows:
        d = l["date"]
        if not d:
            continue
        dur = l["duration"] or 0
        b = bucket_for(l["category"])
        slot = BUCKET_TO_CARD.get(b)
        if slot == "study":
            if b == "focus":
                f_focus += dur
            elif b == "activity":
                f_activity += dur
        elif slot == "coaching":
            f_coaching += dur
        elif slot == "screen":
            f_screen += dur
        elif slot == "waste":
            f_waste += dur

    full_summary = {
        "totalDays": f_days,
        "workdays": f_workdays,
        "weekends": f_weekends,
        "totalTokens": full_tokens,
        "studyHours": round((f_focus + f_activity) / 60, 1),
        "focusHours": round(f_focus / 60, 1),
        "activityHours": round(f_activity / 60, 1),
        "coachingHours": round(f_coaching / 60, 1),
        "screenHours": round(f_screen / 60, 1),
        "wasteHours": round(f_waste / 60, 1)
    }

    # Month averages
    overall_b = wd_b = we_b = 0
    overall_c = wd_c = we_c = 0
    for d_key, d_val in days.items():
        if d_val["absent"]:
            continue
        if ym and d_key[:7] != ym:
            continue
        parsed = parse_date_safe(d_key)
        if not parsed:
            continue
        dow = parsed.weekday()
        overall_b += d_val["focusBlocks"]
        overall_c += 1
        if dow >= 5:
            we_b += d_val["focusBlocks"]
            we_c += 1
        else:
            wd_b += d_val["focusBlocks"]
            wd_c += 1

    def avg(blocks, count):
        return round((blocks * 0.5) / count, 1) if count > 0 else 0

    month_averages = {
        "overallHours": avg(overall_b, overall_c),
        "workdayHours": avg(wd_b, wd_c),
        "weekendHours": avg(we_b, we_c),
        "dayCounts": {
            "overall": overall_c,
            "workday": wd_c,
            "weekend": we_c
        }
    }

    return {
        "ym": ym or (max_date[:7] if max_date else ""),
        "dataRange": data_range,
        "summary": full_summary,
        "monthSummary": month_summary,
        "monthAverages": month_averages,
        "days": days
    }

# ─── Build Charts (mirrors GAS buildCharts) ────────────────────────────────

def build_charts(conn):
    """Returns chart data matching GAS getCharts format."""
    logs = conn.execute("SELECT * FROM activity_logs").fetchall()
    evals = conn.execute("SELECT * FROM evaluations ORDER BY date").fetchall()

    # Distribution: by stage_name
    dist_map = {}
    for l in logs:
        name = l["stage_name"] or "未知"
        if name not in dist_map:
            dist_map[name] = {"stage": name, "minutes": 0, "category": l["category"] or ""}
        dist_map[name]["minutes"] += l["duration"] or 0

    items = sorted(dist_map.values(), key=lambda x: x["minutes"], reverse=True)

    # Trend: 90-day sliding window from max date
    max_date = None
    for r in evals:
        d = r["date"]
        if d and (not max_date or d > max_date):
            max_date = d
    if not max_date:
        max_date = today_iso()

    daily_fb = {}
    for r in evals:
        d = r["date"]
        if not d:
            continue
        if d not in daily_fb:
            daily_fb[d] = {"focusBlocks": 0, "distractions": 0}
        daily_fb[d]["focusBlocks"] += r["focus_blocks"] or 0
        daily_fb[d]["distractions"] += r["distractions"] or 0

    end = datetime.strptime(max_date, "%Y-%m-%d")
    points = []
    for i in range(89, -1, -1):
        d = end - timedelta(days=i)
        ds = d.strftime("%Y-%m-%d")
        v = daily_fb.get(ds, {"focusBlocks": 0, "distractions": 0})
        points.append({
            "date": ds,
            "focusBlocks": v["focusBlocks"],
            "distractions": v["distractions"]
        })

    # 7-day rolling average
    rolling7 = []
    for i in range(len(points)):
        start = max(0, i - 6)
        slice_pts = points[start:i + 1]
        n = len(slice_pts)
        rolling7.append({
            "date": points[i]["date"],
            "focusBlocks": round(sum(p["focusBlocks"] for p in slice_pts) / n, 2),
            "distractions": round(sum(p["distractions"] for p in slice_pts) / n, 2)
        })

    return {
        "distribution": {"items": items},
        "trend": {
            "from": points[0]["date"] if points else "",
            "to": points[-1]["date"] if points else "",
            "points": points,
            "rolling7": rolling7
        }
    }

# ─── Process evaluation write (mirrors GAS writeOneDay logic) ──────────────

def write_evaluation(conn, payload: dict):
    """Write a single day's evaluation + timeline + stages. Mirrors GAS writeOneDay."""
    date_str = payload.get("date", "")

    # ── Timeline (evaluations table in SQLite) ──
    if payload.get("timeline") and isinstance(payload["timeline"], list):
        for row in payload["timeline"]:
            d = row.get("Date", date_str)
            day_type = row.get("Day_Type", "")
            start_t = row.get("Time_Start", "")
            end_t = row.get("Time_End", "")
            fb = int(row.get("Focus_Blocks", 0))
            dist = int(row.get("Distractions", 0))
            eye = int(row.get("Eye_Rest_Minutes", 0))
            note = row.get("Note", "")
            absent = 1 if (row.get("Absent") == "true" or row.get("Absent") is True) else 0
            category = row.get("Category", "")

            conn.execute("""
                INSERT OR REPLACE INTO evaluations
                (date, day_type, start_time, end_time, focus_blocks, distractions,
                 eye_rest_minutes, note, absent, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (d, day_type, start_t, end_t, fb, dist, eye, note, absent,
                  "gray" if absent else "green"))

    # ── Evaluations ──
    if payload.get("evaluations") and isinstance(payload["evaluations"], dict):
        ev = payload["evaluations"]
        d = ev.get("Date", date_str)
        summary = ev.get("Summary", "")
        rating = ev.get("Rating", "")
        tokens_net = int(ev.get("Tokens_Net", 0))

        # Check if row exists, then update specific fields
        existing = conn.execute("SELECT * FROM evaluations WHERE date=?", (d,)).fetchone()
        if existing:
            conn.execute("""
                UPDATE evaluations SET summary=?, rating=?, tokens_net=?
                WHERE date=?
            """, (summary, rating, tokens_net, d))
        else:
            conn.execute("""
                INSERT INTO evaluations (date, summary, rating, tokens_net)
                VALUES (?, ?, ?, ?)
            """, (d, summary, rating, tokens_net))

    # ── Activity_Logs / Stages ──
    if payload.get("stages") and isinstance(payload["stages"], list):
        base_date = date_str
        # Delete old logs for this date
        conn.execute("DELETE FROM activity_logs WHERE date=?", (base_date,))
        for s in payload["stages"]:
            stage_date = s.get("date", base_date)
            conn.execute("""
                INSERT INTO activity_logs (date, stage_name, category, duration, start_time, end_time, note)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                stage_date,
                s.get("stage", ""),
                s.get("category", ""),
                int(s.get("duration", 0)),
                s.get("start", ""),
                s.get("end", ""),
                s.get("note", "")
            ))

    # ── Token derivation ──
    write_date = date_str or (payload.get("timeline") and payload["timeline"][0].get("Date")) or \
                 (payload.get("evaluations") and payload["evaluations"].get("Date"))
    if write_date and write_date >= TOKEN_START_DATE:
        derive_transactions(conn, write_date)

    return {"status": "Success"}

# ─── Token derivation (mirrors GAS deriveTransactionsForDate) ──────────────

def derive_transactions(conn, date_str: str):
    """Derive award/streak/eyerest transactions for a date."""
    # Delete existing derived transactions for this date
    derived_types = ("award_silver", "award_gold", "streak_gold", "eyerest_silver")
    conn.execute("""
        DELETE FROM token_transactions
        WHERE date = ? AND type IN (?, ?, ?, ?)
    """, (date_str, *derived_types))

    # Get tokens_net from evaluations
    ev = conn.execute("SELECT tokens_net, rating, focus_blocks, distractions, absent FROM evaluations WHERE date=?",
                      (date_str,)).fetchone()
    if ev:
        tokens_net = ev["tokens_net"] or 0
        if tokens_net != 0:
            conn.execute("""
                INSERT INTO token_transactions (date, type, description, silver_delta, gold_delta)
                VALUES (?, 'award_silver', ?, ?, 0)
            """, (date_str, "专注奖励 " + date_str, tokens_net))

        # Check excellent day → award_gold
        is_excellent = (
            not ev["absent"]
            and (ev["focus_blocks"] or 0) >= 2
            and (ev["distractions"] or 0) == 0
        )
        if is_excellent:
            # Check screen overtime
            screen_logs = conn.execute("""
                SELECT SUM(duration) as total FROM activity_logs
                WHERE date=? AND category='Screen'
            """, (date_str,)).fetchone()
            if not screen_logs or (screen_logs["total"] or 0) <= 30:
                conn.execute("""
                    INSERT INTO token_transactions (date, type, description, silver_delta, gold_delta)
                    VALUES (?, 'award_gold', ?, 0, 1)
                """, (date_str, "优秀日金币 " + date_str))

                # Streak: check previous 2 days also have award_gold
                d1 = shift_date(date_str, -1)
                d2 = shift_date(date_str, -2)
                d3 = shift_date(date_str, -3)
                has_gold = lambda ds: conn.execute(
                    "SELECT COUNT(*) as c FROM token_transactions WHERE date=? AND type='award_gold'",
                    (ds,)).fetchone()["c"] > 0
                has_streak = lambda ds: conn.execute(
                    "SELECT COUNT(*) as c FROM token_transactions WHERE date=? AND type='streak_gold'",
                    (ds,)).fetchone()["c"] > 0

                if has_gold(d1) and has_gold(d2) and (not has_gold(d3) or has_streak(d3)):
                    conn.execute("""
                        INSERT INTO token_transactions (date, type, description, silver_delta, gold_delta)
                        VALUES (?, 'streak_gold', ?, 0, 1)
                    """, (date_str, "3 日连击奖励"))

    # Eye rest milestone
    recompute_eyerest(conn, date_str)

    # Rebuild balances
    rebuild_balances(conn)

def recompute_eyerest(conn, date_str: str):
    """Recompute eyerest_silver for the ISO week of date_str."""
    monday, sunday, week_tag = iso_week_bounds(date_str)
    # Delete existing eyerest_silver for this week
    conn.execute("""
        DELETE FROM token_transactions
        WHERE type='eyerest_silver' AND date >= ? AND date <= ?
    """, (monday, sunday))

    # Sum eye_rest_minutes for the week
    week_total = conn.execute("""
        SELECT COALESCE(SUM(eye_rest_minutes), 0) as total FROM evaluations
        WHERE date >= ? AND date <= ?
    """, (monday, sunday)).fetchone()["total"]

    count = week_total // 60
    last_date = conn.execute("""
        SELECT date FROM evaluations WHERE date >= ? AND date <= ? ORDER BY date DESC LIMIT 1
    """, (monday, sunday)).fetchone()
    last = last_date["date"] if last_date else sunday

    for i in range(count):
        conn.execute("""
            INSERT INTO token_transactions (date, type, description, silver_delta, gold_delta)
            VALUES (?, 'eyerest_silver', ?, 1, 0)
        """, (last, f"护眼里程碑 {week_tag} (#{i+1})"))

# ─── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "PoC backend is running", "note": "Independent from production GAS"}

# ─── Health ─────────────────────────────────────────────────────────────────

@app.get("/api/poc/health")
def health():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
    conn.close()
    return {"status": "ok", "evaluations": count}

# ─── Dashboard ──────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(ym: str = ""):
    conn = get_db()
    try:
        return build_dashboard(conn, ym)
    finally:
        conn.close()

# ─── Charts ─────────────────────────────────────────────────────────────────

@router.get("/charts")
async def get_charts():
    conn = get_db()
    try:
        return build_charts(conn)
    finally:
        conn.close()

# ─── Tokens ─────────────────────────────────────────────────────────────────

@router.get("/tokens")
async def get_tokens():
    conn = get_db()
    try:
        return get_tokens_data(conn)
    finally:
        conn.close()

# ─── Redeem Items ───────────────────────────────────────────────────────────

@router.get("/redeem-items")
async def get_redeem_items():
    conn = get_db()
    try:
        items = conn.execute("SELECT * FROM redeem_items WHERE active=1 ORDER BY sort_order ASC").fetchall()
        return [
            {
                "itemId": r["item_id"],
                "label": r["label"],
                "description": r["description"] or "",
                "coinType": r["coin_type"],
                "cost": r["cost"] or 0,
                "active": bool(r["active"]),
                "sort": r["sort_order"] or 0
            }
            for r in items
        ]
    finally:
        conn.close()

# ─── Exchange Rate ──────────────────────────────────────────────────────────

@router.get("/exchange-rate")
async def get_exchange_rate():
    conn = get_db()
    try:
        row = conn.execute("SELECT value FROM app_config WHERE key='exchange_rate'").fetchone()
        rate = int(row["value"]) if row else 5
        return {"rate": rate}
    finally:
        conn.close()

# ─── Daily Logs (Activity_Logs filtered by date) ───────────────────────────

@router.get("/logs")
async def get_logs(date: str = "", limit: int = 100):
    conn = get_db()
    try:
        if date:
            rows = conn.execute("""
                SELECT * FROM activity_logs WHERE date=? ORDER BY start_time ASC
            """, (date,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM activity_logs ORDER BY date DESC, start_time ASC LIMIT ?
            """, (limit,)).fetchall()
        return [
            {
                "Date": r["date"],
                "Stage_Name": r["stage_name"],
                "Category": r["category"],
                "Duration": r["duration"],
                "Start_Time": r["start_time"],
                "End_Time": r["end_time"],
                "Note": r["note"] or ""
            }
            for r in rows
        ]
    finally:
        conn.close()

# ─── Evaluate (POST - single day write, mirrors GAS doPost single) ─────────

class EvaluatePayload(BaseModel):
    token: str = ""
    date: str = ""
    timeline: list = []
    evaluations: dict = {}
    stages: list = []
    batch: list = []
    action: str = ""

@router.post("/evaluate")
async def evaluate(payload: EvaluatePayload, request: Request):
    conn = get_db()
    ip = request.client.host if request else "unknown"
    try:
        result = write_evaluation(conn, payload.dict())
        conn.commit()
        log_action("evaluate", ip, f"date={payload.date}")
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

# ─── Batch Write (mirrors GAS batch) ────────────────────────────────────────

@router.post("/batch-write")
async def batch_write(payload: EvaluatePayload, request: Request):
    conn = get_db()
    ip = request.client.host if request else "unknown"
    try:
        batch = payload.batch
        if not batch:
            return {"status": "error", "message": "batch array required"}
        results = []
        failed_count = 0
        for item in batch:
            try:
                write_evaluation(conn, item)
                results.append({"date": item.get("date", ""), "status": "Success"})
            except Exception as e:
                results.append({"date": item.get("date", ""), "status": "Failed", "error": str(e)})
                failed_count += 1
        conn.commit()
        log_action("batch_write", ip, f"items={len(batch)}, failed={failed_count}")
        return {
            "status": "Success" if failed_count == 0 else "Partial",
            "processed": len(batch),
            "succeeded": len(batch) - failed_count,
            "failed": failed_count,
            "results": results,
            "warning": "Large batch (>60). Consider splitting." if len(batch) > 60 else None
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

# ─── Generic POST handler (catches admin actions) ──────────────────────────

@router.post("/generic")
async def generic_action(request: Request):
    """Handles admin actions: bonus, exchange, markAbsent, upsertRedeemItem, etc."""
    conn = get_db()
    ip = request.client.host if request else "unknown"
    try:
        body = await request.json()
        action = body.get("action", "")
        result = {"status": "error", "message": "Unknown action"}

        if action == "redeem":
            result = action_redeem(conn, body.get("itemId", ""))
        elif action == "bonus":
            result = action_bonus(conn, body.get("pin", ""), body.get("coinType", ""),
                                  body.get("amount", 0), body.get("reason", ""))
        elif action == "exchange":
            result = action_exchange(conn, body.get("direction", ""), body.get("amount", 0))
        elif action == "markAbsent":
            result = action_mark_absent(conn, body.get("date", ""))
        elif action == "upsertRedeemItem":
            result = action_upsert_redeem_item(conn, body.get("item", {}))
        elif action == "upsertRedeemItems":
            result = action_upsert_redeem_items(conn, body.get("items", []))
        elif action == "setExchangeRate":
            result = action_set_exchange_rate(conn, body.get("rate", 5))
        elif action == "evaluate":
            result = write_evaluation(conn, body)
        elif action == "batch":
            result = action_batch(conn, body.get("batch", []))

        conn.commit()
        log_action(action, ip, json.dumps(body)[:200])
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

# ─── Action: Redeem ─────────────────────────────────────────────────────────

def action_redeem(conn, item_id: str):
    item = conn.execute("SELECT * FROM redeem_items WHERE item_id=? AND active=1", (item_id,)).fetchone()
    if not item:
        raise ValueError(f"兑换项不存在或已停用: {item_id}")

    tokens = get_tokens_data(conn)
    cost = item["cost"]
    coin_type = item["coin_type"]

    if coin_type == "silver" and tokens["silverBalance"] < cost:
        raise ValueError("银币余额不足")
    if coin_type == "gold" and tokens["goldBalance"] < cost:
        raise ValueError("金币余额不足")

    s_delta = -cost if coin_type == "silver" else 0
    g_delta = -cost if coin_type == "gold" else 0

    conn.execute("""
        INSERT INTO token_transactions (date, type, description, silver_delta, gold_delta)
        VALUES (?, 'redeem', ?, ?, ?)
    """, (today_iso(), f"兑换 {item['label']}", s_delta, g_delta))

    rebuild_balances(conn)
    fresh = get_tokens_data(conn)
    return {"status": "Success", "newSilverBalance": fresh["silverBalance"],
            "newGoldBalance": fresh["goldBalance"]}

# ─── Action: Bonus ──────────────────────────────────────────────────────────

def action_bonus(conn, pin: str, coin_type: str, amount: int, reason: str = ""):
    if pin != "emma2026!":
        raise ValueError("PIN 校验失败")
    if coin_type not in ("silver", "gold"):
        raise ValueError("coinType 必须是 silver 或 gold")
    amt = abs(int(amount or 0))
    if not amt:
        raise ValueError("数量必须 > 0")

    s_delta = amt if coin_type == "silver" else 0
    g_delta = amt if coin_type == "gold" else 0
    t_type = "bonus_silver" if coin_type == "silver" else "bonus_gold"

    conn.execute("""
        INSERT INTO token_transactions (date, type, description, silver_delta, gold_delta, note)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (today_iso(), t_type, f"手动奖励：{(reason or '无说明')}", s_delta, g_delta, reason or ""))

    rebuild_balances(conn)
    fresh = get_tokens_data(conn)
    return {"status": "Success", "newSilverBalance": fresh["silverBalance"],
            "newGoldBalance": fresh["goldBalance"]}

# ─── Action: Exchange ──────────────────────────────────────────────────────

def action_exchange(conn, direction: str, amount: int):
    if direction not in ("s2g", "g2s"):
        raise ValueError("direction 必须是 s2g（银→金）或 g2s（金→银）")

    rate_row = conn.execute("SELECT value FROM app_config WHERE key='exchange_rate'").fetchone()
    rate = int(rate_row["value"]) if rate_row else 5
    amt = int(amount)
    if amt < 1:
        raise ValueError("交换数量必须 ≥ 1")
    if direction == "s2g":
        if amt < rate:
            raise ValueError(f"银币交换数量不能小于汇率 {rate}")
        if amt % rate != 0:
            raise ValueError(f"银币交换数量必须是 {rate} 的整数倍")

    tokens = get_tokens_data(conn)

    if direction == "s2g":
        if tokens["silverBalance"] < amt:
            raise ValueError(f"银币余额不足，需要 {amt} 枚，当前 {tokens['silverBalance']} 枚")
        gold_out = amt // rate
        conn.execute("""
            INSERT INTO token_transactions (date, type, description, silver_delta, gold_delta)
            VALUES (?, 'exchange', ?, ?, ?)
        """, (today_iso(), f"银币→金币交换 {amt}→{gold_out}", -amt, gold_out))
    else:
        if tokens["goldBalance"] < amt:
            raise ValueError(f"金币余额不足，需要 {amt} 枚，当前 {tokens['goldBalance']} 枚")
        silver_out = amt * rate
        conn.execute("""
            INSERT INTO token_transactions (date, type, description, silver_delta, gold_delta)
            VALUES (?, 'exchange', ?, ?, ?)
        """, (today_iso(), f"金币→银币交换 {amt}→{silver_out}", silver_out, -amt))

    rebuild_balances(conn)
    fresh = get_tokens_data(conn)
    return {"status": "Success", "newSilverBalance": fresh["silverBalance"],
            "newGoldBalance": fresh["goldBalance"]}

# ─── Action: Mark Absent ────────────────────────────────────────────────────

def action_mark_absent(conn, date_str: str):
    if not date_str or not isinstance(date_str, str):
        raise ValueError("date 参数必须是字符串")
    parsed = parse_date_safe(date_str)
    if not parsed:
        raise ValueError("date 格式无效，需为 YYYY-MM-DD")

    weekday_labels = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
    weekday = weekday_labels[parsed.weekday()]

    # Write absent evaluation
    conn.execute("""
        INSERT OR REPLACE INTO evaluations
        (date, day_type, start_time, end_time, focus_blocks, distractions,
         eye_rest_minutes, note, absent, status, summary, rating, tokens_net)
        VALUES (?, ?, '00:00', '00:00', 0, 0, 0, 'Emma 不在场', 1, 'gray', 'Emma 不在场', '⚪ 不在场', 0)
    """, (date_str, weekday))

    # Clear activity logs for this date
    conn.execute("DELETE FROM activity_logs WHERE date=?", (date_str,))

    return {"status": "Success", "date": date_str, "weekday": weekday}

# ─── Action: Upsert Redeem Item ─────────────────────────────────────────────

def action_upsert_redeem_item(conn, item: dict):
    if not item or not item.get("itemId"):
        raise ValueError("itemId 必填")
    conn.execute("""
        INSERT OR REPLACE INTO redeem_items (item_id, label, description, coin_type, cost, active, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        item["itemId"],
        item.get("label", ""),
        item.get("description", ""),
        item.get("coinType", "silver"),
        int(item.get("cost", 1)),
        1 if item.get("active", True) else 0,
        int(item.get("sort", 0))
    ))
    return {"status": "Success"}

# ─── Action: Batch Upsert Redeem Items ─────────────────────────────────────

def action_upsert_redeem_items(conn, items: list):
    if not isinstance(items, list):
        raise ValueError("items 必须是数组")
    results = []
    for item in items:
        try:
            action_upsert_redeem_item(conn, item)
            results.append({"itemId": item.get("itemId", "unknown"), "status": "Created"})
        except Exception as e:
            results.append({"itemId": item.get("itemId", "unknown"), "status": "Failed", "error": str(e)})
    return {"status": "Success", "results": results}

# ─── Action: Set Exchange Rate ──────────────────────────────────────────────

def action_set_exchange_rate(conn, rate: int):
    r = int(rate)
    if r < 1:
        raise ValueError("汇率必须 ≥ 1")
    conn.execute("INSERT OR REPLACE INTO app_config (key, value) VALUES ('exchange_rate', ?)", (str(r),))
    conn.execute("UPDATE tokens SET exchange_rate=?", (r,))
    return {"status": "Success", "rate": r}

# ─── Action: Batch ──────────────────────────────────────────────────────────

def action_batch(conn, batch: list):
    if not isinstance(batch, list):
        raise ValueError("batch 必须是数组")
    results = []
    failed = 0
    for item in batch:
        try:
            write_evaluation(conn, item)
            results.append({"date": item.get("date", ""), "status": "Success"})
        except Exception as e:
            results.append({"date": item.get("date", ""), "status": "Failed", "error": str(e)})
            failed += 1
    return {
        "status": "Success" if failed == 0 else "Partial",
        "processed": len(batch),
        "succeeded": len(batch) - failed,
        "failed": failed,
        "results": results,
        "warning": "Large batch (>60). Consider splitting." if len(batch) > 60 else None
    }

app.include_router(router)

# ─── PoC only: Seed dummy data ──────────────────────────────────────────────

@app.post("/api/poc/seed-dummy")
async def seed_dummy():
    conn = get_db()
    try:
        conn.execute("DELETE FROM evaluations")
        conn.execute("DELETE FROM activity_logs")
        conn.execute("DELETE FROM token_transactions")
        conn.execute("UPDATE tokens SET silver_balance=0, gold_balance=0")
        conn.execute("UPDATE app_config SET value='5' WHERE key='exchange_rate'")

        dummy_dates = ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04", "2026-07-05"]
        day_types = ["周三", "周四", "周五", "周六", "周日"]
        ratings = ["🟢 优秀", "🟡 警告", "🟢 优秀", "🔴 危险", "🟢 优秀"]

        for i, d in enumerate(dummy_dates):
            conn.execute("""
                INSERT INTO evaluations (date, day_type, start_time, end_time,
                    focus_blocks, distractions, eye_rest_minutes, rating, summary, note,
                    absent, status, tokens_net, bucket_focus)
                VALUES (?, ?, '09:00', '18:00', ?, ?, ?, ?, ?, ?, 0, 'green', ?, ?)
            """, (d, day_types[i], 2 + i % 3, i % 3, 10 * i,
                  ratings[i], f"PoC 测试数据第{i+1}天", f"测试备注 {i+1}",
                  2 + i, 90 + i * 15))

            # Add seed activity logs
            conn.execute("""
                INSERT INTO activity_logs (date, stage_name, category, duration, start_time, end_time)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (d, "阅读练习", "Focus", 60 + i * 15, "09:00", "10:00"))
            conn.execute("""
                INSERT INTO activity_logs (date, stage_name, category, duration, start_time, end_time)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (d, "拼图游戏", "Activity", 30, "10:30", "11:00"))

        conn.commit()
        return {"status": "ok", "seeded": len(dummy_dates)}
    finally:
        conn.close()