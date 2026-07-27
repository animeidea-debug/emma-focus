# Emma Focus — 项目进度

> 项目状态文档，跨机器共享。克隆到任何设备后先读此文件了解当前状态。

## 项目概览

亲子专注力管理系统，追踪和激励孩子的学习专注力。
- **前端看板**：`index.html`（NAS nginx）
- **后端**：FastAPI + SQLite（本地容器 `site_backend`，替代 GAS）
- **NAS 视频处理**：`merge_v2.sh` → ffmpeg + QSV 加速

## 当前状态（2026-07-27）

> 最近一次完整学习与验证后的快照。详见下方各章节。

**已提交并推送（HEAD = `0cb59c4`，已在 origin/main）：**
- Emma Review 仓库级 Skill（`skills/emma-review/`）、13 岁统一 Prompt、严格 JSON 校验器与 7 项单元测试
- Video Merge ready 契约：书房视频先写 `.part.mp4`、ffprobe 校验、原子发布、写 `.ready` 清单后再发完成通知
- Work 交接文档、自动化设计文档、集成说明
- `gemini_prompt.md` 收敛为指向唯一真源 `skills/emma-review/references/audit-prompt.md`

**已验证（本地静态 + 单元测试全部通过）：**
- `bash -n` / `py_compile` / `git diff --check` ✅
- `tests/test_emma_review_skill.py` 7 项 ✅
- `tests/test_poc_business.py` 6 项 ✅

**已就绪但尚未验证的本地资源（不在 Git 中）：**
- `.venv-emma-review/`：uv 创建的 MLX-VLM 隔离环境（mlx-vlm 已安装）
- `~/Library/Caches/emma-review/models/Qwen3-VL-4B-Instruct-4bit/`：4B 量化模型已完整下载（~2.9 GB），尚未在真实 GPU 会话中加载或基准测试

**未提交的工作区改动：**
- `deprecated/infra/watchtower/docker-compose.yml`（1 行，deprecated 区，待确认是否回滚）
- `Emma_Audit_Directive_v5.5_for_Skill.md`（根目录指令文件，untracked）
- `docs/[Emma_Focus]_2026-07-27_2026-07-.md`（历史对话记录，untracked）

**下一步（按原对话计划）：**
1. ✅ 将 ready 契约部署到 NAS 并验证 — NAS 已运行 `0cb59c4`，`merge_v2.sh` 含完整 ready 逻辑
2. ✅ MLX-VLM 环境与 Qwen3-VL 4B 模型就绪 — 10 个核心包已装，2.9 GB 模型完整下载
3. ⏳ 用 2026-07-26 金标准样本跑兼容性、耗时与内存基准 — 脚本已写好，需桌面终端运行

**立即可做（需真实 Mac GPU，Codex 沙箱无 Metal 设备）：**
```sh
.venv-emma-review/bin/python skills/emma-review/scripts/benchmark_local_vision.py   --video "/Volumes/nvme14-139XXXX2622/export_videos/书房/Study_20260726.mp4"   --gold  "/Volumes/nvme14-139XXXX2622/export_videos/书房/.emma-review/2026-07-26/result.json"
```

## 关键服务

| 服务 | 内网地址 | 外网地址 | 说明 |
|------|---------|---------|------|
| nginx 前端 | `http://192.168.6.108:8888` | ZConnect Funnel | `index.html` + `admin.html` |
| 后端 API | `http://192.168.6.108:8888/api/poc/` | 同上 | FastAPI + SQLite |
| WebDAV 部署 | `http://192.168.6.108:8889` | Tailscale Funnel | 脚本/HTML/后端同步 |
| 远程桌面 | `ssh -p 10000` | Tailscale SSH | 用户名 `13918962622` |

