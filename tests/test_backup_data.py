import csv
import importlib.util
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKUP_SCRIPT = PROJECT_ROOT / "infra/web/backend/backup_data.py"


class BackupDataTest(unittest.TestCase):
    def test_default_backup_path_matches_nas_contract(self):
        spec = importlib.util.spec_from_file_location("emma_backup_contract", BACKUP_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(os.environ, {}, clear=True):
            spec.loader.exec_module(module)
        self.assertEqual(module.BACKUP_BASE, "/app/backups")

    def test_backup_creates_readable_snapshot_and_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "poc.db"
            backup_base = root / "backups"
            unrelated_dir = backup_base / "notes"
            unrelated_dir.mkdir(parents=True)

            conn = sqlite3.connect(db_path)
            for table in (
                "evaluations",
                "activity_logs",
                "token_transactions",
                "redeem_items",
                "app_config",
            ):
                conn.execute(f'CREATE TABLE "{table}" (id INTEGER, value TEXT)')
            conn.execute("INSERT INTO evaluations VALUES (?, ?)", (1, "测试记录"))
            conn.commit()
            conn.close()

            env = os.environ.copy()
            env["EMMA_DB_PATH"] = str(db_path)
            env["EMMA_BACKUP_BASE"] = str(backup_base)
            result = subprocess.run(
                [sys.executable, str(BACKUP_SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            date_dirs = [p for p in backup_base.iterdir() if p.name.isdigit()]
            self.assertEqual(len(date_dirs), 1)
            output_dir = date_dirs[0]

            snapshot = sqlite3.connect(output_dir / "poc.db")
            row = snapshot.execute("SELECT id, value FROM evaluations").fetchone()
            snapshot.close()
            self.assertEqual(row, (1, "测试记录"))

            with (output_dir / "evaluations.csv").open(encoding="utf-8", newline="") as file:
                rows = list(csv.reader(file))
            self.assertEqual(rows, [["id", "value"], ["1", "测试记录"]])
            self.assertTrue(unrelated_dir.is_dir())

    def test_missing_database_returns_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["EMMA_DB_PATH"] = str(Path(tmp) / "missing.db")
            env["EMMA_BACKUP_BASE"] = str(Path(tmp) / "backups")
            result = subprocess.run(
                [sys.executable, str(BACKUP_SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("数据库不存在", result.stderr)


if __name__ == "__main__":
    unittest.main()
