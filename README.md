# Emma 专注力成长看板

亲子专注力管理系统，追踪和激励孩子的学习专注力，通过代币（银币/金币）奖励机制培养自驱自律习惯。

## 项目结构

```
├── index.html / admin.html  # 前端看板 (已迁移到本地 API)
├── README.md                # 项目说明（本文件）
│
├── deploy/                  # 部署脚本
│   ├── deploy.sh            # NAS 部署（HTML + 后端 + 脚本）
│   ├── backup_data.sh       # 数据备份（SQLite → CSV）
│   └── import_gas_to_sqlite.py # GAS→SQLite 迁移工具
│
├── docs/                    # 文档
│   ├── progress.md          # 项目进度（含部署流程）
│   └── gemini_prompt.md     # Gemini 提示词
│
├── infra/web/backend/       # 后端 Python 代码（参考副本）
│   ├── main.py              # 头像服务 (port 80)
│   └── poc_main.py          # 业务逻辑 (port 81, 替代 GAS)
│
└── video merge/             # 视频延时合成
    ├── run_v2.sh            # V2 总控脚本
    ├── merge_v2.sh          # V2 通用合成脚本
    └── notify.sh            # Pushover 通知
```

> **⚠️ 重要**：Docker Compose 和 nginx 配置由 `~/Desktop/NAS` 项目统一管理。
> 修改 `infra/web/` 后需同步到 NAS 项目并执行 `sh ~/Desktop/NAS/deploy/deploy.sh web`。

## 架构

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

## 功能特性

- 📊 **专注力看板** — 日历视图、统计卡片、活动时长分布图表
- 🥈🥇 **代币系统** — 自动计算专注奖励、金币连击奖励、护眼里程碑
- 🛒 **兑换商店** — 银币/金币兑换快乐时间，支持后台配置
- 🔄 **币种交换** — 银币金币互相兑换，汇率可后台设置
- 🎨 **自定义头像** — 支持 Emoji 和上传自定义图片
- 📜 **成长指南** — 活动规则、代币机制、专注力技巧速查
- 🎥 **视频自动合并** — 3 路摄像头 30 倍速延时合成

## 部署流程

### 前端 + 后端代码（Emma Focus 项目）
```sh
cd ~/Desktop/Emma\ Focus
git pull                    # 拉取最新
sh deploy/deploy.sh         # 同步到 NAS (HTML + 后端 + scripts)
```

### Docker Compose / Nginx（NAS 项目）
```sh
cd ~/Desktop/NAS
git pull                    # 拉取最新
sh deploy/deploy.sh web     # 上传 compose + nginx 并重启容器
```

### 数据迁移（仅首次）
```sh
# 1. 从 GAS 导出数据
curl -sL "https://script.google.com/macros/s/{DEPLOY_ID}/exec?action=exportAll&token=emma2026_secure" -o /tmp/export.json

# 2. 复制到容器
ssh -p 10000 13918962622@192.168.6.108 \
  '/usr/bin/docker exec -i site_backend sh -c "cat > /app/export.json"' < /tmp/export.json

# 3. 导入 SQLite（脚本已预置在容器内）
ssh -p 10000 13918962622@192.168.6.108 \
  '/usr/bin/docker exec site_backend python3 /app/import_gas_to_sqlite.py /app/export.json'
```

### 数据备份
```sh
# crontab: 0 8 * * * /tmp/.../scripts/backup_data.sh
# 直接从容器 SQLite 导出所有表为 CSV
docker exec site_backend sqlite3 -header -csv /app/data/poc.db "SELECT * FROM evaluations;" > backup.csv
```

## 技术栈

- 前端：原生 HTML + Tailwind CSS + Chart.js
- 后端：FastAPI + SQLite（Python 容器）
- 代理：nginx（反向代理）
- 视频处理：ffmpeg + Intel QSV 硬件加速
- 数据备份：docker exec → sqlite3 → CSV