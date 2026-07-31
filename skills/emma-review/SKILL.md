---
name: emma-review
description: Prepare, review, and validate date-based Emma study-room video audits for `Study_YYYYMMDD.mp4`, ChatGPT Work handoffs, and Emma Focus Admin JSON. Use when selecting a dated study video, preparing an audit packet, checking model-produced timeline/evaluations/stages JSON, calculating Focus Blocks, Distractions, Tokens_Net, Rating, or planning a safe import into Emma Focus.
---

# Emma Review

Treat all footage and results as sensitive family data. Keep video files and
date-specific results outside Git. Do not upload footage or POST results to any
service without explicit user authorization.

## Workflow

1. Read [references/audit-prompt.md](references/audit-prompt.md) before preparing
   or reviewing an audit.
2. Resolve exactly one date:
   - Accept `YYYY-MM-DD`, `YYYYMMDD`, `today`, `latest`, or an explicit path.
   - Map a date only to `Study_YYYYMMDD.mp4`.
   - Never silently substitute a neighboring date.
3. Inventory the video directory:
   - Run `python3 scripts/emma_review.py inventory VIDEO_DIR`.
   - Report missing dates, unexpected MP4 names, zero-byte files, and duplicate
     date mappings.
4. Confirm that Video Merge published the exact date:
   - Run `python3 scripts/emma_review.py ready DATE --video-dir VIDEO_DIR`.
   - For new videos, require the matching producer-written `.ready` manifest.
   - Use `--allow-legacy-stable` only for historical videos created before
     ready manifests existed.
5. Prepare one task packet:
   - Run `python3 scripts/emma_review.py prepare DATE --video-dir VIDEO_DIR`.
   - The command writes `prompt.txt` and `job.json` beside the video under
     `.emma-review/DATE/`; it does not copy or upload the video.
6. Analyze with ChatGPT Work or another explicitly approved video-capable
   provider and save raw JSON only as `result.json`.
7. Validate before review or import:
   - Run `python3 scripts/emma_review.py validate RESULT_JSON --expected-date DATE`.
   - Reject schema, enum, chronology, aggregation, token, and rating mismatches.
8. Require parent review before production import. Never pass the parent PIN to
   a model, Skill, Work project, prompt, result file, or unattended job.
9. If validation fails, correct deterministic arithmetic locally. Re-review
   observational or classification errors from the footage; never invent
   evidence.

## Audit Guardrails

- Use only `Focus`, `Coaching`, `Screen`, `Activity`, `Distraction`, and
  `Eye Rest` in `stages[].category`.
- Omit adult-only, empty-room, and uncertain-identity intervals from stages.
- Keep stages chronological, non-overlapping, and at minute precision.
- Count one Focus Block per qualifying Focus stage.
- Count one Distraction per Distraction stage and one per Screen stage longer
  than 30 minutes.
- Calculate `Tokens_Net = Focus_Blocks - Distractions` (每次分心扣1个银币).
- Apply rating precedence: absent, danger, excellent, warning.
- Return exactly one timeline row for the audited date.
- Keep observations factual and concise. Write summaries and notes in Chinese.
- Continue recording Eye Rest minutes, but never derive an Eye Rest token reward.

## Batch Use

Inventory the complete folder first, then prepare each requested date as a
separate packet. Do not combine multiple dates into one model request or one
JSON document.

Automated provider upload and production import remain separate implementation
phases. They require an approved provider, retention policy, credential path,
server-side validation, review state, and rollback procedure.
