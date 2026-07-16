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
            VALUES ('2026-07-16', 1, 6, -2, 0)
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

        self.assertEqual([(row["type"], row["silver_delta"]) for row in rows], [("deduct_silver", -2)])

    def test_admin_pin_is_required_and_compared(self):
        with self.assertRaisesRegex(ValueError, "PIN 校验失败"):
            self.backend.require_admin("wrong-pin")
        with self.assertRaisesRegex(ValueError, "首次登录必须"):
            self.backend.require_admin("test-parent-pin")
        self.backend.write_auth("new-parent-pin", must_change=False)
        self.backend.require_admin("new-parent-pin")
        self.assertFalse(self.backend.verify_admin_pin("test-parent-pin"))


if __name__ == "__main__":
    unittest.main()
