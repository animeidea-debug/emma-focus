# Emma Review 集成说明

## 职责分工

- Video Merge：生成书房视频并写入 matching `.ready` manifest；
- `emma-review` Skill：规则、任务包和严格 JSON 校验；
- ChatGPT Work 或已批准模型：生成候选 JSON；
- 本地视觉流水线：生成本地 `pending_review` 候选；
- Emma Focus Admin：家长审核、修正和最终生产写入。

ChatGPT Work 与 Codex 不共享聊天记录。它们只通过仓库中的 Skill、可提交的
规则文档和 Git 外的日期级任务目录交接。

## 安全流程

```text
Study_YYYYMMDD.mp4 + matching ready manifest
  → prepare / local candidate pipeline
  → raw result.json
  → strict validate
  → pending_review
  → parent review in Admin
  → parent-confirmed production import
```

模型或脚本不得直接调用生产写接口，不得接收 PIN，不得在提示词、结果、日志或
版本库中记录凭证。HTTP 成功不等于业务数据正确；写入仍必须经过后端规则、备份
和家长确认。

## 准备与校验

对单一日期执行：

```sh
python3 skills/emma-review/scripts/emma_review.py ready YYYY-MM-DD \
  --video-dir "/path/to/export_videos/书房"

python3 skills/emma-review/scripts/emma_review.py prepare YYYY-MM-DD \
  --video-dir "/path/to/export_videos/书房"

python3 skills/emma-review/scripts/emma_review.py validate \
  /path/to/.emma-review/YYYY-MM-DD/result.json \
  --expected-date YYYY-MM-DD
```

新视频必须具有 producer manifest。只有经家长确认的历史视频才允许额外使用
`--allow-legacy-stable`。

## 本地候选运行器

```sh
EMMA_VIDEO_DIR="/path/to/export_videos/书房" \
EMMA_REVIEW_MODEL="/path/to/local-model" \
sh run_tonight.sh YYYY-MM-DD
```

运行器会复制视频及 matching manifest 到本地缓存，然后运行本地流水线。结果
始终是 `pending_review`；它不上传视频、不 POST 生产 API，也不读取 PIN。

## 自动化门槛

自动导入前至少需要：

- 服务端复用严格校验，并对写入按日期和结果哈希幂等；
- 受限的家长批准机制，不将 PIN 暴露给模型或无人值守脚本；
- 写入前备份、可读审计日志和可验证回滚；
- 失败、待审核和完成状态的家长通知；
- 经多日人工审核验证的模型准确性与保留策略。
