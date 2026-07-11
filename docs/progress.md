# Emma Focus — 项目进度

> 项目状态文档，跨机器共享。克隆到任何设备后先读此文件了解当前状态。

## 项目概览

亲子专注力管理系统，追踪和激励孩子的学习专注力。前端看板 + GAS 后端 + NAS 视频处理流水线。

## 关键服务

| 服务 | 内网地址 | 外网地址 | 说明 |
|------|---------|---------|------|
| nginx 前端 | `http://192.168.6.108:8888` | Tailscale Funnel | `index.html` + `admin.html` |
| GAS API | `https://script.google.com/...` | 同上 | 部署 ID: `AKfycbwg...` |
| WebDAV 部署 | `http://192.168.6.108:8889` | Tailscale Funnel | 脚本/HTML 同步 |
| 远程桌面 | `ssh -p 10000` | Tailscale SSH | 用户名 `13918962622` |

## 组件状态

| 组件 | 版本 | 状态 | 最后部署 | 部署方式 |
|------|------|------|---------|----------|
| **GAS 后端** | `gas/emma_focus_api.gs` | ✅ 运行中 | 2026-07-08 | `sh deploy/deploy_gas.sh` |
| **前端看板** | `index.html` | ✅ 运行中 | 2026-07-09 | `sh deploy/deploy.sh` |
| **书房主机位（小米旧款）** | `auto_merge.sh` | ✅ 22:45 crontab | 2026-07-10 | `sh deploy/deploy.sh` |
| **客厅** | `livingroom_auto_merge.sh` | ✅ 22:45 crontab | 2026-07-10 | `sh deploy/deploy.sh` (hevc_qsv) |
| **V2 通用脚本（新款摄像头）** | `merge_v2.sh` | 🆕 待验证 | 2026-07-10 | `CAMERA=... SOURCE=... sh merge_v2.sh` |
| **V2 总控** | `run_v2.sh` | 🆕 待验证 | 2026-07-10 | 手动运行，cron 待设 |
| **V2 测试** | `test_v2.sh` | 🆕 待验证 | 2026-07-10 | `TEST_MODE=true sh test_v2.sh` |
| **Pushover 通知** | `notify.sh` + MCP server | ✅ 配置完成 | — | Keychain + `.env` |
| **WebDAV 部署容器** | `infra/webdav/docker-compose.yml` | ✅ docker-compose 管理 | 2026-07-09 | `docker compose up -d` |

## 摄像头配置

| 名称 | 型号 | 传感器 | 源目录 | 输出目录 | 源编码→输出编码 | 源分辨率→输出分辨率 |
|------|------|--------|--------|---------|----------------|-------------------|
| 书房主机位 | 小米智能摄像机 云台版2K | 300万 | NVMe14 `xiaomi_camera_videos/` | `export_videos/` | H.265→H.264 (QSV) | 2304×1296→720P |
| 书房辅机位 | 萤石 C6Wi | 800万 | NVMe14 `监控中心/` | `export_videos_yingshi/` | H.265→H.264 (QSV) | 3840×2160→1080P |
| 客厅 🆕 | 小米智能摄像机4 4K | 800万 | SATA13 `XiaomiCamera_00_.../` | `export_videos_livingroom/` | H.265→**H.265 (QSV)** | 3840×2160→4K |

> 所有脚本使用 `-2:HEIGHT` 保持宽高比，Intel N100 QSV 硬件加速。
> 客厅于 2026-07-08 切换为 hevc_qsv 编码，预期文件大小减半。