## 架构说明

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  浏览器访问   │────▶│  nginx (8888) │────▶│ site_backend │
│ index.html   │     │  site_front  │     │ port 80:     │
│ admin.html   │     │              │     │   main.py    │
│              │     │ /api/poc/ →  │     │   (avatar)   │
│              │     │ port 81      │     │ port 81:     │
│              │     │ /api/ →      │     │   poc_main   │
│              │     │ port 80/api  │     │   (业务逻辑)  │
└─────────────┘     └──────────────┘     └─────────────┘
```

**⚠️ nginx + docker-compose 由 NAS 项目（`~/Desktop/NAS`）统一管理，不要在此项目修改。**

## 组件状态

| 组件 | 位置 | 状态 | 最后部署 | 部署方式 |
|------|------|------|---------|----------|
| **本地后端** | `NAS/infra/web/backend/poc_main.py` | ✅ 运行中 | 2026-07-14 | `sh ~/Desktop/NAS/deploy/deploy.sh web` |
| **前端看板** | `index.html` | ✅ 运行中 | 2026-07-14 | `sh deploy/deploy.sh` |
| **管理后台** | `admin.html` | ✅ 运行中 | 2026-07-14 | `sh deploy/deploy.sh` |
| **数据备份** | `infra/web/backend/backup_data.py` | ✅ SQLite 一致性快照 + CSV | 2026-07-17 | NAS 用户 cron → docker exec |
| **GAS 后端** | `gas/emma_focus_api.gs` | ⏹️ 已退役 | 2026-07-14 | 不再使用 |
| **V2 通用脚本** | `merge_v2.sh` / `run_v2.sh` | ✅ 运行中（ready 契约已提交待部署） | 2026-07-14 | `nas-deploy emma-focus --latest` |
| **Pushover 通知** | `notify.sh` + MCP server | ✅ 运行中 | — | Keychain + `.env` |
| **Emma Review Skill** | `skills/emma-review/` | ✅ 已提交 | 2026-07-27 | 已在 origin/main，待 NAS release |
| **本地视觉模型** | `.venv-emma-review/` + Qwen3-VL-4B | ⏳ 已下载待验证 | 2026-07-27 | 真实 Mac 会话基准测试 |
| **基础设施** | `NAS/infra/web/` | ✅ NAS 项目管理 | 2026-07-14 | `cd ~/Desktop/NAS && sh deploy/deploy.sh web` |

## 摄像头配置

| 名称 | 型号 | 源目录 | 输出目录 | 编码 |
|------|------|--------|---------|------|
| 书房 Study | 小米新款 | `/mnt/source_study` | `export_videos/书房/` | hevc_qsv |
| 客厅 LivingRoom | 小米4 4K | `/mnt/source_videos_livingroom` | `export_videos/客厅/` | hevc_qsv |

> 所有脚本使用 `-2:HEIGHT` 保持宽高比，Intel N100 QSV 硬件加速。

## 备份策略（三层保障）

> **核心原则：数据在外，容器在内。** 所有生产数据必须从容器外持久化。

| 层 | 方法 | 频率 | 存储位置 | 历史 |
|----|------|------|---------|------|
| **L0: Volume 映射** | docker-compose volume 将容器 /app/data → NAS 宿主机 | 实时 | NAS 宿主机 `/tmp/.../data/docker/backend/data/` | 容器重启不丢失 |
| **L0b: XLSX 同步** | `deploy.sh` 将本地 `Emma_Focus_DB.xlsx` 同步到 NAS | 每次部署 | NAS 宿主机 `.../data/backups/emma_data/` | 随部署更新 |
| **L1: SQLite 快照** | 容器内 Python SQLite Backup API 创建一致性数据库备份 | 每日 08:00 + 20:00 | 专用挂载 `/app/backups` → `.../data/backups/emma_data/YYYYMMDD/` | 保留 30 天 |
| **L2: CSV 导出** | `backup_data.sh` 导出各表为 CSV（可读性备用） | 同上 | 同上 | 保留 30 天 |

### 灾难恢复 SOP

```
场景 A: 容器内数据损坏但 volume 正常
  → 停止容器 → 删除容器内 /app/data/poc.db → 重启容器
  → 数据库由 volume 上的文件自动重建 ✅

场景 B: Volume 上的数据也被损坏
  → 从 /data/backups/emma_data/ 选择最近的 poc.db
  → 复制到 /tmp/.../data/docker/backend/data/
  → 重启容器 ✅

场景 C: 所有数据库文件丢失，但有 XLSX
  → 从 /data/backups/emma_data/Emma_Focus_DB.xlsx
  → 在本地执行: python3 deploy/import_xlsx_to_sqlite.py <xlsx> [db]
  → 上传到 NAS + 重启容器 ✅
