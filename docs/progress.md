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
| **前端看板** | `index.html` | ✅ 运行中 | 2026-07-08 | `sh deploy/deploy.sh` |
| **书房主机位（小米）** | `auto_merge.sh` | ✅ 22:45 crontab | 2026-07-08 | `sh deploy/deploy.sh` |
| **书房辅机位（萤石）** | `yingshi_auto_merge.sh` | ✅ 22:45 crontab | 2026-07-08 | `sh deploy/deploy.sh` |
| **客厅** | `livingroom_auto_merge.sh` | ✅ 22:45 crontab | 2026-07-08 | `sh deploy/deploy.sh` |
| **Pushover 通知** | `notify.sh` + MCP server | ✅ 配置完成 | — | Keychain + `.env` |

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
| 2026-07-09 | 🔧 fix: deploy.sh `../../` → `../` | 路径错误导致 Mac 7/8 部署未生效，所有 infra 和 scripts 未真正同步到 NAS |
| 2026-07-09 | 📁 新增 `infra/webdav/` | 将 WebDAV 容器配置（`rclone/rclone:latest`）纳入版本管理 |

## 最近提交

| 日期 | Commit | 说明 | 涉及文件 |
|------|--------|------|---------|
| 2026-07-09 | *(待 commit)* | 🔧 fix: deploy.sh 路径错误（../../ → ../）+ infra/webdav 入库 | `deploy.sh`, `infra/webdav/docker-compose.yml` |
| 2026-07-08 | `53ca470` | 🧪 PoC 路由修复 + nginx 配置 | `nginx.conf` |
| 2026-07-08 | `dc89232` | 🧪 PoC rewrite rule + 测试页面路径 | `nginx.conf`, `poc/index_poc.html` |
| 2026-07-08 | `8140870` | 🧪 PoC fastapi+SQLite 后端 | `poc/main.py`, `poc/index_poc.html`, `nginx.conf`, `docker-compose.yml` |
| 2026-07-08 | `dd55181` | 🎨 头像拖拽缩放裁剪 | `index.html` |
| 2026-07-07 | `c1b4b83` | 🔧 deploy.sh --exclude .env | `deploy.sh` |
| 2026-07-07 | `bf48b13` | 🧪 test_merge.sh 快速检测模式 | `test_merge.sh` |
| 2026-07-07 | `166048e` | 🆕 客厅 4K 脚本 | `livingroom_auto_merge.sh`, `docker-compose.yml`, `run_all.sh` |
| 2026-07-07 | `034f0a9` | 🔐 移除 git 中 Pushover 明文 token | `notify.sh`, `.env.example`, `.gitignore` |

## 待办事项

### 高优先级
- [ ] 客厅 H.265 编码验证 — 在 NAS 上运行 test_merge.sh 确认 hevc_qsv 生效
- [ ] 视频合并失败重试具体日期通知（目前只有汇总统计）
- [ ] Mac 下次使用时 `git pull && sh deploy/deploy.sh` 同步路径修复

### 低优先级
- [ ] 海马摄像头视频合并脚本（弟弟的 3D 打印延时）
- [ ] H.264 旧文件清理脚本（自动检测编码格式并删除旧版）
- [ ] crontab 失败推送通知（如果 `run_all.sh` 完全没执行）
- [ ] 书房主机位输出分辨率可配置化（当前硬编码 720P，可改 480P/1080P）
- [ ] 书房辅机位跳过包含特定 Note 的日期（如"Emma 不在场"）
- [ ] WebDAV 容器配置加入部署脚本同步

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

### Windows 环境变量
```powershell
setx WEBDAV_PASS "你的WebDAV密码"
setx PUSHOVER_NAS_TOKEN "你的NAS Token"
setx PUSHOVER_NAS_USER "你的Pushover User Key"
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

### 2026-07-08：`.env` 文件被 rclone sync 意外删除
- **原因**：`rclone sync` 同步脚本目录时，远程 `.env` 文件在本地不存在，被 `--delete-excluded` 删除
- **影响**：通知静默失败，当晚所有 Pushover 通知未发送
- **修复**：
  1. `deploy/deploy.sh` 添加 `--exclude ".env"` ✅
  2. `run_all.sh` 启动时自检 `.env` 是否存在，缺失时通过硬编码凭证发送紧急通知 ✅
  3. 此文档记录事件便于排查 ✅
- **教训**：以后所有敏感文件需在 deploy.sh 中显式排除，不要在 repo 中创建同名的 `.env.example` 之外的任何文件

### 其他已知问题

- SMB 权限问题：已弃用（改用 WebDAV）
- ~~docker exec 双引号 sh -c 导致路径转义错误~~ ✅ 已修复（`a54c478`）
- crontab 由 root 配置，不是 `13918962622` 用户（`sudo crontab -l` 查看）
- Windows 下 `cmd.exe` 不支持 `&&` 命令链，需用 `&` 或批处理文件
- PowerShell 不会从当前目录加载 `.bat`，需用 `.\run_deploy.bat`

## 测试状态

| 日期 | 测试内容 | 结果 |
|------|---------|------|
| 2026-07-07 22:54 | 3 摄像头全量运行（修复前） | 数据正确生成，但通知计数=0 |
| 2026-07-07 22:54 | 3 摄像头全量运行（重试） | ✅ 成功（书房主机位 1天/208MB，书房辅机位 1天/221MB，客厅 8天） |
| 2026-07-07 22:39 | test_merge.sh 快速模式 | ✅ 小米通过，萤石(temp文件)通过，客厅(export文件)通过 |
| — | 客厅 H.265 编码 | 🔄 待今晚 crontab 22:45 执行后检查 |

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
| 总文件数 | 27 |
| 总代码行数 | ~5,353 |
| 最大文件 | `index.html` (1,756行) |
| Shell 脚本 | 7 个，~900 行 |
| GAS 后端 | 1,144 行 |