import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "emma-review" / "scripts" / "emma_review.py"
SPEC = importlib.util.spec_from_file_location("emma_review", SCRIPT)
emma_review = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(emma_review)


def valid_result():
    return {
        "date": "2026-07-26",
        "timeline": [
            {
                "Date": "2026-07-26",
                "Day_Type": "周日",
                "Time_Start": "09:00",
                "Time_End": "11:00",
                "Category": "独立学习",
                "Focus_Blocks": 2,
                "Distractions": 0,
                "Note": "完成两个连续学习阶段。",
                "Absent": False,
                "Eye_Rest_Minutes": 0,
            }
        ],
        "evaluations": {
            "Date": "2026-07-26",
            "Summary": "完成两个符合门槛的独立学习阶段。",
            "Rating": "🟢 优秀",
            "Tokens_Net": 2,
        },
        "stages": [
            {
                "date": "2026-07-26",
                "stage": "数学练习",
                "start": "09:00",
                "end": "10:00",
                "duration": 60,
                "category": "Focus",
                "note": "持续书写练习。",
            },
            {
                "date": "2026-07-26",
                "stage": "阅读",
                "start": "10:00",
                "end": "11:00",
                "duration": 60,
                "category": "Focus",
                "note": "持续阅读并记录。",
            },
        ],
    }


class EmmaReviewValidationTests(unittest.TestCase):
    def test_valid_result(self):
        self.assertEqual(
            emma_review.validate_result(valid_result(), "2026-07-26"), []
        )

    def test_rejects_model_arithmetic_and_rating(self):
        result = valid_result()
        result["evaluations"]["Tokens_Net"] = 3
        result["evaluations"]["Rating"] = "🟡 警告"
        errors = emma_review.validate_result(result, "2026-07-26")
        self.assertIn("evaluations.Tokens_Net must be 2", errors)
        self.assertIn("evaluations.Rating must be 🟢 优秀", errors)

    def test_rejects_stage_outside_timeline(self):
        result = valid_result()
        result["stages"][0]["start"] = "08:50"
        result["stages"][0]["duration"] = 70
        errors = emma_review.validate_result(result, "2026-07-26")
        self.assertIn("stages[0] starts before timeline coverage", errors)

    def test_cli_validate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "result.json"
            path.write_text(
                json.dumps(valid_result(), ensure_ascii=False), encoding="utf-8"
            )
            args = type(
                "Args",
                (),
                {"result": path, "expected_date": "2026-07-26"},
            )
            self.assertEqual(emma_review.cmd_validate(args), 0)


class EmmaReviewReadinessTests(unittest.TestCase):
    def test_requires_producer_manifest_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Study_20260726.mp4").write_bytes(b"video")
            with patch.object(emma_review, "mp4_duration", return_value=10.0):
                with patch.object(
                    emma_review.time, "time", return_value=time.time() + 120
                ):
                    report = emma_review.inspect_readiness(
                        root, emma_review.parse_date("2026-07-26")
                    )
            self.assertFalse(report["ready"])
            self.assertEqual(report["reason"], "producer ready manifest is missing")

    def test_accepts_matching_atomic_ready_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "Study_20260726.mp4"
            video.write_bytes(b"video")
            ready_dir = root / ".ready"
            ready_dir.mkdir()
            (ready_dir / "Study_20260726.ready.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "ready",
                        "camera": "Study",
                        "label": "书房",
                        "audit_date": "2026-07-26",
                        "path": "/mnt/export_videos/书房/Study_20260726.mp4",
                        "bytes": 5,
                        "duration_seconds": 10.0,
                        "completed_at": "2026-07-26T22:36:23+0800",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch.object(emma_review, "mp4_duration", return_value=10.0):
                with patch.object(
                    emma_review.time, "time", return_value=time.time() + 120
                ):
                    report = emma_review.inspect_readiness(
                        root, emma_review.parse_date("2026-07-26")
                    )
            self.assertTrue(report["ready"])
            self.assertTrue(report["producer_confirmed"])

    def test_legacy_stable_requires_explicit_override(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Study_20260726.mp4").write_bytes(b"video")
            with patch.object(emma_review, "mp4_duration", return_value=10.0):
                with patch.object(
                    emma_review.time, "time", return_value=time.time() + 120
                ):
                    report = emma_review.inspect_readiness(
                        root,
                        emma_review.parse_date("2026-07-26"),
                        allow_legacy_stable=True,
                    )
            self.assertTrue(report["ready"])
            self.assertEqual(report["status"], "legacy_stable")


if __name__ == "__main__":
    unittest.main()
