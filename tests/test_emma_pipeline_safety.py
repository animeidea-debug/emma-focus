import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "emma-review" / "scripts" / "emma_pipeline.py"
SPEC = importlib.util.spec_from_file_location("emma_pipeline", SCRIPT)
emma_pipeline = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = emma_pipeline
SPEC.loader.exec_module(emma_pipeline)


class EmmaPipelineSafetyTests(unittest.TestCase):
    def test_defaults_match_the_selected_local_baseline(self):
        args = emma_pipeline.build_parser().parse_args(
            [
                "--date",
                "2026-07-28",
                "--video",
                "Study_20260728.mp4",
            ]
        )
        self.assertEqual(args.resize, 640)
        self.assertEqual(args.batch_size, 5)
        self.assertEqual(args.max_similar_gap, 12.0)
        self.assertEqual(args.mode, "describe")
        self.assertEqual(args.identity_reference, [])
        self.assertEqual(args.feedback_root, "")
        self.assertTrue(
            args.model.endswith("Qwen2.5-VL-7B-Instruct-4bit")
        )
        self.assertNotIn("--post", emma_pipeline.build_parser().format_help())
        self.assertNotIn("--api-token", emma_pipeline.build_parser().format_help())

    def test_resize_preserves_camera_aspect_ratio(self):
        self.assertEqual(
            emma_pipeline.fit_long_edge(1280, 720, 640),
            (640, 360),
        )

    def test_axis_cache_is_keyed_by_image_prompt_and_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "frame.jpg"
            image.write_bytes(b"image-bytes")
            cache = emma_pipeline.AxisInferenceCache(
                str(root / "axis_cache.json"),
                "/models/Qwen2.5-VL-7B-Instruct-4bit",
            )
            prompt = "Output exactly: active or not_active."
            allowed = {"active", "not_active"}

            with patch.object(
                emma_pipeline, "_infer_axis", return_value="active"
            ) as infer:
                first = cache.infer(
                    None, None, None, [str(image)], prompt, allowed
                )
                second = cache.infer(
                    None, None, None, [str(image)], prompt, allowed
                )

            self.assertEqual(first, "active")
            self.assertEqual(second, "active")
            self.assertEqual(infer.call_count, 1)
            self.assertEqual(cache.hits, 1)
            self.assertEqual(cache.misses, 1)
            self.assertTrue((root / "axis_cache.json").is_file())

    def test_static_scene_gets_a_periodic_evidence_anchor(self):
        self.assertFalse(
            emma_pipeline.should_keep_scene_frame(
                similarity=0.99,
                threshold=0.95,
                last_kept_playback=0.0,
                current_playback=8.0,
                max_playback_gap=12.0,
            )
        )
        self.assertTrue(
            emma_pipeline.should_keep_scene_frame(
                similarity=0.99,
                threshold=0.95,
                last_kept_playback=0.0,
                current_playback=12.0,
                max_playback_gap=12.0,
            )
        )

    def test_rejects_a_neighboring_or_wrongly_named_video(self):
        with self.assertRaisesRegex(ValueError, "exact dated video required"):
            emma_pipeline.require_ready_video(
                "2026-07-28", "Study_20260727.mp4"
            )

    def test_validation_failure_is_fatal(self):
        failed = SimpleNamespace(returncode=1)
        with patch.object(
            emma_pipeline.subprocess, "run", return_value=failed
        ):
            with self.assertRaisesRegex(RuntimeError, "validation"):
                emma_pipeline.validate_candidate(
                    "/tmp/result_pipeline.json", "2026-07-28"
                )

    def test_chunk_osd_anchors_frames_to_wall_clock(self):
        frames = [
            emma_pipeline.Frame(0, 0, 0.0, 0.0),
            emma_pipeline.Frame(1, 80, 4.0, 120.0),
            emma_pipeline.Frame(2, 160, 8.0, 240.0),
        ]
        emma_pipeline.apply_chunk_osd(frames, "09:00:00", "09:04:00")
        self.assertEqual([frame.osd_time for frame in frames], [
            "09:00:00",
            "09:02:00",
            "09:04:00",
        ])
        self.assertEqual(frames[1].wall_sec, 9 * 3600 + 2 * 60)
        emma_pipeline.require_osd_timeline(frames)

    def test_osd_anchoring_splits_large_wall_clock_span(self):
        frames = [
            emma_pipeline.Frame(0, 0, 0.0, 0.0),
            emma_pipeline.Frame(1, 1, 4.0, 0.0),
            emma_pipeline.Frame(2, 2, 8.0, 0.0),
            emma_pipeline.Frame(3, 3, 12.0, 0.0),
        ]
        osd_by_index = {
            0: "09:00:00",
            1: "09:10:00",
            2: "09:50:00",
            3: "10:00:00",
        }

        anchored = emma_pipeline.anchor_chunks_by_osd(
            [frames],
            lambda chunk: (
                osd_by_index[chunk[0].index],
                osd_by_index[chunk[-1].index],
            ),
        )

        self.assertEqual(
            [[frame.index for frame in chunk] for chunk, _, _ in anchored],
            [[0, 1], [2, 3]],
        )
        self.assertEqual(
            [frame.osd_time for frame in frames],
            ["09:00:00", "09:10:00", "09:50:00", "10:00:00"],
        )

    def test_extracts_times_from_full_osd_text(self):
        values = emma_pipeline.extract_hms_values(
            "2026/07/27 09:39:59 | 2026/07/27 10:15:46"
        )
        self.assertEqual(values, ["09:39:59", "10:15:46"])

    def test_missing_osd_stops_candidate_generation(self):
        frames = [emma_pipeline.Frame(0, 0, 0.0, 0.0)]
        with self.assertRaisesRegex(RuntimeError, "OSD timestamp missing"):
            emma_pipeline.require_osd_timeline(frames)

    def test_same_activity_does_not_merge_across_long_unobserved_gap(self):
        frames = [
            emma_pipeline.Frame(
                0, 0, 0.0, 9 * 3600, activity="writing_reading",
                person_present="emma", adult_present="no",
            ),
            emma_pipeline.Frame(
                1, 1, 1.0, 9 * 3600 + 15 * 60,
                activity="writing_reading", person_present="emma",
                adult_present="no",
            ),
            emma_pipeline.Frame(
                2, 2, 2.0, 9 * 3600 + 30 * 60,
                activity="writing_reading", person_present="emma",
                adult_present="no",
            ),
            emma_pipeline.Frame(
                3, 3, 3.0, 11 * 3600, activity="writing_reading",
                person_present="emma", adult_present="no",
            ),
            emma_pipeline.Frame(
                4, 4, 4.0, 11 * 3600 + 15 * 60,
                activity="writing_reading", person_present="emma",
                adult_present="no",
            ),
            emma_pipeline.Frame(
                5, 5, 5.0, 11 * 3600 + 30 * 60,
                activity="writing_reading", person_present="emma",
                adult_present="no",
            ),
        ]
        stages = emma_pipeline.merge_stages(frames)
        self.assertEqual(len(stages), 2)
        self.assertEqual([stage.category for stage in stages], ["Focus", "Focus"])

    def test_split_observation_filters_adult_only(self):
        frames = [
            emma_pipeline.Frame(0, 0, 0.0, 14 * 3600 + 36 * 60),
            emma_pipeline.Frame(1, 1, 1.0, 15 * 3600 + 5 * 60),
        ]
        emma_pipeline.apply_chunk_observation(
            frames, "adult_only", "no", "not_active", "writing_reading"
        )
        self.assertEqual(emma_pipeline.merge_stages(frames), [])

    def test_adult_only_interval_is_a_hard_stage_barrier(self):
        frames = [
            emma_pipeline.Frame(
                0, 0, 0.0, 9 * 3600,
                person_present="emma", activity="writing_reading",
                adult_present="no",
            ),
            emma_pipeline.Frame(
                1, 1, 1.0, 9 * 3600 + 10 * 60,
                person_present="adult_only", activity="empty",
                adult_present="no",
            ),
            emma_pipeline.Frame(
                2, 2, 2.0, 9 * 3600 + 20 * 60,
                person_present="emma", activity="writing_reading",
                adult_present="no",
            ),
        ]
        stages = emma_pipeline.merge_stages(frames)
        self.assertEqual(len(stages), 2)
        self.assertEqual(stages[0].end, "09:01")
        self.assertEqual(stages[1].start, "09:20")

    def test_frame_chunks_do_not_bridge_large_filtered_gap(self):
        frames = [
            emma_pipeline.Frame(0, 0, 0.0, 0.0),
            emma_pipeline.Frame(1, 1, 4.0, 0.0),
            emma_pipeline.Frame(2, 2, 40.0, 0.0),
            emma_pipeline.Frame(3, 3, 44.0, 0.0),
        ]
        chunks = emma_pipeline.build_frame_chunks(
            frames, batch_size=5, max_playback_span=20.0
        )
        self.assertEqual([[f.index for f in chunk] for chunk in chunks], [
            [0, 1],
            [2, 3],
        ])

    def test_direct_coaching_overrides_visible_screen(self):
        frames = [
            emma_pipeline.Frame(0, 0, 0.0, 16 * 3600 + 28 * 60),
            emma_pipeline.Frame(1, 1, 1.0, 16 * 3600 + 45 * 60),
            emma_pipeline.Frame(2, 2, 2.0, 17 * 3600),
            emma_pipeline.Frame(3, 3, 3.0, 17 * 3600 + 14 * 60),
        ]
        emma_pipeline.apply_chunk_observation(
            frames, "emma", "yes", "active", "writing_reading", "multiple"
        )
        stages = emma_pipeline.merge_stages(frames)
        self.assertEqual(len(stages), 1)
        self.assertEqual(stages[0].category, "Coaching")

    def test_single_person_cannot_be_coaching(self):
        frames = [
            emma_pipeline.Frame(0, 0, 0.0, 16 * 3600),
            emma_pipeline.Frame(1, 1, 1.0, 16 * 3600 + 10 * 60),
        ]
        emma_pipeline.apply_chunk_observation(
            frames, "emma", "yes", "not_active", "writing_reading", "one"
        )
        self.assertTrue(all(frame.adult_present == "no" for frame in frames))
        self.assertNotEqual(emma_pipeline.merge_stages(frames)[0].category, "Coaching")

    def test_adult_nearby_is_not_automatically_coaching(self):
        self.assertEqual(
            emma_pipeline.interpret_who_label(
                "emma_with_adult_independent"
            ),
            ("emma", "multiple", "no"),
        )
        self.assertEqual(
            emma_pipeline.interpret_who_label(
                "emma_with_adult_coaching"
            ),
            ("emma", "multiple", "yes"),
        )

    def test_loads_only_earlier_submitted_parent_feedback_lessons(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            submitted = root / "2026-07-29"
            submitted.mkdir()
            (submitted / "parent_feedback.json").write_text(
                json.dumps({
                    "date": "2026-07-29",
                    "source": "parent_review",
                    "submitted": True,
                    "corrections": [
                        {
                            "lesson": (
                                "成人在场不等于 Coaching；只有直接讲解才算。"
                            )
                        },
                        {"lesson": "  准备阶段   不算 Focus。  "},
                    ],
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            current_day = root / "2026-07-30"
            current_day.mkdir()
            (current_day / "parent_feedback.json").write_text(
                json.dumps({
                    "date": "2026-07-30",
                    "source": "parent_review",
                    "submitted": True,
                    "corrections": [{"lesson": "不应读取当天反馈"}],
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            draft = root / "2026-07-28"
            draft.mkdir()
            (draft / "parent_feedback.json").write_text(
                json.dumps({
                    "date": "2026-07-28",
                    "source": "parent_review",
                    "submitted": False,
                    "corrections": [{"lesson": "不应读取未提交反馈"}],
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            lessons, source_hashes = emma_pipeline.load_parent_feedback(
                str(root), "2026-07-30"
            )

            self.assertEqual(lessons, [
                "成人在场不等于 Coaching；只有直接讲解才算。",
                "准备阶段 不算 Focus。",
            ])
            self.assertEqual(len(source_hashes), 1)
            self.assertEqual(len(source_hashes[0]), 64)

    def test_short_active_screen_is_not_a_distraction(self):
        frames = [
            emma_pipeline.Frame(0, 0, 0.0, 16 * 3600 + 18 * 60),
            emma_pipeline.Frame(1, 1, 1.0, 16 * 3600 + 28 * 60),
        ]
        emma_pipeline.apply_chunk_observation(
            frames, "emma", "no", "active", "writing_reading"
        )
        stages = emma_pipeline.merge_stages(frames)
        self.assertEqual(len(stages), 1)
        self.assertEqual(stages[0].category, "Screen")
        self.assertEqual(emma_pipeline.calculate_tokens(stages)[1], 0)

    def test_screen_observations_are_applied_per_frame(self):
        frames = [
            emma_pipeline.Frame(0, 0, 0.0, 16 * 3600 + 18 * 60),
            emma_pipeline.Frame(1, 1, 1.0, 16 * 3600 + 20 * 60),
        ]
        emma_pipeline.apply_split_chunk_observations(
            frames,
            identity="emma",
            coaching="no",
            screen_uses=["active", "not_active"],
            activity="writing_reading",
            people_count="one",
        )
        self.assertEqual(
            [frame.activity for frame in frames],
            ["looking_at_screen", "writing_reading"],
        )

    def test_brief_isolated_screen_is_folded_into_paper_study(self):
        frames = [
            emma_pipeline.Frame(
                0, 0, 0.0, 9 * 3600,
                person_present="emma", activity="writing_reading",
                adult_present="no",
            ),
            emma_pipeline.Frame(
                1, 1, 1.0, 9 * 3600 + 2 * 60,
                person_present="emma", activity="looking_at_screen",
                screen_visible="active", adult_present="no",
                note='{"screen_use":"active"}',
            ),
            emma_pipeline.Frame(
                2, 2, 2.0, 9 * 3600 + 4 * 60,
                person_present="emma", activity="writing_reading",
                adult_present="no",
            ),
        ]

        collapsed = emma_pipeline.collapse_brief_isolated_screen_runs(frames)

        self.assertEqual(collapsed, 1)
        self.assertEqual(frames[1].activity, "writing_reading")
        self.assertEqual(frames[1].screen_visible, "not_active")
        self.assertEqual(
            json.loads(frames[1].note)["screen_cleanup"],
            "brief_isolated_between_paper",
        )

    def test_brief_coaching_screen_is_preserved(self):
        frames = [
            emma_pipeline.Frame(
                0, 0, 0.0, 16 * 3600 + 16 * 60,
                person_present="emma", activity="writing_reading",
                adult_present="no",
            ),
            emma_pipeline.Frame(
                1, 1, 1.0, 16 * 3600 + 18 * 60,
                person_present="emma", activity="looking_at_screen",
                screen_visible="active", adult_present="yes",
            ),
            emma_pipeline.Frame(
                2, 2, 2.0, 16 * 3600 + 20 * 60,
                person_present="emma", activity="writing_reading",
                adult_present="no",
            ),
        ]

        collapsed = emma_pipeline.collapse_brief_isolated_screen_runs(frames)

        self.assertEqual(collapsed, 0)
        self.assertEqual(frames[1].activity, "looking_at_screen")

    def test_different_reference_person_is_filtered(self):
        frames = [
            emma_pipeline.Frame(0, 0, 0.0, 14 * 3600 + 36 * 60),
        ]
        emma_pipeline.apply_chunk_observation(
            frames, "adult_only", "no", "not_active", "other"
        )
        self.assertEqual(frames[0].person_present, "adult_only")
        self.assertEqual(emma_pipeline.merge_stages(frames), [])

    def test_review_metadata_contains_hash_without_credentials(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "Study_20260728.mp4"
            output = root / "result_pipeline.json"
            video.write_bytes(b"video")
            output.write_text('{"date":"2026-07-28"}\n', encoding="utf-8")
            args = SimpleNamespace(
                interval=4.0,
                resize=512,
                batch_size=5,
                similarity=0.95,
                mode="describe",
            )
            metadata_path = emma_pipeline.write_review_metadata(
                str(output),
                "2026-07-28",
                str(video),
                "/models/Qwen2.5-VL-7B-Instruct-4bit",
                args,
            )
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["status"], "pending_review")
            self.assertEqual(len(metadata["result_sha256"]), 64)
            self.assertEqual(
                metadata["pipeline"]["time_source"],
                "visible_osd_vlm_crop",
            )
            self.assertNotIn("pin", metadata_path.read_text(encoding="utf-8").lower())
            self.assertNotIn("token", metadata_path.read_text(encoding="utf-8").lower())

    def test_failed_run_invalidates_previous_pending_review_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "result_pipeline.json"
            metadata_path = output.with_suffix(".review.json")
            metadata_path.write_text(
                '{"status":"pending_review"}\n', encoding="utf-8"
            )
            emma_pipeline.write_failure_metadata(
                str(output),
                "2026-07-28",
                str(root / "Study_20260728.mp4"),
                RuntimeError("OSD timestamp missing"),
            )
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["status"], "failed")
            self.assertIn("OSD timestamp missing", metadata["error"])


if __name__ == "__main__":
    unittest.main()
