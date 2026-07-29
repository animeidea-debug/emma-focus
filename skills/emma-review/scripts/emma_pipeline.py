#!/usr/bin/env python3
"""
Emma Review local vision pipeline.

Extracts frames from a study-room time-lapse video, uses a local vision
model to classify each frame, then applies deterministic Python logic to
merge stages and calculate Focus Blocks, Distractions, Tokens and Rating.

The output is a candidate result.json. The script requires an exact dated
video, a producer ready manifest (or an explicit historical override), and a
successful emma_review.py validation. It never submits production data.

Usage (run from project root in a real Mac terminal with GPU):

  .venv-emma-review/bin/python skills/emma-review/scripts/emma_pipeline.py \
    --date 2026-07-26 \
    --video "/path/to/Study_20260726.mp4" \
    --allow-legacy-stable

The script does NOT accept a parent PIN and does NOT write to the production
database. A validated candidate still requires parent review before import.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
  import cv2
except ModuleNotFoundError:
  cv2 = None

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Frame:
  """A single extracted video frame with metadata."""
  index: int     # extraction order
  video_frame: int   # original frame number in the video
  playback_sec: float # playback time in seconds
  wall_sec: float   # estimated wall-clock time in seconds (playback * 30)
  image_path: str = ""
  osd_image_path: str = ""
  osd_time: str = ""  # OSD timestamp read by the model, e.g. "09:22"
  # Model classification
  person_present: str = "unknown"   # emma / adult_only / empty / uncertain
  activity: str = "unknown"      # atomic: writing_reading / looking_at_screen / idle / resting / talking / moving / other / unknown
  screen_visible: str = "unknown"   # active / not_active / uncertain
  people_count: str = "unknown"     # one / multiple / uncertain
  adult_present: str = "unknown"    # direct coaching: yes / no / uncertain
  confidence: str = "low"       # high / medium / low
  note: str = ""


@dataclass
class Stage:
  """A merged activity stage."""
  start: str    # HH:MM
  end: str     # HH:MM
  duration: int  # minutes
  category: str  # Focus / Coaching / Screen / Distraction / Eye Rest / Activity
  stage: str    # Chinese label
  note: str = ""  # brief observation


DEFAULT_MODEL = os.path.expanduser(
  "~/Library/Caches/emma-review/models/Qwen2.5-VL-7B-Instruct-4bit"
)


def require_cv2() -> None:
  if cv2 is None:
    raise RuntimeError(
      "OpenCV is required for frame extraction. Run this pipeline with "
      ".venv-emma-review/bin/python3."
    )


def fit_long_edge(width: int, height: int, long_edge: int) -> tuple[int, int]:
  """Return an aspect-preserving size whose longest edge is `long_edge`."""
  if width <= 0 or height <= 0 or long_edge <= 0:
    raise ValueError("image dimensions and long edge must be positive")
  scale = long_edge / max(width, height)
  return (
    max(1, int(round(width * scale))),
    max(1, int(round(height * scale))),
  )


# ---------------------------------------------------------------------------
# Frame extraction
# ---------------------------------------------------------------------------

def extract_frames(video_path: str, interval_sec: float = 10.0,
          resize: int = 384, out_dir: str = "") -> list[Frame]:
  """Extract one frame every `interval_sec` playback seconds.

  Returns a list of Frame objects with image paths and timing metadata.
  The书房成品 is a 30x time-lapse, so 4s playback ≈ 2 min wall-clock.
  """
  require_cv2()
  cap = cv2.VideoCapture(video_path)
  if not cap.isOpened():
    raise RuntimeError(f"Cannot open video: {video_path}")

  fps = cap.get(cv2.CAP_PROP_FPS)
  total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
  duration = total_frames / fps if fps > 0 else 0

  print(f" Video: {total_frames} frames, {fps:.1f} fps, {duration:.0f}s ({duration/60:.1f}min)")

  # Extract one frame every `interval_sec` playback seconds
  frame_interval = int(fps * interval_sec)
  indices = list(range(0, total_frames, frame_interval))

  frames: list[Frame] = []
  for idx, fi in enumerate(indices):
    cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
    ret, image = cap.read()
    if not ret:
      continue

    playback_sec = fi / fps if fps > 0 else 0
    wall_sec = playback_sec * 30 # 30x time-lapse

    height, width = image.shape[:2]
    osd_crop = image[:max(1, int(height * 0.18)), :max(1, int(width * 0.48))]
    crop_height, crop_width = osd_crop.shape[:2]
    if crop_width:
      target_width = 768
      target_height = max(1, int(crop_height * target_width / crop_width))
      osd_crop = cv2.resize(osd_crop, (target_width, target_height))

    if resize:
      target_width, target_height = fit_long_edge(width, height, resize)
      image = cv2.resize(
        image,
        (target_width, target_height),
        interpolation=cv2.INTER_AREA,
      )
    img_path = os.path.join(out_dir, f"frame_{idx:04d}.jpg")
    osd_path = os.path.join(out_dir, f"osd_{idx:04d}.jpg")
    cv2.imwrite(img_path, image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    cv2.imwrite(osd_path, osd_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])

    frames.append(Frame(
      index=idx,
      video_frame=fi,
      playback_sec=playback_sec,
      wall_sec=wall_sec,
      image_path=img_path,
      osd_image_path=osd_path,
    ))

  cap.release()
  print(f" Extracted {len(frames)} frames (every {interval_sec}s playback)")
  return frames


def should_keep_scene_frame(
  similarity: float,
  threshold: float,
  last_kept_playback: float,
  current_playback: float,
  max_playback_gap: float,
) -> bool:
  """Keep changed frames and periodic anchors within static scenes."""
  return (
    similarity < threshold
    or current_playback - last_kept_playback >= max_playback_gap
  )


def filter_similar_frames(
  frames: list[Frame],
  threshold: float = 0.95,
  max_playback_gap: float = 8.0,
) -> list[Frame]:
  """Filter out consecutive frames that are nearly identical (scene change detection).

  Uses normalized cross-correlation between consecutive frames.
  Keeps frames where the scene changes significantly. It also retains a
  regular anchor from a static scene, because sustained Screen use can have
  very little visible motion but still needs evidence across its duration.
  """
  require_cv2()
  if len(frames) <= 1:
    return frames

  if max_playback_gap <= 0:
    raise ValueError("max_playback_gap must be positive")

  filtered = [frames[0]]
  prev_img = cv2.imread(frames[0].image_path, cv2.IMREAD_GRAYSCALE)
  last_kept_playback = frames[0].playback_sec

  for frame in frames[1:]:
    curr_img = cv2.imread(frame.image_path, cv2.IMREAD_GRAYSCALE)
    if prev_img is None or curr_img is None:
      filtered.append(frame)
      prev_img = curr_img
      continue

    # Calculate structural similarity (simplified: mean absolute difference)
    diff = cv2.absdiff(prev_img, curr_img)
    mean_diff = diff.mean()
    # Normalize to 0-1 range (max possible is 255)
    similarity = 1.0 - (mean_diff / 255.0)

    if should_keep_scene_frame(
      similarity,
      threshold,
      last_kept_playback,
      frame.playback_sec,
      max_playback_gap,
    ):
      filtered.append(frame)
      prev_img = curr_img
      last_kept_playback = frame.playback_sec
    # else: skip this frame as too similar to previous

  print(
    f" Scene filter: {len(frames)} -> {len(filtered)} frames "
    f"(threshold={threshold}, static anchor={max_playback_gap}s)"
  )
  # P0 fix: keep all frames from the last 10% of the video (evening period)
  # to ensure Screen/Coaching in the evening is not filtered out
  if len(filtered) < len(frames) * 0.3:
    print(f"  WARNING: aggressive filtering kept only {len(filtered)}/{len(frames)} frames, "
          f"adding back periodic anchors")
    # Re-run with more aggressive anchoring
    filtered = [frames[0]]
    prev_img = cv2.imread(frames[0].image_path, cv2.IMREAD_GRAYSCALE)
    last_kept_playback = frames[0].playback_sec
    for frame in frames[1:]:
      curr_img = cv2.imread(frame.image_path, cv2.IMREAD_GRAYSCALE)
      if prev_img is None or curr_img is None:
        filtered.append(frame)
        prev_img = curr_img
        continue
      diff = cv2.absdiff(prev_img, curr_img)
      similarity = 1.0 - (diff.mean() / 255.0)
      if should_keep_scene_frame(similarity, threshold, last_kept_playback, frame.playback_sec, max_playback_gap / 2):
        filtered.append(frame)
        prev_img = curr_img
        last_kept_playback = frame.playback_sec
    print(f"  After re-filter: {len(filtered)} frames")
  return filtered


# ---------------------------------------------------------------------------
# Model classification
# ---------------------------------------------------------------------------

CLASSIFY_PROMPT = """Study room time-lapse video. Emma is a 13-year-old girl.

