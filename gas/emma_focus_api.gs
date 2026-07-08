const API_TOKEN = "emma2026_secure"; // 安全验证密钥
const BONUS_PIN = "emma2026!";        // 手动奖励 PIN（服务端校验；可随时修改）
const TOKEN_START_DATE = "2026-06-27"; // 暑假起算日；早于此日期的旧 Evaluations 行不进入交易表

// ==========================================
// 🎨 类别 → 桶 映射（语义解释层，非数据库）
// 增加新类别时只需在此处加一行；前后端均通过这张表派生颜色与桶。
// 未在表中的类别会落到 neutral 桶并记录警告，绝不抛错。
// ==========================================
const CATEGORY_BUCKETS = {
  "Focus":       { bucket: "focus",       color: "#3b82f6" }, // 蓝
  "Coaching":    { bucket: "coaching",    color: "#a855f7" }, // 紫 — 亲子辅导 / 网课
  "Screen":      { bucket: "screen",      color: "#f59e0b" }, // 琥珀 — 自主屏幕使用（超时计入 Distraction）
  "Activity":    { bucket: "activity",    color: "#06b6d4" }, // 青 — 非书面素质拓展（3D打印、手工等）
  "Distraction": { bucket: "distraction", color: "#ef4444" }, // 红
  "Eye Rest":    { bucket: "eyerest",     color: "#22c55e" }  // 绿
};
const NEUTRAL_COLOR = "#9ca3af"; // 未知类别回退色

// 桶 → 顶部四张卡片归属。null 表示不计入任何小时卡。
const BUCKET_TO_CARD = {
  focus:       "study",      // → ① 自主高效充电
  coaching:    "coaching",   // → ② 亲子与网课时光
  screen:      "screen",     // → ③ 电子屏幕时间（新卡片）
  activity:    "study",      // → ① 自主高效充电（productive 合并）
  eyerest:     null,         // 不计入小时卡（已有单独的 Eye_Rest_Minutes 字段）
  distraction: "waste",      // → ④ 分心无效时间
  neutral:     "waste"
};

function bucketFor(category) {
  const hit = CATEGORY_BUCKETS[category];
  if (hit) return hit.bucket;
  if (category) Logger.log("⚠️ 未知类别 fallback 至 neutral: " + category);
  return "neutral";
}

// 标准 JSON 输出包装
function jsonOut(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// ==========================================
// 🚀 核心功能 1：重置为种子数据（⚠️ 会清空所有现有数据！）
// ==========================================
function resetToSeedData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // 检查并创建两个核心数据表
  let timelineSheet = ss.getSheetByName("Timeline") || ss.insertSheet("Timeline");
  let evalSheet = ss.getSheetByName("Evaluations") || ss.insertSheet("Evaluations");

  // 清空表格，防止重复执行造成数据叠加
  timelineSheet.clear();
  evalSheet.clear();

  // 1. 设置 Timeline 表头并加粗（10 列；Eye_Rest_Minutes 为护眼分钟数）
  timelineSheet.appendRow(["Date", "Day_Type", "Time_Start", "Time_End", "Category", "Focus_Blocks", "Distractions", "Note", "Absent", "Eye_Rest_Minutes"]);
  timelineSheet.getRange("A1:J1").setFontWeight("bold").setBackground("#f3f4f6");

  // 写入 Timeline 历史数据 (5.23 - 6.27) — 历史无护眼数据，Eye_Rest_Minutes 全部 0
  // 注意：每日期仅一行，与 writeOneDay() 的校验规则一致
  const timelineData = [
    ["2026-05-23", "周六", "17:54", "19:43", "自主高效", 1, 6, "独立充电日", false, 0],
    ["2026-05-24", "周日", "09:14", "17:13", "混合高能", 5, 2, "混合高能日", false, 0],
    ["2026-05-25", "周一", "00:00", "00:00", "不在场", 0, 0, "Emma外出未归", true, 0],
    ["2026-05-26", "周二", "19:47", "20:06", "亲子互动", 1, 0, "亲子协同日", false, 0],
    ["2026-05-27", "周三", "14:32", "18:06", "自主高效", 5, 4, "深度阅读挑战", false, 0],
    ["2026-05-28", "周四", "00:00", "00:00", "不在场", 0, 0, "Emma外出未归", true, 0],
    ["2026-05-29", "周五", "00:00", "00:00", "不在场", 0, 0, "Emma外出未归", true, 0],
    ["2026-05-30", "周六", "10:02", "10:37", "自主高效", 1, 1, "专注力回升", false, 0],
    ["2026-05-31", "周日", "10:03", "16:18", "自主高效", 6, 4, "耐力大考验", false, 0],
    ["2026-06-27", "周六", "10:24", "17:40", "自主高效", 2, 1, "早间长效专注 · 亲子辅导互动 · 下午全天高能突破", false, 0]
  ];
  timelineData.forEach(row => timelineSheet.appendRow(row));

  // 2. 设置 Evaluations 表头并加粗
  evalSheet.appendRow(["Date", "Summary", "Rating", "Tokens_Net"]);
  evalSheet.getRange("A1:D1").setFontWeight("bold").setBackground("#eef2ff");

  // 写入 Evaluations 历史数据
  const evalData = [
    ["2026-05-23", "独立充电日，空间转换频繁", "🟡 警告", -5],
    ["2026-05-24", "全天混合饱和使用，高强度写作业", "🟢 优秀", 5],
    ["2026-05-25", "Emma不在场", "⚪ 不在场", 0],
    ["2026-05-26", "晚间亲子高效协同教学", "🟢 优秀", 1],
    ["2026-05-27", "下午伏案阅读与练习，表现优异", "🟢 优秀", 5],
    ["2026-05-28", "Emma不在场", "⚪ 不在场", 0],
    ["2026-05-29", "Emma不在场", "⚪ 不在场", 0],
    ["2026-05-30", "前段独立伏案专注表现佳", "🟢 优秀", 1],
    ["2026-05-31", "长时混合时段，后半程高密度伏案", "🟢 优秀", 5],
    ["2026-06-27", "全天高能突破，独立产出2个专注块，下午展现极强抗干扰耐力", "🟢 优秀", 2]
  ];
  evalData.forEach(row => evalSheet.appendRow(row));
}

