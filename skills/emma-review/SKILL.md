---
name: emma-review
description: Prepare, analyze, evidence-review, and validate date-based Emma study-room video audits for `Study_YYYYMMDD.mp4`, local VLM candidates, ChatGPT Work handoffs, and Emma Focus Admin JSON. Use when waiting for a Video Merge ready manifest, running or reviewing a dated video, resolving Emma/adult identity or activity boundaries, checking timeline/evaluations/stages JSON, applying parent feedback, calculating Focus Blocks, Distractions, Tokens_Net, Rating, or planning a safe parent-approved import.
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
6. Produce a candidate with the local pipeline when available. Treat its output
   as a hypothesis, not ground truth. Never allow the model to submit it.
7. Perform an evidence-driven two-pass review:
   - First cover the full video with coarse frames/contact sheets to locate
     Emma presence, adult-only gaps, activity changes, exits, and re-entries.
   - Then inspect denser OSD-timestamped frames around every proposed boundary,
     identity uncertainty, Screen interval, Coaching interval, and threshold
     crossing near 10 or 30 minutes.
   - Reconcile every candidate stage against visible evidence. Do not validate
     merely because arithmetic is internally consistent.
8. Validate before review or import:
   - Run `python3 scripts/emma_review.py validate RESULT_JSON --expected-date DATE`.
   - Reject schema, enum, chronology, aggregation, token, and rating mismatches.
9. Require parent review before production import. Never pass the parent PIN to
   a model, Skill, Work project, prompt, result file, or unattended job.
10. If validation fails, correct deterministic arithmetic locally. Re-review
   observational or classification errors from the footage; never invent
   evidence.
11. After a parent-approved submission, verify the saved date from the backend
    and record only reusable lessons in Git-external `parent_feedback.json`.
    Never feed the current date, exact intervals, raw results, or credentials
    back into the model.

## Boundary and Identity Review

- Emma leaving/re-entering, an empty room, adult-only footage, unresolved
  identity, a clear task reset, or a category change is a hard boundary.
- Never bridge those barriers using the generic "minor transition" rule.
- Merge a short transition only when Emma remains confirmed in frame and the
  same dominant activity visibly resumes. Adult passage or nearby presence does
  not make independent study Coaching.
- Confirm Screen from active attention or interaction, not from a device merely
  being visible. Coaching takes precedence only when direct teaching or joint
  review is visible.
- For identity, use multiple cues: face when visible, stature, clothing,
  movement continuity, seat/location continuity, and entry/exit continuity.
- Explicitly recheck any proposed stage longer than 90 minutes and every
  low-light interval; these are high-risk false-positive or over-merge zones.

## Audit Guardrails

- Use only `Focus`, `Coaching`, `Screen`, `Activity`, `Distraction`, and
  `Eye Rest` in `stages[].category`.
- Omit adult-only, empty-room, and uncertain-identity intervals from stages.
- Keep stages chronological, non-overlapping, and at minute precision.
- Count one Focus Block per qualifying Focus stage.
- Count one Distraction per Distraction stage and one per Screen stage longer
  than 30 minutes.
- Focus is inclusive at 30 minutes: `>=30` qualifies. Independent academic work
  from 15 through 29 minutes is one Distraction when it cannot validly merge.
- Screen is free through exactly 30 minutes: only `>30` adds one Distraction.
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

## Unattended Ready Mode

For a daily local candidate, run `run_ready_review.sh`. It polls only the exact
Study ready manifest, reuses an already matching `pending_review` result, sends
one Pushover outcome, and stops before production submission. Read
`docs/emma-review/automation-design.md` for the observed run window and safety
contract. Pushover is a human notification; the manifest remains the trigger.
