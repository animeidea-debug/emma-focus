# Emma Focus - 项目进度

> 项目技术状态文档。克隆到任何设备后先读此文件了解当前状态。

## 项目概览

亲子专注力管理系统，追踪和激励学习专注力。
- **前端看板**：`index.html`（NAS nginx）
- **后端**：FastAPI + SQLite（本地容器 `site_backend`）
- **NAS 视频处理**：`merge_v2.sh` -> ffmpeg + QSV 加速
- **品牌**：时光当铺 - 自律典当时光，规划兑换自由

## 当前状态（2026-07-28）

**已提交（HEAD = `a35c902`）：**
- Emma Review 仓库级 Skill（`skills/emma-review/`）、统一审计 Prompt、严格 JSON 校验器与单元测试
- Video Merge ready 契约：`.part.mp4` -> ffprobe 校验 -> 原子发布 -> `.ready` 清单
- 品牌更名为时光当铺，代币推导改为独立计算
- TMOS 奖励显示优化（隐藏结算 ID，改名为「时间管理」）
- 统一备份策略（08:00 + 20:00 联动备份，TMOS + Emma 独立目录）

**已验证（本地静态 + 单元测试）：**
- `bash -n` / `py_compile` / `git diff --check` ✅
- `tests/test_emma_review_skill.py` 7 项 ✅
- `tests/test_poc_business.py` 6 项 ✅

## 关键服务

| 服务 | 端口 | 说明 |
|------|------|------|
| nginx 前端 | 8888 | `index.html` + `admin.html` |
| 后端 API | 8888/api/ | FastAPI + SQLite |
| WebDAV 部署 | 8889 | 脚本/HTML/后端同步 |
| SSH | 10000 | 远程管理 |

## 架构

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  浏览器      │────▶│  nginx (8888) │────▶│ site_backend │
│ index.html   │     │  site_front   │     │ main.py      │
│ admin.html   │     │ /api/ -> 80   │     │ poc_main.py  │
└─────────────┘     └──────────────┘     └─────────────┘
```

## 本地视觉流水线

### 架构

```
视频 -> 抽帧(4s间隔) -> 场景差异过滤 -> VLM 分类 -> Python 阶段合并 -> 结果 JSON
                                            ↑                    ↑
                                     原子标签观察         确定性分类决策
                                     (VLM 只做视觉)       (Python 做审计规则)
```

### 模型基准测试

| 模型 | 大小 | 加载 | 推理(12帧) | 峰值内存 | 适用性 |
|------|------|------|-----------|---------|--------|
| Qwen3-VL-4B-Instruct-4bit | 2.9 GB | 0.6s | 16.6s | 4.6GB | ✅ 主力 |
| Qwen3-VL-8B-Instruct-4bit | 7.3 GB | 1.5s | 19.5s | 7.28GB | ✅ 备选 |
| Qwen2.5-VL-7B-Instruct-4bit | 5.3 GB | - | - | - | ⚠️ 视觉准但成人检测过强 |
| Llama-3.2-11B-Vision-Instruct-4bit | 5.6 GB | - | - | - | ❌ 不支持多图/batch=1 |

### 已知技术问题

1. **384px 分辨率不足**：丢失活动细节，无法区分「辅导 vs 独立学习」「休息 vs 分心」
2. **成人检测过强**（Qwen2.5-VL-7B）：adult=yes 误报率接近 100%，导致全部被归类为 Coaching
3. **Distractions 虚高**（8B）：非学习状态被标为 Distraction
4. **mlx-vlm 限制**（Llama-3.2-11B）：不支持多图输入，仅 batch=1，140 帧需约 30 分钟
5. **Eye Rest / Coaching 漏检**：流水线对这两类状态的识别率低

### 下一步架构方向

用户认可方向：**VLM 只描述画面活动，Python 做分类决策**
- VLM 提示词改为纯原子标签（writing_reading/idle/resting/talking/moving/looking_at_screen）
- Python 接管所有分类逻辑，依据时长 + 成人存在做审计规则判断
- 智能合并：中性短片段自动合并到相邻长片段，非中性片段保持独立
- 间距检查（>30min 不合并）防止跨休息期错误合并

## 统一备份策略（07-28）

- TMOS + Emma Focus 联动备份，每天 08:00 + 20:00 自动执行
- 备份目录独立于容器数据目录，防止容器崩溃/rclone 事故导致备份丢失
- 联动脚本 `backup_all.sh` 统一调度，合并 Pushover 通知
- TMOS 备份：SQLite 快照 + SHA256 校验 + JSON 导出
- Emma 备份：SQLite 快照 + 10 张表 CSV 导出
- 30 天自动轮转清理

## 待办清单

### P1 - 本地视觉流水线改进
- [x] 实现抽帧、场景差异过滤和分类流水线（`emma_pipeline.py`）
- [x] 4 天基准测试完成（4B/8B/Qwen2.5-VL-7B/Llama-3.2-11B）
- [x] V6 分类提示词改进（精简+关键规则+wall_sec 时长+批次调整）
- [ ] **探索新架构：VLM 描述画面 -> Python 总结判断**
- [ ] 尝试更高分辨率（448/512px）或边界复核帧策略
- [ ] 解决 Qwen2.5-VL-7B 成人过检问题
- [ ] 实现每日状态机和结果哈希缓存

### P2 - 安全与自动化
- [ ] 服务端审计校验、`pending_review` 队列和不暴露 PIN 的批准流程
- [ ] 审查所有 API 路由的鉴权与暴露面
- [ ] 替换历史共享密钥
- [ ] 为代币记账、评估改写、兑换、备份增加可重复测试

### P3 - 清理
- [ ] 确认 `deprecated/infra/watchtower/docker-compose.yml` 改动是否回滚
- [ ] 提交并推送工作区改动（pipeline + 诊断脚本）

## 项目规模

| 指标 | 数值 |
|------|------|
| 后端 | `poc_main.py` ~1,362 行 / ~54 KB |
| 前端 | `index.html` ~2,081 行；`admin.html` ~733 行 |
| Emma Review | `emma_review.py` ~620 行 + 审计 Prompt 212 行 |
| Shell 脚本 | 活跃 8 个（含 video merge），~1,000 行 |
| 测试 | 5 个测试文件（emma-review 7 项 + poc 业务 6 项 + 备份/通知） |
| Pipeline | `emma_pipeline.py` ~781 行 |

## 跨机器协作流程

```
另一台电脑: git pull -> 修改 -> git commit -> git push
我的 Mac:   git pull -> 继续开发 -> sh deploy/deploy.sh
           修改 compose/nginx -> cd ~/Desktop/NAS -> sh deploy/deploy.sh web
```
