# Emma 专注力成长看板

亲子专注力管理系统，追踪和激励孩子的学习专注力，通过代币（银币/金币）奖励机制培养自驱自律习惯。

## 项目结构

```
├── index.html              # 前端看板仪表盘
├── admin.html              # 管理后台 - 数据审计、兑换商店、汇率配置
└── emma_focus_api.gs       # Google Apps Script 后端 API
```

## 功能特性

- 📊 **专注力看板** — 日历视图、统计卡片、活动时长分布图表
- 🥈🥇 **代币系统** — 自动计算专注奖励、金币连击奖励、护眼里程碑
- 🛒 **兑换商店** — 银币/金币兑换快乐时间，支持后台配置
- 🔄 **币种交换** — 银币金币互相兑换，汇率可后台设置
- 🎨 **自定义头像** — 支持 Emoji 和上传自定义图片
- 📜 **成长指南** — 活动规则、代币机制、专注力技巧速查

## 部署

1. 将 `emma_focus_api.gs` 部署到 Google Apps Script
2. 将 `index.html` 和 `admin.html` 部署到任意静态托管服务
3. 在 GAS 部署中获取 API URL，更新 `index.html` 中的 `GOOGLE_API_URL` 和 `API_TOKEN`

## 技术栈

- 前端：原生 HTML + Tailwind CSS + Chart.js
- 后端：Google Apps Script (GAS)
- 数据存储：Google Sheets