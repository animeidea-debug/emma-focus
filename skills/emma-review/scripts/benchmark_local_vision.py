#!/usr/bin/env python3
"""
Benchmark Qwen3-VL-4B-Instruct-4bit on the 2026-07-26 gold standard sample.

Tests three things:
1. Compatibility  – can MLX-VLM load the model and process video frames?
2. Timing         – model load, frame extraction, and inference latency
3. Memory         – peak RSS and MLX-reported peak memory

The script does NOT write to the production database. It only loads the model,
extracts frames from the supplied video, runs inference, and prints a structured
report for manual comparison with the gold standard result.json.

Usage (run from the Emma Focus project root in a real Mac terminal):

    .venv-emma-review/bin/python skills/emma-review/scripts/benchmark_local_vision.py \
        --video "/Volumes/nvme14-139XXXX2622/export_videos/书房/Study_20260726.mp4" \
        --gold  "/Volumes/nvme14-139XXXX2622/export_videos/书房/.emma-review/2026-07-26/result.json"

Options:
    --model PATH     Model directory (default: ~/Library/Caches/emma-review/models/Qwen3-VL-4B-Instruct-4bit)
    --num-frames N   Number of frames to extract (default: 12)
    --max-tokens N   Max generation tokens (default: 2048)
    --skip-video     Skip the direct video-path test, only test multi-image
    --simple-prompt  Use a simplified description prompt instead of the full audit
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

# --- psutil is safe to import even without GPU ---
try:
    import psutil
except ImportError:
    print("ERROR: psutil not installed. Run: uv pip install psutil", file=sys.stderr)
    sys.exit(1)


def fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def fmt_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(seconds, 60)
    return f"{int(m)}m{s:.0f}s"


def mem_rss_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)


def print_header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_metric(key: str, value: str, ok: bool = True) -> None:
    mark = "✅" if ok else "❌"
    print(f"  {mark} {key:.<40s} {value}")


def extract_frames(video_path: str, num_frames: int, out_dir: str, resize: int = None) -> list[str]:
    """Extract evenly-spaced frames from a video using OpenCV."""
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration_sec = total_frames / fps if fps > 0 else 0

    print(f"  Video: {total_frames} frames, {fps:.1f} fps, {duration_sec:.0f}s ({fmt_time(duration_sec)})")

    if total_frames <= 0:
        raise RuntimeError("Video has no frames or frame count is unavailable")

    # Evenly sample N frames across the entire video
    indices = [int(i * total_frames / num_frames) for i in range(num_frames)]

    frame_paths = []
    for idx, frame_idx in enumerate(indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            print(f"  ⚠️  Frame {idx} at index {frame_idx} could not be read, skipping")
            continue
        if resize:
            frame = cv2.resize(frame, (resize, resize))
        out_path = os.path.join(out_dir, f"frame_{idx:02d}.jpg")
        cv2.imwrite(out_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        frame_paths.append(out_path)

    cap.release()
    return frame_paths


SIMPLE_PROMPT = """You are looking at frames extracted from a study-room monitoring video.
The video is a time-lapse recording. Each image represents a different point in time
during the day.

For each image, briefly describe:
1. Is a young person (a 13-year-old girl) visible in the frame?
2. What activity is she doing (if visible)?
3. Are there any screen devices (tablet, phone, computer) visible and in use?
4. Is an adult present?

Keep your response concise. List one line per image."""


FULL_AUDIT_PROMPT = """Analyze {num_images} frames from a study-room time-lapse video ({date}) of Emma (13yo girl).

The video filename is: {video_filename}

For each frame, identify: Is Emma present? What is she doing? Any screens visible? Adult present?

Then output ONE JSON object:
{{"date":"{date}","timeline":[{{"Focus_Blocks":N,"Distractions":N,"Eye_Rest_Minutes":N,"Absent":false}}],"evaluations":{{"Summary":"中文总结","Rating":"🟢优秀/🟡警告/🔴危险","Tokens_Net":N}},"stages":[{{"start":"HH:MM","end":"HH:MM","duration":N,"category":"Focus/Coaching/Screen/Distraction/Eye Rest","stage":"中文标签"}}]}}

