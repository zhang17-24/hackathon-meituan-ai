# NailFlow 代码架构建议

## Monorepo

```text
nailflow/
  apps/
    web/                 # React/Vite 工作台，路由、上传、对话流、人工确认
    api/                 # FastAPI 或 Node BFF，任务状态、文件、鉴权、SSE
    worker/              # 视觉模型任务、批处理、队列消费
  packages/
    agents/              # DeerFlow graph 与子 Agent 定义
      planner/
      vision/
      stylist/
      ops/
      customer_service/
    vision/              # hand landmark、nail mask、inpaint、quality scoring
    ops/                 # 趋势分析、活动生成、客服 RAG、门店执行器
    shared/              # Run、Asset、User、Merchant、NailStyle 类型
  data/
    raw/                 # 原始赛题素材
    processed/           # mask、缩略图、向量索引
    mock/                # 订单、预约、客服、门店库存 mock 数据
  research/
    sources/             # PDF、zip、网页资料
    cloned_repos/        # 参考项目 copy
    notes/               # 调研与产品方案
```

## Agent Graph

```text
User Intent
  -> PlannerAgent
  -> VisionAgent       # 手部检测、甲面 mask、局部试戴
  -> StylistAgent      # 款式理解、提示词、审美解释
  -> QualityAgent      # 边界、肤色、光照、款式相似度评分
  -> OpsAgent          # 趋势洞察、运营日报、活动建议
  -> CustomerAgent     # 多轮客服、预约、售后
  -> HumanConfirmNode  # 高风险动作人工确认
  -> ExecutorTool      # Mock API / 美团 API
```

## 核心数据模型

- `Run`：一次 Agent 执行，包含状态、步骤、日志、产物和人工确认点。
- `Asset`：用户手图、款式图、mask、输出图、缩略图。
- `NailStyle`：颜色、图案、甲型、饰品、风格标签、价格区间。
- `MerchantSignal`：点击、收藏、订单、搜索、库存、预约。
- `ActionProposal`：Agent 建议的运营动作，必须支持确认、拒绝、回滚记录。

## 技术路线

- 前端：React Router + SSE/WebSocket 展示 Agent 日志，上传区和画布区分离。
- 后端：优先复用 DeerFlow 的 sub-agent、memory、sandbox、skills 思路。
- 视觉：MediaPipe Hands 定位手部，SAM 做甲面 mask，局部扩散模型做试戴。
- 运营：向量库 + 规则约束 + 工具调用，客服回复必须引用门店事实或 mock 事实。
- 评测：生成质量分、运营转化指标、异常处理覆盖数，映射到赛题评分标准。
