#!/usr/bin/env python3
"""Prepare and validate deterministic Emma Review audit jobs."""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path


VIDEO_RE = re.compile(r"^Study_(\d{8})\.mp4$", re.IGNORECASE)
CATEGORIES = {"Focus", "Coaching", "Screen", "Activity", "Distraction", "Eye Rest"}
RATINGS = {"🟢 优秀", "🟡 警告", "🔴 危险", "⚪ 不在场"}
WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
TOP_KEYS = {"date", "timeline", "evaluations", "stages"}
TIMELINE_KEYS = {
    "Date",
    "Day_Type",
    "Time_Start",
    "Time_End",
    "Category",
    "Focus_Blocks",
    "Distractions",
    "Note",
    "Absent",
    "Eye_Rest_Minutes",
}
EVALUATION_KEYS = {"Date", "Summary", "Rating", "Tokens_Net"}
STAGE_KEYS = {"date", "stage", "start", "end", "duration", "category", "note"}


def parse_date(value: str) -> date:
    cleaned = value.strip()
    fmt = "%Y%m%d" if re.fullmatch(r"\d{8}", cleaned) else "%Y-%m-%d"
    try:
        return datetime.strptime(cleaned, fmt).date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date: {value}") from exc


def minute(value: object, field: str, errors: list[str]) -> int | None:
    if not isinstance(value, str) or not re.fullmatch(
        r"(?:[01]\d|2[0-3]):[0-5]\d", value
    ):
        errors.append(f"{field} must be HH:MM")
        return None
    hour, mins = map(int, value.split(":"))
    return hour * 60 + mins


def require_int(
    value: object, field: str, errors: list[str], *, minimum: int | None = None
) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"{field} must be an integer")
        return None
    if minimum is not None and value < minimum:
        errors.append(f"{field} must be at least {minimum}")
    return value


def require_string(value: object, field: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"{field} must be a string")


def find_atom(
    handle, start: int, end: int, wanted: bytes
) -> tuple[int, int] | None:
    cursor = start
    while cursor + 8 <= end:
        handle.seek(cursor)
        header = handle.read(8)
        if len(header) != 8:
            return None
        size, kind = struct.unpack(">I4s", header)
        header_size = 8
        if size == 1:
            raw = handle.read(8)
            if len(raw) != 8:
                return None
            size = struct.unpack(">Q", raw)[0]
            header_size = 16
        elif size == 0:
            size = end - cursor
        if size < header_size or cursor + size > end:
            return None
        payload_start = cursor + header_size
        atom_end = cursor + size
        if kind == wanted:
            return payload_start, atom_end
        cursor = atom_end
    return None


def mp4_duration(path: Path) -> float | None:
    """Read duration from an ISO BMFF mvhd atom without external dependencies."""
    try:
        with path.open("rb") as handle:
            file_end = path.stat().st_size
            moov = find_atom(handle, 0, file_end, b"moov")
            if moov is None:
                return None
            mvhd = find_atom(handle, moov[0], moov[1], b"mvhd")
            if mvhd is None:
                return None
            handle.seek(mvhd[0])
            version = handle.read(1)
            if not version:
                return None
            handle.read(3)
            if version[0] == 1:
                handle.read(16)
                timescale, duration = struct.unpack(">IQ", handle.read(12))
            else:
                handle.read(8)
                timescale, duration = struct.unpack(">II", handle.read(8))
            return duration / timescale if timescale else None
    except (OSError, EOFError, struct.error):
        return None


