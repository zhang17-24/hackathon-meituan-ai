# EvaluationAgent: 评分驱动开发 Agent

`EvaluationAgent` 是 NailFlow 的质量总控。它在每次用户端试戴或运营端任务完成后运行，判断本次输出能否支撑黑客松评分，并把缺口转成下一轮开发任务。

## 为什么先做评价 Agent

赛题的评分规则很明确：完整性、创新性、应用效果、商业价值，以及速度、异常覆盖、代码模块化等加分项。如果没有评价 Agent，开发容易陷入“页面好看但无法证明有效”的状态。评价 Agent 把评分规则变成产品内的自动自检器。

## 评分维度

### 1. 完整性

检查问题：

- 用户是否完成上传手图、选择款式、试戴生成、结果解释、预约/收藏。
- 运营是否完成趋势分析、建议生成、人工确认、动作执行。
- 是否覆盖人群、商圈、预算、时间、门店能力等约束。
- 是否处理失败场景：手部检测失败、款式图低质、模型超时、客服无答案。

### 2. 应用效果

检查问题：

- 试戴图是否只改甲面，是否保留肤色、手纹、光照和背景。
- 款式是否像参考图，是否有边界溢出或饰品漂移。
- 客服回复是否准确、可执行、不过度承诺。
- 运营建议是否能被门店执行，并有转化指标。

### 3. 创新性

检查问题：

- 是否体现多 Agent 协作。
- 是否外接生图模型并用工具链约束质量。
- 是否有长期记忆、自动复盘、营销策略生成。
- 是否能把评价结果反向喂给 Planner 改进。

### 4. 商业价值

检查问题：

- 是否降低用户决策成本。
- 是否提升预约转化、收藏、复购、客单价。
- 是否帮助商家降低运营和客服成本。
- 是否支持美团本地生活链路：门店、价格、预约、评价、售后。

### 5. 硬约束与加分项

检查问题：

- 方案生成是否 <30s。
- 工具响应是否 <3s。
- 端到端流程是否 <2min。
- 代码是否模块化、能一键部署。
- 是否至少处理 3 类失败。

## 输入输出

输入建议统一为 `EvaluationContext`：

```ts
type EvaluationContext = {
  runId: string;
  scenario: "try_on" | "ops" | "customer_service" | "full_demo";
  userRequest: string;
  assets: {
    handImage?: string;
    styleImage?: string;
    tryOnImage?: string;
    nailMask?: string;
  };
  toolLogs: Array<{
    tool: string;
    status: "success" | "failed" | "timeout";
    latencyMs: number;
    summary: string;
  }>;
  outputs: {
    tryOnExplanation?: string;
    marketingPlan?: string;
    customerReply?: string;
    actionProposal?: string;
  };
  memoryHits: string[];
  retrievalHits: string[];
  errors: string[];
};
```

输出必须符合 [evaluation_result.schema.json](schemas/evaluation_result.schema.json)。

## 与开发流结合

1. 每个功能 PR 或 demo run 都附带一份评价结果。
2. 低于 75 分不得作为主 demo 路径。
3. 任何 `blocking_issues` 都先修，再做新功能。
4. `next_dev_tasks` 按评分收益排序，作为第二天开发列表。
