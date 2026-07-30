# Emma Focus — 项目进度

> 当前交接快照。长期规则见 `AGENTS.md`，稳定产品和操作说明见 `README.md`。
> 日期级视频、审计结果、家长反馈和生产数据不进入本文件。
> 最后更新：2026-07-31

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
- Codex morning-brief 插件 v0.1.1：ZConnect 重定向检测、LAN HTTP 支持、scoped read token；
- GitHub Action 自动同步 morning-brief 插件到 family marketplace；
- 07-30 首次完整实战：pipeline 候选 → 家长审核修正 → 提交入库 → 写入 parent feedback。

## 安全与发布边界

- 模型、Skill 和无人值守脚本不得获得家长 PIN 或生产写权限；
- 所有候选都必须经 Admin 家长审核后才可入库；
- 部署使用 NAS 的完整 SHA 发布流程；不要从本仓库改动 Compose、nginx 或 NAS cron；
- 视频、数据库、导出、家长反馈、身份参考图和模型原始输出均在 Git 外；
- `deprecated/` 仅作历史参考，任何改动必须单独确认归属。

## 当前重点

1. 连续积累人工审核样本（已有 2026-07-28 和 07-30 两天 parent feedback）；
2. 完成缓存/状态机和 Pushover 候选完成或失败通知；
3. 根据 accumulated feedback 量化流水线对身份、Screen、Coaching 的准确率；
4. Emma Mac 端 pull 最新代码后在内网完成 morning-brief token 配置；
5. 为代币记账、评估改写、兑换、备份和恢复补齐可重复测试；
6. 审查所有状态变更 API 的认证与外网暴露边界。

## 已知问题

- 本地 7B 模型无法可靠区分"家长在旁独立学习"vs"家长辅导"（Coaching 漏判/误判）；
- 妈妈在远处桌子时偶尔被模型误判为 Emma 使用屏幕（身份/位置混淆）；
- 短于 30 分钟的独立学习段会被规则降级为 Distraction，但家长有时认为这些也应算 Focus；
- Eye Rest 与 Activity（整理东西）的区分不准确。

## 操作入口

- 规则与校验：`skills/emma-review/`；
- 每日流程：`docs/emma-review/automation-design.md`；
- 集成边界：`docs/emma-review/integration.md`；
- Work 交接：`docs/emma-review/work-handoff.md`；
- 部署和恢复：`README.md` 与 NAS 仓库的 `nas-deploy` 文档；
- Morning brief 配置：`docs/runbooks/configure-emma-focus-morning-brief.md`；
- Morning brief 设计决策：`docs/decisions/agent-morning-brief-integration.md`；
- 每晚视频分析：`EMMA_VIDEO_DIR=... EMMA_REVIEW_MODEL=... sh run_tonight.sh YYYY-MM-DD`。
