# Emma Focus — 项目进度

> 项目状态文档，跨机器共享。克隆到任何设备后先读此文件了解当前状态。

## 项目概览

亲子专注力管理系统，追踪和激励孩子的学习专注力。
- **前端看板**：`index.html`（NAS nginx）
- **后端**：FastAPI + SQLite（本地容器 `site_backend`，替代 GAS）
- **NAS 视频处理**：`merge_v2.sh` → ffmpeg + QSV 加速

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
| **V2 通用脚本** | `merge_v2.sh` / `run_v2.sh` | ✅ 运行中 | 2026-07-14 | `sh deploy/deploy.sh` |
| **Pushover 通知** | `notify.sh` + MCP server | ✅ 运行中 | — | Keychain + `.env` |
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
| 2026-07-13 | 🔄 infra 管理迁移到 NAS 项目 | deploy.sh 移除 docker compose 同步 |
| 2026-07-09 | 🔧 nginx 多项目隔离 | Family Time Flow 项目覆盖首页 |
| 2026-07-09 | 🏗️ clinerules 迁移到 infra-template | 统一管理共享 Cline 规则 |

## 最近提交

| 日期 | Commit | 说明 | 涉及文件 |
|------|--------|------|---------|
| 2026-07-14 | `8a32670` | 🧹 清理退役文件+统一基础设施管理 | `deprecated/`, `admin.html`, `README.md`, `.clinerules` |
| 2026-07-14 | `8255704` | 🔧 docker-compose 持久化 poc.db | `docker-compose.yml`, `backend/data/` |
| 2026-07-14 | `f24cb39` | 📝 .clinerules: GAS退役 | `.clinerules` |
| 2026-07-14 | `2ba9f2c` | 📝 文档+备份更新: GAS→SQLite | `backup_data.sh`, `README.md`, `docs/progress.md` |
| 2026-07-14 | `c89422e` | 🏗️ Phase 1: 本地后端迁移完成 | `poc_main.py`, `index.html`, `admin.html`, `deploy.sh` |

## 部署流程（重要！）

### Emma Focus 自身内容（HTML/脚本/后端代码）
```sh
cd ~/Desktop/Emma\ Focus
git pull           # 拉取最新
sh deploy/deploy.sh  # 同步 HTML + 后端 + scripts 到 WebDAV
```

### Docker Compose / nginx 配置（由 NAS 项目管理）
```sh
cd ~/Desktop/NAS
git pull
sh deploy/deploy.sh web   # 上传 + 重启 site_frontend + site_backend
```

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

### 待办
- [ ] 删除旧萤石数据目录（export_videos_yingshi + 监控中心/）

### 已完成
- [x] 2026-07-17：清理本仓库 `infra/webdav/`、`infra/tdarr/` 重复 Compose；NAS 仓库成为唯一生产配置来源
- [x] 2026-07-17：备份统一到 `/app/backups`，定时任务归 NAS 用户 cron，常规部署禁止同步远端 `.env`
- [x] 2026-07-17：Pushover 统一库、分级声音、连续失败升级、Heartbeat 恢复通知和每日摘要完成
- [x] 2026-07-19：修复 cron shell 不兼容（NAS 统一 notify.sh 使用 bash-only 语法，但 crontab 中 3 个 cron 用 `/bin/sh` 执行，导致所有通知相关脚本静默失败）
- [x] 2026-07-19：cron lock 策略改进 — NAS cron 使用 `flock -w` 等待锁；脚本不再假设 flock 文件包含 PID
- [x] 2026-07-20：备份状态改用 UID 1002 可写的 `/tmp/nas-monitor-state/backup`；视频结果 JSON 改由 Tdarr 容器清理，消除宿主权限错误

## 项目规模

| 指标 | 数值 |
|------|------|
| 后端 | `poc_main.py` ~17 端点, ~44K |
| 前端 | `index.html` ~1,900 行 |
| Shell 脚本 | 7 个，~1,000 行 |

## 跨机器协作流程

```
另一台电脑: git pull → 修改 → git commit → git push
我的 Mac:   git pull → 继续开发 → sh deploy/deploy.sh
           修改 compose/nginx → cd ~/Desktop/NAS → sh deploy/deploy.sh web