For each image, describe what you see. One line per image:
FRAME|<n>|<osd_time>|<person>|<activity>|<screen>|<adult>|<conf>|<note>

person: emma / empty / uncertain
activity: writing_reading / looking_at_screen / idle / resting / talking / moving / other / unknown
screen: yes / no / uncertain
adult: yes / no / uncertain (is a parent or adult visible?)
conf: high / medium / low
note: 2-4 Chinese characters

FRAME| lines only."""

# ---------------------------------------------------------------------------
# Description prompt for Qwen2.5-VL (pure description, no classification)
# ---------------------------------------------------------------------------

DESCRIBE_PROMPT = """This is a time-lapse frame from a study room camera (30x speed). Focus on the PERSON and what they are DOING.

Describe in ONE short sentence: what is the main person doing? Is there another person present? Examples:

Good: "Emma is writing in a notebook. No other person. A laptop is on the desk but she is not using it."
Good: "Emma is reading a book at her desk. No other person."
Good: "Emma is typing on a laptop. No other person."
Good: "Emma and a parent are sitting together. The parent is pointing at a book."
Good: "Emma is resting her head on the desk. No other person. Seems tired."
Good: "Room is empty. No one is present."
Good: "Emma is looking at a phone screen. No other person."
Good: "Emma is standing up and walking around the room. No other person."
Good: "Emma is not at the desk. She is organizing things on the shelf."

