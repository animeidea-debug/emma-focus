# Emma 专注力成长看板

亲子专注力管理系统，追踪和激励孩子的学习专注力，通过代币（银币/金币）奖励机制培养自驱自律习惯。

## 项目结构

```
├── index.html              # 前端看板仪表盘
├── admin.html              # 管理后台 - 数据审计、兑换商店、汇率配置
├── emma_focus_api.gs       # Google Apps Script 后端 API
│
└── video merge/            # 监控视频延时合成（部署于极空间 NAS）
    ├── run_all.sh           # crontab 总控调度 + Pushover 通知
    ├── auto_merge.sh        # 小米摄像头 → 720P 30倍速
    ├── yingshi_auto_merge.sh# 萤石摄像头 → 1080P 30倍速
    ├── notify.sh            # Pushover 通知辅助函数库
    └── docker-compose.yml   # tdarr 服务编排 + Intel QSV 硬解
```

## 功能特性

- 📊 **专注力看板** — 日历视图、统计卡片、活动时长分布图表
- 🥈🥇 **代币系统** — 自动计算专注奖励、金币连击奖励、护眼里程碑
- 🛒 **兑换商店** — 银币/金币兑换快乐时间，支持后台配置
- 🔄 **币种交换** — 银币金币互相兑换，汇率可后台设置
- 🎨 **自定义头像** — 支持 Emoji 和上传自定义图片
- 📜 **成长指南** — 活动规则、代币机制、专注力技巧速查
- 🎥 **视频自动合并** — 小米+萤石监控视频 30 倍速延时合成

## 部署

### GAS 后端

1. 将 `emma_focus_api.gs` 部署到 Google Apps Script
2. 在 GAS 部署中获取 API URL，更新 `index.html` 中的 `GOOGLE_API_URL` 和 `API_TOKEN`

### NAS 前端 + 脚本（一键部署）

```sh
# 直接将本地改动推送到极空间 NAS
sh deploy.sh
```

`deploy.sh` 会自动：
1. 从 macOS Keychain 读取 SMB 凭证（首次需在 Finder 连接并记住密码）
2. 挂载 SMB 共享到 `/Volumes/nvme14-139XXXX2622/`
3. `rsync` 同步 `video merge/` → `scripts/`
4. 复制 `index.html` / `admin.html` → `docker/html/`
5. 发送 Pushover 部署完成通知

## 技术栈

- 前端：原生 HTML + Tailwind CSS + Chart.js
- 后端：Google Apps Script (GAS)
- 数据存储：Google Sheets
- 视频处理：ffmpeg + Intel QSV 硬件加速

---

## 🎥 video merge — 监控视频延时合成

在极空间 NAS 上运行，通过 Docker + ffmpeg 将小米和萤石监控摄像头的每日视频片段合成为 30 倍速延时视频，供 Gemini 分析 Emma 的日常活动。

### 架构

```
极空间 NAS (Intel N100)
  ├── crontab 22:00 ──→ run_all.sh (总控)
  ├── Docker: tdarr_server + tdarr_node
  │    ├── /mnt/source_videos          ← 小米原始视频 (映射自 xiaomi_camera_videos/)
  │    ├── /mnt/export_videos           ← 小米 720P 延时输出
  │    ├── /mnt/source_videos_yingshi   ← 萤石原始视频
  │    └── /mnt/export_videos_yingshi   ← 萤石 1080P 延时输出
  └── temp_workspace/                   ← 临时文件 (映射到容器 /tmp)
```

### 脚本说明

| 脚本 | 功能 |
|------|------|
| `auto_merge.sh` | 小米摄像头 → 720P 30倍速延时，筛选 09:00-22:59 白昼时段 |
| `yingshi_auto_merge.sh` | 萤石摄像头 → 1080P 30倍速延时，逐小时合成后无损拼接 |
| `run_all.sh` | 串行调度 + Pushover 通知（开始/完成/失败） |
| `notify.sh` | Pushover 通知辅助函数库（被其他脚本 source） |
| `docker-compose.yml` | Docker 服务编排，含 Intel QSV 硬件加速配置 |

### 功能特性

| 特性 | 说明 |
|------|------|
| 🔄 **自动重试** | ffmpeg 失败后自动重试 1 次（共 2 次尝试），记录尝试次数 |
| 🔔 **Pushover 通知** | 开始/小米完成/萤石完成/全部完成共 4 条通知，含统计摘要 |
| 🎯 **可配置分辨率** | `XIAOMI_RES` / `YINGSHI_RES` 环境变量，默认 720/1080 |
| 📄 **日志轮转** | 单文件超过 10MB 自动重命名 `.old` 后新建 |
| 📊 **文件信息** | 成功日志记录文件大小和视频时长 (mm:ss) |
| ✅ **失败容错** | 小米异常不影响萤石执行 |

### 配置方式

通过环境变量自定义（可在 crontab 或 run_all.sh 中设置）：

```sh
# 调整输出分辨率
export XIAOMI_RES=480    # 小米输出 480P
export YINGSHI_RES=720   # 萤石输出 720P

# 调整日志轮转阈值（单位 bytes）
export MAX_LOG_SIZE=20971520  # 20MB

# 然后执行
sh run_all.sh
```

### 部署步骤

1. 将 `video merge/` 目录下所有文件拷贝到 NAS 脚本目录（如 `/tmp/.../data/scripts/`）
2. 确保 docker-compose 已启动：`docker-compose -f docker-compose.yml up -d`
3. 添加 crontab 每日定时执行：`crontab -e`
   ```
   0 22 * * * cd /path/to/scripts && sh run_all.sh >> /var/log/video_merge.log 2>&1
   ```

### 输出文件

- 小米：`Xiaomi_Camera_YYYYMMDD.mp4` → `export_videos/`
- 萤石：`Ezviz_60x_1080P_YYYYMMDD.mp4` → `export_videos_yingshi/`
