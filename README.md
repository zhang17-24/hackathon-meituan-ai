# NailFlow: 美甲 AI 试戴与智能运营 Agent

面向美团黑客松“美甲 AI 试戴与智能运营”赛题的双端 Agent 产品原型。项目目标不是只做一个聊天机器人，而是用 DeerFlow 风格的多 Agent 工作流，把“AI 试戴、效果评估、门店运营、客服营销、人工确认”连成一个可演示、可迭代、可评分的系统。

## 赛题理解

截图中的任务目标可以拆成两个业务闭环：

- 用户端智能试戴：用户上传手部照片，选择美甲款式，系统生成尽量真实的试戴效果图，并提供清晰操作流程、加载状态、结果展示。
- 运营端智能运营：AI 助手自动识别爆款趋势、生成运营日报、推荐款式组合与营销动作，并支持人工确认后执行。

核心矛盾是：用户无法“所见即所得”，运营无法“实时感知”。所以本项目要同时解决图像可信度和运营行动力。

## 评分体系驱动开发

本项目先做评价体系，再做功能。每个功能都必须能为评分项提供证据。

| 一级指标 | 权重 | 赛题要求映射 | 可量化证据 | 开发优先级 |
| --- | ---: | --- | --- | --- |
| 完整性 | 30 | 理解人群、地理、时间约束；流程覆盖完整链路；异常处理能力 | 用户端完成“上传-选款-试戴-解释-预约”；运营端完成“趋势-建议-确认-执行”；至少覆盖 3 类异常 | P0 |
| 应用效果 | 25 | 试戴真实、运营建议有效、能解决实际问题 | 甲面边界、肤色一致、光照一致、款式相似度、客服命中率、营销动作可执行率 | P0 |
| 创新性 | 20 | 多约束拆解、并行工具链、智能容错、可视化确认 | DeerFlow 多 Agent 编排；外接生图模型；评价 Agent 自动反推改进；长期记忆营销 | P1 |
| 商业价值 | 15 | 降低决策成本、提升转化、拉新复购和运营效率 | 试戴后预约转化、收藏率、营销活动点击率、客服节省时间、复购推荐 | P1 |
| 加分项与硬约束 | 10 | 代码模块化、一键部署、Mock API、速度、异常覆盖 | 生成 <30s；工具响应 <3s；端到端 <2min；README/脚本清晰；至少 3 类失败处理 | P0 |

### 评价 Agent 的作用

`EvaluationAgent` 是本项目的第一优先级 Agent。它不生成业务结果，而是审查每次运行是否达标。

输入：

- 用户手图、款式图、试戴输出图。
- Agent 执行日志、工具调用结果、异常记录。
- 运营数据或 mock 数据：点击、收藏、预约、订单、客服问题。
- 用户偏好与长期记忆：肤色、甲型、预算、常去商圈、历史喜好。

输出：

- `total_score`: 0-100 总分。
- `rubric_scores`: 完整性、应用效果、创新性、商业价值、硬约束分项。
- `blocking_issues`: 必须修复的问题。
- `next_dev_tasks`: 下一步开发任务，按评分收益排序。
- `demo_evidence`: 答辩时可展示的证据。

## Agent 设计

```text
User Intent
  -> PlannerAgent
  -> TryOnAgent
      -> HandDetectTool
      -> NailMaskTool
      -> ImageGenerationTool
      -> TryOnQualityTool
  -> OpsAgent
      -> TrendRetrievalTool
      -> MarketingPlanTool
      -> CustomerServiceTool
      -> ActionProposalTool
  -> EvaluationAgent
  -> HumanConfirmNode
```

### TryOnAgent

美甲试戴建议外接生图模型，而不是只靠前端贴图。Agent 内置工具负责拆解和约束：

- `HandDetectTool`: 检测手部姿态、指尖、甲床候选区域。
- `NailMaskTool`: 生成或修正甲面 mask，优先只编辑甲面。
- `StyleUnderstandingTool`: 从款式图提取颜色、甲型、纹理、饰品、风格标签。
- `ImageGenerationTool`: 调用外部图像模型，使用 inpaint / mask edit / reference image 生成试戴图。
- `TryOnQualityTool`: 评估边界溢出、肤色漂移、光照一致、款式相似度和商业自然度。

### OpsAgent

运营 Agent 要像 OpenClaw 一样常驻、有记忆、能跨渠道响应。它不是 FAQ，而是“门店运营助手”。

- 长期记忆：记录用户偏好、门店能力、热门款、历史营销效果、售后风险。
- 检索方式：早期可以用 `grep/ripgrep` 检索 markdown/json/csv；中期升级为 RAG 向量库；最终接美团真实数据 API。
- 营销手段：套餐组合、限时优惠、达人短文案、复购提醒、节日主题、低转化款清仓、售后安抚。
- 人工确认：所有会影响价格、库存、预约、退款、上架的动作都必须先生成 `ActionProposal`。

## 提示词资产

- [Evaluation Agent Prompt](agents/prompts/evaluation_agent_prompt.md)
- [AI 美甲试戴 Prompt](agents/prompts/tryon_agent_prompt.md)
- [AI 运营客服 Prompt](agents/prompts/ops_agent_prompt.md)
- [评价 Agent 说明](agents/evaluation_agent.md)
- [评分 JSON Schema](agents/schemas/evaluation_result.schema.json)

## 前端原型

前端在 [web](web) 目录，当前是普通用户可理解的页面壳：

- `/`: 拍手图、选款式、看 AI 试戴进度。
- `/styles`: 款式灵感和搜索。
- `/booking`: 附近门店预约。
- `/service`: 美甲顾问客服。
- `/plans`: 我的试戴方案和售后记录。

运行：

```bash
cd web
npm install
npm run build
cd dist
python3 ../serve_spa.py
```

打开 `http://127.0.0.1:8008/`。

## 下一步开发顺序

1. 先实现 `EvaluationAgent` 的结构化打分，哪怕业务结果先是 mock。
2. 接入外部图像模型，跑通“手图 + 款式图 + mask + prompt -> 试戴图”。
3. 建立本地运营知识库，用 `rg` 检索 mock 数据生成运营建议。
4. 加长期记忆：用户偏好、门店历史、营销反馈、售后风险。
5. 让评价 Agent 每次运行后自动产出 `next_dev_tasks`，用评分收益驱动迭代。