## 关键决策记录

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-07-07 | 选 WebDAV 替代 SMB | SMB 破坏文件权限（600/700），需额外 chmod |
| 2026-07-07 | 选 Tailscale Funnel 替代 DDNS | DDNS `zy12683em2039.vicp.fun` 不稳定 |
| 2026-07-07 | 凭证统一走 Keychain / `.env` | 杜绝 git 中明文密码 |
| 2026-07-07 | 测试模式 `head -1` + `head -2` | 限制 1 天 x 2 片段，~1 分钟完成测试 |
| 2026-07-08 | 客厅改 `hevc_qsv` | 4K 下 H.265 省 50% 空间，播放器兼容性好 |
| 2026-07-08 | 结果 JSON 写入共享卷 | 修复容器 `/tmp` 与宿主机隔离导致的计数=0 |
| 2026-07-09 | 🔧 fix: deploy.sh `../../` → `../` | 路径错误导致 Mac 7/8 部署未生效 |
| 2026-07-09 | 📁 新增 `infra/webdav/` | 将 WebDAV 容器纳入版本管理 |
| 2026-07-09 | 🔧 nginx 多项目隔离 | Family Time Flow 项目覆盖首页 |
| 2026-07-09 | 🔐 scripts +x 权限自动修复 | WebDAV 强制 644，crontab 静默拒绝执行 |
| 2026-07-09 | 🐳 WebDAV compose 修复 | rclone 镜像 ENTRYPOINT 与 sh -c 不兼容 |
| 2026-07-09 | 🏗️ clinerules 迁移到 infra-template | 统一管理共享 Cline 规则，各项目通过 `## [shared]` + `## [project]` 分割 |
| 2026-07-10 | 🐛 fix: yingshi 过滤 bug | find 把 d_path 自身匹配到 [0-9][0-9] 导致全天遍历 |
| 2026-07-10 | 🔄 简化: 去掉萤石摄像头 + 优化 run_all | 容器重启杀 ffmpeg 导致客厅 0 字节文件，livingroom 0字节检测修复 |
| 2026-07-10 | ✨ 新增 V2 统一脚本（merge_v2/run_v2/test_v2） | 参数化设计，兼容新旧文件名格式，统一输出到 export_videos |
| 2026-07-11 | 🔥 vpp_qsv 全硬件加速 5x | intel-gpu-top 证实 GPU Video 引擎从 0.16%→可用 |
| 2026-07-11 | 🆕 书房新摄像头 Study 就绪 | SATA13 → /mnt/source_study，720P HEVC |
| 2026-07-11 | 📐 统一输出目录 | 所有文件输出到 export_videos/，命名规范 {Camera}_{YYYYMMDD}.mp4 |
| 2026-07-11 | 🔗 合并旧书房+新书房 7/11 全天数据 | Xiaomi(上午23M) + Study(下午81M) → Study_20260711.mp4(104MB) |

## 最近提交

| 日期 | Commit | 说明 | 涉及文件 |
|------|--------|------|---------|
| 2026-07-11 | *(待 commit)* | 📝 更新文档 + 推送 | `docs/progress.md` |
| 2026-07-11 | `e776886` | 🐛 fix: Pushover 通知汇总变量 | `run_all.sh` |
| 2026-07-11 | `ba6cb6b` | 🐛 fix: site-backend volume 路径 | `infra/web/docker-compose.yml` |
| 2026-07-11 | `dee2142` | 🆕 书房新摄像头验证通过 720P | `run_v2.sh` |
| 2026-07-10 | `096534a` | ✨ 新增 V2 统一脚本系列 | `merge_v2.sh`, `run_v2.sh`, `test_v2.sh` |
| 2026-07-09 | `a1b9d1e` | 🐳 fix: WebDAV compose sh -c 不兼容 rclone ENTRYPOINT + 密码持久化 | `deploy.sh`, `infra/webdav/docker-compose.yml` |
| 2026-07-09 | `14dfe16` | 🔐 fix: deploy.sh 部署后自动 chmod +x （WebDAV 不保留权限，crontab 静默拒绝） | `deploy.sh` |
| 2026-07-09 | `18ac277` | 🔔 fix: run_all.sh 通知静默失败（.env 被删除 + notify.sh 无 fallback） | `notify.sh`, `run_all.sh`, `deploy.sh` |
| 2026-07-09 | `f144d28` | 🔧 fix: deploy.sh 路径错误（../../ → ../）+ infra/webdav 入库 | `deploy.sh`, `infra/webdav/docker-compose.yml` |
| 2026-07-09 | `09b38c2` | 🏗️ clinerules 迁移到 infra-template 仓库（单一真源） | `infra-template`, `.clinerules`, `clinerules/*` |
| 2026-07-09 | *(待 commit)* | 🔧 nginx 多项目隔离 + 首页恢复 | `nginx.conf`, `clinerules/global.template` |
| 2026-07-08 | `53ca470` | 🧪 PoC 路由修复 + nginx 配置 | `nginx.conf` |
| 2026-07-08 | `dc89232` | 🧪 PoC rewrite rule + 测试页面路径 | `nginx.conf`, `poc/index_poc.html` |
| 2026-07-08 | `8140870` | 🧪 PoC fastapi+SQLite 后端 | `poc/main.py`, `poc/index_poc.html`, `nginx.conf`, `docker-compose.yml` |
| 2026-07-08 | `dd55181` | 🎨 头像拖拽缩放裁剪 | `index.html` |
| 2026-07-07 | `c1b4b83` | 🔧 deploy.sh --exclude .env | `deploy.sh` |
| 2026-07-07 | `bf48b13` | 🧪 test_merge.sh 快速检测模式 | `test_merge.sh` |
| 2026-07-07 | `166048e` | 🆕 客厅 4K 脚本 | `livingroom_auto_merge.sh`, `docker-compose.yml`, `run_all.sh` |
| 2026-07-07 | `034f0a9` | 🔐 移除 git 中 Pushover 明文 token | `notify.sh`, `.env.example`, `.gitignore` |