def scan(video_dir: Path) -> dict:
    videos: list[dict] = []
    unexpected: list[str] = []
    by_date: dict[str, list[str]] = {}
    for path in sorted(video_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".mp4":
            continue
        match = VIDEO_RE.fullmatch(path.name)
        if not match:
            unexpected.append(path.name)
            continue
        try:
            day = datetime.strptime(match.group(1), "%Y%m%d").date()
        except ValueError:
            unexpected.append(path.name)
            continue
        iso = day.isoformat()
        by_date.setdefault(iso, []).append(path.name)
        seconds = mp4_duration(path)
        videos.append(
            {
                "date": iso,
                "file": path.name,
                "bytes": path.stat().st_size,
                "duration_seconds": (
                    round(seconds, 3) if seconds is not None else None
                ),
                "zero_byte": path.stat().st_size == 0,
            }
        )
    unique_days = sorted(datetime.strptime(x, "%Y-%m-%d").date() for x in by_date)
    missing: list[str] = []
    if unique_days:
        cursor = unique_days[0]
        while cursor <= unique_days[-1]:
            if cursor.isoformat() not in by_date:
                missing.append(cursor.isoformat())
            cursor += timedelta(days=1)
    return {
        "video_dir": str(video_dir.resolve()),
        "count": len(videos),
        "date_start": unique_days[0].isoformat() if unique_days else None,
        "date_end": unique_days[-1].isoformat() if unique_days else None,
        "total_bytes": sum(video["bytes"] for video in videos),
        "missing_dates_within_range": missing,
        "duplicate_dates": {
            key: names for key, names in by_date.items() if len(names) > 1
        },
        "unexpected_mp4_names": unexpected,
        "videos": videos,
    }


def inspect_readiness(
    video_dir: Path,
    day: date,
    *,
    stable_seconds: int = 60,
    allow_legacy_stable: bool = False,
) -> dict:
    compact = day.strftime("%Y%m%d")
    video = video_dir / f"Study_{compact}.mp4"
    ready_file = video_dir / ".ready" / f"Study_{compact}.ready.json"
    report = {
        "date": day.isoformat(),
        "video": str(video.resolve()),
        "ready_manifest": str(ready_file.resolve()),
        "status": "not_ready",
        "ready": False,
        "producer_confirmed": False,
        "reason": "",
    }
    if not video.is_file():
        report["reason"] = "exact dated video is missing"
        return report
    stat = video.stat()
    duration = mp4_duration(video)
    report.update(
        {
            "video_bytes": stat.st_size,
            "video_duration_seconds": (
                round(duration, 3) if duration is not None else None
            ),
            "stable_for_seconds": max(0, int(time.time() - stat.st_mtime)),
        }
    )
    if stat.st_size <= 0:
        report["reason"] = "video is empty"
        return report
    if duration is None or duration <= 0:
        report["reason"] = "video container duration is unreadable"
        return report
    if report["stable_for_seconds"] < stable_seconds:
        report["reason"] = f"video has not been stable for {stable_seconds} seconds"
        return report
    if ready_file.is_file():
        try:
            manifest = json.loads(ready_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            report["reason"] = f"ready manifest is invalid: {exc}"
            return report
        expected = {
            "status": "ready",
            "camera": "Study",
            "bytes": stat.st_size,
        }
        mismatches = [
            key for key, value in expected.items() if manifest.get(key) != value
        ]
        if manifest.get("audit_date") not in {day.isoformat(), compact}:
            mismatches.append("audit_date")
        if Path(str(manifest.get("path", ""))).name != video.name:
            mismatches.append("path")
        if mismatches:
            report["reason"] = (
                "ready manifest does not match video: " + ", ".join(mismatches)
            )
            return report
        report.update(
            {
                "status": "producer_confirmed",
                "ready": True,
                "producer_confirmed": True,
                "reason": "Video Merge validated and published the ready manifest",
                "manifest": manifest,
            }
        )
        return report
    if allow_legacy_stable:
        report.update(
            {
                "status": "legacy_stable",
                "ready": True,
                "reason": (
                    "legacy video is readable and stable, but has no producer "
                    "ready manifest"
                ),
            }
        )
        return report
    report["reason"] = "producer ready manifest is missing"
    return report


def cmd_inventory(args: argparse.Namespace) -> int:
    video_dir = args.video_dir.resolve()
    if not video_dir.is_dir():
        print(f"ERROR: not a directory: {video_dir}", file=sys.stderr)
        return 2
    report = scan(video_dir)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    gib = report["total_bytes"] / 1024**3
    print(
        f"{report['count']} videos | {report['date_start']}.."
        f"{report['date_end']} | {gib:.2f} GiB"
    )
    print(f"Missing dates: {', '.join(report['missing_dates_within_range']) or 'none'}")
    duplicates = (
        json.dumps(report["duplicate_dates"], ensure_ascii=False)
        if report["duplicate_dates"]
        else "none"
    )
    print(f"Duplicate dates: {duplicates}")
    print(
        f"Unexpected MP4 names: "
        f"{', '.join(report['unexpected_mp4_names']) or 'none'}"
    )
    for item in report["videos"]:
        duration = (
            "unknown"
            if item["duration_seconds"] is None
            else f"{item['duration_seconds'] / 60:.1f} min"
        )
        print(
            f"{item['date']}  {item['file']}  "
            f"{item['bytes'] / 1024**2:.1f} MiB  {duration}"
        )
    return 0


def cmd_ready(args: argparse.Namespace) -> int:
    video_dir = args.video_dir.resolve()
    if not video_dir.is_dir():
        print(f"ERROR: not a directory: {video_dir}", file=sys.stderr)
        return 2
    try:
        day = select_date(args.date, video_dir)
    except (argparse.ArgumentTypeError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    report = inspect_readiness(
        video_dir,
        day,
        stable_seconds=args.stable_seconds,
        allow_legacy_stable=args.allow_legacy_stable,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready"] else 1


def select_date(selector: str, video_dir: Path) -> date:
    cleaned = selector.strip().lower()
    if cleaned == "today":
        return date.today()
    if cleaned != "latest":
        return parse_date(selector)
    candidates: list[date] = []
    if video_dir.is_dir():
        for candidate in video_dir.iterdir():
            match = VIDEO_RE.fullmatch(candidate.name)
            if not match or not candidate.is_file():
                continue
            try:
                candidates.append(datetime.strptime(match.group(1), "%Y%m%d").date())
            except ValueError:
                continue
    if not candidates:
        raise FileNotFoundError(
            f"no matching Study_YYYYMMDD.mp4 files in {video_dir}"
        )
    return max(candidates)


def cmd_prepare(args: argparse.Namespace) -> int:
    video_dir = args.video_dir.resolve()
    try:
        day = select_date(args.date, video_dir)
    except (argparse.ArgumentTypeError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    video = video_dir / f"Study_{day.strftime('%Y%m%d')}.mp4"
    if not video.is_file():
        print(f"ERROR: exact dated video not found: {video}", file=sys.stderr)
        return 2
    skill_dir = Path(__file__).resolve().parent.parent
    template = (skill_dir / "references" / "audit-prompt.md").read_text(
        encoding="utf-8"
    )
    marker = "---\n\n"
    prompt = template.split(marker, 1)[1] if marker in template else template
    prompt = prompt.replace("{{DATE}}", day.isoformat()).replace(
        "{{VIDEO_FILENAME}}", video.name
    )
    output_dir = (
        args.output_dir or video_dir / ".emma-review" / day.isoformat()
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = output_dir / "prompt.txt"
    job_path = output_dir / "job.json"
    result_path = output_dir / "result.json"
    prompt_path.write_text(prompt.rstrip() + "\n", encoding="utf-8")
    manifest = {
        "date": day.isoformat(),
        "video": str(video.resolve()),
        "video_bytes": video.stat().st_size,
        "video_duration_seconds": mp4_duration(video),
        "prompt": str(prompt_path),
        "result": str(result_path),
        "status": "prepared",
        "upload_performed": False,
    }
    job_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def expected_rating(absent: bool, distractions: int, tokens: int) -> str:
    if absent:
        return "⚪ 不在场"
    if distractions >= 3 or tokens < 0:
        return "🔴 危险"
    if distractions == 0 and tokens >= 2:
        return "🟢 优秀"
    return "🟡 警告"


def exact_keys(
    obj: object, expected: set[str], field: str, errors: list[str]
) -> bool:
    if not isinstance(obj, dict):
        errors.append(f"{field} must be an object")
        return False
    if set(obj) != expected:
        errors.append(
            f"{field} keys mismatch; expected {sorted(expected)}, got {sorted(obj)}"
        )
        return False
    return True


def validate_result(data: object, expected_date: str | None = None) -> list[str]:
    errors: list[str] = []
    if not exact_keys(data, TOP_KEYS, "root", errors):
        if not isinstance(data, dict):
            return errors

    root_date = data.get("date")
    parsed_day: date | None = None
    if isinstance(root_date, str):
        try:
            parsed_day = parse_date(root_date)
        except argparse.ArgumentTypeError:
            pass
    if parsed_day is None or root_date != parsed_day.isoformat():
        errors.append("date must be a valid YYYY-MM-DD")
    if expected_date:
        try:
            requested_date = parse_date(expected_date).isoformat()
            if root_date != requested_date:
                errors.append(f"date does not match expected date {requested_date}")
        except argparse.ArgumentTypeError as exc:
            errors.append(str(exc))

    timeline = data.get("timeline", [])
    if not isinstance(timeline, list) or len(timeline) != 1:
        errors.append("timeline must contain exactly one row")
        row: dict = {}
    else:
        row = timeline[0]
        exact_keys(row, TIMELINE_KEYS, "timeline[0]", errors)

    evaluations = data.get("evaluations", {})
    exact_keys(evaluations, EVALUATION_KEYS, "evaluations", errors)
    stages = data.get("stages", [])
    if not isinstance(stages, list):
        errors.append("stages must be an array")
        stages = []

    coverage_start = coverage_end = None
    if isinstance(row, dict):
        if row.get("Date") != root_date:
            errors.append("timeline[0].Date must match root date")
        if parsed_day and row.get("Day_Type") != WEEKDAYS[parsed_day.weekday()]:
            errors.append(f"Day_Type must be {WEEKDAYS[parsed_day.weekday()]}")
        coverage_start = minute(
            row.get("Time_Start"), "timeline[0].Time_Start", errors
        )
        coverage_end = minute(row.get("Time_End"), "timeline[0].Time_End", errors)
        if (
            coverage_start is not None
            and coverage_end is not None
            and coverage_end <= coverage_start
        ):
            errors.append("timeline coverage must end after it starts")
        require_string(row.get("Category"), "timeline[0].Category", errors)
        require_string(row.get("Note"), "timeline[0].Note", errors)

    if isinstance(evaluations, dict):
        if evaluations.get("Date") != root_date:
            errors.append("evaluations.Date must match root date")
        require_string(evaluations.get("Summary"), "evaluations.Summary", errors)

    focus_blocks = distractions = eye_rest = 0
    previous_end: int | None = None
    for index, stage in enumerate(stages):
        label = f"stages[{index}]"
        if not exact_keys(stage, STAGE_KEYS, label, errors):
            continue
        if stage.get("date") != root_date:
            errors.append(f"{label}.date must match root date")
        require_string(stage.get("stage"), f"{label}.stage", errors)
        require_string(stage.get("note"), f"{label}.note", errors)
        category = stage.get("category")
        if category not in CATEGORIES:
            errors.append(f"{label}.category is not an allowed enum")
        start = minute(stage.get("start"), f"{label}.start", errors)
        end = minute(stage.get("end"), f"{label}.end", errors)
        duration = require_int(
            stage.get("duration"), f"{label}.duration", errors, minimum=0
        )
        if start is not None and end is not None:
            if end <= start:
                errors.append(f"{label} must end after it starts")
            elif duration is not None and duration != end - start:
                errors.append(f"{label}.duration must equal end minus start")
            if previous_end is not None and start < previous_end:
                errors.append(f"{label} overlaps or is out of order")
            previous_end = end
            if coverage_start is not None and start < coverage_start:
                errors.append(f"{label} starts before timeline coverage")
            if coverage_end is not None and end > coverage_end:
                errors.append(f"{label} ends after timeline coverage")
        if category == "Focus":
            focus_blocks += 1
            if duration is not None and duration < 30:
                errors.append(f"{label} Focus duration must be at least 30")
        elif category == "Distraction":
            distractions += 1
        elif category == "Screen" and duration is not None and duration > 30:
            distractions += 1
        elif category == "Eye Rest" and duration is not None:
            eye_rest += duration
            if duration < 10:
                errors.append(f"{label} Eye Rest duration must be at least 10")

    absent = row.get("Absent") if isinstance(row, dict) else None
    if not isinstance(absent, bool):
        errors.append("timeline[0].Absent must be boolean")
        absent = False
    totals = (
        ("Focus_Blocks", focus_blocks),
        ("Distractions", distractions),
        ("Eye_Rest_Minutes", eye_rest),
    )
    for field, expected in totals:
        actual = row.get(field) if isinstance(row, dict) else None
        require_int(actual, f"timeline[0].{field}", errors, minimum=0)
        if actual != expected:
            errors.append(f"timeline[0].{field} must be {expected}")
    if absent and (stages or focus_blocks or distractions or eye_rest):
        errors.append("absent audit must have no stages and zero totals")

    tokens = focus_blocks - distractions
    if isinstance(evaluations, dict):
        actual_tokens = evaluations.get("Tokens_Net")
        require_int(actual_tokens, "evaluations.Tokens_Net", errors)
        if actual_tokens != tokens:
            errors.append(f"evaluations.Tokens_Net must be {tokens}")
        rating = evaluations.get("Rating")
        if rating not in RATINGS:
            errors.append("evaluations.Rating is not an exact allowed value")
        rating_expected = expected_rating(absent, distractions, tokens)
        if rating != rating_expected:
            errors.append(f"evaluations.Rating must be {rating_expected}")
    return errors


def cmd_validate(args: argparse.Namespace) -> int:
    path = args.result.resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INVALID: {exc}")
        return 1
    errors = validate_result(data, args.expected_date)
    if errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    row = data["timeline"][0]
    print(
        f"VALID: {path} | Focus={row['Focus_Blocks']} "
        f"Distractions={row['Distractions']} "
        f"EyeRest={row['Eye_Rest_Minutes']} "
        f"Tokens={data['evaluations']['Tokens_Net']}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inventory = sub.add_parser("inventory", help="inspect dated Study MP4 files")
    inventory.add_argument(
        "video_dir", nargs="?", type=Path, default=Path.cwd()
    )
    inventory.add_argument("--json", action="store_true")
    inventory.set_defaults(func=cmd_inventory)
    ready = sub.add_parser(
        "ready", help="check whether Video Merge published a dated Study video"
    )
    ready.add_argument("date")
    ready.add_argument("--video-dir", type=Path, default=Path.cwd())
    ready.add_argument("--stable-seconds", type=int, default=60)
    ready.add_argument("--allow-legacy-stable", action="store_true")
    ready.set_defaults(func=cmd_ready)
    prepare = sub.add_parser("prepare", help="create one dated audit packet")
    prepare.add_argument("date")
    prepare.add_argument("--video-dir", type=Path, default=Path.cwd())
    prepare.add_argument("--output-dir", type=Path)
    prepare.set_defaults(func=cmd_prepare)
    validate = sub.add_parser(
        "validate", help="validate one Emma Focus Admin result JSON"
    )
    validate.add_argument("result", type=Path)
    validate.add_argument("--expected-date")
    validate.set_defaults(func=cmd_validate)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