// ==========================================
// 📡 核心功能 2：供前端读取大盘的 GET 接口
// ==========================================
function doGet(e) {
  // 1. 鉴权逻辑保持不变
  if (!e.parameter || e.parameter.token !== API_TOKEN) {
    return ContentService.createTextOutput(JSON.stringify({error: "Unauthorized"})).setMimeType(ContentService.MimeType.JSON);
  }

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const action = e.parameter.action;

  // 2. 新增逻辑：如果请求的是特定日期的详细日志
  if (action === "getLogs" && e.parameter.date) {
    const targetDate = new Date(e.parameter.date).setHours(0, 0, 0, 0);
    const logSheet = ss.getSheetByName("Activity_Logs");
    const logData = getSheetDataAsObjects(logSheet);
    
    // 筛选出该日期的数据
    const filteredLogs = logData.filter(row => {
      return new Date(row.Date).setHours(0, 0, 0, 0) === targetDate;
    });

    // 如果筛选结果为空，确保返回一个空的 JSON 数组
  if (filteredLogs.length === 0) {
    return ContentService.createTextOutput(JSON.stringify([])).setMimeType(ContentService.MimeType.JSON);
  }
    return ContentService.createTextOutput(JSON.stringify(filteredLogs)).setMimeType(ContentService.MimeType.JSON);
  }

  // ▶ 新增：聚合大盘端点（取代 frontend 计算）
  if (action === "getDashboard") {
    return jsonOut(buildDashboard(ss, e.parameter.ym));
  }

  // ▶ 新增：图表端点（全期分布 + 90 天趋势）
  if (action === "getCharts") {
    return jsonOut(buildCharts(ss));
  }

  // ▶ 新增：金/银币余额 + 交易流水
  if (action === "getTokens") {
    return jsonOut(getTokensData(ss));
  }

  // ▶ 新增：兑换商店配置
  if (action === "getRedeemItems") {
    return jsonOut(getRedeemItemsData(ss));
  }

  // ▶ 新增：币种交换汇率
  if (action === "getExchangeRate") {
    return jsonOut(getExchangeRateData(ss));
  }

  // ⚠️ 旧 action（getStats / 默认 raw）已被 getDashboard 取代；明确返回错误避免误用
  return jsonOut({ error: "Unknown action. Use getDashboard, getCharts, or getLogs." });
}

// ==========================================
// ✍️ 核心功能 3：供 AI 自动写入的 POST 接口
//   - 单日（兼容）：{ token, date, timeline, evaluations, stages }
//   - 批量（新增）：{ token, batch: [<one-day payload>, ...] }
// ==========================================
function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);
    if (payload.token !== API_TOKEN) throw new Error("Unauthorized");
    Logger.log("接收到的 Payload: " + JSON.stringify(payload));

    const ss = SpreadsheetApp.getActiveSpreadsheet();

    // ▶ Token / Redeem 系统：基于 action 分发，绕过 timeline 校验
    if (payload.action === "redeem") {
      return jsonOut(actionRedeem(ss, payload.itemId));
    }
    if (payload.action === "bonus") {
      return jsonOut(actionBonus(ss, payload.pin, payload.coinType, payload.amount, payload.reason));
    }
    if (payload.action === "upsertRedeemItem") {
      return jsonOut(actionUpsertRedeemItem(ss, payload.item));
    }
    if (payload.action === "upsertRedeemItems") {
      return jsonOut(actionUpsertRedeemItems(ss, payload.items));
    }
    if (payload.action === "markAbsent") {
      return jsonOut(actionMarkAbsent(ss, payload.date));
    }
    if (payload.action === "exchange") {
      return jsonOut(actionExchange(ss, payload.direction, payload.amount));
    }
    if (payload.action === "setExchangeRate") {
      return jsonOut(actionSetExchangeRate(ss, payload.rate));
    }

    // ▶ 批量分支：逐条独立处理，失败的条目在 results 中标记
    if (Array.isArray(payload.batch)) {
      const results = payload.batch.map((item, i) => {
        try {
          writeOneDay(ss, item);
          return { date: item && item.date, status: "Success" };
        } catch (err) {
          return { date: item && item.date, index: i, status: "Failed", error: err.message };
        }
      });
      const failed = results.filter(r => r.status === "Failed").length;
      return jsonOut({
        status:    failed === 0 ? "Success" : "Partial",
        processed: results.length,
        succeeded: results.length - failed,
        failed,
        results,
        // 体量提示：单次写超过 ~60 天有触发 GAS 6 分钟上限的风险
        warning: payload.batch.length > 60 ? "Large batch (>60). Consider splitting." : undefined
      });
    }

    // ▶ 单日分支（与之前行为一致）
    writeOneDay(ss, payload);
    return jsonOut({ status: "Success" });
  } catch (error) {
    return jsonOut({ error: error.message });
  }
}

// 单日写入：Timeline upsert + Evaluations upsert + Activity_Logs delete-then-insert
function writeOneDay(ss, item) {
  if (!item || typeof item !== "object") throw new Error("Empty item");

  // --- Timeline: delete ALL rows for payload dates, then append fresh rows ---
  if (item.timeline) {
    if (!Array.isArray(item.timeline)) throw new Error("timeline must be an array");

    // 守卫 1：同一 payload 内禁止重复日期
    const seen = {};
    item.timeline.forEach(r => {
      const d = r && r.Date;
      if (!d) throw new Error("timeline row missing Date");
      if (seen[d]) throw new Error("Duplicate timeline date: " + d + " — only one row per date is allowed (push session detail to stages[]).");
      seen[d] = true;
    });

    // 守卫 2：如 payload 顶层 item.date 已指定，timeline 行必须匹配
    if (item.date) {
      item.timeline.forEach(r => {
        if (r.Date !== item.date) {
          throw new Error("timeline row Date (" + r.Date + ") does not match payload.date (" + item.date + ")");
        }
      });
    }

    const tSheet = ss.getSheetByName("Timeline");
    // 先把 payload 中所有日期的现有行全部删除（倒序遍历保持行号稳定）
    // 这解决了历史多行问题（如 2026-06-27 的三行）
    const payloadDates = new Set(item.timeline.map(r => r.Date));
    const tData = tSheet.getDataRange().getValues();
    for (let i = tData.length - 1; i >= 1; i--) {
      const cellDate = String(tData[i][0]).substring(0, 10);
      if (payloadDates.has(cellDate)) tSheet.deleteRow(i + 1);
    }
    // 然后追加新行
    item.timeline.forEach(row => {
      tSheet.appendRow([
        row.Date, row.Day_Type, row.Time_Start, row.Time_End, row.Category,
        row.Focus_Blocks, row.Distractions, row.Note, row.Absent,
        row.Eye_Rest_Minutes != null ? row.Eye_Rest_Minutes : 0
      ]);
    });
  }

  // --- Evaluations: delete ALL rows for the date, then append fresh row ---
  if (item.evaluations) {
    const eSheet = ss.getSheetByName("Evaluations");
    if (!eSheet) throw new Error("无法获取 Evaluations 表");
    const evalData = item.evaluations;
    const eData = eSheet.getDataRange().getValues();
    for (let i = eData.length - 1; i >= 1; i--) {
      const cellDate = String(eData[i][0]).substring(0, 10);
      if (cellDate === evalData.Date) eSheet.deleteRow(i + 1);
    }
    eSheet.appendRow([evalData.Date, evalData.Summary, evalData.Rating, evalData.Tokens_Net]);
  }

  // --- Activity_Logs: always clear this date, then insert new stages (if any) ---
  // baseDate is derived from multiple sources so absent submissions (empty stages) still clear old logs
  const baseDate = item.date
    || (item.timeline && item.timeline[0] && item.timeline[0].Date)
    || (item.evaluations && item.evaluations.Date);

  if (baseDate) {
    clearActivityLogsForDate(ss, baseDate);
    if (item.stages && item.stages.length > 0) {
      const logSheet = ss.getSheetByName("Activity_Logs");
      item.stages.forEach(s => {
        const stageDate = s.date || baseDate;
        logSheet.appendRow([stageDate, s.stage, s.start, s.end, s.duration, s.category, s.note]);
      });
    }
  }

  // --- 奖励派生：按当日数据生成 / 重算 Transactions ---
  const writeDate = item.date
    || (item.timeline && item.timeline[0] && item.timeline[0].Date)
    || (item.evaluations && item.evaluations.Date);
  if (writeDate && writeDate >= TOKEN_START_DATE) {
    deriveTransactionsForDate(ss, writeDate);
  }

  // 失效 dashboard 缓存
  invalidateDashboardCache(ss, writeDate);
}

