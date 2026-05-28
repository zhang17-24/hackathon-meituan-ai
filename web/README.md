# NailFlow Web Prototype

一个用于美团黑客松演示的静态前端壳子，风格参考 Codex/Marvis 的 Agent 工作台。

## Routes

- `/`：Agent Chat 总控台
- `/try-on`：AI 美甲试戴流程
- `/ops`：类 OpenClaw 的运营客服 Agent
- `/architecture`：建议代码架构
- `/dataset`：本地素材库抽样

## Next

接入后端后，建议把上传、任务状态、Agent 日志、质量评分和人工确认动作抽成统一的 `Run` 数据模型。
