# Emma Focus — 项目进度

> 项目状态文档，跨机器共享。克隆到任何设备后先读此文件了解当前状态。

## 项目概览

亲子专注力管理系统，追踪和激励孩子的学习专注力。前端看板 + GAS 后端 + NAS 视频处理流水线。

## 组件状态

| 组件 | 状态 | 部署方式 | 备注 |
|------|------|----------|------|
| **GAS 后端** | ✅ 运行中 | `clasp push` | 部署 ID: `AKfycbwgll7iC0nSzK3IKXR0zlYu6Hh-5uChrj96gcHBmqvEp0dWOUsvizZmrzJmub0V7aDf1Q` |
| **前端看板** | ✅ 运行中 | `sh deploy.sh` → NAS docker/html/ | nginx port 8888 |
| **视频合并（小米）** | ✅ 运行中 | `sh deploy.sh` → NAS scripts/ | crontab 22:00 |
| **视频合并（萤石）** | ✅ 运行中 | `sh deploy.sh` → NAS scripts/ | crontab 22:00 |
| **Pushover 通知** | ✅ 配置完成 | `~/.clinerules`（全局） | 内置于 NAS 脚本 + 部署流程 |

## 最近提交

| 日期 | Commit | 说明 |
|------|--------|------|
| 2026-07-06 | `a54c478` | 🐛 修复：视频合并路径转义 bug（docker exec -e 传参） |
| 2026-07-06 | `9370a7d` | docs: progress.md + 项目级 .clinerules |
| 2026-07-06 | `8baf19a` | infra 重构 + deploy.sh 权限修复 |
| 2026-07-06 | `9c8180d` | clasp 配置 + GAS 自动部署 |
| 2026-07-06 | `1da185b` | deploy.sh 一键 NAS 部署 |
| 2026-07-06 | `dc396fc` | 视频合并：重试+通知+日志轮转 |
| 2026-07-06 | `c3ecf93` | 视频合并脚本加入仓库 |
| 2026-07-06 | `06f9579` | 缓存导航修复 + 总计日均=0 修复 |

## 待办事项

- [x] WebDAV 远程部署支持（`deploy.sh` 已验证通过）
- [ ] GAS 部署版本管理（`clasp deploy` 策略待确认）
- [ ] 视频合并失败重试具体日期通知（目前只有汇总统计）

## 已知问题

- SMB 权限问题：rsync 后需手动 `chmod`（已在 `deploy.sh` 中自动处理）
- NAS 无 SSH 端口（22 refused），无法远程执行命令
- ~~docker exec 双引号 sh -c 导致路径转义错误~~ ✅ 已修复（`a54c478`）
- Windows 下 `cmd.exe` 不支持 `&&` 命令链，需用 `&` 或批处理文件
- Windows 下 PowerShell 不会从当前目录加载 `.bat`，需用 `.\run_deploy.bat` 或 `cmd.exe /c run_deploy.bat`

## 项目结构

```
├── index.html / admin.html       # 前端看板
├── emma_focus_api.gs             # GAS 后端 API
├── deploy.sh                     # 一键部署 NAS + 权限修复
├── progress.md                   # 项目状态文档（本文件）
│
├── infra/
│   ├── web/docker-compose.yml    # nginx + fastapi 前端服务
│   └── tdarr/docker-compose.yml  # tdarr 视频处理 (Intel QSV)
│
└── video merge/                  # 延时合成脚本
    ├── run_all.sh                # crontab 总控 + Pushover
    ├── auto_merge.sh             # 小米 720P 30倍速
    ├── yingshi_auto_merge.sh     # 萤石 1080P 30倍速
    └── notify.sh                 # Pushover 辅助函数
```

## 快速开始（macOS）

```sh
# 1. 克隆仓库
git clone https://github.com/animeidea-debug/emma-focus.git
cd emma-focus

# 2. GAS 部署（如果需要改动后端）
npm install -g @google/clasp
clasp login            # 浏览器授权
clasp push             # 上传代码

# 3. NAS 部署（如果需要同步到 NAS）
# 密码从 macOS Keychain 读取（需先存入）：
#   security add-generic-password -s "emma-webdav" -a "garychen" -w "密码"
sh deploy.sh

# 4. 查看最新状态
cat progress.md
```

## 快速开始（Windows）

### 首次设置

```powershell
# 1. 安装 Git for Windows（自带 Git Bash）
#    下载：https://git-scm.com/

# 2. 安装 rclone
#    下载：https://rclone.org/downloads/
#    解压到：%USERPROFILE%\Downloads\rclone\rclone-v1.74.3-windows-amd64\

# 3. 设置 WebDAV 密码（用户级环境变量，持久化）
setx WEBDAV_PASS "你的密码"

# 4. 将 rclone 加入 PATH（用户级，持久化）
setx PATH "%PATH%;%USERPROFILE%\Downloads\rclone\rclone-v1.74.3-windows-amd64"
```

### 日常部署

```powershell
# 使用 run_deploy.bat（推荐）
# 该脚本会自动：
# 1. 读取 WEBDAV_PASS 环境变量
# 2. 配置 rclone（LAN + Tailscale Funnel）
# 3. 运行 deploy.sh 进行部署

# 运行（注意：PowerShell 需要 .\ 前缀）
.\run_deploy.bat

# 或直接用 cmd.exe 调用
cmd.exe /c run_deploy.bat
```

### GAS 部署（Windows）

```powershell
# 安装 clasp
npm install -g @google/clasp

# 登录（浏览器会打开 Google 授权页面）
clasp login

# 推送代码（公司网络需通过代理）
# 方式 A：使用 run_gas_deploy.bat（推荐，已配置代理）
.\run_gas_deploy.bat

# 方式 B：手动设置代理后推送
$env:HTTPS_PROXY = "http://proxy.sin.sap.corp:8080"
$env:HTTP_PROXY = "http://proxy.sin.sap.corp:8080"
clasp push
```

**注意**：公司网络下 `clasp` 需要通过代理访问 Google。浏览器能直接访问是因为使用了 Windows 登录凭证，但命令行工具需要显式设置 `HTTPS_PROXY` / `HTTP_PROXY` 环境变量。

### 网络说明

- **家庭网络**：自动使用 LAN（192.168.6.108:8889），速度快
- **公司网络/外网**：自动使用 Tailscale Funnel（https://z4pro-xxel.tail1a5bb9.ts.net/），无需配置代理
- **旧 DDNS 方案**：已弃用（zy12683em2039.vicp.fun）

### 注意事项

- `cmd.exe` 不支持 `&&` 命令链，使用 `&` 代替
- PowerShell 不会从当前目录加载 `.bat`，需用 `.\run_deploy.bat`
- 公司网络无需额外代理配置，Tailscale Funnel 已解决外网访问问题
```

## 跨机器协作流程

```
另一台电脑: git pull → 修改 → git commit → git push
我的 Mac:   git pull → 继续开发 → clasp push + sh deploy.sh
Windows:    git pull → 修改 → git commit → git push
            (部署需回家用 Mac 或配置代理后执行)