## 凭证清单（新电脑首次设置）

> ⚠️ 以下命令包含占位符，需从 macOS Keychain 或管理员获取实际密码填入。

### macOS Keychain
```sh
security add-generic-password -s "emma-webdav" -a "garychen" -w "你的WebDAV密码"
security add-generic-password -s "pushover-emma-token" -a "garychen" -w "你的Pushover Emma Token"
security add-generic-password -s "pushover-emma-user" -a "garychen" -w "你的Pushover User Key"
security add-generic-password -s "pushover-nas-token" -a "garychen" -w "你的Pushover NAS Token"
security add-generic-password -s "pushover-nas-user" -a "garychen" -w "你的Pushover User Key"
```

### NAS `.env` 文件（`/tmp/.../scripts/.env`）
```
export PUSHOVER_NAS_TOKEN=你的NAS Token
export PUSHOVER_NAS_USER=你的Pushover User Key
```

### WebDAV `.env` 文件（`infra/webdav/.env`，gitignored）
```
WEBDAV_PASS=你的WebDAV密码
WEBDAV_USER=garychen
```

> 🔴 **已从 git 历史中移除明文密码。** 如果之前 clone 过此仓库，建议轮换所有密码。

## 关键端口与 URL

| 端口 | 服务 | 内网 | 外网 |
|------|------|------|------|
| 8888 | nginx 前端 | `http://192.168.6.108:8888` | Tailscale Funnel |
| 8889 | WebDAV 部署 | `http://192.168.6.108:8889` | 同上 |
| 10000 | SSH | `ssh -p 10000 13918962622@192.168.6.108` | 同上 |
| 8265 | tdarr Web UI | `http://192.168.6.108:8265` | — |
| 5000 | fastapi 后端 | `http://192.168.6.108:5000` | — |

## 已知问题 / 事故记录

### 2026-07-09：WebDAV docker-compose sh -c 不兼容 rclone ENTRYPOINT
- **原因**：`rclone/rclone:latest` 镜像的 ENTRYPOINT 是 `rclone`，但 docker-compose.yml 用 `command: sh -c "serve webdav ..."`。执行后变成 `rclone sh -c "serve webdav ..."` → `sh` 不是 rclone 子命令 → 容器崩溃
- **影响**：WebDAV 容器每次重启后无法自愈，只能手动 `docker run` 启动
- **修复**：
  1. command 改为 JSON 数组格式 ✅
  2. 密码从同目录 `.env` 文件读取（`docker compose` 自动加载）✅
  3. `deploy.sh` 同步后自动重启 webdav ✅
- **验证**：`docker compose up -d` → Up 稳定，`curl -u garychen:密码` → HTTP 200 ✅

### 2026-07-09：脚本无 +x 权限导致 crontab 静默失败
- **原因**：WebDAV `rclone sync` 不保留执行权限，所有 .sh 文件为 644。文件属主 `root:root`，用户 `13918962622` 无法 chmod。crontab 调绝对路径时 shell 静默拒绝。
- **影响**：每晚 22:45 的 `run_all.sh` 从未实际执行过
- **修复**：
  1. 通过 `docker exec tdarr_node chmod +x` 修复当前权限 ✅
  2. `deploy/deploy.sh` 部署后自动 SSH 执行 chmod ✅
- **教训**：WebDAV 不保留 +x，部署后必须通过容器内 root 修复权限

### 2026-07-09：通知静默失败（.env 被删除）
- **根因**：`deploy.sh --delete-excluded` 每次同步删除远程 `.env` → `pushover_notify()` 凭证为空 → 静默跳过
- **影响**：即使用户手动跑脚本也收不到任何通知
- **修复**：
  1. `notify.sh` 内置缺省凭证（`.env` 缺失时自动 fallback）✅
  2. `deploy.sh` 同步后主动 `rclone copy .env` ✅
- **教训**：关键配置文件必须在 deploy.sh 中双重保护（exclude + 主动复制）

### 2026-07-09：WebDAV docker-compose 明码密码
- **原因**：Windows 在 `infra/webdav/docker-compose.yml` 中用 `--pass Momoco198399` 硬编码
- **影响**：密码在 git 历史中暴露
- **修复**：改用同目录 `.env` 文件（已 gitignored）
- **Windows 配置**：为 `docker compose` 创建 `infra/webdav/.env`

