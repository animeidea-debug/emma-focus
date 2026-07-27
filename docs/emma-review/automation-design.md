# Emma Review 每日视频流程

## 目标与边界

每天只分析书房成品 `Study_YYYYMMDD.mp4`。Video Merge 负责宣告成品 ready；
Emma Review 负责抽帧、分类、确定性计算、JSON 校验和待审核队列。Pushover
用于给家长显示状态，不作为机器间消息总线。

视频和日期级分析产物都留在 NAS 挂载卷，不进入 Git。模型、脚本或无人值守
任务不得持有家长 PIN，生产写入继续经过 `pending_review` 和家长批准。

## 目录契约

| 用途 | 路径 |
|---|---|
| Mac 书房视频目录 | `/Volumes/nvme14-139XXXX2622/export_videos/书房` |
| NAS 主机目录 | `/tmp/zfsv3/nvme14/13918962622/data/export_videos/书房` |
| Tdarr 容器目录 | `/mnt/export_videos/书房` |
| 每日视频 | `Study_YYYYMMDD.mp4` |
| 生产者 ready 清单 | `.ready/Study_YYYYMMDD.ready.json` |
| 分析任务目录 | `.emma-review/YYYY-MM-DD/` |

三种根路径不同，但文件名、字节数、日期和 ready 清单内容必须一致。

## Ready 的唯一可靠定义

Video Merge 必须按以下顺序发布：

1. ffmpeg 写入 `Study_YYYYMMDD.part.mp4`；
2. ffprobe 确认容器可读取且文件非空；
3. 在同一目录内原子改名为 `Study_YYYYMMDD.mp4`；
4. 原子写入 `.ready/Study_YYYYMMDD.ready.json`；
5. 发送 `✅ 书房视频合并完成 | YYYYMMDD` Pushover；
6. 开始处理客厅视频。

因此，家长看到书房完成通知时即可预期 Emma Review 已能开始。自动化不读取
Pushover；它监听同一成功事件写出的 ready 清单。全局 `.finished` 只能说明
书房和客厅流程均已退出，而且部分失败时也会存在，不能作为书房 ready 信号。

历史视频没有 ready 清单时，可在人工确认已收到完成通知后使用：

```sh
python3 skills/emma-review/scripts/emma_review.py ready 2026-07-26 \
  --video-dir "/Volumes/nvme14-139XXXX2622/export_videos/书房" \
  --allow-legacy-stable
```

## 每日状态机

```text
waiting_for_ready
  → prepared
  → extracting
  → coarse_classified
  → boundary_review
  → validated
  → pending_review
  → approved
  → submitted
```

任一步失败均进入 `failed`，保留输入指纹、错误、重试次数和上一个成功阶段。
对同一日期和视频指纹重复运行时必须复用缓存；已 `submitted` 的同一结果哈希
不得再次写入。

## 本地视觉流水线

### 机械预处理

- 读取视频时长、帧率和尺寸，并记录视频字节数与修改时间；
- 第一遍每 10 秒播放时间取一帧，用场景差异过滤连续重复或空房间候选；
- 同时保留完整画面和单独的 OSD 高分辨率裁剪；
- 将 9–16 张连续画面组成一批，但保留每张图的播放时间索引；
- 缓存帧、图像指纹和模型原始响应。

书房成品是 30 倍延时视频。每 10 秒播放时间约等于 5 分钟墙钟时间，所以该
采样率只能用于粗分段，不能直接确认短暂分心、10 分钟 Eye Rest 或精确边界。
对画面变化、类别变化、低置信度和身份不明确区间，应在边界前后改用每
1–3 秒播放时间取帧。

### 模型分工

1. 4B Instruct：空房间、Emma 是否在场、明显活动类别和候选边界；
2. 8B Instruct：只复核低置信度、成人/Emma 身份、Coaching、Screen 和
   Focus 边界；
3. Codex 或经批准的云端视频模型：只处理本地模型冲突或证据不足的片段；
4. Python：合并区间、计算分钟、Focus Blocks、Distractions、Tokens、
   Rating，并运行严格 JSON 校验。

模型只应输出观察事实、候选类别、边界和置信度，不负责奖励算术，也不能直接
写生产数据库。

## M5 MacBook Air 24 GB 可行性

优先测试 MLX-VLM 与 Qwen3-VL Instruct 量化模型：

- 4B 4-bit/5-bit 适合常规粗筛；
- 8B 4-bit 适合按需复核，预计可装入 24 GB 统一内存，但实际峰值由帧数、
  图像分辨率、视觉 token 和 KV cache 决定；
- 30B-A3B 即使每次只激活部分参数，也需装载完整量化权重并保留视觉与缓存
  空间，不适合 24 GB Air 的每日常驻任务；
- Air 无风扇，长时间视觉预填充可能降频，速度必须实测，不能先承诺
  5–15 分钟。

MLX-VLM 的发布记录已出现 Qwen3-VL 视频处理修复和 OpenAI 兼容服务，但其
公开 README 的视频支持列表仍主要列出 Qwen2/Qwen2.5-VL 等型号。因此正式
选型前必须用真实片段验证 Qwen3-VL 的视频/多图路径、OSD OCR 和批量稳定性，
不能只依据模型卡。

## 基准验收

以 2026-07-26 人工审核结果作为第一个金标准，再选至少四天覆盖：

- Emma 完全不在场；
- 成人单独出现；
- Coaching；
- Screen 超过 30 分钟；
- 短时学习、短暂分心和 Eye Rest 边界。

每个模型配置记录总耗时、峰值内存、抽帧数、模型调用数、身份准确率、类别
准确率、阶段边界误差、Focus/Distractions/Tokens 是否完全一致。满足以下
条件前不得自动提交：

- 身份错误为零；
- Focus/Distractions/Tokens 与人工结果完全一致；
- 关键阶段边界误差在预先约定范围内；
- 连续多日无崩溃、无内存压力告警；
- 所有低置信度结果进入 `pending_review`。