// 清除指定日期的所有 Activity_Logs 行（供 writeOneDay 和 actionMarkAbsent 复用）
function clearActivityLogsForDate(ss, dateStr) {
  const logSheet = ss.getSheetByName("Activity_Logs");
  if (!logSheet) return;
  const targetDate = new Date(dateStr).setHours(0, 0, 0, 0);
  const data = logSheet.getDataRange().getValues();
  for (let i = data.length - 1; i >= 1; i--) {
    if (new Date(data[i][0]).setHours(0, 0, 0, 0) === targetDate) {
      logSheet.deleteRow(i + 1);
    }
  }
}

// ==========================================
// 🪙 Token / 交易 — 奖励派生、余额重建、读写
// ==========================================

// 在某日期（及其相关上下文）上重新派生 award/streak/eyerest 行，然后重建余额。
// 不触碰 bonus / redeem / exchange 行（那些由用户操作直接写入）。
function deriveTransactionsForDate(ss, date) {
  const txSheet = ss.getSheetByName("Transactions");
  if (!txSheet) return;

  // 1. 删除当日所有派生类型行（保留 bonus_*, redeem, exchange）
  const derived = { award_silver:1, award_gold:1, streak_gold:1 };
  const data = txSheet.getDataRange().getDisplayValues();
  for (let i = data.length - 1; i >= 1; i--) {
    if (data[i][0] === date && derived[data[i][1]]) txSheet.deleteRow(i + 1);
  }

  // 2. 从 Evaluations 取当日 Tokens_Net → 派生 award_silver
  const evals = getSheetDataAsObjects(ss.getSheetByName("Evaluations"));
  const ev = evals.find(r => r.Date === date);
  const tokensNet = ev ? Number(ev.Tokens_Net) || 0 : 0;
  if (tokensNet !== 0) {
    appendTransactionRow(txSheet, [date, "award_silver", "专注奖励 " + date, tokensNet, 0, 0, 0, ""]);
  }

  // 3. 从 Timeline + Activity_Logs 判断「优秀日」→ 派生 award_gold
  const timeline = getSheetDataAsObjects(ss.getSheetByName("Timeline"));
  const tl = timeline.find(r => r.Date === date);
  const logs = getSheetDataAsObjects(ss.getSheetByName("Activity_Logs"));
  if (tl && isExcellentDay(tl, logs)) {
    appendTransactionRow(txSheet, [date, "award_gold", "优秀日金币 " + date, 0, 1, 0, 0, ""]);

    // 4. 连击：前两天也都有 award_gold 行 → 第 3 天 +1 streak_gold
    // 计数器重置规则：D-3 不能有 award_gold（说明上一轮还没结束），
    // 或者 D-3 已有 streak_gold（说明上一轮已结束，这是新周期的 D3）。
    const d1 = shiftDate(date, -1);
    const d2 = shiftDate(date, -2);
    const d3 = shiftDate(date, -3);
    const refreshedData = txSheet.getDataRange().getDisplayValues();
    const hasGold = ds => refreshedData.some((r, i) => i > 0 && r[0] === ds && r[1] === "award_gold");
    const hasStreak = ds => refreshedData.some((r, i) => i > 0 && r[0] === ds && r[1] === "streak_gold");
    if (hasGold(d1) && hasGold(d2) && (!hasGold(d3) || hasStreak(d3))) {
      appendTransactionRow(txSheet, [date, "streak_gold", "3 日连击奖励", 0, 1, 0, 0, ""]);
    }
  }

  // 5. 周护眼里程碑：重算本日所在 ISO 周
  recomputeEyeRestMilestone(ss, date);

  // 6. 全表余额重建
  rebuildBalances(ss);
}

// 优秀日：Focus_Blocks ≥ 2 AND Distractions == 0 AND 当日无 >30min 的 Screen stage。
function isExcellentDay(timelineRow, allLogs) {
  if (!timelineRow) return false;
  if (String(timelineRow.Absent).toLowerCase() === "true" || timelineRow.Absent === true) return false;
  const fb = Number(timelineRow.Focus_Blocks) || 0;
  const ds = Number(timelineRow.Distractions) || 0;
  if (fb < 2 || ds !== 0) return false;
  // 检查 Screen 超时
  const screenLogs = allLogs.filter(l => l.Date === timelineRow.Date && bucketFor(l.Category) === "screen");
  const anyOver30 = screenLogs.some(l => (Number(l.Duration) || 0) > 30);
  return !anyOver30;
}