```

## 关键决策记录

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-07-14 | **🏗️ 本地后端替换 GAS** | GAS 有限额和延迟；本地 FastAPI+SQLite 20ms 响应 |
| 2026-07-14 | **🗄️ 数据迁移 GAS→SQLite** | 52 天 + 222 日志 + 64 交易成功迁移 |
| 2026-07-14 | **🔧 docker-compose 由 NAS 项目统一管理** | deploy.sh 移除 compose 操作，调用 `../NAS/deploy/deploy.sh web` |
| 2026-07-14 | **⏱️ nginx proxy_read_timeout 120s** | 解决 ZConnect 外网首次加载 504 |
| 2026-07-14 | **🔐 数据持久化 + 三层备份策略** | P0 事故后重建，V=A volume 映射消除容器内数据，增加 SQLite 快照和 XLSX 同步 |
| 2026-07-17 | **📦 基础设施单一真源完成** | WebDAV/Tdarr Compose 与 NAS 仓库核对；`/data/backups` 挂载迁移至 NAS，Emma Focus 重复副本删除 |
| 2026-07-17 | **🔔 Pushover 通知闭环** | 保留总任务及分摄像头启动通知；部分失败正确告警；22:05 未启动看门狗；备份 cron 补齐成功/失败通知 |
| 2026-07-17 | **🛡️ NAS 通知可靠性收口** | NAS 统一通知库负责超时/重试/API 回执/JSONL 日志；Heartbeat 首次失败、第三次升级与恢复去重；23:10 每日摘要；应用部署禁止覆盖通知库 |
| 2026-07-17 | **🔒 跨项目备份/密钥契约** | 生产备份统一使用 `/app/backups`；NAS UID 1002 cron 管理 08:00/20:00；Emma 部署永不覆盖远端 `.env` |
| 2026-07-26 | **👁️ 取消护眼代币奖励** | 护眼分钟继续用于活动记录与图表，但不再产生银币；一次性迁移删除历史 `eyerest_silver` 流水并重算余额 |
| 2026-07-27 | **🤖 Emma Review 仓库级 Skill** | Work 与 Codex 共享同一规则、13 岁身份提示和严格 JSON 校验器；模型结果先校验、家长复核，禁止直接携带 PIN 写生产 |
| 2026-07-27 | **✅ Emma Review 首次生产闭环** | 2026-07-26 Work JSON 经严格校验、备份、家长隐藏 PIN 授权后通过内网 API 入库；回读确认 12 个阶段和 +1 银币，原兑换流水未变 |
| 2026-07-27 | **🎬 Emma Review ready 契约** | 书房视频改为临时文件编码、ffprobe 校验、原子发布、日期级 ready 清单后再发完成通知；自动分析读取清单而不抓取 Pushover |
| 2026-07-28 | **🏷️ 品牌升级为「时光当铺」** | 前端页面更名为时光当铺，导航栏、标题、副标语统一更新；通过 `nas-deploy` 部署（17/17 tests ✅） |
| 2026-07-28 | **🐛 银币奖励不依赖 Gemini tokens_net** | `derive_transactions` 改为后端独立计算 `silver_award = focus_blocks - (distractions // 3)`，修正 Gemini 可能设错 tokens_net=0 导致银币未发放的问题 |
| 2026-07-27 | **🖥️ 本地视觉模型基准** | 4B@384px 可粗筛（4.6GB）；8B@384px 理解力更强（7.28GB，24GB Air 可运行）；两者均无法准确分类活动，验证需 Python 确定性计算 |
| 2026-07-22 | **⭐ TMOS 奖励与头像统一** | TMOS 星星/等级使用幂等事件账本；银币金币继续写入 Emma `token_transactions`；头像与等级边框在两端统一展示 |
| 2026-07-22 | **🧾 TMOS 奖励三层账本** | 奖励事实、币结算、Emma 钱包交易通过唯一 settlement ID 关联；Emma 可筛选 TMOS 交易并展开原始奖励，冲正保留完整链路 |
| 2026-07-22 | **🛡️ 共享 backend 部署边界** | Emma 后端改为非删除式 `rclone copy`；禁止在共享 `/docker/backend` 根目录使用 `sync`，避免删除 TMOS/FTF 及持久化目录 |
| 2026-07-13 | 🔄 infra 管理迁移到 NAS 项目 | deploy.sh 移除 docker compose 同步 |
| 2026-07-09 | 🔧 nginx 多项目隔离 | Family Time Flow 项目覆盖首页 |
| 2026-07-09 | 🏗️ clinerules 迁移到 infra-template | 统一管理共享 Cline 规则 |

## 最近提交

| 日期 | Commit | 说明 | 涉及文件 |
|------|--------|------|---------|
| 2026-07-27 | `0cb59c4` | 🤖 Emma Review 工作流 + video ready 清单 | `skills/`, `.agents/`, `docs/emma-review/`, `merge_v2.sh`, `run_v2.sh`, `admin.html`, 测试 |
| 2026-07-26 | `2a6502f` | 🔀 Merge PR #7：取消护眼代币奖励 | `poc_main.py`, `index.html`, `admin.html` |
| 2026-07-26 | `1524fe5` | 👁️ 删除护眼代币奖励并回收历史流水 | `poc_main.py`, `index.html`, `admin.html` |
| 2026-07-24 | `e41398b` | 📦 文档化 NAS release 部署契约 | `README.md`, `docs/progress.md` |
| 2026-07-22 | `8efc4b9` | ⭐ TMOS 钱包交易来源展示 | `index.html`, `poc_main.py` |
| 2026-07-22 | `b786807` | 📊 统一 TMOS 成长档案 | `index.html`, `poc_main.py` |
| 2026-07-14 | `8a32670` | 🧹 清理退役文件+统一基础设施管理 | `deprecated/`, `admin.html`, `README.md`, `.clinerules` |
| 2026-07-14 | `8255704` | 🔧 docker-compose 持久化 poc.db | `docker-compose.yml`, `backend/data/` |
| 2026-07-14 | `f24cb39` | 📝 .clinerules: GAS退役 | `.clinerules` |
| 2026-07-14 | `2ba9f2c` | 📝 文档+备份更新: GAS→SQLite | `backup_data.sh`, `README.md`, `docs/progress.md` |
| 2026-07-14 | `c89422e` | 🏗️ Phase 1: 本地后端迁移完成 | `poc_main.py`, `index.html`, `admin.html`, `deploy.sh` |

## 部署流程（重要！）

### NAS Git release（正式路径）
```sh
nas-deploy emma-focus --ref <完整的40位提交SHA>
nas-deploy status
```

NAS 仓库拥有统一 `nas-deploy` runner、Compose、release symlink、数据库备份、
健康检查和回滚。Emma Focus 仓库仍拥有产品网页、Python 后端和视频脚本源码。
`.env`、Pushover 通知库和生产数据库不会随 release 覆盖。原 WebDAV 脚本仅
作为迁移期应急路径保留。

## 数据备份

每天 08:00 和 20:00 由 NAS 仓库管理的 UID 1002 用户 crontab 执行 `docker exec site_backend python3 /app/backup_data.py`：
- **L1**: `sqlite3 .backup` 完整数据库文件快照（一致性）
- **L2**: CSV 导出各表（可读性备用）
- 保留最近 30 天历史
- 每次部署时自动同步本地 XLSX 到 NAS 备份目录

## 已知问题 / 事故记录

### 2026-07-19：cron shell 不兼容——NAS 统一 notify.sh 导致所有通知相关定时任务静默失败
- **类型**：⚠️ **P1 事故**（非数据丢失，但核心运维通知链路完全中断约 48 小时）
- **原因**：Codex 在 `codex/pushover-notification-hardening` 分支（NAS 仓库）创建了统一版 `notify.sh`（`#!/bin/bash`，使用 `local`、`BASH_SOURCE`、`args+=()` 等 bash-only 语法），并通过 NAS deploy 同步到生产。但 cron 表中 3 个 Emma Focus 脚本仍用 `/bin/sh` 执行，source notify.sh 时直接崩溃。
- **cron 运行用户**：`13918962622`（UID 1002），NAS 标准运维用户，非 root。cron daemon 以 root 启动但按 UID 1002 执行任务。
- **影响**：
  - `run_v2.sh`（视频合并 22:00）→ 静默失败，merge 完全停止
  - `backup_data.sh`（数据备份 08:00/20:00）→ 静默失败，SQLite 快照停止
  - `video_merge_watchdog.sh`（看门狗 22:05）→ 静默失败，无异常告警（讽刺的是告警机制自己坏了，所以没有告警）
  - `camera_heartbeat.sh` 和 `notification_daily_summary.sh` 用 `/bin/bash` 执行，不受影响
- **发现方式**：手动执行 `run_v2.sh` 看到 `Bad substitution` / `Syntax error: "(" unexpected` 错误
- **修复**：`~/Desktop/NAS/cron/project.cron` 中 3 处 `/bin/sh` → `/bin/bash`，然后 `bash cron/manage.sh install` 通过 SSH 安装（已验证 `crontab -l` 所有 5 个条目均使用 `/bin/bash`）
- **警示**：
  1. 如果更换 notify.sh 的实现语言（sh→bash），必须同步更新所有 source 它的脚本的 shebang 和 cron shell
  2. Codex 可能在不同仓库创建不一致的 notify.sh 版本（Emma Focus 的 `video merge/notify.sh` 是 `#!/bin/sh`，NAS 仓库的 `scripts/notify.sh` 是 `#!/bin/bash`）
  3. deploy.sh 已配置 `--exclude "notify.sh"` 防止 Emma Focus 部署覆盖 NAS 统一版，这本身是正确设计，但导致 Emma Focus 本地仓库的 sh 版本 notify.sh 永远不会同步到生产——一旦 NAS 统一版换了语言，Emma Focus 脚本必须全部改用 bash

### 2026-07-17：Codex 编辑后——客厅 volume 丢失 + notify.sh 不兼容 sh
- **原因**：Codex 修改 tdarr docker-compose 时移除了客厅源目录 volume mapping `XiaomiCamera_00_B888808E0906 → /mnt/source_videos_livingroom:ro`，且重写了 `notify.sh` 为纯 bash 语法（`BASH_SOURCE`, `function()`），但 `merge_v2.sh` 和 `run_v2.sh` 的 shebang 是 `#!/bin/sh`，调用也用 `sh`
- **影响**：客厅视频合并始终找到 0 个文件；脚本报 `Bad substitution` / `Syntax error: "(" unexpected`；cron lock 过期阻塞后续执行
- **修复**：重新添加客厅 volume 并重启 tdarr_node；改 `merge_v2.sh` shebang → `#!/bin/bash`，`run_v2.sh/test_v2.sh` 中 `sh` 调用 → `bash`；清理 stale lock 文件
- **警示**：Codex 编辑后必须检查：① volume 映射完整性  ② notify.sh 的 bash 兼容性

### 2026-07-14：nginx proxy 502 — site_backend:81 未监听
- **原因**：`docker-compose.yml` 的 `command` 只启动了 `main:app`（port 80），未启动 `poc_main:app`（port 81）
- **影响**：首次部署后所有 `/api/poc/` 返回 502，avatar API（port 80）正常
- **修复**：`command` 改为并行启动两个 uvicorn 进程 ✅
- **重启方式**：`/usr/bin/docker rm -f site_frontend site_backend` → `docker compose -p site up -d`

## 凭证清单（新电脑首次设置）

> ⚠️ 所有密码通过 macOS Keychain 读取，不在文件中明文存储。

### macOS Keychain
```sh
security add-generic-password -s "emma-webdav" -a "garychen" -w "你的WebDAV密码"
```

### NAS `.env` 文件（`/tmp/.../scripts/.env`）
```
export PUSHOVER_NAS_TOKEN=你的NAS Token
export PUSHOVER_NAS_USER=你的Pushover User Key
```

### Web 后端 `.env`（NAS 项目 `infra/web/.env`）
```
EMMA_ADMIN_INITIAL_PIN=一次性临时PIN
```

`NAS/infra/web/docker-compose.yml` 的 `site-backend` 必须将其注入为 `EMMA_ADMIN_INITIAL_PIN`。首次进入 Admin 页面后强制改为正式 PIN，正式 PIN 的带盐哈希持久化在 `/app/data/security/admin_auth.json`。在该配置完成前，不得部署依赖新鉴权逻辑的后端。

首次修改完成且 `/api/poc/auth/status` 返回 `mustChange=false` 后，删除 NAS `.env` 中的一次性变量并移除 Compose 注入，避免长期保留初始化凭证。

## 关键端口与 URL

| 端口 | 服务 | 内网 |
|------|------|------|
| 8888 | nginx 前端 | `http://192.168.6.108:8888` |
| 8889 | WebDAV 部署 | `http://192.168.6.108:8889` |
| 10000 | SSH | `ssh -p 10000 13918962622@192.168.6.108` |

## 待办事项

### 待办（按优先级）

**P0 — 立即下一步（原对话计划延续）：**
- [ ] 将 ready 契约部署到 NAS 并验证（`nas-deploy emma-focus --latest`，代码已提交未发布）
- [ ] 在真实 Mac 桌面会话验证 MLX-VLM 能加载 Qwen3-VL 4B（沙箱无 GPU，需桌面会话）
- [ ] 用 2026-07-26 金标准样本运行 4B 兼容性、耗时与峰值内存基准

**P1 — 本地视觉流水线：**
- [ ] 实现抽帧、场景差异过滤和联络表生成（`automation-design.md` 中定义的机械预处理）
- [ ] 选出另外 4 天覆盖关键场景的人工审核日期（不在场/成人单独/Coaching/Screen>30min/Eye Rest）
- [ ] 用 5 个金标准日期基准测试 Qwen3-VL 4B/8B 的准确率、耗时与峰值内存
- [ ] 实现每日状态机（waiting_for_ready → ... → submitted）和结果哈希缓存

**P2 — 安全与自动化门槛：**
- [ ] 设计服务端审计校验、`pending_review` 队列和不暴露家长 PIN 的批准流程
- [ ] 审查所有状态变更 API 路由的鉴权与暴露面，再扩展外部访问
- [ ] 替换历史共享密钥，决定是否需要 Git 历史清洗
- [ ] 为代币记账、评估改写、兑换、交换、备份和 XLSX 恢复增加可重复测试

**P3 — 清理：**
- [ ] 删除旧萤石数据目录（export_videos_yingshi + 监控中心/）
- [ ] 确认 `deprecated/infra/watchtower/docker-compose.yml` 的 1 行改动是否回滚
- [ ] 确认 `Emma_Audit_Directive_v5.5_for_Skill.md` 是否应纳入 Git 或移入 skills/

### 已完成
- [x] 2026-07-27：建立 repo 级 Emma Review Skill、Work 交接文档、13 岁统一 Prompt 和严格 JSON 校验测试
- [x] 2026-07-27：完成 2026-07-26 Work 结果首次受控生产提交和数据库回读验证
- [x] 2026-07-27：Video Merge ready 契约落地（.part.mp4 → ffprobe → 原子发布 → .ready 清单）
- [x] 2026-07-27：gemini_prompt.md 收敛为指向唯一真源，消除 Admin/Skill 提示词漂移
- [x] 2026-07-27：创建 MLX-VLM 隔离环境并下载 Qwen3-VL-4B-Instruct-4bit 模型（~2.9 GB）
- [x] 2026-07-27：Qwen3-VL-4B 基准测试完成 -- 模型加载 0.6s，12帧@384px 推理 16.6s，峰值 4.6GB；4B 适合粗筛，精确审计需 8B 或云端
- [x] 2026-07-27：Qwen3-VL-8B 基准测试完成 -- 加载 1.5s，推理 19.5s，峰值 7.28GB；8B 理解力更强（中文摘要+OSD时间戳）但两者都无法从低分辨率采样准确分类活动，验证需 Python 确定性计算
- [x] 2026-07-27：完整流水线首次验证通过 -- emma_pipeline.py 95帧抽取→67帧过滤→6批8B分类→Python确定性计算→严格校验通过；Focus=2 Rating=🔴与金标准一致
- [x] 2026-07-27：完成 2026-07-26 Work 结果首次受控生产提交和数据库回读验证
- [x] 2026-07-17：清理本仓库 `infra/webdav/`、`infra/tdarr/` 重复 Compose；NAS 仓库成为唯一生产配置来源
- [x] 2026-07-17：备份统一到 `/app/backups`，定时任务归 NAS 用户 cron，常规部署禁止同步远端 `.env`
- [x] 2026-07-17：Pushover 统一库、分级声音、连续失败升级、Heartbeat 恢复通知和每日摘要完成
- [x] 2026-07-19：修复 cron shell 不兼容（NAS 统一 notify.sh 使用 bash-only 语法，但 crontab 中 3 个 cron 用 `/bin/sh` 执行，导致所有通知相关脚本静默失败）
- [x] 2026-07-19：cron lock 策略改进 — NAS cron 使用 `flock -w` 等待锁；脚本不再假设 flock 文件包含 PID
- [x] 2026-07-20：备份状态改用 UID 1002 可写的 `/tmp/nas-monitor-state/backup`；视频结果 JSON 改由 Tdarr 容器清理，消除宿主权限错误

## 项目规模

| 指标 | 数值 |
|------|------|
| 后端 | `poc_main.py` ~1,362 行 / ~54 KB |
| 前端 | `index.html` ~2,081 行；`admin.html` ~733 行 |
| Emma Review | `emma_review.py` ~620 行 + 审计 Prompt 212 行 |
| Shell 脚本 | 活跃 8 个（含 video merge），~1,000 行 |
| 测试 | 5 个测试文件（emma-review 7 项 + poc 业务 6 项 + 备份/通知） |

## 跨机器协作流程

```
另一台电脑: git pull → 修改 → git commit → git push
我的 Mac:   git pull → 继续开发 → sh deploy/deploy.sh
           修改 compose/nginx → cd ~/Desktop/NAS → sh deploy/deploy.sh web