Focus=30+min study. Distraction=off-task. Screen>30min=+1 distraction. Tokens=Focus-Dist (1:1). 🔴 if Dist>=3. Raw JSON only."""


def run_benchmark(args: argparse.Namespace) -> int:
    print_header("Emma Review Local Vision Benchmark")
    print(f"  Model:  {args.model}")
    print(f"  Video:  {args.video}")
    print(f"  Gold:   {args.gold}")
    print(f"  Frames: {args.num_frames}")
    print(f"  Resize: {args.resize or 'native'}")

    # --- Load gold standard for comparison ---
    gold = None
    if args.gold and os.path.exists(args.gold):
        with open(args.gold) as f:
            gold = json.load(f)
        g = gold["evaluations"]
        t = gold["timeline"][0]
        print(f"\n  Gold standard ({g['Date']}):")
        print(f"    Focus={t['Focus_Blocks']}  Distractions={t['Distractions']}  "
              f"EyeRest={t['Eye_Rest_Minutes']}min  Tokens={g['Tokens_Net']}  "
              f"Rating={g['Rating']}  Stages={len(gold['stages'])}")

    baseline_mem = mem_rss_mb()

    # === TEST 1: Model Loading ===
    print_header("TEST 1: Model Loading (Compatibility + Timing)")

    try:
        from mlx_vlm import load, apply_chat_template, generate
        from mlx_vlm.utils import load_config
    except Exception as e:
        print_metric("Import mlx_vlm", f"FAILED: {e}", ok=False)
        print("\nThis script must run in a real Mac terminal with GPU access.")
        print("The Codex sandbox has no Metal device and cannot load MLX models.")
        return 1

    t0 = time.time()
    try:
        model, processor = load(args.model)
        load_time = time.time() - t0
        config = load_config(args.model)
        print_metric("Model loaded", "OK", ok=True)
        print_metric("Load time", fmt_time(load_time), ok=True)
        print_metric("Memory after load", f"{mem_rss_mb():.0f} MB (delta +{mem_rss_mb()-baseline_mem:.0f} MB)", ok=True)
    except Exception as e:
        print_metric("Model loaded", f"FAILED: {e}", ok=False)
        traceback.print_exc()
        return 1

    # === TEST 2: Frame Extraction ===
    print_header("TEST 2: Frame Extraction")

    with tempfile.TemporaryDirectory(prefix="emma-bench-") as tmpdir:
        t0 = time.time()
        try:
            frame_paths = extract_frames(args.video, args.num_frames, tmpdir, resize=args.resize)
            extract_time = time.time() - t0
            print_metric("Frames extracted", f"{len(frame_paths)}/{args.num_frames}", ok=len(frame_paths) > 0)
            print_metric("Extraction time", fmt_time(extract_time), ok=True)
            for p in frame_paths:
                print(f"    {os.path.basename(p)}: {fmt_bytes(os.path.getsize(p))}")
        except Exception as e:
            print_metric("Frame extraction", f"FAILED: {e}", ok=False)
            traceback.print_exc()
            return 1

        if not frame_paths:
            print_metric("No frames extracted", "Cannot continue", ok=False)
            return 1

        # === TEST 3: Multi-Image Inference ===
        prompt_type = "simple" if args.simple_prompt else "full audit"
        print_header(f"TEST 3: Multi-Image Inference ({prompt_type})")

        video_filename = os.path.basename(args.video)
        date_str = "2026-07-26"
        if gold:
            date_str = gold.get("date", date_str)

        if args.simple_prompt:
            user_prompt = SIMPLE_PROMPT
        else:
            user_prompt = FULL_AUDIT_PROMPT.format(
                num_images=len(frame_paths),
                video_filename=video_filename,
                date=date_str,
            )

        try:
            messages = [{"role": "user", "content": user_prompt}]
            formatted_prompt = apply_chat_template(
                processor, config, messages,
                add_generation_prompt=True,
                num_images=len(frame_paths),
            )
            print_metric("Prompt formatted", f"{len(formatted_prompt)} chars", ok=True)
        except Exception as e:
            print_metric("Prompt formatting", f"FAILED: {e}", ok=False)
            traceback.print_exc()
            return 1

        t0 = time.time()
        try:
            result = generate(
                model, processor,
                prompt=formatted_prompt,
                image=frame_paths,
                max_tokens=args.max_tokens,
                temperature=0.0,
                enable_thinking=False,
                seed=42,
                verbose=False,
            )
            inference_time = time.time() - t0

            print_metric("Inference completed", "OK", ok=True)
            print_metric("Inference time", fmt_time(inference_time), ok=True)
            print_metric("Prompt tokens", str(result.prompt_tokens), ok=True)
            print_metric("Generation tokens", str(result.generation_tokens), ok=True)
            print_metric("Prompt TPS (prefill)", f"{result.prompt_tps:.1f} tok/s", ok=True)
            print_metric("Generation TPS", f"{result.generation_tps:.1f} tok/s", ok=True)
            print_metric("Peak memory (MLX)", f"{result.peak_memory:.2f} GB", ok=True)
            print_metric("Peak memory (RSS)", f"{mem_rss_mb():.0f} MB", ok=True)

            print(f"\n  --- Model Output (first 2000 chars) ---")
            output_text = result.text[:2000]
            print(output_text)
            if len(result.text) > 2000:
                print(f"  ... ({len(result.text)} chars total)")

            # === Compare with gold standard ===
            if gold and not args.simple_prompt:
                print_header("GOLD STANDARD COMPARISON")
                g = gold["evaluations"]
                t = gold["timeline"][0]
                print(f"  Gold:    Focus={t['Focus_Blocks']}  Dist={t['Distractions']}  "
                      f"Tokens={g['Tokens_Net']}  Rating={g['Rating']}  Stages={len(gold['stages'])}")
                print(f"  Output:  (see above - compare manually)")
                print(f"\n  Note: The 4B model output is a rough assessment from {len(frame_paths)} sampled frames.")
                print(f"  Full accuracy benchmark requires the complete frame extraction +")
                print(f"  boundary refinement pipeline described in automation-design.md.")

        except Exception as e:
            print_metric("Inference", f"FAILED: {e}", ok=False)
            traceback.print_exc()

            # If multi-image fails, try single image as fallback
            print(f"\n  Attempting single-image fallback...")
            try:
                result = generate(
                    model, processor,
                    prompt=apply_chat_template(
                        processor, config,
                        [{"role": "user", "content": "Describe what you see in this image."}],
                        add_generation_prompt=True, num_images=1,
                    ),
                    image=frame_paths[0],
                    max_tokens=256,
                    temperature=0.0,
                    enable_thinking=False,
                    seed=42,
                )
                print_metric("Single-image fallback", "OK", ok=True)
                print(f"  Output: {result.text[:500]}")
            except Exception as e2:
                print_metric("Single-image fallback", f"ALSO FAILED: {e2}", ok=False)

    # === TEST 4: Direct Video Path (optional) ===
    if not args.skip_video:
        print_header("TEST 4: Direct Video Path (experimental)")

        try:
            messages = [{"role": "user", "content": "Describe what happens in this video."}]
            formatted = apply_chat_template(
                processor, config, messages,
                add_generation_prompt=True,
            )
            t0 = time.time()
            result = generate(
                model, processor,
                prompt=formatted,
                video=args.video,
                max_tokens=512,
                temperature=0.0,
                enable_thinking=False,
                seed=42,
            )
            video_time = time.time() - t0
            print_metric("Video path inference", "OK", ok=True)
            print_metric("Video inference time", fmt_time(video_time), ok=True)
            print_metric("Generation tokens", str(result.generation_tokens), ok=True)
            print(f"  Output: {result.text[:500]}")
        except Exception as e:
            print_metric("Video path inference", f"FAILED: {e}", ok=False)
            print("  (This is expected if mlx-vlm doesn't fully support Qwen3-VL video input yet)")

    # === Summary ===
    print_header("BENCHMARK SUMMARY")
    print(f"  Model:      {os.path.basename(args.model)}")
    print(f"  Load time:  {fmt_time(load_time)}")
    print(f"  Peak RSS:   {mem_rss_mb():.0f} MB")
    print(f"  Machine:    {os.uname().machine}")
    print(f"\n  Next steps:")
    print(f"  - If all tests passed, proceed to full pipeline benchmark with 5 gold-standard dates")
    print(f"  - If video path failed, use multi-image approach for production")
    print(f"  - Record these metrics in docs/emma-review/work-handoff.md")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Qwen3-VL-4B on the 2026-07-26 gold standard sample."
    )
    default_model = os.path.expanduser(
        "~/Library/Caches/emma-review/models/Qwen3-VL-4B-Instruct-4bit"
    )
    parser.add_argument("--model", default=default_model, help="Model directory path")
    parser.add_argument("--video", required=True, help="Path to Study_YYYYMMDD.mp4")
    parser.add_argument("--gold", default=None, help="Path to gold standard result.json")
    parser.add_argument("--num-frames", type=int, default=12, help="Number of frames to extract")
    parser.add_argument("--max-tokens", type=int, default=2048, help="Max generation tokens")
    parser.add_argument("--skip-video", action="store_true", help="Skip direct video path test")
    parser.add_argument("--resize", type=int, default=None,
                        help="Resize frames to this square dimension (e.g. 384) to reduce token count")
    parser.add_argument("--simple-prompt", action="store_true", help="Use simplified description prompt")
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"ERROR: Model not found at {args.model}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.video):
        print(f"ERROR: Video not found at {args.video}", file=sys.stderr)
        sys.exit(1)

    sys.exit(run_benchmark(args))


if __name__ == "__main__":
    main()