// 重算某日所在 ISO 周的 eyerest_silver — 让该周派生行数 = floor(weekMinutes / 60)
function recomputeEyeRestMilestone(ss, anyDateInWeek) {
  const txSheet = ss.getSheetByName("Transactions");
  if (!txSheet) return;
  const { monday, sunday, weekTag } = isoWeekBounds(anyDateInWeek);

  // 删掉该周所有 eyerest_silver 派生行
  const data = txSheet.getDataRange().getValues();
  for (let i = data.length - 1; i >= 1; i--) {
    if (data[i][1] === "eyerest_silver" && data[i][0] >= monday && data[i][0] <= sunday) {
      txSheet.deleteRow(i + 1);
    }
  }

  // 统计该周 Timeline 的 Eye_Rest_Minutes
  const timeline = getSheetDataAsObjects(ss.getSheetByName("Timeline"));
  let weekMinutes = 0, lastDateInWeek = monday;
  timeline.forEach(r => {
    if (!r.Date || r.Date < monday || r.Date > sunday) return;
    weekMinutes += Number(r.Eye_Rest_Minutes) || 0;
    if (r.Date > lastDateInWeek) lastDateInWeek = r.Date;
  });
  const count = Math.floor(weekMinutes / 60);
  for (let i = 0; i < count; i++) {
    appendTransactionRow(txSheet, [lastDateInWeek, "eyerest_silver", "护眼里程碑 " + weekTag + " (#" + (i + 1) + ")", 1, 0, 0, 0, ""]);
  }
}

// 给出 YYYY-MM-DD，返回所在 ISO 周（周一为周首）的边界与中文标记
function isoWeekBounds(dateStr) {
  const d = new Date(dateStr + "T00:00:00");
  // JS getDay: 周日=0, 周一=1, ... 周六=6 — 换算成「周一=0」偏移
  const dow = (d.getDay() + 6) % 7;
  const monday = new Date(d); monday.setDate(d.getDate() - dow);
  const sunday = new Date(monday); sunday.setDate(monday.getDate() + 6);
  const fmt = x => x.getFullYear() + "-" + String(x.getMonth()+1).padStart(2,"0") + "-" + String(x.getDate()).padStart(2,"0");
  return {
    monday: fmt(monday),
    sunday: fmt(sunday),
    weekTag: fmt(monday).substring(5) + "~" + fmt(sunday).substring(5)
  };
}

function shiftDate(dateStr, delta) {
  const d = new Date(dateStr + "T00:00:00");
  d.setDate(d.getDate() + delta);
  return d.getFullYear() + "-" + String(d.getMonth()+1).padStart(2,"0") + "-" + String(d.getDate()).padStart(2,"0");
}

function appendTransactionRow(sheet, row) {
  // row: [Date, Type, Description, Silver_Delta, Gold_Delta, Silver_Balance, Gold_Balance, Note]
  sheet.appendRow(row);
}

// 自表头之下扫描所有行（按行号 = 时间顺序），逐行累加 delta 并写回 Balance 列
function rebuildBalances(ss) {
  const sheet = ss.getSheetByName("Transactions");
  if (!sheet) return;
  const last = sheet.getLastRow();
  if (last < 2) return;
  const range = sheet.getRange(2, 1, last - 1, 8);
  const values = range.getValues();
  let sBal = 0, gBal = 0;
  values.forEach(row => {
    // 仅 ≥ TOKEN_START_DATE 的行计入余额；其它行 Balance 留作历史快照
    const dateStr = String(row[0]).substring(0, 10);
    const inScope = dateStr >= TOKEN_START_DATE;
    if (inScope) {
      sBal += Number(row[3]) || 0;
      gBal += Number(row[4]) || 0;
      row[5] = sBal;
      row[6] = gBal;
    }
  });
  range.setValues(values);
}

// 读取 Transactions（仅 ≥ TOKEN_START_DATE），返回 {silverBalance, goldBalance, transactions[]}
function getTokensData(ss) {
  // 懒初始化：表不存在 → 自动建表（首次访问时无需手动 init）
  if (!ss.getSheetByName("Transactions")) initTransactionsSheet(ss);
  const sheet = ss.getSheetByName("Transactions");
  if (!sheet || sheet.getLastRow() < 2) {
    return { silverBalance: 0, goldBalance: 0, transactions: [] };
  }
  const rows = getSheetDataAsObjects(sheet);
  const inScope = rows.filter(r => r.Date && r.Date >= TOKEN_START_DATE);
  // 按写入顺序，最后一行为当前总余额
  const tail = inScope[inScope.length - 1];
  const silverBalance = tail ? Number(tail.Silver_Balance) || 0 : 0;
  const goldBalance   = tail ? Number(tail.Gold_Balance)   || 0 : 0;
  // 倒序：最新交易在前
  const transactions = inScope.slice().reverse().map(r => ({
    date:          r.Date,
    type:          r.Type,
    description:   r.Description,
    silverDelta:   Number(r.Silver_Delta) || 0,
    goldDelta:     Number(r.Gold_Delta)   || 0,
    silverBalance: Number(r.Silver_Balance) || 0,
    goldBalance:   Number(r.Gold_Balance)   || 0,
    note:          r.Note || ""
  }));
  return { silverBalance, goldBalance, transactions };
}

// 读取兑换商店配置
function getRedeemItemsData(ss) {
  // 懒初始化：表不存在 → 自动建表并写入种子项目
  if (!ss.getSheetByName("RedeemItems")) initRedeemItemsSheet(ss);
  const sheet = ss.getSheetByName("RedeemItems");
  if (!sheet || sheet.getLastRow() < 2) return [];
  const rows = getSheetDataAsObjects(sheet);
  return rows.map(r => ({
    itemId:      r.ItemId,
    label:       r.Label,
    description: r.Description,
    coinType:    r.CoinType,
    cost:        Number(r.Cost) || 0,
    active:      String(r.Active).toLowerCase() === "true" || r.Active === true,
    sort:        Number(r.Sort) || 0
  })).sort((a, b) => a.sort - b.sort);
}

// 写入一笔兑换：扣减余额，描述用 item.label
function actionRedeem(ss, itemId) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000); // 30秒超时
  try {
    if (!ss.getSheetByName("Transactions")) initTransactionsSheet(ss);
    const items = getRedeemItemsData(ss);
    const item = items.find(i => i.itemId === itemId && i.active);
    if (!item) throw new Error("兑换项不存在或已停用: " + itemId);
    const { silverBalance, goldBalance } = getTokensData(ss);
    if (item.coinType === "silver" && silverBalance < item.cost) throw new Error("银币余额不足");
    if (item.coinType === "gold"   && goldBalance   < item.cost) throw new Error("金币余额不足");

    const today = todayISO();
    const sheet = ss.getSheetByName("Transactions");
    const sDelta = item.coinType === "silver" ? -item.cost : 0;
    const gDelta = item.coinType === "gold"   ? -item.cost : 0;
    appendTransactionRow(sheet, [today, "redeem", "兑换 " + item.label, sDelta, gDelta, 0, 0, ""]);
    rebuildBalances(ss);
    const fresh = getTokensData(ss);
    return { status: "Success", newSilverBalance: fresh.silverBalance, newGoldBalance: fresh.goldBalance };
  } finally {
    lock.releaseLock();
  }
}

