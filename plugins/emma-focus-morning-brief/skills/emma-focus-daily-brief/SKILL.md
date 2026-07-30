---
name: emma-focus-daily-brief
description: Generate a concise, warm morning focus brief from authoritative Emma Focus data. Use when a parent asks about yesterday's reviewed focus, activity stages, wallet changes, current balances, or the recent focus trend.
---

# Emma Focus Daily Brief

1. Call `check_connection`; if it fails, report the connection problem and stop.
2. Call `get_focus_brief` once for the requested Asia/Shanghai reference date.
3. Treat `data_state: missing` as unknown, never as zero. Treat `pending_review` as provisional.
4. State observed focus facts, wallet deltas, and balances plainly. Do not invent rewards, explanations, or missing activity.
5. Use supportive, non-judgmental Chinese. Keep the child-facing summary short; mention pending or missing data neutrally.
6. Do not request a PIN, token, browser session, or write action. These MCP tools are read-only.

Read [the API contract](references/api-contract.md) only when field meanings or date boundaries matter.
