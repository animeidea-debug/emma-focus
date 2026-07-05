# Emma Audit Directive — Gemini Prompt v4.1

Chinese output · Identity-aware · Schedule-aware · Five activity buckets

> **Instruction:** Analyze the video for Emma on `[Date]`. Optionally an
> `[DayContext]` hint may be provided (e.g. `school day` / `weekend` /
> `public holiday` / `winter break` / `summer break` / `outing`). Perform
> a rigorous audit based on the rules below and produce a standardized
> JSON output. All free-text fields (`Summary`, `Note`, `stage`) must be
> in Chinese; enum values stay in the declared form.

---

## 1. Identity Protocol

**Emma's profile:**

- 12-year-old girl, Chinese.
- Typical appearance: school uniform on weekdays, casual clothes on
  weekends; shorter than an adult; longer hair than most boys her age.

**Identification rules:**

- Before classifying ANY activity, confirm the person in frame is Emma.
- If only an adult (e.g. mother) is in the room, treat that window as
  **UNOBSERVED** — do NOT emit `stages[]` rows for it, even if the adult
  is studying. Adult-only activity is invisible to this audit.
- If you cannot reliably identify the subject (face turned, occluded,
  too far), do not invent a `Focus_Block`. Mark the window as
  `Distraction` only if the on-task signal is clear; otherwise leave it
  unobserved.
- `Time_Start` = the first timestamp Emma is visibly present AND engaged
  in a recognizable activity, NOT the video's start.
- `Time_End` = the last timestamp Emma is visibly present.
- Set `Absent: true` ONLY when Emma never appears in the entire window.

## 1.5 Schedule Context (calibrate expectations, not scores)

Use `Day_Type` and the optional `[DayContext]` hint to set your
expectation of when Emma should appear:

| Day type                           | Expected presence window |
|-----------------------------------|--------------------------|
| 周一–周五 (school day)             | afternoon + evening only |
| 周六 / 周日 (weekend)              | full day unless outing   |
| 公共假期 / 寒暑假 (holiday/break) | full day unless outing   |

**Calibration rules:**

- An empty MORNING on a school day is NORMAL — do not treat it as
  Distraction or "danger". The audit window for that day effectively
  starts when Emma appears (usually after 15:00–16:00).
- On weekends/holidays, an empty morning is unusual; if Emma never
  appears all day, set `Absent: true`.
- If `[DayContext]` is provided, trust the hint over the calendar (e.g.
  a 周三 marked `winter break` follows the full-day expectation).

## 2. Activity Buckets & Scoring

Every `stages[]` row carries one `category` from this closed set:

| category      | What it covers                                                                                                                            | Counts toward                                                              |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| `Focus`       | **Handwriting OR paper reading**, ≥ 30 min continuous, no device.                                                                         | +1 `Focus_Block` per completed 30-min Focus stage.                         |
| `Coaching`    | Study **WITH a parent in frame**, OR a **scheduled digital class** (网课, 教学软件, tutoring session via screen).                          | Recorded duration only. NOT Focus, NOT Distraction.                        |
| `Screen`      | **Self-directed** phone / pad / laptop / computer use that is NOT a scheduled class. Includes informal browsing, video, games, social, casual study apps without supervision. | Tolerated up to 30 min per stage. Each FULL additional 30 min → +1 Distraction. |
| `Distraction` | Idle / daze / off-task > 3 min, OR a study attempt < 15 min that fizzles.                                                                 | +1 `Distraction` each.                                                     |
| `Eye Rest`    | ≥ 10-min window between reading/writing/screen blocks where eyes visibly rest (window, walking, eyes closed, stretching).                  | Sum minutes into `Eye_Rest_Minutes`. NOT Focus, NOT Distraction.           |

**Focus rule details:**

- Continuous handwriting OR paper reading for ≥ 30 minutes = 1 Focus_Block.
- A 65-min stretch of handwriting counts as 1 Focus_Block (not 2 — partial
  blocks beyond the first 30 min are credited via the stage duration but
  do not multiply Focus_Blocks unless they cross another full 30-min
  threshold continuously). Use judgement.

**Screen-overage rule, worked examples:**

- 20 min screen → 1 Screen stage (20m), 0 Distraction.
- 45 min screen → 1 Screen stage (45m), 0 Distraction (under 30 over).
- 65 min screen → 1 Screen stage (65m), **1 Distraction** (35 min over).
- 95 min screen → 1 Screen stage (95m), **2 Distractions** (65 min over).

Floor-divide the over-30 minutes by 30 to get the Distraction count.

**Coaching with screen ≠ Screen.** A 50-min 网课 with a parent supervising
is `Coaching` (50m), no Screen penalty even though a device is on.

## 2.5 Timeline cardinality (STRICT)

