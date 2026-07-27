# Emma Review 集成说明

## 当前边界

ChatGPT Work 用于视频理解和生成候选 JSON；Emma Focus 仓库中的
`emma-review` Skill 负责规则、任务包与确定性校验；家长 Admin 负责最终审核
和生产入库。

ChatGPT Work 与 Codex 的聊天记录不会自动合并。两者通过同一个本地仓库、
仓库级 Skill，以及视频目录旁的 `.emma-review/YYYY-MM-DD/` 任务目录交接。

每日 ready 信号、视频目录映射、本地视觉模型分工和验收基线见
`docs/emma-review/automation-design.md`。

## 安全工作流

```text
Study_YYYYMMDD.mp4
  → Video Merge ffprobe 校验、原子发布并写入 .ready 清单
  → prepare 生成 prompt.txt 和 job.json
  → ChatGPT Work 或已批准的视频模型生成 result.json
  → validate 严格校验
  → 家长在 Admin 预览和修正
  → 家长输入 PIN 并确认入库
```

在服务端校验、待审核状态和专用受限凭证完成前，不允许 ChatGPT Work 或其他
模型直接 POST 生产 `/api/poc/evaluate`、`/api/poc/batch-write` 或
`/api/poc/generic`。

原因：

- 当前后端会立即写入 evaluation、stage 和派生代币流水。
- 当前后端信任请求中的 `Tokens_Net` 等聚合字段。
- 家长 PIN 不得提供给模型、Skill、提示词、结果文件或无人值守任务。
- 模型返回 HTTP 成功不等于业务数据正确。

## Work 项目交接

在 ChatGPT 桌面版 Emma Review Work 中授权打开 Emma Focus 本地目录，并
安装或选择仓库中的 `emma-review` Skill。用 `@Emma Review` 显式调用。

已有 Work 项目应生成一份不含视频、身份细节和凭证的交接摘要，保存为
`docs/emma-review/work-handoff.md`。真实视频及日期结果必须保存在 Git
仓库之外。

对于 2026-07-26 首次结果：

1. 保留 Work 返回的原始 JSON，不要手工改写。
2. 将它命名为 `result.json`，放入对应视频目录的
   `.emma-review/2026-07-26/`。
3. 运行：

   ```sh
   python3 skills/emma-review/scripts/emma_review.py \
     validate /path/to/.emma-review/2026-07-26/result.json \
     --expected-date 2026-07-26
   ```

4. 校验通过后仍先在 Admin 页面人工审阅，再由家长确认入库。

## 后续自动化门槛

全自动导入前至少需要：

- 后端复用同一套严格校验规则；
- 结果先进入 `pending_review`，不得直接影响正式账本；
- 家长批准操作使用短期会话或独立受限凭证，不暴露 PIN；
- 按日期幂等，重复提交不会重复奖励；
- 写入前备份、完整审计日志和可验证回滚；
- 失败与待审核结果通过 Pushover 通知。

## 2026-07-26 首次生产闭环验证

2026-07-27 完成第一次受控提交实验：

- 原始 Work JSON 通过仓库严格校验器；
- 写入前创建 `/app/backups/20260727/poc.db` 并通过完整性检查；
- ZConnect 外网 API 对无浏览器会话的请求返回 302，因此不作为自动化入口；
- 使用 Mac 到 NAS 的内网 API，并由 macOS 原生隐藏对话框临时读取家长 PIN；
- PIN 未写入文件、命令参数、日志或模型上下文；
- 生产回读确认 2 Focus、4 Distractions、15 分钟 Eye Rest、12 个阶段；
- 新增一笔 `award_silver +1`，当天原有两笔兑换流水保持不变。

该实验只验证了安全的交互式提交。正式自动化仍应采用候选结果
`pending_review`、结果哈希绑定、短期单次批准令牌和服务端校验。
