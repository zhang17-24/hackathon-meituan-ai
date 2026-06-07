---
name: daily_report
description: 每日美甲运营日报生成与推送 — 聚合趋势数据、生成洞察报告、格式化日报并推送到飞书/钉钉
group: nail_ops
version: v1
tools:
  - trend_query_tool
  - trend_discovery_tool
  - ops_analysis_tool
---

# 日报生成技能

## 触发条件
- 定时：每日 08:55 (APScheduler cron)
- 手动：运营人员在对话中说"生成日报"或"今天的数据怎么样"

## 执行流程
1. 调用 trend_query_tool(days=7, top_n=20) 获取近期趋势数据
2. 调用 trend_discovery_tool(days=7) 生成洞察报告（爆款/冷门识别）
3. 调用 ops_analysis_tool 基于洞察生成具体运营建议
4. 按日报模板格式化：数据概览 → 爆款TOP5 → 冷门预警 → 运营建议
5. 通过飞书/钉钉推送

## 输出模板

### nailflow 运营日报
> {date} | 近 {days} 天数据

**数据概览**
- 追踪款式数 / 活跃信号数 / 爆款数 / 冷门预警数

**热门款式 TOP 5**
（含试戴量变化趋势和运营建议）

**冷门预警**
（连续低信号款式，建议下架或换封面）

**运营建议**
（基于 AI 分析的具体可执行建议）

## 注意事项
- 数据为空时推送"今日暂无足够数据"提示
- 周末数据量少时自动扩大窗口到 14 天