// 手动奖励：服务端校验 PIN
function actionBonus(ss, pin, coinType, amount, reason) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000); // 30秒超时
  try {
    if (pin !== BONUS_PIN) throw new Error("PIN 校验失败");
    if (coinType !== "silver" && coinType !== "gold") throw new Error("coinType 必须是 silver 或 gold");
    const amt = Math.abs(Number(amount) || 0);
    if (!amt) throw new Error("数量必须 > 0");
    if (!ss.getSheetByName("Transactions")) initTransactionsSheet(ss);

    const today = todayISO();
    const sheet = ss.getSheetByName("Transactions");
    const sDelta = coinType === "silver" ? amt : 0;
    const gDelta = coinType === "gold"   ? amt : 0;
    const type = coinType === "silver" ? "bonus_silver" : "bonus_gold";
    appendTransactionRow(sheet, [today, type, "手动奖励：" + (reason || "无说明"), sDelta, gDelta, 0, 0, reason || ""]);
    rebuildBalances(ss);
    const fresh = getTokensData(ss);
    return { status: "Success", newSilverBalance: fresh.silverBalance, newGoldBalance: fresh.goldBalance };
  } finally {
    lock.releaseLock();
  }
}

// 新增 / 更新兑换项
function actionUpsertRedeemItem(ss, item) {
  if (!item || !item.itemId) throw new Error("itemId 必填");
  if (!ss.getSheetByName("RedeemItems")) initRedeemItemsSheet(ss);
  const sheet = ss.getSheetByName("RedeemItems");
  if (!sheet) throw new Error("RedeemItems 表不存在");
  const data = sheet.getDataRange().getValues();
  let foundRow = -1;
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === item.itemId) { foundRow = i + 1; break; }
  }
  const row = [
    item.itemId,
    item.label || "",
    item.description || "",
    item.coinType || "silver",
    Number(item.cost) || 1,
    item.active === false ? false : true,
    Number(item.sort) || 0
  ];
  if (foundRow > 0) {
    sheet.getRange(foundRow, 1, 1, 7).setValues([row]);
  } else {
    sheet.appendRow(row);
  }
  return { status: "Success" };
}

// 批量新增 / 更新兑换项
function actionUpsertRedeemItems(ss, items) {
  if (!Array.isArray(items)) throw new Error("items 必须是数组");
  if (!ss.getSheetByName("RedeemItems")) initRedeemItemsSheet(ss);
  const sheet = ss.getSheetByName("RedeemItems");
  if (!sheet) throw new Error("RedeemItems 表不存在");
  
  const data = sheet.getDataRange().getValues();
  const existingIds = {};
  for (let i = 1; i < data.length; i++) {
    existingIds[data[i][0]] = i + 1; // itemId -> row number (1-indexed)
  }
  
  const results = [];
  items.forEach(item => {
    if (!item || !item.itemId) {
      results.push({ itemId: item?.itemId || "unknown", status: "Failed", error: "itemId 必填" });
      return;
    }
    const row = [
      item.itemId,
      item.label || "",
      item.description || "",
      item.coinType || "silver",
      Number(item.cost) || 1,
      item.active === false ? false : true,
      Number(item.sort) || 0
    ];
    const foundRow = existingIds[item.itemId];
    if (foundRow) {
      sheet.getRange(foundRow, 1, 1, 7).setValues([row]);
      results.push({ itemId: item.itemId, status: "Updated" });
    } else {
      sheet.appendRow(row);
      results.push({ itemId: item.itemId, status: "Created" });
    }
  });
  
  return { status: "Success", results };
}

// 快速缺席标记：构造标准缺席 payload 并写入所有相关表
function actionMarkAbsent(ss, dateStr) {
  if (!dateStr || typeof dateStr !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    throw new Error("date 参数必须是 YYYY-MM-DD 格式");
  }
  const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  const weekdayLabel = weekdays[new Date(dateStr + "T00:00:00").getDay()];
  const item = {
    date: dateStr,
    timeline: [{
      Date: dateStr, Day_Type: weekdayLabel,
      Time_Start: "00:00", Time_End: "00:00",
      Category: "不在场", Focus_Blocks: 0, Distractions: 0,
      Note: "Emma 不在场", Absent: true, Eye_Rest_Minutes: 0
    }],
    evaluations: {
      Date: dateStr, Summary: "Emma 不在场",
      Rating: "⚪ 不在场", Tokens_Net: 0
    },
    stages: []
  };
  writeOneDay(ss, item);
  return { status: "Success", date: dateStr, weekday: weekdayLabel };
}

// ==========================================
// 🔄 币种交换 — 汇率配置 & 交换操作
// ==========================================

// 读取汇率（从 AppConfig 表，默认 5）
function getExchangeRateData(ss) {
  initAppConfigSheet(ss);
  const sheet = ss.getSheetByName("AppConfig");
  const data = sheet.getDataRange().getDisplayValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === "exchange_rate") {
      const rate = Number(data[i][1]) || 5;
      return { rate };
    }
  }
  // 未找到则写入默认值
  sheet.appendRow(["exchange_rate", 5]);
  return { rate: 5 };
}

// 设置汇率（管理员后台调用）
function actionSetExchangeRate(ss, rate) {
  const r = Math.floor(Number(rate));
  if (r < 1) throw new Error("汇率必须 ≥ 1");
  initAppConfigSheet(ss);
  const sheet = ss.getSheetByName("AppConfig");
  const data = sheet.getDataRange().getDisplayValues();
  let found = false;
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === "exchange_rate") {
      sheet.getRange(i + 1, 2).setValue(r);
      found = true;
      break;
    }
  }
  if (!found) sheet.appendRow(["exchange_rate", r]);
  return { status: "Success", rate: r };
}

// 创建（若不存在）并初始化 AppConfig 表
function initAppConfigSheet(ss) {
  let sheet = ss.getSheetByName("AppConfig") || ss.insertSheet("AppConfig");
  const headers = ["Key", "Value"];
  const first = sheet.getRange(1, 1, 1, 2).getDisplayValues()[0];
  if (first[0] !== "Key" || first[1] !== "Value") {
    sheet.getRange(1, 1, 1, 2).setValues([headers]);
    sheet.getRange(1, 1, 1, 2).setFontWeight("bold").setBackground("#e0e7ff");
  }
  sheet.setFrozenRows(1);
}

