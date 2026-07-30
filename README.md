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
│   └── emma-review/         # Work 交接、隐私边界与导入流程
│
├── skills/emma-review/      # Emma Review 规则、Prompt 和严格 JSON 校验器
├── .agents/skills/          # Codex 项目级 Skill 发现链接
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

## 文档与协作入口

- `AGENTS.md`：长期有效的项目边界、安全规则和验证要求，供 Codex/Cline 等编码代理读取。
- `docs/progress.md`：当前状态、已验证事实、进行中工作和下一步计划；项目交接时优先阅读。
- `README.md`：面向开发者和维护者的稳定项目说明，不记录逐次会话流水。
- `docs/emma-review/`：视频分析、Work 交接、隐私边界和审核导入流程。

统一约定使用复数文件名 `AGENTS.md`。GitHub SSH 凭证属于本机和 GitHub
账户配置，不写入仓库；项目 remote 可以使用 SSH，但不得提交私钥、口令或
个人密钥路径。

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
- 🥈🥇 **代币系统** — 自动计算专注奖励、分心扣除和金币连击奖励
- 🛒 **兑换商店** — 银币/金币兑换快乐时间，支持后台配置
- 🔄 **币种交换** — 银币金币互相兑换，汇率可后台设置
- 🎨 **自定义头像** — 支持 Emoji 和上传自定义图片
- ⭐ **TMOS 成长联动** — 星星等级、称号与头像边框统一展示；TMOS 银币/金币写入同一交易账本，并可按来源筛选、展开结算和原始奖励
- 📜 **成长指南** — 活动规则、代币机制、专注力技巧速查
- 🎥 **视频自动合并** — 书房与客厅摄像头按各自参数自动生成延时视频
- 🤖 **Emma Review** — ChatGPT Work/视频模型生成候选审计 JSON，本地严格校验后由家长确认入库
- 🔔 **运行通知闭环** — 总任务与分摄像头启动/结果通知、未启动看门狗、备份告警、Heartbeat 去重/恢复/升级与每日摘要；生产通知库由 NAS 仓库统一管理

## Emma Review

仓库级 Skill 位于 `skills/emma-review/`，并通过
`.agents/skills/emma-review` 被 Codex 自动发现。完整审计 Prompt 的唯一真源
是 `skills/emma-review/references/audit-prompt.md`。

模型生成的 JSON 不得直接写入生产后端。先执行：

```sh
python3 skills/emma-review/scripts/emma_review.py \
  validate /path/to/result.json --expected-date YYYY-MM-DD
```

校验通过后仍需在 Admin 页面人工预览并由家长确认。真实视频、分析结果、PIN
和模型凭证不得提交 Git。详细流程见 `docs/emma-review/integration.md`。

本地视觉流水线当前以 Qwen2.5-VL-7B 4-bit 为主模型，输入按最长边 640px
等比例缩放，不再把 16:9 画面拉伸成正方形。它支持使用 Git 外的家长确认
参考图做同人匹配，并将人物身份、人数、成人直接辅导、Emma 主动屏幕交互、
注意力方向和基础活动拆成窄问题，再由 Python 按明确优先级合成类别。主动
Screen 必须同时满足“正在操作/观看设备”和“注意力在屏幕”两项证据；短于
5 分钟、前后均为独自纸面学习的孤立查询可折回连续学习，但 Coaching 前的
短时 Screen 保留。场景过滤后的大观察缺口必须拆组，OSD 跨度超过 20 分钟
的组还会递归细分；成人或不确定身份区间是阶段合并的硬边界。任一组 OSD
缺失或倒退都会终止候选生成。流水线只生成带结果哈希的 `pending_review`
候选，不接受 PIN，也不直接 POST 生产 API。

后续日期运行时，流水线会从同一 Git 外 `.emma-review` 根目录读取更早日期、
已提交的 `parent_feedback.json`。它只把去重、限量后的通用 `lesson` 提供给
本地 VLM，并在 review metadata 中记录反馈数量和源文件哈希；具体日期区间、
完整结果和 PIN 不会进入模型提示。人物观察明确区分“成人仅在旁”与“直接
辅导”，前者不再自动归为 Coaching。

本地运行框架固定在 `skills/emma-review/requirements-local-vision.txt`；
当前为 `mlx-vlm 0.6.8`。升级只发生在 `.venv-emma-review` 隔离环境中，
不会改变 NAS 后端或生产容器。

本机候选运行器要求显式提供视频与模型目录，并默认拒绝没有 Video Merge
`.ready` 清单的文件：

```sh
EMMA_VIDEO_DIR="/path/to/export_videos/书房" \
EMMA_REVIEW_MODEL="/path/to/local-model" \
sh run_tonight.sh YYYY-MM-DD
```

它只在本地生成 `pending_review` 候选；视频、结果、家长反馈和任何身份参考图
均保留在 Git 外。

## 部署流程

### NAS Git release（推荐）
```sh
nas-deploy emma-focus --ref <完整的40位提交SHA>
# 或在确认 main 已可发布后：
nas-deploy emma-focus --latest
```

该命令由 NAS 基础设施仓库管理，会在 NAS 上拉取源码、运行测试、备份
SQLite、切换网页/后端/受控视频脚本并执行健康检查。数据库、`.env` 和统一
`notify.sh` 不属于 release。旧的 `sh deploy/deploy.sh` WebDAV 流程只保留
为迁移期应急路径。

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
# 由 NAS 项目的 UID 1002 用户 crontab 在每天 08:00 和 20:00 执行。
docker exec site_backend python3 /app/backup_data.py

# 容器输出：/app/backups/YYYYMMDD/
# NAS 输出：.../data/backups/emma_data/YYYYMMDD/
```

## 技术栈

- 前端：原生 HTML + Tailwind CSS + Chart.js
- 后端：FastAPI + SQLite（Python 容器）
- 代理：nginx（反向代理）
- 视频处理：ffmpeg + Intel QSV 硬件加速
- 数据备份：Python SQLite 一致性快照 + CSV 导出

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
