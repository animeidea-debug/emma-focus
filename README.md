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
├── infra/web/backend/       # 后端 Python 代码（由 deploy.sh 同步）
│   ├── main.py              # 头像服务 (port 80)
│   └── poc_main.py          # 业务逻辑 (port 81, 替代 GAS)
│
├── deprecated/              # 已退役文件保留区（GAS、旧 compose 等）
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

## 安全配置

首次部署使用一次性 `EMMA_ADMIN_INITIAL_PIN`。PIN 不得写入本仓库、HTML 或 Docker Compose 明文；应放在 NAS 项目 `infra/web/.env` 中，并由 Compose 注入后端容器：

```yaml
services:
  site-backend:
    environment:
      EMMA_ADMIN_INITIAL_PIN: ${EMMA_ADMIN_INITIAL_PIN:?EMMA_ADMIN_INITIAL_PIN is required}
```

首次进入 Admin 页面后必须修改临时 PIN。正式 PIN 仅以 PBKDF2 带盐哈希保存在持久化 volume 的 `/app/data/security/admin_auth.json`；修改成功后，环境变量中的临时 PIN 永久失效。

初始化完成并确认 `mustChange=false` 后，应从 NAS `.env` 和 Compose 中移除 `EMMA_ADMIN_INITIAL_PIN`。日常运行不需要保留临时 PIN；只有显式执行账户恢复时才重新配置。

默认不启用跨域访问，当前 nginx 同源部署无需设置 CORS。如确有独立前端来源，可用逗号分隔的 `EMMA_CORS_ORIGINS` 显式配置允许来源。

测试数据端点默认关闭。只有隔离测试环境可以设置 `EMMA_ENABLE_SEED_DUMMY=true`，生产环境禁止启用。
