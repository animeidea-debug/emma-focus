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
| 2026-07-06 | `8baf19a` | infra 重构 + deploy.sh 权限修复 |
| 2026-07-06 | `9c8180d` | clasp 配置 + GAS 自动部署 |
| 2026-07-06 | `1da185b` | deploy.sh 一键 NAS 部署 |
| 2026-07-06 | `dc396fc` | 视频合并：重试+通知+日志轮转 |
| 2026-07-06 | `c3ecf93` | 视频合并脚本加入仓库 |
| 2026-07-06 | `06f9579` | 缓存导航修复 + 总计日均=0 修复 |

## 待办事项

- [ ] WebDAV 远程部署支持（`deploy.sh` fallback）
- [ ] 项目级 `.clinerules` 跨机器共享
- [ ] GAS 部署版本管理（每次 `clasp push` 后是否需要 `clasp deploy` 创建新版本？）
- [ ] 视频合并失败重试具体日期通知（目前只有汇总统计）

## 已知问题

- SMB 权限问题：rsync 后需手动 `chmod`（已在 `deploy.sh` 中自动处理）
- NAS 无 SSH 端口（22 refused），无法远程执行命令
- `appsscript.json` 中 `timeZone` 为静态值，如需改动需手动更新

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

## 快速开始（另一台电脑）

```sh
# 1. 克隆仓库
git clone https://github.com/animeidea-debug/emma-focus.git
cd emma-focus

# 2. GAS 部署（如果需要改动后端）
npm install -g @google/clasp
clasp login            # 浏览器授权
clasp push             # 上传代码

# 3. NAS 部署（如果需要同步到 NAS）
# 先在 Finder 中连接：smb://192.168.6.108 并保存凭证
sh deploy.sh

# 4. 查看最新状态
cat progress.md
```

跨机器协作流程：
```
另一台电脑: git pull → 修改 → git commit → git push
我的 Mac:   git pull → 继续开发 → clasp push + sh deploy.sh