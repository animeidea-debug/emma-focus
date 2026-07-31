# Emma Focus - 项目进度

> 当前交接快照。长期规则见 `AGENTS.md`，稳定产品和操作说明见 `README.md`。
> 日期级视频、审计结果、家长反馈和生产数据不进入本文件。
> 最后更新：2026-08-01

## 项目状态

Emma Focus 是私有家庭专注力工具：原生 HTML 前端、FastAPI/SQLite 后端、NAS
视频合成，以及候选式 Emma Review 流程。生产数据在 NAS 持久卷中；NAS 仓库
拥有 Compose、nginx、共享挂载和 cron。

当前主线已具备：

- 家长审核的评估、代币、兑换和备份能力；
- Video Merge 原子发布与 matching ready manifest；
- 本地 Qwen2.5-VL-7B-4bit 视觉候选流水线、严格 JSON 校验、`pending_review` metadata；
- ready manifest 同时兼容 ISO 和紧凑日期；
- 安全的本地候选运行器（`run_tonight.sh`），默认拒绝未 ready 视频；
- parent feedback 闭环：流水线自动加载之前日期的家长修正经验作为 VLM 提示词；
- GitHub SSH 与统一 `AGENTS.md` / `README.md` / `docs/progress.md` 文档规范；
- 07-30 首次完整实战：pipeline 候选 -> 家长审核修正 -> 提交入库 -> 写入 parent feedback。
- 代币规则变更（2026-08-01，已追溯）：`Tokens_Net = Focus_Blocks - Distractions`，
  每次分心扣 1 银币（旧规则为每 3 次分心扣 1）。Rating 阈值（Distractions>=3
  或 Tokens_Net<0 为 🔴危险）不变。已在 NAS 用 `nas-deploy emma-focus --ref
  ede13fa` 发布，并对全部 69 个历史日期幂等重算 `derive_transactions`，其中 25
  天银币余额变化；追溯后余额 Silver=48 Gold=18。发布前自动备份位于
  `/app/backups/releases/emma-pre-release-20260731-235434.db`。
- 07-31 第二次实战：Qwen2.5-VL-7B 候选 -> 家长修正（过度合并 195min/106min Focus、
  晚间 108min 与 21 点段为假阳性）-> 提交入库（FB=3 Dist=4 TN=-1 🔴），并写入
  7 条 parent feedback。

### 插件合并 (2026-07-31)

- `emma-focus-morning-brief` 已与 `tmos-morning-brief` 合并为统一的
  `emma-daily-brief` 插件，存放在 marketplace 仓库
  (`animeidea-debug/codex-family-marketplace`, commit `1f77e3e`)。
- 合并后的插件提供 3 个 MCP 工具：`check_connection`（双源连接检查）、
  `get_tmos_brief`（TMOS 每日数据）、`get_focus_brief`（Emma Focus 每日数据）。
- 已从本仓库删除 `plugins/emma-focus-morning-brief/` 源码目录和
  `.github/workflows/sync-to-marketplace.yml` 同步 Action——合并后的插件
  仅存在于 marketplace 仓库，不再从产品仓库自动同步。
- `emma-daily-brief@family` v1.0.0 已在 Gary 的 Mac 安装启用。

## 安全与发布边界

- 模型、Skill 和无人值守脚本不得获得家长 PIN 或生产写权限；
- 所有候选都必须经 Admin 家长审核后才可入库；
- 部署使用 NAS 的完整 SHA 发布流程；不要从本仓库改动 Compose、nginx 或 NAS cron；
- 视频、数据库、导出、家长反馈、身份参考图和模型原始输出均在 Git 外；
- `deprecated/` 仅作历史参考，任何改动必须单独确认归属。

## 当前重点

1. 连续积累人工审核样本（已有 07-28、07-30、07-31 三天 parent feedback）；
2. 完成缓存/状态机和 Pushover 候选完成或失败通知；
3. 重点修正 07-31 暴露的过度合并问题：超长 Focus/Distraction 块（>90min
   跨午休、>100min"碎片学习"）必须在长时间空档、成人活动变化处拆分；晚间
   低光/局部画面身份误判为假阳性，需多线索确认身份；
4. 根据 accumulated feedback 量化流水线对身份、Screen、Coaching 的准确率；
5. Emma Mac 端迁移到 `emma-daily-brief`：卸载旧插件 -> 升级 marketplace ->
   安装 `emma-daily-brief@family` -> 在内网运行 `configure.mjs`；
6. 评估 `zspace-docker` 插件用于只读检查 `site_backend`（ps/logs/stats）
   和受控 `web` 部署；需先完成 zspace-nas runtime 的 venv setup；
7. 审查所有状态变更 API 的认证与外网暴露边界。

## 已知问题

- 本地 7B 模型无法可靠区分"家长在旁独立学习"vs"家长辅导"（Coaching 漏判/误判）；
- 妈妈在远处桌子时偶尔被模型误判为 Emma 使用屏幕（身份/位置混淆）；
- 短于 30 分钟的独立学习段按规则降级为 Distraction（家长确认该规则执行）；
- 流水线倾向于把带成人在场的长段合并成一个超大 Focus（出现过 195min、106min），
  无法可靠切出其中的 Coaching、休息和 Screen；
- 晚间/低光下会把空房间或他人误判为 Emma，产生长段假阳性 Distraction；
- 学习相关的屏幕查阅应并入相邻 Focus，但模型常把它切成独立 Screen；
- Eye Rest 与 Activity（整理东西）的区分不准确。

## 操作入口

- 规则与校验：`skills/emma-review/`；
- 每日流程：`docs/emma-review/automation-design.md`；
- 集成边界：`docs/emma-review/integration.md`；
- Work 交接：`docs/emma-review/work-handoff.md`；
- 部署和恢复：`README.md` 与 NAS 仓库的 `nas-deploy` 文档；
- Daily brief 配置：marketplace 仓库 `plugins/emma-daily-brief/scripts/configure.mjs`；
- Daily brief 设计决策：`docs/decisions/agent-morning-brief-integration.md`；
- 每晚视频分析：`EMMA_VIDEO_DIR=... EMMA_REVIEW_MODEL=... sh run_tonight.sh YYYY-MM-DD`。
