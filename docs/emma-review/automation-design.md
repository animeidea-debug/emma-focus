# Emma Review 每日视频流程

## 目标与边界

Emma Review 对每天的一份书房成品 `Study_YYYYMMDD.mp4` 生成可审核候选。
Video Merge 负责发布 ready 信号；本地流水线负责抽帧、观察、确定性聚合、JSON
校验和 `pending_review` 元数据。Pushover 只通知家长，不作为机器间消息总线。

视频、抽帧、模型原始响应、日期级结果、家长反馈和身份参考图都属于敏感家庭
数据，必须保留在 Git 外。模型、脚本和无人值守任务不得持有家长 PIN，也不得
直接写入生产数据库。

## Ready 契约

每日生产者必须按以下顺序发布：

1. ffmpeg 写入 `Study_YYYYMMDD.part.mp4`；
2. ffprobe 确认容器可读取且文件非空；
3. 在同一目录原子改名为 `Study_YYYYMMDD.mp4`；
4. 原子写入 `.ready/Study_YYYYMMDD.ready.json`；
5. 发送完成通知。

自动化以 matching ready manifest 为唯一机器信号。消费者必须核对视频文件名、
日期、字节数、相机标识和 manifest 路径。`audit_date` 可为 `YYYY-MM-DD` 或
`YYYYMMDD`，但必须与目标日期完全一致。

历史视频没有 ready manifest 时，只有家长明确确认后才能使用
`--allow-legacy-stable`；日常运行不得自动退回该模式。

## 状态机

```text
waiting_for_ready
  → prepared
  → extracting
  → coarse_classified
  → boundary_review
  → validated
  → pending_review
  → approved
  → submitted
```

失败进入 `failed`，记录视频指纹、失败原因、重试次数和最后成功阶段。同一日期与
同一视频指纹的重跑必须复用缓存；同一结果哈希不得重复写入。

## 本地视觉流水线

- 抽帧、场景过滤和 OSD 裁剪只生成本地临时产物；
- 每组画面同时进行人物/人数/直接辅导/屏幕交互/基础活动等窄观察；
- OSD 是阶段起止时间的主要来源。OSD 缺失、倒退或观察间隔超过安全范围时，
  不生成新候选；
- Python 按明确优先级合并阶段，计算 Focus Blocks、Distractions、Tokens 和
  Rating，并运行严格 JSON 校验；
- 候选写为 `pending_review`，最终入库必须由家长在 Admin 审核确认。

当前本地模型适合粗观察，不足以可靠完成身份、Screen 和 Coaching 的最终判断。
低置信度或冲突区间可交由第二个本地模型或已批准的云端模型复核；无论模型来源，
均不得绕过家长审核。

## 本机运行

```sh
EMMA_VIDEO_DIR="/path/to/export_videos/书房" \
EMMA_REVIEW_MODEL="/path/to/local-model" \
sh run_tonight.sh YYYY-MM-DD
```

运行器会将视频和 matching ready manifest 复制到本地缓存，再调用流水线。它不
接收 PIN、不调用生产 API；输出是本地候选 JSON 与 review metadata。

## 每日自动触发与通知

截至 2026-08-01，最近 6 个正常逐日 ready 时间为 22:34、22:36、22:38、
22:44、22:44 和 22:59；一次 22:00 批量记录是历史清单补写，不代表日常完成
时间。默认自动窗口据此设为每天 22:30–00:00，每 60 秒只检查当天书房
`Study_YYYYMMDD.ready.json`。窗口结束仍未 ready 时停止，并发送一次失败通知。

```sh
EMMA_VIDEO_DIR="/path/to/export_videos/书房" \
EMMA_REVIEW_MODEL="/path/to/local-model" \
EMMA_REVIEW_WAIT_SECONDS=5400 \
EMMA_REVIEW_POLL_SECONDS=60 \
sh run_ready_review.sh YYYY-MM-DD
```

触发器会把结果保存在视频目录旁的 Git 外 `.emma-review/DATE/`，并在同一视频
已有可验证的 `pending_review` 候选时跳过昂贵的重复分析。成功通知只报告汇总
和“待家长复核”；失败通知说明是未 ready 还是分析失败。两者都不会提交生产。

Codex 每日任务只负责在 22:30 启动上述本机触发器。Pushover 的 Video Merge
通知仍是给家长看的即时确认，不作为程序输入；即使通知延迟或丢失，matching
ready manifest 仍可可靠启动分析。

本机 Codex 自动任务 `Emma Review 书房视频候选` 已启用。它只运行当前工作区的
只读候选流程，不提交、部署或改写生产数据；任务是否启用和时间调整由 Codex
应用的 Automations 页面管理。

## 验收门槛

在缩小人工审核或讨论自动导入前，必须在多日人工金标准上验证：

- 身份与观察过滤不把成人单独或不确定片段算入 Emma；
- Focus、Distractions、Tokens 与人工审核一致；
- 关键边界使用 OSD 且误差在预先约定范围内；
- 低置信度、失败和异常全部停在 `pending_review` 或 `failed`；
- 重跑不重复写入，缓存、备份与回滚路径可验证。