// 执行币种交换
function actionExchange(ss, direction, amount) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000); // 30秒超时
  try {
    if (direction !== "s2g" && direction !== "g2s") throw new Error("direction 必须是 s2g（银→金）或 g2s（金→银）");
    const { rate } = getExchangeRateData(ss);
    const amt = Math.floor(Number(amount));
    if (amt < 1) throw new Error("交换数量必须 ≥ 1");
    if (direction === "s2g") {
      if (amt < rate) throw new Error("银币交换数量不能小于汇率 " + rate);
      if (amt % rate !== 0) throw new Error("银币交换数量必须是 " + rate + " 的整数倍");
    }

    if (!ss.getSheetByName("Transactions")) initTransactionsSheet(ss);
    const { silverBalance, goldBalance } = getTokensData(ss);

    if (direction === "s2g") {
      if (silverBalance < amt) throw new Error("银币余额不足，需要 " + amt + " 枚，当前 " + silverBalance + " 枚");
      const goldOut = amt / rate;
      const sheet = ss.getSheetByName("Transactions");
      appendTransactionRow(sheet, [todayISO(), "exchange", "银币→金币交换 " + amt + "→" + goldOut, -amt, goldOut, 0, 0, ""]);
    } else {
      if (goldBalance < amt) throw new Error("金币余额不足，需要 " + amt + " 枚，当前 " + goldBalance + " 枚");
      const silverOut = amt * rate;
      const sheet = ss.getSheetByName("Transactions");
      appendTransactionRow(sheet, [todayISO(), "exchange", "金币→银币交换 " + amt + "→" + silverOut, silverOut, -amt, 0, 0, ""]);
    }

    rebuildBalances(ss);
    const fresh = getTokensData(ss);
    return { status: "Success", newSilverBalance: fresh.silverBalance, newGoldBalance: fresh.goldBalance };
  } finally {
    lock.releaseLock();
  }
}

function todayISO() {
  const d = new Date();
  return d.getFullYear() + "-" + String(d.getMonth()+1).padStart(2,"0") + "-" + String(d.getDate()).padStart(2,"0");
}

// ==========================================
// 📊 大盘聚合 / 图表数据 — 把前端的计算搬到这里
// ==========================================

// 失效 dashboard 缓存（写入数据后调用）
function invalidateDashboardCache(ss, dateStr) {
  try {
    const cache = CacheService.getScriptCache();
    const keys = ["dashboard_cache:all"];
    if (dateStr) {
      const ym = dateStr.substring(0, 7);
      keys.push("dashboard_cache:" + ym);
    }
    keys.forEach(k => cache.remove(k));
  } catch (e) {
    Logger.log("Cache invalidation failed: " + e.message);
  }
}

// 单次调用读完 3 张表，全在内存里派生
function buildDashboard(ss, ym) {
  // 短期内存缓存：同一个月在 5 分钟内直接返回，避免重复读表
  const CACHE_KEY = "dashboard_cache:" + (ym || "all");
  const CACHE_TTL = 5 * 60 * 1000; // 5 分钟
  try {
    const cache = CacheService.getScriptCache();
    const cached = cache.get(CACHE_KEY);
    if (cached) {
      const parsed = JSON.parse(cached);
      if (parsed.ts && (Date.now() - parsed.ts < CACHE_TTL)) {
        return parsed.data;
      }
      cache.remove(CACHE_KEY);
    }
  } catch (e) {
    Logger.log("Cache read failed: " + e.message);
  }

  const timeline = getSheetDataAsObjects(ss.getSheetByName("Timeline"));
  const evals    = getSheetDataAsObjects(ss.getSheetByName("Evaluations"));
  const logs     = getSheetDataAsObjects(ss.getSheetByName("Activity_Logs"));

  // 索引 Evaluations 按日期，便于 days 与 summary 复用
  const evalsByDate = {};
  evals.forEach(r => { if (r.Date) evalsByDate[r.Date] = r; });

  // 派生 dataRange（从实际存在的 Timeline 行计算 min/max，不写死年份）
  const dataRange = computeDataRange(timeline);

  // 如果调用方未传 ym，回退到最近月份（让首屏总能看到数据）
  if (!ym) ym = dataRange.maxYM || ymToday();

  const days          = consolidateTimeline(timeline, evalsByDate, logs, ym);
  const summary       = computeSummary(timeline, evals, logs);
  const monthSummary  = ym ? computeSummary(timeline, evals, logs, ym) : summary;
  const monthAverages = computeMonthAverages(days, ym);

  return { ym, dataRange, summary, monthSummary, monthAverages, days };
}

// 当年-月字符串（兜底用；getSheetDataAsObjects 已返回字符串日期）
function ymToday() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  return d.getFullYear() + "-" + m;
}

// Timeline 行 → { minYM, maxYM }；无数据时返回 null/null
function computeDataRange(timeline) {
  let min = null, max = null;
  timeline.forEach(r => {
    if (!r.Date) return;
    const ym = r.Date.substring(0, 7);
    if (!min || ym < min) min = ym;
    if (!max || ym > max) max = ym;
  });
  return { minYM: min, maxYM: max };
}

