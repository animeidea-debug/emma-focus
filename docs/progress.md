# Emma Focus — 项目进度

> 当前交接快照。长期规则见 `AGENTS.md`，稳定产品和操作说明见 `README.md`。
> 日期级视频、审计结果、家长反馈和生产数据不进入本文件。

## 项目状态

Emma Focus 是私有家庭专注力工具：原生 HTML 前端、FastAPI/SQLite 后端、NAS
视频合成，以及候选式 Emma Review 流程。生产数据在 NAS 持久卷中；NAS 仓库
拥有 Compose、nginx、共享挂载和 cron。

当前主线已具备：

- 家长审核的评估、代币、兑换和备份能力；
- Video Merge 原子发布与 matching ready manifest；
- 本地 Emma Review 候选流水线、严格 JSON 校验与 `pending_review` metadata；
- ready manifest 同时兼容 ISO 和紧凑日期；
- 安全的本地候选运行器（`run_tonight.sh`），默认拒绝未 ready 视频；
- GitHub SSH 与统一 `AGENTS.md` / `README.md` / `docs/progress.md` 文档规范；
- Codex morning-brief 插件已安装，focus-brief 后端已部署；
- **morning-brief ZConnect 重定向问题已修复**：configure.mjs 现在检测
  重定向并提示使用 LAN URL；MCP 服务器增加了 LAN HTTP 支持和重定向检测。

## 安全与发布边界

- 模型、Skill 和无人值守脚本不得获得家长 PIN 或生产写权限；
- 所有候选都必须经 Admin 家长审核后才可入库；
- 部署使用 NAS 的完整 SHA 发布流程；不要从本仓库改动 Compose、nginx 或 NAS cron；
- 视频、数据库、导出、家长反馈、身份参考图和模型原始输出均在 Git 外；
- `deprecated/` 仅作历史参考，任何改动必须单独确认归属。

## 当前重点

1. **在家长 Mac 的 LAN 环境下完成 morning-brief token 配置**：
   ```sh
   node plugins/emma-focus-morning-brief/scripts/configure.mjs \
     --base-url http://192.168.6.108:8888/api/poc
   ```
   ZConnect 外网 URL 会拦截 CLI 请求并重定向到极空间网页，必须用内网 IP。
2. 连续积累人工审核样本，量化本地候选对身份、Screen、Coaching、Eye Rest 和阶段边界的偏差；
3. 完成缓存/状态机和 Pushover 候选完成或失败通知；
4. 只对低置信度片段评估第二本地模型或云端复核；
5. 为代币记账、评估改写、兑换、备份和恢复补齐可重复测试；
6. 审查所有状态变更 API 的认证与外网暴露边界。

## 操作入口

- 规则与校验：`skills/emma-review/`；
- 每日流程：`docs/emma-review/automation-design.md`；
- 集成边界：`docs/emma-review/integration.md`；
- Work 交接：`docs/emma-review/work-handoff.md`；
- 部署和恢复：`README.md` 与 NAS 仓库的 `nas-deploy` 文档；
- Morning brief 配置：`docs/runbooks/configure-emma-focus-morning-brief.md`；
- Morning brief 设计决策：`docs/decisions/agent-morning-brief-integration.md`。