### 2026-07-09：Family Time Flow 项目覆盖 Emma Focus 首页
- **原因**：Family Time Flow 项目复用 `infra/web/` 模板，部署时将 `index.html` 同步到 `/docker/html/`，覆盖首页。
- **修复**：
  1. `infra/web/nginx.conf` 添加 `location /family-time-flow/` ✅
  2. `clinerules/global.template` 新增多项目共享 nginx 规则 ✅
- **教训**：每个项目必须使用独立子目录 + 独立 location 块

### 2026-07-09：deploy.sh 路径错误导致部署未生效
- **原因**：`deploy/deploy.sh` 路径使用 `../../`，实际应为 `../`
- **修复**：所有 `../../` 改为 `../` ✅
- **教训**：部署脚本应使用 `set -e` 在目录不存在时报错

### 2026-07-08：`.env` 文件被 rclone sync 意外删除
- **原因**：`rclone sync` 同步脚本目录时，远程 `.env` 文件被 `--delete-excluded` 删除
- **影响**：通知静默失败
- **修复**：`deploy/deploy.sh` 添加 `--exclude ".env"` ✅

### 其他已知问题
- SMB 权限问题：已弃用（改用 WebDAV）
- ~~docker exec 双引号 sh -c 导致路径转义错误~~ ✅ 已修复（`a54c478`）
- crontab 由 root 配置，不是 `13918962622` 用户（`sudo crontab -l` 查看）
- Windows 下 `cmd.exe` 不支持 `&&` 命令链，需用 `&` 或批处理文件

## 待办事项

### 已修复
- [x] 🐛 yingshi_auto_merge.sh 双引号 sh -c 导致宿主机 $ 变量预展开
- [x] 🔑 result JSON 权限问题 — 三个脚本均添加 `chmod 644`，确保 run_all.sh 可删除
- [x] 🔒 tdarr node 源目录统一 `:ro` 只读保护原始视频
- [x] 🗑️ .clinerules 移除已弃用的 SMB 凭证行
- [x] ⏭️ 三个脚本新增"最新日期跳过不完整日期"逻辑（仅下午有录像才处理最新日期）
- [x] 🐛 yingshi_auto_merge.sh `sed` 引号冲突修复（单引号块内 sed 嵌套单引号导致 Syntax error）
- [x]  deploy.sh 连接策略重写（指数退避重试 + LAN 独立路径不跳 Tailscale）

### 待办
- [ ] 删除旧萤石数据目录（export_videos_yingshi + 监控中心/）
- [ ] 将 docker-compose.yml 的 Study volume 写入 NAS 上的文件（防止重启丢失）
- [ ] 清理旧 `run_all.sh` crontab 条目（22:00 已改为 run_v2.sh）
- [ ] 其他项目（如 family-time-flow）的 `.clinerules` 同步更新为 `## [shared]` + `## [project]` 格式

## 测试状态

| 日期 | 测试内容 | 结果 |
|------|---------|------|
| 2026-07-09 23:30 | run_all.sh 手动测试（修复权限后） | ✅ 书房主机位 ffmpeg 正在运行 |
| 2026-07-09 23:36 | WebDAV compose 修复验证 | ✅ `docker compose up -d` Up 13 分钟，auth 返回 HTTP 200 |
| 2026-07-09 16:34 | 部署脚本路径修复 | ✅ `livingroom_auto_merge.sh` 成功同步 |
| 2026-07-07 22:54 | 3 摄像头全量运行 | ✅ 成功 |
| 2026-07-07 22:39 | test_merge.sh 快速模式 | ✅ 全部通过 |

## 远程访问方式

### Web SSH Console（推荐，无需安装软件）
- **URL**: https://tailscale-ssh-console-animeidea-outlook-com-7t9bk783ge.tail1a5bb9.ts.net
- **访问方式**: 通过 Tailscale 网络，浏览器直接打开
- **权限**: root（无需密码）
- **用途**: 查看日志、编辑文件、重启服务、运行命令

### 本地 SSH（回家后使用）
```powershell
ssh -p 10000 13918962622@192.168.6.108
```

### WebDAV Funnel（文件操作）
- 用于部署脚本和文件同步
- URL: https://z4pro-xxel.tail1a5bb9.ts.net/

## 跨机器协作流程

```
另一台电脑: git pull → 修改 → git commit → git push → pull request
我的 Mac:   git pull → 继续开发 → sh deploy/deploy_gas.sh + sh deploy/deploy.sh
Windows:    git pull → 修改 → git commit → git push
```

## 项目规模

| 指标 | 数值 |
|------|------|
| 总文件数 | 28 |
| 总代码行数 | ~5,400 |
| 最大文件 | `index.html` (1,756行) |
| Shell 脚本 | 7 个，~900 行 |
| GAS 后端 | 1,144 行 |