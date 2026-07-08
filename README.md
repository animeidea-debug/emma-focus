# Emma 专注力成长看板

亲子专注力管理系统，追踪和激励孩子的学习专注力，通过代币（银币/金币）奖励机制培养自驱自律习惯。

## 项目结构

```
├── index.html / admin.html  # 前端看板
├── README.md                # 项目说明（本文件）
│
├── gas/                     # GAS 后端
│   ├── .clasp.json          # clasp 配置（scriptId）
│   ├── .claspignore         # clasp 忽略规则
│   ├── appsscript.json      # GAS 清单
│   └── emma_focus_api.gs    # GAS API 实现
│
├── deploy/                  # 部署脚本
│   ├── deploy.sh            # NAS 部署（跨平台）
│   ├── deploy_gas.sh        # GAS 部署（Mac：家庭网络）
│   ├── run_deploy.bat       # NAS 部署（Windows）
│   └── run_gas_deploy.bat   # GAS 部署（Windows：公司网络）
│
├── docs/                    # 文档
│   ├── progress.md          # 项目进度
│   └── gemini_prompt.md     # Gemini 提示词
│
├── infra/                   # Docker 编排
│   ├── web/docker-compose.yml
│   └── tdarr/docker-compose.yml
│
└── video merge/             # 视频延时合成
    ├── run_all.sh           # crontab 总控
    ├── auto_merge.sh        # 小米 720P
    ├── yingshi_auto_merge.sh# 萤石 1080P
    ├── livingroom_auto_merge.sh # 客厅 4K
    ├── test_merge.sh        # 测试框架
    └── notify.sh            # Pushover 通知
```

## 功能特性

- 📊 **专注力看板** — 日历视图、统计卡片、活动时长分布图表
- 🥈🥇 **代币系统** — 自动计算专注奖励、金币连击奖励、护眼里程碑
- 🛒 **兑换商店** — 银币/金币兑换快乐时间，支持后台配置
- 🔄 **币种交换** — 银币金币互相兑换，汇率可后台设置
- 🎨 **自定义头像** — 支持 Emoji 和上传自定义图片
- 📜 **成长指南** — 活动规则、代币机制、专注力技巧速查
- 🎥 **视频自动合并** — 3 路摄像头 30 倍速延时合成

## 部署

### GAS 后端

1. 将 `gas/emma_focus_api.gs` 部署到 Google Apps Script
2. 在 GAS 部署中获取 API URL，更新 `index.html` 中的 `GOOGLE_API_URL` 和 `API_TOKEN`

### NAS 前端 + 脚本（一键部署）

```sh
# 直接将本地改动推送到极空间 NAS
sh deploy/deploy.sh
```

`deploy/deploy.sh` 会自动：
1. 从 macOS Keychain（Mac）或 WEBDAV_PASS 环境变量（Windows）读取凭证
2. 配置 rclone WebDAV 连接（自动创建 remote）
3. 内网 IP 优先 → 外网 Tailscale Funnel fallback
4. `rclone sync` 同步所有文件（权限自动保留）
5. 发送 Pushover 部署完成通知

### GAS 后端部署

```sh
# Mac（家庭网络，直连）
sh deploy/deploy_gas.sh
```

```powershell
# Windows（公司网络，通过代理）
.\deploy\run_gas_deploy.bat
```

### Windows NAS 部署

```powershell
# 需先设置 WEBDAV_PASS 环境变量
.\deploy\run_deploy.bat
```

## 技术栈

- 前端：原生 HTML + Tailwind CSS + Chart.js
- 后端：Google Apps Script (GAS)
- 数据存储：Google Sheets
- 视频处理：ffmpeg + Intel QSV 硬件加速

---

## 🎥 video merge — 监控视频延时合成

在极空间 NAS 上运行，通过 Docker + ffmpeg 将 3 路摄像头的每日视频合成为 30 倍速延时视频，供 Gemini 分析。