// 同一日期多行合并；附 Evaluations 字段；按桶累加 Activity_Logs 分钟数
// 策略：策略上每日只应有 1 行 timeline（写入侧已强约束），但读侧仍做防御性合并以兼容历史
// 数据（如 2026-06-27 的三行）；命中合并时记录警告便于追踪。
function consolidateTimeline(timeline, evalsByDate, logs, ym) {
  const days = {};
  const seenInYM = {}; // ym 范围内每个日期出现次数；>1 触发警告

  timeline.forEach(row => {
    if (!row.Date) return;
    if (ym && row.Date.substring(0, 7) !== ym) return;
    const d = row.Date;
    seenInYM[d] = (seenInYM[d] || 0) + 1;

    if (!days[d]) {
      days[d] = {
        date: d,
        dayType: row.Day_Type || "",
        startTime: row.Time_Start || "",
        endTime:   row.Time_End   || "",
        focusBlocks: 0,
        distractions: 0,
        eyeRestMinutes: 0,
        notes: [],
        absent: false,
        category: row.Category || ""
      };
    }
    const D = days[d];
    D.focusBlocks    += Number(row.Focus_Blocks)    || 0;
    D.distractions   += Number(row.Distractions)    || 0;
    D.eyeRestMinutes += Number(row.Eye_Rest_Minutes) || 0;

    // earliest non-zero start / latest non-zero end（字符串 HH:MM 比较即可）
    if (row.Time_Start && row.Time_Start !== "00:00") {
      if (!D.startTime || D.startTime === "00:00" || row.Time_Start < D.startTime) D.startTime = row.Time_Start;
    }
    if (row.Time_End && row.Time_End !== "00:00") {
      if (!D.endTime || D.endTime === "00:00" || row.Time_End > D.endTime) D.endTime = row.Time_End;
    }
    if (row.Note) D.notes.push(row.Note);
    if (String(row.Absent).toLowerCase() === "true" || row.Absent === true) D.absent = true;
  });

  // 累加 Activity_Logs.Duration 到对应日期的 bucketMinutes
  logs.forEach(l => {
    if (!l.Date || !days[l.Date]) return;
    const D = days[l.Date];
    if (!D.bucketMinutes) D.bucketMinutes = {};
    const b = bucketFor(l.Category);
    D.bucketMinutes[b] = (D.bucketMinutes[b] || 0) + (Number(l.Duration) || 0);
  });

  // 终结整理：附 Evaluations 字段、合并 note、确定 status
  Object.keys(days).forEach(d => {
    const D = days[d];
    D.note = D.notes.join(" · ");
    delete D.notes;

    const ev = evalsByDate[d];
    D.summary   = ev ? (ev.Summary    || "") : "";
    D.rating    = ev ? (ev.Rating     || "") : "";
    D.tokensNet = ev ? (Number(ev.Tokens_Net) || 0) : 0;
    D.status    = statusFromRating(D.rating, D.absent, D.focusBlocks, D.distractions);

    if (!D.bucketMinutes) D.bucketMinutes = {};
  });

  // 防御性合并若触发，记录警告（如历史 2026-06-27 三行）
  Object.keys(seenInYM).forEach(d => {
    if (seenInYM[d] > 1) {
      Logger.log("⚠️ Legacy multi-row timeline detected for " + d + " (" + seenInYM[d] + " rows); summed defensively. Consider consolidating in-sheet.");
    }
  });

  return days;
}

// rating 字段含 emoji → 状态色（无 eval 行回退到老规则）
function statusFromRating(rating, absent, blocks, dist) {
  if (absent) return "gray";
  if (typeof rating === "string" && rating) {
    if (rating.indexOf("🟢") !== -1) return "green";
    if (rating.indexOf("🟡") !== -1) return "amber";
    if (rating.indexOf("🔴") !== -1) return "red";
    if (rating.indexOf("⚪") !== -1) return "gray";
  }
  // legacy fallback — 仅当没有 eval 行时才走这里
  if (blocks === 0 || dist > 3) return "red";
  if (blocks >= 2 && dist <= 1) return "green";
  return "amber";
}

// 全期汇总：tokens 直接累加 Evaluations.Tokens_Net；小时数按桶折算
// 若传入 ym（如 "2026-06"），则只统计该月的数据
function computeSummary(timeline, evals, logs, ym) {
  // 如果传入了 ym，过滤数据只保留该月
  const inRange = (dateStr) => !ym || (dateStr && dateStr.substring(0, 7) === ym);

  let totalTokens = 0;
  // 仅计入 TOKEN_START_DATE 之后的 evaluations，与 getTokensData 保持一致
  evals.forEach(r => {
    if (r.Date && r.Date >= TOKEN_START_DATE && inRange(r.Date)) {
      totalTokens += Number(r.Tokens_Net) || 0;
    }
  });

  // 小时统计：通过 bucketFor 走 CATEGORY_BUCKETS → BUCKET_TO_CARD，
  // 新增类别只需在 CATEGORY_BUCKETS 和 BUCKET_TO_CARD 中各加一行即可生效。
  let focus = 0, activity = 0, coaching = 0, screen = 0, waste = 0;
  logs.forEach(row => {
    if (!inRange(row.Date)) return;
    const dur = Number(row.Duration) || 0;
    const slot = BUCKET_TO_CARD[bucketFor(row.Category)] || null;
    if (slot === "study") {
      const b = bucketFor(row.Category);
      if (b === "focus")    focus    += dur;
      if (b === "activity") activity += dur;
    } else if (slot === "coaching") coaching += dur;
    else if (slot === "screen")   screen   += dur;
    else if (slot === "waste")    waste    += dur;
    // null 槽位（eyerest）不计入任何卡
  });

  // 日期去重 → 工作日 / 周末计数（按非缺席 Timeline 行）
  const seen = {};
  let totalDays = 0, workdays = 0, weekends = 0;
  timeline.forEach(r => {
    if (!r.Date || seen[r.Date]) return;
    if (!inRange(r.Date)) return;
    seen[r.Date] = true;
    if (String(r.Absent).toLowerCase() === "true" || r.Absent === true) return;
    totalDays++;
    const dow = new Date(r.Date).getDay();
    if (dow === 0 || dow === 6) weekends++; else workdays++;
  });

  return {
    totalDays, workdays, weekends, totalTokens,
    studyHours:    +((focus + activity) / 60).toFixed(2),
    focusHours:    +(focus    / 60).toFixed(2),
    activityHours: +(activity / 60).toFixed(2),
    coachingHours: +(coaching / 60).toFixed(2),
    screenHours:   +(screen   / 60).toFixed(2),
    wasteHours:    +(waste    / 60).toFixed(2)
  };
}

// 当月日均小时（总体 / 工作日 / 周末）。Hours = focusBlocks * 0.5
function computeMonthAverages(days, ym) {
  let overallB = 0, wdB = 0, weB = 0;
  let overallC = 0, wdC = 0, weC = 0;

  Object.keys(days).forEach(d => {
    const D = days[d];
    if (D.absent) return;
    if (ym && d.substring(0, 7) !== ym) return;
    const dow = new Date(d).getDay();
    overallB += D.focusBlocks; overallC++;
    if (dow === 0 || dow === 6) { weB += D.focusBlocks; weC++; }
    else                        { wdB += D.focusBlocks; wdC++; }
  });

  const avg = (blocks, days) => days > 0 ? +((blocks * 0.5) / days).toFixed(1) : 0;
  return {
    overallHours: avg(overallB, overallC),
    workdayHours: avg(wdB, wdC),
    weekendHours: avg(weB, weC),
    dayCounts: { overall: overallC, workday: wdC, weekend: weC }
  };
}