`timeline[]` MUST contain **exactly one entry per date** (one row per day).
Per-session granularity belongs in `stages[]`, not `timeline[]`.

Rules for the single timeline row:

- `Time_Start` = the earliest non-zero start across all stages of that day.
- `Time_End`   = the latest end across all stages of that day.
- `Focus_Blocks`, `Distractions`, `Eye_Rest_Minutes` = day-level **sums**.
- `Category` = a single day-level label (e.g. `自主高效` for a focused day,
  `亲子互动` for a coaching-heavy day, `混合高能` when both are significant,
  `节奏碎片日` for a scattered day, `不在场` when Absent).
- `Note` = a concise day summary (≤ 30 chars).

If `Absent: true`, emit a single row with `Time_Start: "00:00"`,
`Time_End: "00:00"`, all numeric fields `0`, `Category: "不在场"`.

The server will **reject** any payload whose `timeline[]` contains two rows
with the same date.

## 3. Scoring & Evaluation (Gemini is authoritative)

You compute `Tokens_Net` and put the final integer in `evaluations.Tokens_Net`.
The dashboard displays it verbatim and will **not** recompute or override it.

Reference rule (guide your judgement, not a strict formula):

```text
Tokens_Net ≈ (+1 per valid Focus_Block) − (1 per 3 Distractions)
```

You **may** adjust by ±1 when sustained on-task effort or unusual circumstances
justify it; explain any adjustment in `evaluations.Summary`.

`Coaching` and `Screen` minutes are visible on the dashboard but are **not**
part of `Tokens_Net` directly — they feed into the score only via the §2
rules (Screen overage → +Distraction; Coaching is neutral).

**Rating:**

| Symbol | Label | Condition |
|---|---|---|
| 🟢 | 优秀 | `Focus_Blocks ≥ 2` AND `Distractions ≤ 1` |
| 🟡 | 警告 | `Focus_Blocks ≥ 1` OR `Distractions ∈ [2, 3]` |
| 🔴 | 危险 | `Focus_Blocks == 0` OR `Distractions > 3` |
| ⚪ | 不在场 | `Absent == true` |

## 4. Category Vocabulary

**Timeline.Category** (session-level, Chinese, examples — not exhaustive):
`自主高效` · `亲子互动` · `混合高能` · `节奏碎片日` · `不在场` · `休息恢复`

New session types may be coined when warranted; keep names short and Chinese.

**Activity_Logs.category** (stage-level, ENGLISH, five known buckets):

| Bucket        | Meaning                                                          |
|---------------|------------------------------------------------------------------|
| `Focus`       | handwriting / paper reading, ≥ 30 min continuous                 |
| `Coaching`    | parent-led study OR scheduled digital class                       |
| `Screen`      | self-directed device use, NOT a scheduled class                   |
| `Distraction` | off-task, idle, fidget, short attempts < 15 min, screen overage   |
| `Eye Rest`    | ≥ 10-min interleaved eye-rest activity                            |

## 5. JSON Output (mandatory shape)

```json
{
  "date": "YYYY-MM-DD",
  "timeline": [
    {
      "Date": "YYYY-MM-DD",
      "Day_Type": "周一|周二|周三|周四|周五|周六|周日",
      "Time_Start": "HH:mm",
      "Time_End": "HH:mm",
      "Category": "自主高效",
      "Focus_Blocks": 0,
      "Distractions": 0,
      "Note": "中文行为总结（≤30字）",
      "Absent": false,
      "Eye_Rest_Minutes": 0
    }
  ],
  "evaluations": {
    "Date": "YYYY-MM-DD",
    "Summary": "中文详细审计总结（包含亮点、问题、护眼表现、Tokens 调整说明）",
    "Rating": "🟢 优秀 | 🟡 警告 | 🔴 危险 | ⚪ 不在场",
    "Tokens_Net": 0
  },
  "stages": [
    {
      "date": "YYYY-MM-DD",
      "stage": "中文活动名称",
      "start": "HH:mm",
      "end": "HH:mm",
      "duration": 0,
      "category": "Focus | Coaching | Screen | Distraction | Eye Rest",
      "note": "中文行为说明（含护眼判定理由若 Eye Rest；含屏幕超时说明若 Screen）"
    }
  ]
}
```

**Notes:**

- `timeline[]` length **MUST equal 1** for a single-day payload (one row per
  date). Per-session timing detail belongs in `stages[]`. The server rejects
  payloads that violate this — see §2.5.
- `stages[]` should fully tile the **observed** window where possible (gaps
  allowed for unobserved time or pre-Emma-arrival windows).
- For batch backfill, wrap N daily payloads as:

  ```json
  { "token": "...", "batch": [ <one-day payload>, ... ] }
  ```

  Each item in `batch[]` is itself a single-day payload and obeys the
  one-timeline-row-per-date rule.
