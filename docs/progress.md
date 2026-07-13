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
| **数据备份** | `deploy/backup_data.sh` | ✅ 本地 SQLite 备份 | 2026-07-14 | docker exec → CSV |
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

## 关键决策记录

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-07-14 | **🏗️ 本地后端替换 GAS** | GAS 有限额和延迟；本地 FastAPI+SQLite 20ms 响应 |
| 2026-07-14 | **🗄️ 数据迁移 GAS→SQLite** | 52 天 + 222 日志 + 64 交易成功迁移 |
| 2026-07-14 | **🔧 docker-compose 由 NAS 项目统一管理** | deploy.sh 移除 compose 操作，调用 `../NAS/deploy/deploy.sh web` |
| 2026-07-14 | **⏱️ nginx proxy_read_timeout 120s** | 解决 ZConnect 外网首次加载 504 |
| 2026-07-13 | 🔄 infra 管理迁移到 NAS 项目 | deploy.sh 移除 docker compose 同步 |
| 2026-07-09 | 🔧 nginx 多项目隔离 | Family Time Flow 项目覆盖首页 |
| 2026-07-09 | 🏗️ clinerules 迁移到 infra-template | 统一管理共享 Cline 规则 |

## 最近提交

| 日期 | Commit | 说明 | 涉及文件 |
|------|--------|------|---------|
| 2026-07-14 | `c89422e` | 🏗️ Phase 1: 本地后端迁移完成 | `poc_main.py`, `index.html`, `admin.html`, `deploy.sh` |
| 2026-07-14 | *(待 commit)* | 🔧 数据迁移+文档+备份更新 | `backup_data.sh`, `docs/progress.md`, `README.md` |

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

### GAS 后端（已退役，不再需要）
```sh
cd ~/Desktop/Emma\ Focus/gas
clasp push
```

## 数据备份

每天 08:00 通过 crontab 执行 `backup_data.sh`，直接从容器 SQLite 导出 CSV：
```sh
docker exec site_backend sqlite3 -header -csv /app/data/poc.db "SELECT * FROM evaluations;" > backup.csv
```

## 已知问题 / 事故记录

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

## 关键端口与 URL

| 端口 | 服务 | 内网 |
|------|------|------|
| 8888 | nginx 前端 | `http://192.168.6.108:8888` |
| 8889 | WebDAV 部署 | `http://192.168.6.108:8889` |
| 10000 | SSH | `ssh -p 10000 13918962622@192.168.6.108` |

## 待办事项

### 待办
- [ ] 删除旧萤石数据目录（export_videos_yingshi + 监控中心/）
- [ ] 在 root crontab 添加备份脚本: `0 8 * * * /tmp/.../scripts/backup_data.sh`

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