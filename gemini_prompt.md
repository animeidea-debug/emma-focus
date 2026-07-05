# Emma Audit Directive — Gemini Prompt v5.2

Chinese output · Identity-aware · Schema-strict · 6-Bucket Tracking (v5.2 Production Edition)

> **Instruction:** Analyze the video sequence for Emma on `[Date]`. Rigorously evaluate the behaviors using the tracking protocols below. Formulate your findings into the strict tripartite JSON schema required by the Admin dashboard. All free-text descriptive properties (`Summary`, `Note`, `stage`, `note`) MUST be written in Chinese. Enum values must adhere exactly to the defined structural rules.

---

## 1. Identity Protocol & Hard Filtering

### Subject Definition
* **Target Subject:** Emma (12-year-old Chinese girl, typical feature: often wears hair in a ponytail or casual braids).
* **Frame Anchor:** `Time_Start` must be logged at the exact moment Emma appears and engages in a measurable task. If Emma is entirely absent from the room for the whole day, set `"Absent": true` inside the `timeline` array.

### Extreme Adult Filtering ("The Invisible Adult Rule")
* **Rule:** Adults (Father, Mother, Grandparents) frequently enter the room to clean, work independently on laptops, or read.
* **Action:** You MUST treat adult-only time blocks as completely **UNOBSERVED**. Do NOT emit any rows inside the `stages[]` array for these periods to prevent data pollution.
* **Coaching Exception:** Adults only become "visible" to the logging algorithm when they are directly interacting with Emma in a structured mentoring context (`Coaching`).

---

## 2. Six Activity Buckets & Classification Rules

Every tracked frame involving Emma must fall cleanly into one of these six categories inside `stages[].category`:

1. **`Focus` (深度专注)**
   * **Definition:** Continuous, independent written work (worksheets, homework), paper textbook reading, or audiobook listening. Must be **≥ 30 minutes** to establish a `Focus Block`. (Earns +1 Focus Token).
2. **`Coaching` (成人辅导/协同)**
   * **Definition:** Structured mentoring, or online screen classes taken alongside a parent. Exempt from independent screen limits.
3. **`Screen` (娱乐屏幕违规)**
   * **Definition:** Emma independently operating a device to watch entertainment videos (Netflix, anime) without supervision.
   * **Threshold:** Granted a 30-minute tolerance window. Exceeding this window by even 1 minute instantly voids the block, flips the category to `Screen`, and triggers a `Distraction` event.
4. **`Activity` (非书面素质拓展)**
   * **Definition:** High-concentration, productive but non-written/non-reading tasks (e.g., 3D printing crafts, manual model assembly, neatening schoolbags). Triggers 0 Distractions, but earns 0 Focus Tokens.
5. **`Distraction` (干扰分心)**
   * **Definition:** Pure daydreaming, playing with desk toys, short unauthorized interferences, or screen session over-tolerance. Instantly voids focus and increments the raw Distraction count by +1.
6. **`Eye Rest` (健康护眼休息)**
   * **Definition:** Relaxation blocks where Emma is resting eyes, stretching, or eating snacks without looking at any screen. Must be **≥ 10 continuous minutes**.

---

## 3. Token Calculation Formula & 4 Rating Outcomes

To maintain dashboard consistency, calculate the metrics using this strict algebraic sequence:

$$\text{Tokens\_Net} = \text{Total Established Focus Blocks} - \lfloor \frac{\text{Total Tracked Distractions}}{3} \rfloor$$

### Four Rating Outcomes (`evaluations.Rating`):
* **`🟢 优秀` (Excellent):** Triggered when $\text{Distractions} = 0$ AND $\text{Tokens\_Net} \ge 2$.
* **`🟡 警告` (Warning):** Triggered when $\text{Distractions}$ is exactly $1$ or $2$, OR when $\text{Tokens\_Net}$ is positive but under acceleration limits.
* **`🔴 危险` (Critical Risk):** Triggered immediately if $\text{Distractions} \ge 3$ OR if the cumulative $\text{Tokens\_Net} < 0$.
* **`⚪ 不在场` (Absent):** Triggered if Emma does not show up for the full day (`"Absent": true`). In this case, `Tokens_Net` is automatically set to `0`.

---

## 4. Mandatory JSON Dashboard Schema

Output the final payload strictly adhering to this structural template:

```json
{
  "date": "YYYY-MM-DD",
  "timeline": [
    {
      "Date": "YYYY-MM-DD",
      "Day_Type": "周一|周二|周三|周四|周五|周六|周日",
      "Time_Start": "HH:MM",
      "Time_End": "HH:MM",
      "Category": "自主高效 | 效率低下 | 正常波动",
      "Focus_Blocks": 0,
      "Distractions": 0,
      "Note": "全天综合行为摘要（严格限制在 40 字以内）",
      "Absent": false,
      "Eye_Rest_Minutes": 0
    }
  ],
  "evaluations": {
    "Date": "YYYY-MM-DD",
    "Summary": "中文详细表现深度分析（包含全天学习走势、屏幕设备合规解析、分心与扣分说明）",
    "Rating": "🟢 优秀 | 🟡 警告 | 🔴 危险 | ⚪ 不在场",
    "Tokens_Net": 0
  },
  "stages": [
    {
      "date": "YYYY-MM-DD",
      "stage": "精炼的阶段行为名称 (如: 独立深度书写 / 3D打印素质手工 / 娱乐屏幕违规)",
      "start": "HH:MM",
      "end": "HH:MM",
      "duration": 0,
      "category": "Focus | Coaching | Screen | Activity | Distraction | Eye Rest",
      "note": "对该时间段的合规判定理由说明（中文）"
    }
  ]
}