// 图表端点：全期活动分布 + 90 天专注/分心趋势
function buildCharts(ss) {
  const timeline = getSheetDataAsObjects(ss.getSheetByName("Timeline"));
  const logs     = getSheetDataAsObjects(ss.getSheetByName("Activity_Logs"));

  // 分布：按 Stage_Name 累加 Duration，附 Category（取第一次出现的值）；降序
  const distMap = {};
  logs.forEach(l => {
    const name = l.Stage_Name || "未知";
    if (!distMap[name]) distMap[name] = { stage: name, minutes: 0, category: l.Category || "" };
    distMap[name].minutes += Number(l.Duration) || 0;
  });
  const items = Object.keys(distMap).map(k => distMap[k]).sort((a, b) => b.minutes - a.minutes);

  // 趋势：90 天滑窗，锚定 Timeline 最大日期（不依赖墙钟，便于回填）
  let maxDate = null;
  timeline.forEach(r => { if (r.Date && (!maxDate || r.Date > maxDate)) maxDate = r.Date; });
  if (!maxDate) maxDate = new Date().toISOString().substring(0, 10);

  const dailyFB = {}; // date → {focusBlocks, distractions}
  timeline.forEach(r => {
    if (!r.Date) return;
    if (!dailyFB[r.Date]) dailyFB[r.Date] = { focusBlocks: 0, distractions: 0 };
    dailyFB[r.Date].focusBlocks  += Number(r.Focus_Blocks)  || 0;
    dailyFB[r.Date].distractions += Number(r.Distractions)  || 0;
  });

  // 构建从 max-89 天到 max 的连续日期序列（补零）
  const points = [];
  const end = new Date(maxDate);
  for (let i = 89; i >= 0; i--) {
    const d = new Date(end);
    d.setDate(d.getDate() - i);
    const ds = d.toISOString().substring(0, 10);
    const v = dailyFB[ds] || { focusBlocks: 0, distractions: 0 };
    points.push({ date: ds, focusBlocks: v.focusBlocks, distractions: v.distractions });
  }

  // 7 日尾随平均（visualise improvement）
  const rolling7 = points.map((_, i) => {
    const slice = points.slice(Math.max(0, i - 6), i + 1);
    const n = slice.length;
    return {
      date: points[i].date,
      focusBlocks:  +(slice.reduce((s, p) => s + p.focusBlocks,  0) / n).toFixed(2),
      distractions: +(slice.reduce((s, p) => s + p.distractions, 0) / n).toFixed(2)
    };
  });

  return {
    distribution: { items },
    trend: {
      from: points[0].date,
      to:   points[points.length - 1].date,
      points,
      rolling7
    }
  };
}

// ==========================================
// 辅助工具：表格行转 JSON
// ==========================================
function getSheetDataAsObjects(sheet) {
  if (!sheet) return [];
  const range = sheet.getDataRange();
  // 获取显示值 (getDisplayValues)，它会原样读取表格里您肉眼看到的“10:18”，而不是读取它背后的时间戳
  const data = range.getDisplayValues(); 
  if (data.length < 2) return [];
  const headers = data[0];
  const rows = data.slice(1);
  
  return rows.map(row => {
    let obj = {};
    headers.forEach((header, index) => {
      obj[header] = row[index]; // 直接取显示出的字符串，不经过任何 Date 解析
    });
    return obj;
  });
}

function initEmmaDatabase() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // 1. 初始化 Activity_Logs
  let logSheet = ss.getSheetByName("Activity_Logs") || ss.insertSheet("Activity_Logs");
  logSheet.getRange(1, 1, 1, 7).setValues([["Date", "Stage_Name", "Start_Time", "End_Time", "Duration", "Category", "Note"]]);
  logSheet.setFrozenRows(1);

  // 2. 优化 Timeline 表头（如果还没设）
  let tSheet = ss.getSheetByName("Timeline");
  if(tSheet) tSheet.setFrozenRows(1);

  // 3. 优化 Evaluations 表头
  let eSheet = ss.getSheetByName("Evaluations");
  if(eSheet) eSheet.setFrozenRows(1);

  // 4. Transactions 表（金币 / 银币流水）
  initTransactionsSheet(ss);

  // 5. RedeemItems 表（兑换商店配置）
  initRedeemItemsSheet(ss);

  SpreadsheetApp.getUi().alert("Emma 数据库结构已自动初始化完毕！");
}

// 创建（若不存在）并初始化 Transactions 表
function initTransactionsSheet(ss) {
  let sheet = ss.getSheetByName("Transactions") || ss.insertSheet("Transactions");
  const headers = ["Date", "Type", "Description", "Silver_Delta", "Gold_Delta", "Silver_Balance", "Gold_Balance", "Note"];
  // 仅当首行尚未含完整表头时刷新（避免每次 init 都清空数据）
  const first = sheet.getRange(1, 1, 1, headers.length).getDisplayValues()[0];
  const needsHeader = headers.some((h, i) => first[i] !== h);
  if (needsHeader) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold").setBackground("#fef3c7");
  }
  sheet.setFrozenRows(1);
}

// 创建（若不存在）并初始化 RedeemItems 表，并写入种子数据（若为空表）
function initRedeemItemsSheet(ss) {
  let sheet = ss.getSheetByName("RedeemItems") || ss.insertSheet("RedeemItems");
  const headers = ["ItemId", "Label", "Description", "CoinType", "Cost", "Active", "Sort"];
  const first = sheet.getRange(1, 1, 1, headers.length).getDisplayValues()[0];
  const needsHeader = headers.some((h, i) => first[i] !== h);
  if (needsHeader) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold").setBackground("#dbeafe");
  }
  sheet.setFrozenRows(1);

  // 仅在表中无数据行时写入种子项目
  if (sheet.getLastRow() < 2) {
    const seeds = [
      ["switch_30m",  "🕹️ Switch 30 分钟",   "畅玩 30 分钟大作",      "silver", 1, true, 10],
      ["netflix_30m", "🎬 Netflix 30 分钟",  "轻松漫游 30 分钟",      "silver", 1, true, 20],
      ["snack",       "🍦 一份零食",         "犒劳一下自己",          "silver", 1, true, 30],
      ["switch_1h",   "🎮 Switch 1 小时",   "深度沉浸 1 小时",       "gold",   1, true, 100],
      ["movie",       "🎬 完整电影一部",     "约 2 小时电影时光",     "gold",   1, true, 110],
      ["outing",      "🏞️ 周末外出活动",     "公园 / 商场 / 朋友家",  "gold",   1, true, 120]
    ];
    seeds.forEach(row => sheet.appendRow(row));
  }
}