### 当前摄像头

| # | 名称 | 源位置 | 输出目录 |
|---|------|--------|---------|
| 1 | **书房主机位** | NVMe14 `xiaomi_camera_videos/` | `export_videos/` |
| 2 | **书房辅机位** | NVMe14 `监控中心/` | `export_videos_yingshi/` |
| 3 | **客厅** | SATA13 `XiaomiCamera_00_B888808E0906/` | `export_videos_livingroom/` |

### 编码与分辨率

| 摄像头 | 型号 | 传感器 | 源编码 | 源分辨率 | 输出编码 | 输出分辨率 |
|--------|------|--------|--------|---------|---------|---------|
| 书房主机位 | 小米智能摄像机 云台版2K | 300万像素 | H.265 | 2304×1296 | H.264 (QSV) | 720P |
| 书房辅机位 | 萤石 C6Wi | 800万像素 | H.265 | 3840×2160 | H.264 (QSV) | 1080P |
| 客厅 | 小米智能摄像机4 4K | 800万像素 | H.265 | 3840×2160 | **H.265 (QSV)** 🆕 | 4K |

> **编码说明：**
> - 所有源视频均为 H.265 (HEVC) 编码。
> - 客厅输出已切换为 **hevc_qsv**（硬件 H.265 编码），文件大小预计减半。
> - 书房主/辅机位保持 H.264 输出以保持兼容性。
> - 使用 `-2:HEIGHT` 保持原始宽高比。
> - 书房主/辅机位降分辨率输出节省空间，客厅保留 4K 原分辨率。

### 脚本说明

| 脚本 | 功能 |
|------|------|
| `auto_merge.sh` | 小米 → 720P 30x，09:00-22:59 |
| `yingshi_auto_merge.sh` | 萤石 → 1080P 30x，逐小时合成再拼接 |
| `livingroom_auto_merge.sh` | 🆕 客厅 → 4K 30x，平面目录文件名解析 |
| `test_merge.sh` | 🧪 测试框架：重启容器→清 temp→快速验证（~1 分钟） |
| `run_all.sh` | crontab 22:45 总控 [1/3][2/3][3/3] |
| `notify.sh` | Pushover 通知（从 `.env` 读取凭证，不在 git 中） |

### 功能特性

| 特性 | 说明 |
|------|------|
| 🔄 **自动重试** | ffmpeg 失败后自动重试 1 次（共 2 次尝试） |
| 🔔 **Pushover 通知** | 开始/完成/失败通知，走 NAS Task App |
| 🎯 **可配置分辨率** | `XIAOMI_RES` / `YINGSHI_RES` / `LIVINGROOM_RES` |
| 📄 **日志轮转** | 单文件超过 10MB 自动重命名 `.old` 后新建 |
| 📊 **文件信息** | 成功日志记录文件大小和视频时长 |
| 🧪 **测试模式** | `TEST_MODE=true` → 1 天 x 2 片段，不影响生产数据 |

### 配置方式

```sh
# 调整输出分辨率
export XIAOMI_RES=480        # 小米 480P
export YINGSHI_RES=720       # 萤石 720P
export LIVINGROOM_RES=2160   # 客厅 4K

# 调整日志轮转阈值
export MAX_LOG_SIZE=20971520  # 20MB

# 然后执行
sh run_all.sh
```

### 测试

```sh
# 在 NAS 上执行（自动重启容器 + 清理 temp + 快速验证）
cd /tmp/zfsv3/nvme14/13918962622/data/scripts
sh test_merge.sh
```

### 输出文件

- 小米：`Xiaomi_Camera_YYYYMMDD.mp4` → `export_videos/`
- 萤石：`Ezviz_60x_1080P_YYYYMMDD.mp4` → `export_videos_yingshi/`
- 客厅：`LivingRoom_4K_YYYYMMDD.mp4` → `export_videos_livingroom/`