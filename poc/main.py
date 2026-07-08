"""
Emma Focus — PoC Backend (fastapi + SQLite)
============================================
Independent proof-of-concept that does NOT touch production data.

Run via docker: site_backend container serves this at /poc/ through nginx.

Endpoints:
  GET  /api/poc/dashboard?ym=YYYY-MM  — dashboard data
  GET  /api/poc/charts                 — chart data
  GET  /api/poc/tokens                 — token/coin data
  GET  /api/poc/redeem-items           — redeem shop items
  POST /api/poc/evaluation             — dummy evaluation submit

Database: /app/data/poc.db (standalone, separate from site.db)
"""

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import os
import json
from datetime import datetime

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_PATH = "/app/data/poc.db"
os.makedirs("/app/data", exist_ok=True)

router = APIRouter(prefix="/api/poc")

# =============================================
# Database initialization
# =============================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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

        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            stage_name TEXT DEFAULT '',
            category TEXT DEFAULT '',
            duration INTEGER DEFAULT 0,
            start_time TEXT DEFAULT '',
            end_time TEXT DEFAULT ''
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
            gold_delta INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS redeem_items (
            item_id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            description TEXT DEFAULT '',
            coin_type TEXT NOT NULL,
            cost INTEGER NOT NULL,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS api_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            ip TEXT DEFAULT '',
            payload TEXT DEFAULT ''
        );

        -- Insert default data if empty
        INSERT OR IGNORE INTO tokens (silver_balance, gold_balance, exchange_rate) VALUES (0, 0, 5);
    """)
    conn.commit()
    conn.close()

init_db()

# =============================================
# Helper: log API calls
# =============================================
def log_action(action: str, ip: str = "", payload: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO api_log (timestamp, action, ip, payload) VALUES (?, ?, ?, ?)",
                     (datetime.now().isoformat(), action, ip, payload[:200]))
        conn.commit()
        conn.close()
    except:
        pass

# =============================================
# Endpoints
# =============================================
@app.get("/")
def root():
    return {"status": "PoC backend is running", "note": "Independent from production GAS"}

@app.get("/api/poc/health")
def health():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
    conn.close()
    return {"status": "ok", "evaluations": count}

# POST: Submit dummy evaluation (PoC write test)
class EvaluationPayload(BaseModel):
    date: str = ""
    day_type: str = ""
    start_time: str = ""
    end_time: str = ""
    focus_blocks: int = 0
    distractions: int = 0
    eye_rest_minutes: int = 0
    rating: str = ""
    summary: str = ""
    note: str = ""
    absent: bool = False
    token_silver: int = 0
    token_gold: int = 0
    bucket_minutes: dict = {}

@router.post("/evaluation")
async def submit_evaluation(data: EvaluationPayload, request=None):
    conn = get_db()
    ip = request.client.host if request else "unknown"
    try:
        bm = data.bucket_minutes or {}
        conn.execute("""
            INSERT OR REPLACE INTO evaluations
            (date, day_type, start_time, end_time, focus_blocks, distractions,
             eye_rest_minutes, rating, summary, note, absent, status, tokens_net,
             bucket_focus, bucket_coaching, bucket_screen, bucket_activity,
             bucket_eyerest, bucket_distraction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?)
        """, (
            data.date, data.day_type, data.start_time, data.end_time,
            data.focus_blocks, data.distractions, data.eye_rest_minutes,
            data.rating, data.summary, data.note, 1 if data.absent else 0,
            "green" if not data.absent else "gray",
            data.token_silver + data.token_gold * 5,
            bm.get("focus", 0), bm.get("coaching", 0), bm.get("screen", 0),
            bm.get("activity", 0), bm.get("eyerest", 0), bm.get("distraction", 0)
        ))
        if data.token_silver or data.token_gold:
            conn.execute("UPDATE tokens SET silver_balance = silver_balance + ?, gold_balance = gold_balance + ?",
                         (data.token_silver, data.token_gold))
        conn.commit()
        log_action("submit_evaluation", ip, f"date={data.date}")
        return {"status": "ok", "date": data.date}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

# GET: Dashboard data
@router.get("/dashboard")
async def get_dashboard(ym: str = ""):
    conn = get_db()
    try:
        # Get all evaluations
        rows = conn.execute("SELECT * FROM evaluations ORDER BY date").fetchall()
        days = {}
        total_focus = total_coaching = total_screen = total_activity = 0
        total_eyerest = total_distraction = 0
        workdays = weekends = 0
        min_date = max_date = ""

        for r in rows:
            d = dict(r)
            date_str = d["date"]
            if not min_date or date_str < min_date: min_date = date_str
            if not max_date or date_str > max_date: max_date = date_str

            if date_str.startswith(ym) if ym else True:
                bm = {
                    "focus": d["bucket_focus"], "coaching": d["bucket_coaching"],
                    "screen": d["bucket_screen"], "activity": d["bucket_activity"],
                    "eyerest": d["bucket_eyerest"], "distraction": d["bucket_distraction"]
                }
                days[date_str] = {
                    "date": date_str, "dayType": d["day_type"] or "",
                    "startTime": d["start_time"] or "", "endTime": d["end_time"] or "",
                    "focusBlocks": d["focus_blocks"], "distractions": d["distractions"],
                    "eyeRestMinutes": d["eye_rest_minutes"], "rating": d["rating"] or "",
                    "summary": d["summary"] or "", "note": d["note"] or "",
                    "absent": bool(d["absent"]), "status": d["status"] or "gray",
                    "tokensNet": d["tokens_net"], "bucketMinutes": bm
                }
                h = bm["focus"] + bm["coaching"] + bm["screen"] + bm["activity"]
                total_focus += bm["focus"]
                total_coaching += bm["coaching"]
                total_screen += bm["screen"]
                total_activity += bm["activity"]
                total_eyerest += bm["eyerest"]
                total_distraction += bm["distraction"]
                if not d["absent"]:
                    if d["day_type"] in ["周六", "周日"]:
                        weekends += 1
                    else:
                        workdays += 1

        total_days = len([k for k in days.keys() if (not ym) or k.startswith(ym)])
        study_hours = (total_focus + total_coaching + total_screen) / 60
        waste_hours = total_distraction / 60
        total_hours = study_hours + (total_coaching / 60) + waste_hours

        summary = {
            "totalDays": total_days, "workdays": workdays, "weekends": weekends,
            "totalTokens": sum(d.get("tokens_net", 0) for d in days.values()),
            "studyHours": round(study_hours, 1),
            "coachingHours": round(total_coaching / 60, 1),
            "wasteHours": round(waste_hours, 1),
            "focusHours": round(total_focus / 60, 1),
            "activityHours": round(total_activity / 60, 1)
        }

        data_range = {}
        if min_date and max_date:
            data_range = {
                "minYM": min_date[:7], "maxYM": max_date[:7],
                "minDate": min_date, "maxDate": max_date
            }

        return {
            "ym": ym or (max_date[:7] if max_date else ""),
            "dataRange": data_range,
            "summary": summary,
            "monthSummary": summary,
            "monthAverages": {
                "overallHours": round(total_hours / max(total_days, 1), 1),
                "workdayHours": round(total_hours / max(workdays, 1), 1),
                "weekendHours": round(total_hours / max(weekends, 1), 1),
                "dayCounts": {"overall": total_days, "workday": workdays, "weekend": weekends}
            },
            "days": days
        }
    finally:
        conn.close()

# GET: Tokens
@router.get("/tokens")
async def get_tokens():
    conn = get_db()
    try:
        t = conn.execute("SELECT * FROM tokens LIMIT 1").fetchone()
        txns = conn.execute("SELECT * FROM token_transactions ORDER BY id DESC LIMIT 100").fetchall()
        return {
            "silverBalance": t["silver_balance"] if t else 0,
            "goldBalance": t["gold_balance"] if t else 0,
            "transactions": [dict(r) for r in txns]
        }
    finally:
        conn.close()

# GET: Redeem items
@router.get("/redeem-items")
async def get_redeem_items():
    conn = get_db()
    try:
        items = conn.execute("SELECT * FROM redeem_items WHERE active=1").fetchall()
        return [dict(r) for r in items]
    finally:
        conn.close()

# GET: API log (for debugging)
@router.get("/log")
async def get_log(limit: int = 20):
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM api_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

app.include_router(router)

# Dummy data seeder (for PoC, not production)
@app.post("/api/poc/seed-dummy")
async def seed_dummy():
    conn = get_db()
    try:
        conn.execute("DELETE FROM evaluations")
        dummy_dates = ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04", "2026-07-05"]
        for i, d in enumerate(dummy_dates):
            conn.execute("""
                INSERT INTO evaluations (date, day_type, start_time, end_time,
                    focus_blocks, distractions, eye_rest_minutes, rating, summary, note,
                    absent, status, tokens_net, bucket_focus)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (d, ["周三","周四","周五","周六","周日"][i], "09:00", "18:00",
                  2 + i % 3, i % 3, 10 * i,
                  ["🟢 优秀","🟡 警告","🟢 优秀","🔴 危险","🟢 优秀"][i],
                  f"PoC 测试数据第{i+1}天", f"测试备注 {i+1}",
                  0, "green", 2 + i, 90 + i * 15))
        conn.commit()
        return {"status": "ok", "seeded": len(dummy_dates)}
    finally:
        conn.close()