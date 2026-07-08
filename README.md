# Emma 专注力成长看板

亲子专注力管理系统，追踪和激励孩子的学习专注力，通过代币（银币/金币）奖励机制培养自驱自律习惯。

## 项目结构

```
├── index.html              # 前端看板仪表盘
├── admin.html              # 管理后台 - 数据审计、兑换商店、汇率配置
├── emma_focus_api.gs       # Google Apps Script 后端 API
│
├── deploy/                 # 部署脚本
│   ├── deploy.sh            # NAS 部署（跨平台：Mac/Windows/Linux）
│   ├── deploy_gas.sh        # GAS 部署（Mac：家庭网络，直连）
│   ├── run_deploy.bat       # NAS 部署（Windows：公司/家庭网络）
│   └── run_gas_deploy.bat   # GAS 部署（Windows：公司网络，代理）
│
├── infra/                  # Docker 编排文件（版本管理）
│   ├── web/docker-compose.yml   # nginx + fastapi 前端服务
│   └── tdarr/docker-compose.yml # tdarr 视频处理 + Intel QSV
│
└── video merge/            # 监控视频延时合成（部署于极空间 NAS）
    ├── run_all.sh            # crontab 总控调度 + Pushover 通知
    ├── auto_merge.sh         # 小米摄像头 → 720P 30倍速
    ├── yingshi_auto_merge.sh # 萤石摄像头 → 1080P 30倍速
    ├── livingroom_auto_merge.sh # 🆕 客厅摄像头 → 4K 30倍速
    ├── test_merge.sh         # 🧪 测试框架（快速验证所有脚本）
    └── notify.sh             # Pushover 通知辅助函数库
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

1. 将 `emma_focus_api.gs` 部署到 Google Apps Script
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

| # | 名称 | 位置 | 分辨率 | 源盘 | 输出目录 |
|---|------|------|--------|------|---------|
| 1 | 小米 (Emma) | NVMe14 `xiaomi_camera_videos/` | 720P | NVMe14 SSD | `export_videos/` |
| 2 | 萤石 (Emma) | NVMe14 `监控中心/` | 1080P | NVMe14 SSD | `export_videos_yingshi/` |
| 3 | 🆕 客厅小米 | SATA13 `XiaomiCamera_00_B888808E0906/` | 4K | SATA13 HDD | `export_videos_livingroom/` |

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