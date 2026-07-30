import asyncio
import importlib.util
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = PROJECT_ROOT / "infra/web/backend/poc_main.py"


def load_backend(db_path):
    class FakeApp:
        def __init__(self, *args, **kwargs):
            pass

        def add_middleware(self, *args, **kwargs):
            pass

        def include_router(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            return lambda function: function

        post = get
        delete = get

    class FakeRouter(FakeApp):
        pass

    class FakeHTTPException(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code
            self.detail = detail

    fastapi = types.ModuleType("fastapi")
    fastapi.FastAPI = FakeApp
    fastapi.APIRouter = FakeRouter
    fastapi.HTTPException = FakeHTTPException
    fastapi.Request = object
    fastapi.Header = lambda default=None: default
    middleware = types.ModuleType("fastapi.middleware")
    cors = types.ModuleType("fastapi.middleware.cors")
    cors.CORSMiddleware = object
    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = object

    previous = os.environ.get("EMMA_DB_PATH")
    previous_initial_pin = os.environ.get("EMMA_ADMIN_INITIAL_PIN")
    previous_auth_file = os.environ.get("EMMA_AUTH_FILE")
    os.environ["EMMA_DB_PATH"] = str(db_path)
    os.environ["EMMA_ADMIN_INITIAL_PIN"] = "test-parent-pin"
    os.environ["EMMA_AUTH_FILE"] = str(Path(db_path).parent / "admin_auth.json")
    try:
        fake_modules = {
            "fastapi": fastapi,
            "fastapi.middleware": middleware,
            "fastapi.middleware.cors": cors,
            "pydantic": pydantic,
        }
        with patch.dict(sys.modules, fake_modules):
            spec = importlib.util.spec_from_file_location("emma_test_backend", BACKEND_PATH)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    finally:
        if previous is None:
            os.environ.pop("EMMA_DB_PATH", None)
        else:
            os.environ["EMMA_DB_PATH"] = previous
        if previous_initial_pin is None:
            os.environ.pop("EMMA_ADMIN_INITIAL_PIN", None)
        else:
            os.environ["EMMA_ADMIN_INITIAL_PIN"] = previous_initial_pin
        if previous_auth_file is None:
            os.environ.pop("EMMA_AUTH_FILE", None)
        else:
            os.environ["EMMA_AUTH_FILE"] = previous_auth_file


class PocBusinessTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "poc.db"
        self.backend = load_backend(self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_mark_absent_uses_correct_weekday(self):
        conn = self.backend.get_db()
        result = self.backend.action_mark_absent(conn, "2026-07-16")
        conn.commit()
        row = conn.execute(
            "SELECT day_type, absent FROM evaluations WHERE date='2026-07-16'"
        ).fetchone()
        conn.close()

        self.assertEqual(result["weekday"], "周四")
        self.assertEqual((row["day_type"], row["absent"]), ("周四", 1))

    def test_negative_token_derivation_is_idempotent(self):
        conn = self.backend.get_db()
        conn.execute(
            """
            INSERT INTO evaluations
                (date, focus_blocks, distractions, tokens_net, absent)
            VALUES ('2026-07-16', 1, 6, -1, 0)
            """
        )
        self.backend.derive_transactions(conn, "2026-07-16")
        self.backend.derive_transactions(conn, "2026-07-16")
        rows = conn.execute(
            """
            SELECT type, silver_delta FROM token_transactions
            WHERE date='2026-07-16' AND type='deduct_silver'
            """
        ).fetchall()
        conn.close()

        self.assertEqual([(row["type"], row["silver_delta"]) for row in rows], [("deduct_silver", -1)])

    def test_eye_rest_minutes_do_not_create_rewards(self):
        conn = self.backend.get_db()
        conn.execute(
            """
            INSERT INTO evaluations
                (date, focus_blocks, distractions, eye_rest_minutes, tokens_net, absent)
            VALUES ('2026-07-16', 0, 0, 180, 0, 0)
            """
        )
        self.backend.derive_transactions(conn, "2026-07-16")
        count = conn.execute(
            "SELECT COUNT(*) FROM token_transactions WHERE type='eyerest_silver'"
        ).fetchone()[0]
        conn.close()

        self.assertEqual(count, 0)

    def test_write_evaluation_persists_status_from_rating(self):
        conn = self.backend.get_db()
        payload = {
            "date": "2026-07-29",
            "timeline": [{
                "Date": "2026-07-29",
                "Day_Type": "周三",
                "Time_Start": "09:21",
                "Time_End": "19:18",
                "Focus_Blocks": 4,
                "Distractions": 2,
                "Eye_Rest_Minutes": 0,
                "Absent": False,
                "Note": "人工确认",
            }],
            "evaluations": {
                "Date": "2026-07-29",
                "Summary": "人工确认",
                "Rating": "🟡 警告",
                "Tokens_Net": 4,
            },
            "stages": [],
        }

        self.backend.write_evaluation(conn, payload)
        row = conn.execute(
            "SELECT rating, status FROM evaluations WHERE date='2026-07-29'"
        ).fetchone()
        conn.close()

        self.assertEqual((row["rating"], row["status"]), ("🟡 警告", "amber"))

    def test_legacy_eye_rest_rewards_are_revoked_once(self):
        conn = self.backend.get_db()
        conn.execute(
            "DELETE FROM app_config WHERE key='migration_remove_eyerest_rewards_v1'"
        )
        conn.execute(
            """
            INSERT INTO token_transactions
                (date, type, description, silver_delta, gold_delta)
            VALUES
                ('2026-07-10', 'award_silver', '专注奖励', 3, 0),
                ('2026-07-10', 'eyerest_silver', '护眼里程碑', 1, 0),
                ('2026-07-11', 'eyerest_silver', '护眼里程碑', 1, 0)
            """
        )
        removed = self.backend.remove_legacy_eyerest_rewards(conn)
        removed_again = self.backend.remove_legacy_eyerest_rewards(conn)
        balance = conn.execute(
            "SELECT silver_balance FROM tokens LIMIT 1"
        ).fetchone()[0]
        count = conn.execute(
            "SELECT COUNT(*) FROM token_transactions WHERE type='eyerest_silver'"
        ).fetchone()[0]
        conn.close()

        self.assertEqual(removed, 2)
        self.assertEqual(removed_again, 0)
        self.assertEqual(balance, 3)
        self.assertEqual(count, 0)

    def test_tmos_settlement_is_exposed_with_source_events(self):
        conn = self.backend.get_db()
        conn.execute("""CREATE TABLE tmos_reward_events (
            user TEXT, fact_id TEXT PRIMARY KEY, fact_type TEXT, fact_date TEXT, title TEXT,
            stars INTEGER, silver_credit_milli INTEGER, policy_version INTEGER, active INTEGER,
            created_at TEXT, updated_at TEXT)""")
        conn.execute("INSERT INTO tmos_reward_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     ("default", "task-1", "task", "2026-07-22", "数学复习", 2, 400, 3, 1, "now", "now"))
        cursor = conn.execute("INSERT INTO token_transactions(date,type,description,silver_delta,gold_delta) VALUES(?,?,?,?,?)",
                              ("2026-07-22", "tmos_silver_conversion", "TMOS 星星结算", 1, 0))
        conn.execute("""INSERT INTO tmos_reward_settlements
            (settlement_id,user,settlement_type,source_event_ids,star_credit_milli_delta,silver_delta,gold_delta,
             policy_version,created_at,wallet_transaction_id) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            ("settle-1", "default", "silver_conversion", '["task-1"]', 1000, 1, 0, 3, "now", cursor.lastrowid))
        conn.commit()
        transaction = self.backend.get_tokens_data(conn)["transactions"][0]
        conn.close()
        self.assertEqual(transaction["source"], "tmos")
        self.assertEqual(transaction["settlement"]["sourceEvents"][0]["title"], "数学复习")

    def test_admin_pin_is_required_and_compared(self):
        with self.assertRaisesRegex(ValueError, "PIN 校验失败"):
            self.backend.require_admin("wrong-pin")
        with self.assertRaisesRegex(ValueError, "首次登录必须"):
            self.backend.require_admin("test-parent-pin")
        self.backend.write_auth("new-parent-pin", must_change=False)
        self.backend.require_admin("new-parent-pin")
        self.assertFalse(self.backend.verify_admin_pin("test-parent-pin"))

    def prepare_focus_brief_parent(self):
        self.backend.write_auth("brief-parent-pin", must_change=False)

    def test_focus_brief_missing_evaluation_is_not_zero(self):
        self.prepare_focus_brief_parent()
        conn = self.backend.get_db()
        brief = self.backend.build_focus_brief(conn, "2026-07-30", 7)
        conn.close()
        self.assertEqual(brief["yesterday"]["data_state"], "missing")
        self.assertNotIn("focus_minutes", brief["yesterday"])
        self.assertEqual(len(brief["trend"]), 7)
        self.assertEqual(brief["trend"][-1]["data_state"], "missing")

    def test_focus_brief_aggregates_activity_wallet_and_trend(self):
        conn = self.backend.get_db()
        conn.execute("""INSERT INTO evaluations
            (date, focus_blocks, distractions, eye_rest_minutes, rating, summary, absent, status)
            VALUES ('2026-07-29', 2, 1, 10, '🟢 优秀', '已审核', 0, 'green')""")
        conn.executemany("""INSERT INTO activity_logs
            (date, stage_name, category, duration) VALUES ('2026-07-29', ?, ?, ?)""", [
                ("阅读", "Focus", 45), ("手工", "Activity", 15), ("休息", "Eye Rest", 10),
            ])
        conn.executemany("""INSERT INTO token_transactions
            (date,type,description,silver_delta,gold_delta) VALUES ('2026-07-29','award_silver','专注',?,0)""", [(2,), (1,)])
        conn.execute("""INSERT INTO evaluations
            (date, focus_blocks, distractions, rating, absent, status)
            VALUES ('2026-07-28', 1, 2, '🟡 警告', 0, 'amber')""")
        conn.execute("""INSERT INTO activity_logs
            (date, stage_name, category, duration) VALUES ('2026-07-28','练习','Focus',30)""")
        conn.commit()
        brief = self.backend.build_focus_brief(conn, "2026-07-30", 2)
        conn.close()
        self.assertEqual(brief["yesterday"]["activity"]["focus_minutes"], 45)
        self.assertEqual(brief["yesterday"]["activity"]["study_minutes"], 60)
        self.assertEqual(brief["yesterday"]["activity_stages"][0]["stage"], "阅读")
        self.assertEqual(brief["yesterday"]["wallet_changes"][0]["count"], 2)
        self.assertEqual(brief["yesterday"]["wallet_changes"][0]["silver_delta"], 3)
        self.assertEqual(brief["trend"][0]["focus_minutes"], 30)
        self.assertEqual(brief["trend"][1]["silver_delta"], 3)

    def test_focus_brief_groups_tmos_settlement_once(self):
        conn = self.backend.get_db()
        cursor = conn.execute("""INSERT INTO token_transactions
            (date,type,description,silver_delta,gold_delta) VALUES ('2026-07-29','tmos_silver_conversion','TMOS 结算',1,0)""")
        conn.execute("""INSERT INTO tmos_reward_settlements
            (settlement_id,user,settlement_type,source_event_ids,star_credit_milli_delta,silver_delta,gold_delta,
             policy_version,created_at,wallet_transaction_id) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            ("settle-brief", "default", "silver_conversion", '["task-1","task-2"]', 1000, 1, 0, 3, "now", cursor.lastrowid))
        conn.commit()
        changes, _ = self.backend._brief_wallet_changes(conn, "2026-07-29")
        conn.close()
        self.assertEqual(changes, [{"source": "tmos", "type": "tmos_silver_conversion", "count": 1,
                                    "silver_delta": 1, "gold_delta": 0, "settlement_ids": ["settle-brief"]}])

    def test_focus_brief_token_is_hashed_expiring_and_revocable(self):
        self.prepare_focus_brief_parent()
        issued = self.backend.issue_focus_brief_token("brief-parent-pin", "Codex", 90)
        self.assertEqual(issued["scope"], "focus-brief:read")
        self.assertTrue(issued["token"].startswith("emma_focus_brief_"))
        conn = self.backend.get_db()
        stored = conn.execute("SELECT token_hash FROM focus_brief_tokens WHERE id=?", (issued["token_id"],)).fetchone()[0]
        conn.close()
        self.assertEqual(stored, self.backend.focus_brief_token_hash(issued["token"]))
        self.assertNotEqual(stored, issued["token"])
        self.assertIsNone(self.backend.require_focus_brief_auth(f"Bearer {issued['token']}"))
        asyncio.run(self.backend.revoke_focus_brief_token(issued["token_id"], "brief-parent-pin"))
        with self.assertRaises(self.backend.HTTPException) as caught:
            self.backend.require_focus_brief_auth(f"Bearer {issued['token']}")
        self.assertEqual(caught.exception.status_code, 401)

    def test_focus_brief_expired_token_and_write_boundary_are_rejected(self):
        self.prepare_focus_brief_parent()
        issued = self.backend.issue_focus_brief_token("brief-parent-pin", "Codex", 1)
        conn = self.backend.get_db()
        conn.execute("UPDATE focus_brief_tokens SET expires_at='2000-01-01T00:00:00+00:00' WHERE id=?", (issued["token_id"],))
        conn.commit()
        conn.close()
        with self.assertRaises(self.backend.HTTPException) as caught:
            self.backend.require_focus_brief_auth(f"Bearer {issued['token']}")
        self.assertEqual(caught.exception.status_code, 401)
        with self.assertRaisesRegex(ValueError, "PIN 校验失败"):
            self.backend.require_admin(issued["token"])
        request = types.SimpleNamespace(
            client=types.SimpleNamespace(host="test"),
            json=lambda: __import__("asyncio").sleep(0, result={
                "action": "bonus", "pin": issued["token"], "coinType": "silver", "amount": 1,
            }),
        )
        result = asyncio.run(self.backend.generic_action(request))
        self.assertEqual(result["status"], "error")
        self.assertIn("PIN", result["message"])


if __name__ == "__main__":
    unittest.main()