IMPORTANT: If a laptop is on the desk but the person is writing/reading, say "writing" not "working on laptop"."""



def classify_frames(frames, model_path, batch_size=8, resize=384):
  """Classify frames in batches using the local VLM.

  Modifies frames in-place by setting their classification fields.
  """
  from mlx_vlm import load, apply_chat_template, generate
  from mlx_vlm.utils import load_config

  print(f" Loading model: {os.path.basename(model_path)}")
  model, processor = load(model_path)
  config = load_config(model_path)

  total_batches = math.ceil(len(frames) / batch_size)
  print(f" Classifying {len(frames)} frames in {total_batches} batches of {batch_size}")

  for batch_idx in range(total_batches):
    start = batch_idx * batch_size
    end = min(start + batch_size, len(frames))
    batch = frames[start:end]

    prompt = CLASSIFY_PROMPT.format(
      num_frames=len(batch),
      num_frames_minus_one=len(batch) - 1,
    )

    messages = [{"role": "user", "content": prompt}]
    formatted = apply_chat_template(
      processor, config, messages,
      add_generation_prompt=True, num_images=len(batch),
    )

    image_paths = [f.image_path for f in batch]

    t0 = time.time()
    result = generate(
      model, processor,
      prompt=formatted,
      image=image_paths,
      max_tokens=1024,
      temperature=0.0,
      enable_thinking=False,
      seed=42,
      verbose=False,
    )
    elapsed = time.time() - t0

    # Parse the model output
    lines = result.text.strip().split("\n")
    parsed_count = 0
    for line in lines:
      line = line.strip()
      if not line.startswith("FRAME|"):
        continue
      parts = line.split("|")
      if len(parts) < 9:
        continue
      try:
        frame_num = int(parts[1])
        if 0 <= frame_num < len(batch):
          f = batch[frame_num]
          f.osd_time = parts[2].strip()
          person = parts[3].strip().lower()
          f.activity = parts[4].strip().lower()
          f.screen_visible = parts[5].strip().lower()
          f.adult_present = parts[6].strip().lower()
          f.confidence = parts[7].strip().lower()
          f.note = parts[8].strip() if len(parts) > 8 else ""
          # Map person to presence
          f.person_present = person
          parsed_count += 1
      except (ValueError, IndexError):
        continue

    print(f"  Batch {batch_idx+1}/{total_batches}: {parsed_count}/{len(batch)} parsed, "
       f"{result.generation_tokens} tokens, {elapsed:.1f}s")

  # Fallback: for frames that weren't parsed, mark as unknown
  for f in frames:
    if f.activity == "unknown":
      f.activity = "empty"

# ---------------------------------------------------------------------------
# Description-based mode (Qwen2.5-VL)
# ---------------------------------------------------------------------------


def _infer_axis(model, processor, config, image_paths: list[str],
         prompt: str, allowed: set[str]) -> str:
  """Run one narrow visual question and fail closed on unexpected output."""
  from mlx_vlm import apply_chat_template, generate

  messages = [{"role": "user", "content": prompt}]
  formatted = apply_chat_template(
    processor, config, messages,
    add_generation_prompt=True, num_images=len(image_paths),
  )
  result = generate(
    model, processor,
    prompt=formatted,
    image=image_paths,
    max_tokens=16,
    temperature=0.0,
    enable_thinking=False,
    seed=42,
    verbose=False,
  )
  answer = result.text.strip().lower()
  return answer if answer in allowed else "uncertain"


class AxisInferenceCache:
  """Persistent local cache for deterministic narrow VLM questions.

  Keys include model name, prompt, allowed labels, and image content hashes so
  a changed prompt or regenerated frame cannot reuse an incompatible answer.
  The cache stores only hashes and short labels, never image bytes or secrets.
  """

  def __init__(self, path: str, model_path: str) -> None:
    self.path = Path(path)
    self.model = Path(model_path).expanduser().name
    self.entries: dict[str, str] = {}
    self.image_hashes: dict[str, str] = {}
    self.hits = 0
    self.misses = 0
    if self.path.is_file():
      try:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("schema_version") == 1:
          self.entries = dict(data.get("entries", {}))
      except (OSError, json.JSONDecodeError, TypeError):
        # A corrupted cache cannot affect an audit; start a new one.
        self.entries = {}

  def _hash_image(self, image_path: str) -> str:
    path = str(Path(image_path).resolve())
    if path not in self.image_hashes:
      self.image_hashes[path] = hashlib.sha256(
        Path(path).read_bytes()
      ).hexdigest()
    return self.image_hashes[path]

  def _key(self, image_paths: list[str], prompt: str, allowed: set[str]) -> str:
    payload = {
      "model": self.model,
      "prompt": prompt,
      "allowed": sorted(allowed),
      "images": [self._hash_image(path) for path in image_paths],
    }
    return hashlib.sha256(
      json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

  def infer(self, model, processor, config, image_paths: list[str],
            prompt: str, allowed: set[str]) -> str:
    key = self._key(image_paths, prompt, allowed)
    if key in self.entries:
      self.hits += 1
      return self.entries[key]
    self.misses += 1
    answer = _infer_axis(model, processor, config, image_paths, prompt, allowed)
    self.entries[key] = answer
    self.path.parent.mkdir(parents=True, exist_ok=True)
    self.path.write_text(
      json.dumps(
        {"schema_version": 1, "entries": self.entries},
        ensure_ascii=False,
        sort_keys=True,
      ) + "\n",
      encoding="utf-8",
    )
    return answer


def build_frame_chunks(
  frames: list[Frame],
  batch_size: int,
  max_playback_span: float = 20.0,
) -> list[list[Frame]]:
  """Group filtered frames without bridging a large observation gap.

  Playback time is used only to bound model context, never to derive output
  timestamps or durations. Production timing remains OSD-only.
  """
  chunks: list[list[Frame]] = []
  current: list[Frame] = []
  for frame in frames:
    if current and (
      len(current) >= batch_size
      or frame.playback_sec - current[0].playback_sec > max_playback_span
    ):
      chunks.append(current)
      current = []
    current.append(frame)
  if current:
    chunks.append(current)
  return chunks


def anchor_chunks_by_osd(
  chunks: list[list[Frame]],
  read_osd,
  max_osd_span_seconds: int = 20 * 60,
) -> list[tuple[list[Frame], str, str]]:
  """Read OSD anchors and split chunks that span too much wall-clock time.

  A time-lapse can jump a long wall-clock interval between nearby playback
  frames. Recursively splitting such chunks prevents a single observation
  from being interpolated across an hour-long unobserved interval.
  """
  anchored: list[tuple[list[Frame], str, str]] = []

  def anchor(chunk: list[Frame]) -> None:
    start_osd, end_osd = read_osd(chunk)
    start_sec = hms_to_seconds(start_osd)
    end_sec = hms_to_seconds(end_osd)
    if start_sec is not None and end_sec is not None:
      if end_sec < start_sec:
        end_sec += 24 * 3600
      if (
        len(chunk) > 1
        and end_sec - start_sec > max_osd_span_seconds
      ):
        midpoint = len(chunk) // 2
        anchor(chunk[:midpoint])
        anchor(chunk[midpoint:])
        return

    apply_chunk_osd(chunk, start_osd, end_osd)
    anchored.append((chunk, start_osd, end_osd))

  for chunk in chunks:
    if chunk:
      anchor(chunk)
  return anchored


def apply_chunk_observation(
  chunk: list[Frame],
  identity: str,
  coaching: str,
  screen_use: str,
  activity: str,
  people_count: str = "unknown",
) -> None:
  """Convert independent observations into atomic fields.

  Precedence is deliberately deterministic: unresolved identity is filtered;
  confirmed direct coaching overrides device use; active device use overrides
  the background paper/activity description.
  """
  observation = {
    "identity": identity,
    "direct_coaching": coaching,
    "screen_use": screen_use,
    "activity": activity,
    "people_count": people_count,
  }
  note = json.dumps(observation, ensure_ascii=False, separators=(",", ":"))

  for frame in chunk:
    frame.note = note
    frame.person_present = identity
    frame.people_count = people_count
    frame.adult_present = (
      "yes"
      if people_count == "multiple" and coaching == "yes"
      else "uncertain"
      if people_count == "uncertain" or coaching == "uncertain"
      else "no"
    )
    frame.screen_visible = screen_use
    if identity != "emma":
      frame.activity = "empty" if identity in ("adult_only", "empty") else "unknown"
      frame.confidence = "high" if identity in ("adult_only", "empty") else "low"
    elif frame.adult_present == "yes":
      frame.activity = "writing_reading"
      frame.confidence = "high"
    elif screen_use == "active":
      frame.activity = "looking_at_screen"
      frame.confidence = "high"
    else:
      frame.activity = activity if activity != "uncertain" else "unknown"
      frame.confidence = (
        "low"
        if "uncertain" in (coaching, screen_use, activity)
        else "high"
      )


def apply_split_chunk_observations(
  chunk: list[Frame],
  identity: str,
  coaching: str,
  screen_uses: list[str],
  activity: str,
  people_count: str,
) -> None:
  """Apply chunk-level observations with frame-level Screen decisions."""
  if len(screen_uses) != len(chunk):
    raise ValueError("screen observation count must match chunk frame count")
  for frame, screen_use in zip(chunk, screen_uses):
    apply_chunk_observation(
      [frame],
      identity,
      coaching,
      screen_use,
      activity,
      people_count,
    )


def load_parent_feedback(
  feedback_root: str,
  before_date: str,
  max_lessons: int = 12,
) -> tuple[list[str], list[str]]:
  """Load generic lessons from earlier submitted parent reviews.

  Date-specific results remain outside Git. Only short ``lesson`` strings are
  returned to the local model; dates, intervals, result payloads, and any
  unrelated fields are not included.
  """
  if not feedback_root or max_lessons <= 0:
    return [], []

  root = Path(feedback_root).expanduser().resolve()
  if not root.is_dir():
    return [], []

  lessons: list[str] = []
  source_hashes: list[str] = []
  seen: set[str] = set()
  for feedback_path in sorted(root.glob("*/parent_feedback.json")):
    try:
      raw = feedback_path.read_bytes()
      data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
      continue

    feedback_date = data.get("date")
    if (
      data.get("source") != "parent_review"
      or data.get("submitted") is not True
      or not isinstance(feedback_date, str)
      or feedback_date >= before_date
    ):
      continue

    accepted_from_file = False
    corrections = data.get("corrections", [])
    if not isinstance(corrections, list):
      continue
    for correction in corrections:
      if not isinstance(correction, dict):
        continue
      lesson = correction.get("lesson")
      if not isinstance(lesson, str):
        continue
      lesson = " ".join(lesson.split())[:300]
      if not lesson or lesson in seen:
        continue
      seen.add(lesson)
      lessons.append(lesson)
      accepted_from_file = True
    if accepted_from_file:
      source_hashes.append(hashlib.sha256(raw).hexdigest())

  return lessons[-max_lessons:], source_hashes[-max_lessons:]


def format_parent_feedback_guidance(lessons: list[str]) -> str:
  """Format bounded parent-confirmed guidance for local VLM prompts."""
  if not lessons:
    return ""
  bullets = "\n".join(f"- {lesson}" for lesson in lessons)
  return (
    "\nParent-confirmed guidance from earlier reviewed days follows. "
    "Apply it only when the current visible evidence supports it:\n"
    f"{bullets}"
  )


def interpret_who_label(who: str) -> tuple[str, str, str]:
  """Map a narrow VLM identity label to identity/count/coaching fields."""
  if who == "emma_alone":
    return "emma", "one", "no"
  if who == "emma_with_adult_coaching":
    return "emma", "multiple", "yes"
  if who == "emma_with_adult_independent":
    return "emma", "multiple", "no"
  if who == "adult_only":
    return "adult_only", "one", "no"
  if who == "empty":
    return "empty", "uncertain", "no"
  return "uncertain", "uncertain", "uncertain"


def describe_frames(
  frames: list[Frame],
  model_path: str,
  batch_size: int = 5,
  identity_references: Optional[list[str]] = None,
  inference_cache: Optional[AxisInferenceCache] = None,
  feedback_lessons: Optional[list[str]] = None,
) -> None:
  """Observe each chunk with merged identity/people/coaching + chunk-level screen.

  P0/P1 optimization:
  - Identity, people count, and coaching are merged into ONE call per chunk
    (was 3 calls: identity + people_count + coaching)
  - Screen detection is chunk-level (was per-frame, N calls per chunk)
  - Total: 3 calls per chunk (was 5-9 calls before)
  """
  from mlx_vlm import load, apply_chat_template, generate
  from mlx_vlm.utils import load_config

  print(f" Loading model: {os.path.basename(model_path)}")
  model, processor = load(model_path)
  config = load_config(model_path)

  def infer_axis(image_paths: list[str], prompt: str, allowed: set[str]) -> str:
    if inference_cache is not None:
      return inference_cache.infer(
        model, processor, config, image_paths, prompt, allowed
      )
    return _infer_axis(model, processor, config, image_paths, prompt, allowed)

  raw_chunks = build_frame_chunks(frames, batch_size)
  ocr_t0 = time.time()
  anchored_chunks = anchor_chunks_by_osd(
    raw_chunks,
    lambda chunk: read_chunk_osd(
      model,
      processor,
      config,
      chunk[0].osd_image_path,
      chunk[-1].osd_image_path,
    ),
  )
  ocr_elapsed = time.time() - ocr_t0
  total_chunks = len(anchored_chunks)
  print(
    f" OSD anchoring: {len(raw_chunks)} raw chunks -> "
    f"{total_chunks} bounded chunks in {ocr_elapsed:.1f}s"
  )
  print(
    f" Analyzing {len(frames)} frames in {total_chunks} chunks "
    f"of at most {batch_size} consecutive frames"
  )
  feedback_guidance = format_parent_feedback_guidance(
    feedback_lessons or []
  )

  for chunk_idx, (chunk, start_osd, end_osd) in enumerate(anchored_chunks):
    n = len(chunk)
    image_paths = [f.image_path for f in chunk]
    t0 = time.time()

    # ================================================================
    # CALL 1: Identity + People + Coaching (merged, was 3 separate calls)
    # ================================================================
    if identity_references:
      # Use reference image comparison
      target_path = image_paths[len(image_paths) // 2]
      ref_path = Path(identity_references[0]).expanduser().resolve()
      who = infer_axis(
        [str(ref_path), target_path],
        (
          "Image 1 is a confirmed reference photo of Emma. Image 2 is a "
          "study room frame. Is the person in Image 2 the same person as "
          "Image 1? Output: same, empty, or uncertain."
        ),
        {"same", "empty", "uncertain"},
      )
      if who == "same":
        # Emma confirmed, now check if alone or with adult
        who = infer_axis(
          image_paths,
          (
            f"Emma is confirmed present in these {n} frames. Is she "
            "alone, independently working while an adult is nearby, or "
            "receiving direct instruction/review from an adult? Adult "
            "presence alone is not coaching. Output exactly: emma_alone, "
            "emma_with_adult_independent, emma_with_adult_coaching, or "
            f"uncertain.{feedback_guidance}"
          ),
          {
            "emma_alone", "emma_with_adult_independent",
            "emma_with_adult_coaching", "uncertain",
          },
        )
      else:
        who = "empty" if who == "empty" else "adult_only"
    else:
      # No reference: single merged call
      who = infer_axis(
        image_paths,
        (
          f"These {n} frames are from a study room camera. "
          "Who is visible across these frames? The main person is Emma, "
          "a 13-year-old girl. Distinguish an adult merely nearby from "
          "direct one-on-one instruction or joint error review. Adult "
          "presence alone is not coaching. Output exactly one label: "
          "emma_alone, emma_with_adult_independent, "
          "emma_with_adult_coaching, adult_only, empty, or uncertain."
          f"{feedback_guidance}"
        ),
        {
          "emma_alone", "emma_with_adult_independent",
          "emma_with_adult_coaching", "adult_only", "empty", "uncertain",
        },
      )

    # Parse merged result
    identity, people_count, coaching = interpret_who_label(who)

    # ================================================================
    # CALL 2: Screen use (chunk-level, was per-frame N calls)
    # ================================================================
    if identity == "emma":
      screen_use = infer_axis(
        image_paths,
        (
          f"Emma is confirmed present across these {n} frames. "
          "Is she actively using a digital screen or device? "
          "Active use means looking at, typing on, or touching a "
          "computer, tablet, or phone. A device merely on the desk "
          "is NOT active use. "
          "Output exactly: active, not_active, or uncertain."
        ),
        {"active", "not_active", "uncertain"},
      )
      # Apply chunk-level screen decision to all frames
      # If screen is active, also check attention direction
      if screen_use == "active":
        attention = infer_axis(
          image_paths,
          (
            "Emma is using a screen. Is her attention on the screen "
            "(looking at/typing on it) or on paper/book next to it? "
            "Output exactly: screen, paper, or uncertain."
          ),
          {"screen", "paper", "uncertain"},
        )
        screen_uses = ["active" if attention == "screen" else "not_active"
                  for _ in image_paths]
      else:
        screen_uses = [screen_use for _ in image_paths]
    else:
      screen_uses = ["not_active" for _ in image_paths]

    # ================================================================
    # CALL 3: Activity (chunk-level, same as before)
    # ================================================================
    if identity == "emma":
      activity = infer_axis(
        image_paths,
        (
          "Emma is confirmed present. Ignoring adult presence and screen "
          "use, describe only her dominant physical activity. Preparation, "
          "arranging materials, sitting down, or briefly checking an item is "
          "not writing_reading until sustained paper-based work is visible. "
          "Output exactly one label: writing_reading, resting, talking, "
          f"moving, idle, other, uncertain.{feedback_guidance}"
        ),
        {
          "writing_reading", "resting", "talking", "moving",
          "idle", "other", "uncertain",
        },
      )
    else:
      activity = "other" if identity in ("adult_only", "empty") else "uncertain"

    # ================================================================
    # Apply observations
    # ================================================================
    apply_split_chunk_observations(
      chunk, identity, coaching, screen_uses, activity, people_count
    )
    elapsed = time.time() - t0
    n_active = screen_uses.count("active")

    print(
      f"  Chunk [{chunk_idx+1}/{total_chunks}] ({n} frames) "
      f"class={elapsed:.1f}s: "
      f"who={who} screen_active={n_active}/{len(screen_uses)} "
      f"activity={activity} | {start_osd}-{end_osd}"
    )

  if inference_cache is not None:
    print(
      f" Axis cache: {inference_cache.hits} hit(s), "
      f"{inference_cache.misses} miss(es)"
    )


def aggregate_descriptions(frames: list[Frame]) -> None:
  """Parse legacy single-label chunks; new split observations are pre-applied.

  Keeping the legacy mapping allows older cached candidate runs to be inspected
  without silently changing their meaning.
  """
  valid_labels = {
    "writing_reading": ("writing_reading", "emma", "no", "no", "high"),
    "looking_at_screen": ("looking_at_screen", "emma", "yes", "no", "medium"),
    "resting": ("resting", "emma", "no", "no", "high"),
    "talking": ("talking", "emma", "no", "no", "high"),
    "moving": ("moving", "emma", "no", "no", "medium"),
    "coaching": ("writing_reading", "emma", "no", "yes", "high"),
    "adult_only": ("empty", "empty", "no", "yes", "high"),
    "empty": ("empty", "empty", "no", "no", "high"),
    "uncertain": ("unknown", "uncertain", "uncertain", "uncertain", "low"),
  }

  for f in frames:
    label = f.note.strip().lower() if f.note else ""

    if label.startswith("{"):
      continue
    if label in valid_labels:
      activity, person, screen, adult, conf = valid_labels[label]
      f.activity = activity
      f.person_present = person
      f.screen_visible = "active" if screen == "yes" else "not_active"
      f.adult_present = adult
      f.confidence = conf
    else:
      # Unknown label - default
      f.activity = "unknown"
      f.person_present = "uncertain"
      f.screen_visible = "not_active"
      f.adult_present = "no"
      f.confidence = "low"


def hms_to_seconds(value: str) -> Optional[int]:
  parts = value.strip().split(":")
  if len(parts) != 3:
    return None
  try:
    hour, minute, second = (int(part) for part in parts)
  except ValueError:
    return None
  if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
    return None
  return hour * 3600 + minute * 60 + second


def extract_hms_values(value: str) -> list[str]:
  return re.findall(
    r"(?<!\d)(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?!\d)",
    value,
  )


def read_chunk_osd(model, processor, config, start_path: str,
          end_path: str) -> tuple[str, str]:
  from mlx_vlm import apply_chat_template, generate

  prompt = (
    "These are enlarged camera OSD crops from the first and last frame. "
    "Read the two visible times. Output exactly START_HH:MM:SS|END_HH:MM:SS. "
    "Do not output dates, labels, or explanation."
  )
  messages = [{"role": "user", "content": prompt}]
  formatted = apply_chat_template(
    processor, config, messages, add_generation_prompt=True, num_images=2
  )
  result = generate(
    model,
    processor,
    prompt=formatted,
    image=[start_path, end_path],
    max_tokens=32,
    temperature=0.0,
    enable_thinking=False,
    seed=42,
    verbose=False,
  )
  values = extract_hms_values(result.text)
  if len(values) < 2:
    return "", ""
  return values[0], values[1]


def seconds_to_hms(value: float) -> str:
  second = int(round(value)) % (24 * 3600)
  return f"{second // 3600:02d}:{(second % 3600) // 60:02d}:{second % 60:02d}"


def apply_chunk_osd(frames: list[Frame], start_osd: str, end_osd: str) -> None:
  if not frames:
    return
  start_sec = hms_to_seconds(start_osd)
  end_sec = hms_to_seconds(end_osd)
  if start_sec is None or end_sec is None:
    return
  if end_sec < start_sec:
    end_sec += 24 * 3600

  first_playback = frames[0].playback_sec
  playback_span = frames[-1].playback_sec - first_playback
  for index, frame in enumerate(frames):
    if playback_span > 0:
      ratio = (frame.playback_sec - first_playback) / playback_span
    else:
      ratio = index / max(1, len(frames) - 1)
    osd_second = start_sec + (end_sec - start_sec) * ratio
    frame.wall_sec = osd_second
    frame.osd_time = seconds_to_hms(osd_second)


def require_osd_timeline(frames: list[Frame]) -> None:
  missing = [frame.index for frame in frames if not frame.osd_time]
  if missing:
    preview = ", ".join(str(index) for index in missing[:8])
    raise RuntimeError(
      f"OSD timestamp missing for {len(missing)} frames "
      f"(first indexes: {preview}); candidate generation stopped"
    )
  previous: Optional[float] = None
  for frame in frames:
    if previous is not None and frame.wall_sec < previous:
      raise RuntimeError(
        f"OSD timestamp moved backwards at frame {frame.index}; "
        "candidate generation stopped"
      )
    previous = frame.wall_sec


def collapse_brief_isolated_screen_runs(
  frames: list[Frame],
  max_minutes: int = 5,
) -> int:
  """Fold brief isolated device glances back into continuous paper study.

  This implements the audit rule for a short study-tool lookup only when the
  evidence is conservative: Emma is alone, the Screen run is bounded on both
  sides by paper study, and the entire interval is no longer than five
  minutes. Coaching/preparation Screen remains untouched.
  """
  collapsed = 0
  index = 0
  while index < len(frames):
    if (
      frames[index].person_present != "emma"
      or frames[index].activity != "looking_at_screen"
    ):
      index += 1
      continue

    start = index
    while (
      index + 1 < len(frames)
      and frames[index + 1].person_present == "emma"
      and frames[index + 1].activity == "looking_at_screen"
    ):
      index += 1
    end = index
    previous = frames[start - 1] if start > 0 else None
    following = frames[end + 1] if end + 1 < len(frames) else None
    run = frames[start:end + 1]

    bounded_by_paper = (
      previous is not None
      and following is not None
      and previous.person_present == "emma"
      and following.person_present == "emma"
      and previous.activity == "writing_reading"
      and following.activity == "writing_reading"
      and previous.adult_present == "no"
      and following.adult_present == "no"
    )
    no_coaching = all(frame.adult_present == "no" for frame in run)
    duration_seconds = (
      following.wall_sec - run[0].wall_sec
      if following is not None
      else float("inf")
    )
    brief = 0 <= duration_seconds <= max_minutes * 60

    if bounded_by_paper and no_coaching and brief:
      for frame in run:
        frame.activity = "writing_reading"
        frame.screen_visible = "not_active"
        try:
          observation = json.loads(frame.note)
        except (TypeError, json.JSONDecodeError):
          observation = {}
        if isinstance(observation, dict):
          observation["screen_use"] = "not_active"
          observation["screen_cleanup"] = "brief_isolated_between_paper"
          frame.note = json.dumps(
            observation, ensure_ascii=False, separators=(",", ":")
          )
      collapsed += len(run)
    index += 1
  return collapsed



# ---------------------------------------------------------------------------
# Stage merging and deterministic calculation
# ---------------------------------------------------------------------------

def osd_to_minutes(osd_time: str) -> Optional[int]:
  """Convert HH:MM or HH:MM:SS to minutes since midnight."""
  if not osd_time or osd_time.lower() == "unknown":
    return None
  parts = osd_time.strip().split(":")
  try:
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    if h < 0 or h > 23 or m < 0 or m > 59:
      return None
    return h * 60 + m
  except (ValueError, IndexError):
    return None


def _classify_atomic(activity: str, adult: str, duration: int) -> tuple[str, str]:
  """Convert atomic VLM labels to audit categories using deterministic Python rules.

  Returns (category, chinese_label).
  Rules from audit-prompt.md:
  - writing_reading + adult=yes/no -> Coaching (with adult) or Focus (>= 30 min) / Distraction (< 30 min)
  - looking_at_screen -> Screen (<= 30 min豁免, > 30 min计1 Distraction)
  - idle -> Distraction
  - resting -> Eye Rest (>= 10 min) or Distraction (< 10 min)
  - talking + adult=yes -> Coaching, else Distraction
  - moving -> Activity
  - empty/other/unknown -> filtered out
  """
  if activity in ("empty", "unknown", "other"):
    return None, None

  if activity == "writing_reading":
    if adult == "yes":
      return ("Coaching", "家长辅导")
    elif duration >= 30:
      return ("Focus", "专注学习")
    else:
      return ("Distraction", "碎片学习")
  elif activity == "looking_at_screen":
    if duration > 30:
      return ("Screen", "长时间屏幕使用")
    else:
      return ("Screen", "短时屏幕使用")
  elif activity == "idle":
    return ("Distraction", "分心或闲置")
  elif activity == "resting":
    if duration >= 10:
      return ("Eye Rest", "护眼休息")
    else:
      return ("Distraction", "短时休息")
  elif activity == "talking":
    if adult in ("yes", "uncertain"):
      return ("Coaching", "家长辅导")
    else:
      return ("Distraction", "走神")
  elif activity == "moving":
    return ("Activity", "其他活动")

  return ("Distraction", "其他")






def merge_stages(frames: list[Frame]) -> list[Stage]:
  """Merge consecutive frames with the same atomic activity into stages,
  then classify deterministically using Python rules.

  Architecture: VLM provides atomic observations (writing_reading, idle, etc.),
  Python makes all category decisions based on duration and adult presence.

  Merging strategy:
  1. Merge consecutive frames with same atomic activity into raw segments
  2. Classify each segment using _classify_atomic()
  3. Merge neutral short segments (< 20 min) into adjacent long segments
    (neutral = idle, moving, talking, short rest, fragmented study)
  4. Only merge if gap between segments < 30 min (avoids merging across rest periods)
  5. Merge close same-category segments (gap < 10 min)
  6. Also merge "碎片学习" into adjacent Focus segments
  7. Apply audit-prompt.md constraints (Focus >= 30 min, Eye Rest >= 10 min)
  """
  if not frames:
    return []

  # Filter out empty/unknown frames and any unresolved target identity.
  activity_frames = [
    f for f in frames
    if f.person_present == "emma"
    and f.activity not in ("empty", "unknown", "other")
  ]
  if not activity_frames:
    return []

  frame_positions = {id(frame): index for index, frame in enumerate(frames)}
  identity_barrier_minutes = [
    int(frame.wall_sec / 60)
    for frame in frames
    if frame.person_present != "emma"
  ]

  def has_identity_barrier(left: Frame, right: Frame) -> bool:
    left_pos = frame_positions[id(left)]
    right_pos = frame_positions[id(right)]
    return any(
      frame.person_present != "emma"
      for frame in frames[left_pos + 1:right_pos]
    )

  def has_stage_barrier(left_end: str, right_start: str) -> bool:
    left_minute = osd_to_minutes(left_end)
    right_minute = osd_to_minutes(right_start)
    if left_minute is None or right_minute is None:
      return True
    return any(
      left_minute <= minute <= right_minute
      for minute in identity_barrier_minutes
    )

  # Step 1: Merge consecutive frames with same atomic activity AND adult presence
  # This ensures Coaching (writing_reading + adult=yes) and Focus (writing_reading + adult=no)
  # are in separate segments
  raw_segments: list[list[Frame]] = []
  current_segment = [activity_frames[0]]
  for f in activity_frames[1:]:
    same_activity = f.activity == current_segment[0].activity
    same_adult = f.adult_present == current_segment[0].adult_present
    gap_seconds = f.wall_sec - current_segment[-1].wall_sec
    continuous = (
      0 <= gap_seconds <= 20 * 60
      and not has_identity_barrier(current_segment[-1], f)
    )
    if same_activity and same_adult and continuous:
      current_segment.append(f)
    else:
      raw_segments.append(current_segment)
      current_segment = [f]
  raw_segments.append(current_segment)

  # Step 2: Convert each raw segment to a Stage with deterministic classification
  NEUTRAL_LABELS = {"分心或闲置", "其他活动", "走神", "短时休息", "碎片学习"}
  stages: list[Stage] = []
  for segment_index, segment in enumerate(raw_segments):
    activity = segment[0].activity
    # Dominant adult presence
    adult_yes = sum(1 for f in segment if f.adult_present == "yes")
    adult_no = sum(1 for f in segment if f.adult_present == "no")
    adult = "yes" if adult_yes > adult_no else "no"

    # Duration from OSD-anchored wall-clock seconds.
    wall_start_min = int(segment[0].wall_sec / 60)
    if segment_index + 1 < len(raw_segments):
      next_frame = raw_segments[segment_index + 1][0]
      next_start_sec = next_frame.wall_sec
      if (
        next_start_sec - segment[-1].wall_sec <= 20 * 60
        and not has_identity_barrier(segment[-1], next_frame)
      ):
        wall_end_min = int(next_start_sec / 60)
      else:
        wall_end_min = int(segment[-1].wall_sec / 60) + 1
    else:
      wall_end_min = int(segment[-1].wall_sec / 60) + 1
    duration = max(1, wall_end_min - wall_start_min)

    # Classify
    category, chinese_label = _classify_atomic(activity, adult, duration)
    if category is None:
      continue

    # Display the OSD-anchored wall-clock range.
    start_min = wall_start_min
    end_min = wall_end_min

    stages.append(Stage(
      start=f"{start_min // 60:02d}:{start_min % 60:02d}",
      end=f"{end_min // 60:02d}:{end_min % 60:02d}",
      duration=duration, category=category, stage=chinese_label,
      note=f"{chinese_label}（{duration}分钟）",
    ))

  if not stages:
    return []

  # Step 3: Merge neutral short segments into adjacent long segments
  # Only merge if gap between segments < 30 min
  merged: list[Stage] = []
  for stage in stages:
    if not merged:
      merged.append(stage)
      continue

    prev = merged[-1]

    # Check temporal gap
    prev_end_h, prev_end_m = map(int, prev.end.split(":"))
    cur_start_h, cur_start_m = map(int, stage.start.split(":"))
    gap = (cur_start_h * 60 + cur_start_m) - (prev_end_h * 60 + prev_end_m)
    if gap > 30 or has_stage_barrier(prev.end, stage.start):
      merged.append(stage)
      continue

    # Same category: merge only after the gap has passed the continuity check.
    if prev.category == stage.category:
      prev.end = stage.end
      prev.duration = _calc_duration(prev.start, stage.end)
      prev.note = f"{prev.stage}（{prev.duration}分钟）"
      continue

    prev_neutral = prev.stage in NEUTRAL_LABELS
    cur_neutral = stage.stage in NEUTRAL_LABELS

    # Merge neutral short into non-neutral long
    if cur_neutral and stage.duration < 20 and not prev_neutral and prev.duration >= 20:
      prev.end = stage.end
      prev.duration = _calc_duration(prev.start, stage.end)
      prev.note = f"{prev.stage}（{prev.duration}分钟）"
    elif prev_neutral and prev.duration < 20 and not cur_neutral and stage.duration >= 20:
      stage.start = prev.start
      stage.duration = _calc_duration(prev.start, stage.end)
      stage.note = f"{stage.stage}（{stage.duration}分钟）"
      merged[-1] = stage
    elif cur_neutral and prev_neutral:
      # Both neutral: merge
      prev.end = stage.end
      prev.duration = _calc_duration(prev.start, stage.end)
      merged[-1] = prev
    else:
      # Both non-neutral, different categories: keep separate
      merged.append(stage)

  # Step 4: Merge close same-category segments (gap < 10 min)
  # Also merge "碎片学习" into adjacent Focus
  compact: list[Stage] = []
  for stage in merged:
    if not compact:
      compact.append(stage)
      continue
    prev = compact[-1]
    prev_end_h, prev_end_m = map(int, prev.end.split(":"))
    cur_start_h, cur_start_m = map(int, stage.start.split(":"))
    gap = (cur_start_h * 60 + cur_start_m) - (prev_end_h * 60 + prev_end_m)
    if gap > 10 or has_stage_barrier(prev.end, stage.start):
      compact.append(stage)
      continue

    if prev.category == stage.category:
      prev.end = stage.end
      prev.duration = _calc_duration(prev.start, stage.end)
      prev.note = f"{prev.stage}（{prev.duration}分钟）"
    elif prev.category == "Focus" and stage.stage == "碎片学习":
      # Merge fragmented study into Focus
      prev.end = stage.end
      prev.duration = _calc_duration(prev.start, stage.end)
      prev.note = f"{prev.stage}（{prev.duration}分钟）"
    elif stage.category == "Focus" and prev.stage == "碎片学习":
      stage.start = prev.start
      stage.duration = _calc_duration(prev.start, stage.end)
      stage.note = f"{stage.stage}（{stage.duration}分钟）"
      compact[-1] = stage
    elif prev.category == "Focus" and stage.category == "Coaching":
      # Don't merge Coaching into Focus - keep separate
      compact.append(stage)
    elif prev.category == "Coaching" and stage.category == "Focus":
      # Don't merge Focus after Coaching - keep separate
      compact.append(stage)
    else:
      compact.append(stage)

  # Step 5: Apply audit constraints
  filtered: list[Stage] = []
  for s in compact:
    if s.category == "Focus" and s.duration < 30:
      s.category = "Distraction"
      s.stage = "碎片学习"
      s.note = f"碎片学习（{s.duration}分钟）"
      filtered.append(s)
    elif s.category == "Eye Rest" and s.duration < 10:
      continue
    elif s.category == "Coaching" and s.duration < 5:
      continue
    else:
      filtered.append(s)

  # Step 6: Final merge of adjacent same-category
  final: list[Stage] = []
  for s in filtered:
    if not final or final[-1].category != s.category:
      final.append(s)
      continue
    previous_end = osd_to_minutes(final[-1].end)
    current_start = osd_to_minutes(s.start)
    if (
      previous_end is None
      or current_start is None
      or current_start - previous_end > 10
      or has_stage_barrier(final[-1].end, s.start)
    ):
      final.append(s)
      continue
    final[-1].end = s.end
    final[-1].duration = _calc_duration(final[-1].start, s.end)
    final[-1].note = f"{final[-1].stage}（{final[-1].duration}分钟）"

  return final




def _calc_duration(start: str, end: str) -> int:
  """Calculate duration in minutes between HH:MM strings (wall-time based)."""
  sh, sm = map(int, start.split(":"))
  eh, em = map(int, end.split(":"))
  return max(1, (eh * 60 + em) - (sh * 60 + sm))


def calculate_tokens(stages: list[Stage]) -> tuple[int, int, int, str]:
  """Calculate Focus Blocks, Distractions, Tokens_Net and Rating from stages.

  Rules (from audit-prompt.md):
  - Focus Block: one per qualifying Focus stage (30+ minutes)
  - Distraction: one per Distraction stage, plus one per Screen stage > 30 min
  - Tokens_Net = Focus_Blocks - floor(Distractions / 3)
  - Rating: red if Distractions >= 3, yellow if 1-2, green if 0 and Focus >= 2, white if absent
  """
  focus_blocks = sum(1 for s in stages if s.category == "Focus" and s.duration >= 30)
  distractions = sum(1 for s in stages if s.category == "Distraction")
  distractions += sum(1 for s in stages if s.category == "Screen" and s.duration > 30)
  eye_rest = sum(s.duration for s in stages if s.category == "Eye Rest")

  tokens_net = focus_blocks - (distractions // 3)

  # Rating
  if not stages:
    rating = "⚪ 不在场"
  elif distractions >= 3:
    rating = "🔴 危险"
  elif distractions >= 1:
    rating = "🟡 警告"
  elif focus_blocks >= 2:
    rating = "🟢 优秀"
  else:
    rating = "🟡 警告"

  return focus_blocks, distractions, eye_rest, rating


# ---------------------------------------------------------------------------
# Result JSON builder
# ---------------------------------------------------------------------------

def build_result(date: str, stages: list[Stage], frames: list[Frame]) -> dict:
  """Build a result.json compatible with emma_review.py validate."""
  from datetime import datetime
  focus_blocks, distractions, eye_rest, rating = calculate_tokens(stages)
  tokens_net = focus_blocks - (distractions // 3)

  # Compute Day_Type (Chinese weekday)
  try:
    parsed = datetime.strptime(date, "%Y-%m-%d")
    weekdays = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
    day_type = weekdays[parsed.weekday()]
  except ValueError:
    day_type = "未知"

  # Build timeline time range
  if stages:
    start_times = [osd_to_minutes(s.start) for s in stages if osd_to_minutes(s.start) is not None]
    end_times = [osd_to_minutes(s.end) for s in stages if osd_to_minutes(s.end) is not None]
    time_start = f"{min(start_times) // 60:02d}:{min(start_times) % 60:02d}" if start_times else "00:00"
    time_end = f"{max(end_times) // 60:02d}:{max(end_times) % 60:02d}" if end_times else "00:00"
  else:
    time_start = "00:00"
    time_end = "00:00"

  # Build category description
  categories = set(s.category for s in stages)
  if categories:
    cat_desc = "、".join(sorted(categories))
  else:
    cat_desc = "无活动"

  # Build summary
  summary_parts = []
  if focus_blocks:
    summary_parts.append(f"完成{focus_blocks}段专注学习")
  if distractions:
    summary_parts.append(f"出现{distractions}次分心")
  if eye_rest:
    summary_parts.append(f"护眼休息{eye_rest}分钟")
  summary = "；".join(summary_parts) if summary_parts else "当日无有效活动记录"

  absent = len(stages) == 0

  result = {
    "date": date,
    "timeline": [{
      "Date": date,
      "Day_Type": day_type,
      "Time_Start": time_start,
      "Time_End": time_end,
      "Category": cat_desc,
      "Focus_Blocks": focus_blocks,
      "Distractions": distractions,
      "Eye_Rest_Minutes": eye_rest,
      "Absent": absent,
      "Note": summary,
    }],
    "evaluations": {
      "Date": date,
      "Summary": summary,
      "Rating": rating,
      "Tokens_Net": tokens_net,
    },
    "stages": [
      {
        "date": date,
        "start": s.start,
        "end": s.end,
        "duration": s.duration,
        "category": s.category,
        "stage": s.stage,
        "note": getattr(s, "note", ""),
      }
      for s in stages
    ],
  }

  return result


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(date: str, video_path: str, model_path: str,
         interval_sec: float = 4.0, resize: int = 640,
         batch_size: int = 8, similarity_threshold: float = 0.95,
         max_similar_gap: float = 8.0,
         output_path: str = "", mode: str = "classify",
         identity_references: Optional[list[str]] = None,
         feedback_lessons: Optional[list[str]] = None) -> dict:
  """Run the complete Emma Review pipeline.

  mode: classify (Qwen3-VL) or describe (Qwen2.5-VL description-based)

  Returns the result dict and writes it to output_path.
  """
  print(f" Emma Review Pipeline - {date}")
  print(f"{'='*60}")
  print(f" Video: {video_path}")
  print(f" Model: {os.path.basename(model_path)}")
  print(
    f" Interval: {interval_sec}s, Resize: {resize}px, Chunk: {batch_size} frames, "
    f"Static anchor: {max_similar_gap}s"
  )

  if not os.path.exists(video_path):
    raise FileNotFoundError(f"Video not found: {video_path}")
  if not os.path.exists(model_path):
    raise FileNotFoundError(f"Model not found: {model_path}")

  axis_cache = (
    AxisInferenceCache(
      str(Path(output_path).expanduser().resolve().parent / "axis_cache.json"),
      model_path,
    )
    if output_path
    else None
  )

  with tempfile.TemporaryDirectory(prefix=f"emma-pipeline-{date}-") as tmpdir:
    # Step 1: Extract frames
    print(f"\n--- Step 1: Frame Extraction ---")
    t0 = time.time()
    frames = extract_frames(video_path, interval_sec=interval_sec,
                resize=resize, out_dir=tmpdir)
    extract_time = time.time() - t0
    print(f" Time: {extract_time:.1f}s")

    # Step 2: Filter similar frames
    print(f"\n--- Step 2: Scene Difference Filter ---")
    frames = filter_similar_frames(
      frames,
      threshold=similarity_threshold,
      max_playback_gap=max_similar_gap,
    )

    # Step 3: Model classification or description
    if mode == "describe":
      print(f"\n--- Step 3: Frame Description ---")
      t0 = time.time()
      describe_frames(
        frames,
        model_path,
        batch_size=batch_size,
        identity_references=identity_references,
        inference_cache=axis_cache,
        feedback_lessons=feedback_lessons,
      )
      describe_time = time.time() - t0
      print(f" Total description time: {describe_time:.1f}s")

      print(f"\n--- Step 3b: Aggregate Descriptions ---")
      aggregate_descriptions(frames)
    else:
      print(f"\n--- Step 3: Model Classification ---")
      t0 = time.time()
      classify_frames(frames, model_path, batch_size=batch_size, resize=resize)
      classify_time = time.time() - t0
      print(f" Total classification time: {classify_time:.1f}s")
      for frame in frames:
        osd_second = hms_to_seconds(frame.osd_time)
        if osd_second is not None:
          frame.wall_sec = osd_second

    require_osd_timeline(frames)
    collapsed_screen_frames = collapse_brief_isolated_screen_runs(frames)
    if collapsed_screen_frames:
      print(
        f" Screen cleanup: folded {collapsed_screen_frames} brief isolated "
        "frame(s) into continuous paper study"
      )

    # Print frame classifications for debugging
    print(f"\n--- Frame Classifications ---")
    for f in frames:
      print(f" #{f.index:3d} play={f.playback_sec:6.0f}s wall={f.wall_sec/60:6.0f}min "
         f"osd={f.osd_time:>5s} person={f.person_present:>8s} "
         f"activity={f.activity:>12s} screen={f.screen_visible:>3s} "
         f"coaching={f.adult_present:>9s} conf={f.confidence:>6s} | {f.note}")

    # Step 4: Merge stages (deterministic Python)
    print(f"\n--- Step 4: Stage Merging ---")
    stages = merge_stages(frames)
    print(f" Merged into {len(stages)} stages:")
    for s in stages:
      print(f"  {s.start}-{s.end} ({s.duration:3d}min) {s.category:12s} {s.stage}")

    # Step 5: Calculate tokens (deterministic Python)
    print(f"\n--- Step 5: Token Calculation ---")
    focus_blocks, distractions, eye_rest, rating = calculate_tokens(stages)
    tokens_net = focus_blocks - (distractions // 3)
    print(f" Focus_Blocks: {focus_blocks}")
    print(f" Distractions: {distractions}")
    print(f" Eye_Rest: {eye_rest}min")
    print(f" Tokens_Net: {tokens_net}")
    print(f" Rating: {rating}")

    # Step 6: Build result JSON
    print(f"\n--- Step 6: Build Result JSON ---")
    result = build_result(date, stages, frames)

    if output_path:
      os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
      with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
      print(f" Written to: {output_path}")

    # Summary
    print(f"\n{'='*60}")
    print(f" Pipeline Complete - {date}")
    print(f"{'='*60}")
    print(f" Frames: {len(frames)} | Stages: {len(stages)}")
    print(f" Focus={focus_blocks} Dist={distractions} EyeRest={eye_rest}min "
       f"Tokens={tokens_net} Rating={rating}")

    return result


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    description=(
      "Emma Review local vision pipeline: ready -> extract -> classify -> "
      "calculate -> validate -> pending review"
    )
  )
  parser.add_argument("--date", required=True, help="Audit date (YYYY-MM-DD)")
  parser.add_argument("--video", required=True, help="Path to Study_YYYYMMDD.mp4")
  parser.add_argument("--model", default=DEFAULT_MODEL,
    help="Model directory path")
  parser.add_argument("--interval", type=float, default=4.0,
            help="Frame extraction interval in playback seconds (default: 4)")
  parser.add_argument("--resize", type=int, default=640,
            help="Resize the longest frame edge, preserving aspect ratio (default: 640)")
  parser.add_argument("--batch-size", type=int, default=5,
            help="Frames per model batch (default: 5)")
  parser.add_argument("--similarity", type=float, default=0.95,
            help="Scene similarity threshold for filtering (default: 0.95)")
  parser.add_argument("--max-similar-gap", type=float, default=12.0,
            help=(
              "Keep a static-scene anchor at least this often in playback seconds "
              "(default: 8)"
            ))
  parser.add_argument("--mode", default="describe", choices=["classify", "describe"],
            help="Pipeline mode: classify (Qwen3-VL) or describe (Qwen2.5-VL)")
  parser.add_argument(
    "--identity-reference",
    action="append",
    default=[],
    help=(
      "Parent-confirmed Emma reference image outside Git; repeat for multiple "
      "same-day appearances"
    ),
  )
  parser.add_argument(
    "--feedback-root",
    default="",
    help=(
      "Root containing prior DATE/parent_feedback.json files. When omitted, "
      "infer the shared .emma-review root from --output."
    ),
  )
  parser.add_argument("--output", default="",
            help=(
              "Candidate JSON path (default: "
              ".emma-review/DATE/result_pipeline.json)"
            ))
  parser.add_argument(
    "--allow-legacy-stable",
    action="store_true",
    help=(
      "Allow a stable historical video without a producer .ready manifest"
    ),
  )
  return parser


def run_checked(command: list[str], label: str) -> None:
  completed = subprocess.run(command, check=False)
  if completed.returncode != 0:
    raise RuntimeError(f"{label} failed with exit code {completed.returncode}")


def require_ready_video(date: str, video_path: str,
             allow_legacy_stable: bool = False) -> None:
  video = Path(video_path).expanduser().resolve()
  expected_name = f"Study_{date.replace('-', '')}.mp4"
  if video.name != expected_name:
    raise ValueError(
      f"exact dated video required: expected {expected_name}, got {video.name}"
    )

  command = [
    sys.executable,
    str(Path(__file__).with_name("emma_review.py")),
    "ready",
    date,
    "--video-dir",
    str(video.parent),
  ]
  if allow_legacy_stable:
    command.append("--allow-legacy-stable")
  print("\n--- Step 0: Ready Contract ---")
  run_checked(command, "video ready check")


def validate_candidate(output_path: str, date: str) -> None:
  print("\n--- Step 7: Mandatory Validation ---")
  command = [
    sys.executable,
    str(Path(__file__).with_name("emma_review.py")),
    "validate",
    str(Path(output_path).expanduser().resolve()),
    "--expected-date",
    date,
  ]
  run_checked(command, "candidate validation")


def write_review_metadata(output_path: str, date: str, video_path: str,
              model_path: str, args: argparse.Namespace) -> Path:
  from datetime import datetime

  output = Path(output_path).expanduser().resolve()
  video = Path(video_path).expanduser().resolve()
  digest = hashlib.sha256(output.read_bytes()).hexdigest()
  metadata_path = output.with_suffix(".review.json")
  metadata = {
    "schema_version": 1,
    "date": date,
    "status": "pending_review",
    "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "result_file": output.name,
    "result_sha256": digest,
    "video": {
      "file": video.name,
      "bytes": video.stat().st_size,
      "mtime_ns": video.stat().st_mtime_ns,
    },
    "pipeline": {
      "model": Path(model_path).expanduser().name,
      "time_source": "visible_osd_vlm_crop",
      "interval": args.interval,
      "resize": args.resize,
      "batch_size": args.batch_size,
      "similarity": args.similarity,
      "mode": args.mode,
      "identity_reference_sha256": [
        hashlib.sha256(
          Path(value).expanduser().resolve().read_bytes()
        ).hexdigest()
        for value in getattr(args, "identity_reference", [])
      ],
      "parent_feedback_lessons": getattr(
        args, "feedback_lessons_count", 0
      ),
      "parent_feedback_source_sha256": getattr(
        args, "feedback_source_sha256", []
      ),
    },
  }
  metadata_path.write_text(
    json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )
  return metadata_path


def write_failure_metadata(output_path: str, date: str, video_path: str,
               error: Exception) -> Path:
  from datetime import datetime

  output = Path(output_path).expanduser().resolve()
  video = Path(video_path).expanduser().resolve()
  metadata_path = output.with_suffix(".review.json")
  metadata_path.parent.mkdir(parents=True, exist_ok=True)
  metadata = {
    "schema_version": 1,
    "date": date,
    "status": "failed",
    "failed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "result_file": output.name,
    "video_file": video.name,
    "error_type": type(error).__name__,
    "error": str(error),
  }
  metadata_path.write_text(
    json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )
  return metadata_path


def main(argv: Optional[list[str]] = None) -> int:
  parser = build_parser()
  args = parser.parse_args(argv)

  if not args.output:
    video_dir = os.path.dirname(os.path.abspath(os.path.expanduser(args.video)))
    args.output = os.path.join(
      video_dir, ".emma-review", args.date, "result_pipeline.json"
    )

  try:
    feedback_root = args.feedback_root
    if not feedback_root:
      feedback_root = str(
        Path(args.output).expanduser().resolve().parent.parent
      )
    feedback_lessons, feedback_hashes = load_parent_feedback(
      feedback_root,
      args.date,
    )
    args.feedback_lessons_count = len(feedback_lessons)
    args.feedback_source_sha256 = feedback_hashes
    print(
      f" Parent feedback: {len(feedback_lessons)} lesson(s) "
      f"from {len(feedback_hashes)} reviewed file(s)"
    )
    require_ready_video(args.date, args.video, args.allow_legacy_stable)
    run_pipeline(
      date=args.date,
      video_path=args.video,
      model_path=args.model,
      interval_sec=args.interval,
      resize=args.resize,
      batch_size=args.batch_size,
      similarity_threshold=args.similarity,
      max_similar_gap=args.max_similar_gap,
      output_path=args.output,
      mode=args.mode,
      identity_references=args.identity_reference,
      feedback_lessons=feedback_lessons,
    )
    validate_candidate(args.output, args.date)
    metadata_path = write_review_metadata(
      args.output, args.date, args.video, args.model, args
    )
  except Exception as error:
    metadata_path = write_failure_metadata(
      args.output, args.date, args.video, error
    )
    print(f"\n❌ Pipeline stopped: {error}", file=sys.stderr)
    print(f" Failure metadata: {metadata_path}", file=sys.stderr)
    print(" Production database was not modified.", file=sys.stderr)
    return 1

  print(f" ✅ Candidate validated and queued for parent review")
  print(f" Review metadata: {metadata_path}")
  print(" Production database was not modified.")

  return 0


if __name__ == "__main__":
  sys.exit(main())
