# 美团黑客松 AI 美甲 Agent 调研资料索引

## 已下载到本地的论文/资料

- `research/sources/nail-polish-try-on-arxiv-1906.02222.pdf`：Virtual try-on nail polish 相关论文，重点看指甲区域定位、颜色/纹理迁移与视觉一致性。
- `research/sources/mediapipe-hands-arxiv-2006.10214.pdf`：MediaPipe Hands，重点看手部 21 点关键点检测、移动端实时性与手势/手形先验。
- `research/sources/segment-anything-arxiv-2304.02643.pdf`：Segment Anything，重点看 promptable mask、zero-shot 分割能力和可交互标注流程。

## 已 copy 到本地的参考项目

- `research/cloned_repos/deer-flow`：ByteDance DeerFlow 2.0。README 中定义为 super agent harness，包含 sub-agents、memory、sandbox、extensible skills，适合作为本项目 Agent 编排底座。
- `research/cloned_repos/openclaw`：OpenClaw。README 中强调本地常驻、多渠道、个人 AI assistant，可借鉴为“类龙虾”的门店运营客服：常驻、可被微信/IM 唤起、能执行待确认动作。
- `research/cloned_repos/segment-anything`：Meta Segment Anything。README 中强调点/框 prompt 生成高质量 mask，可用于甲面区域分割、人工微调和浏览器端 mask demo。

## 关键外部链接

- DeerFlow GitHub: https://github.com/bytedance/deer-flow
- DeerFlow Website: https://deerflow.tech
- OpenClaw GitHub: https://github.com/openclaw/openclaw
- OpenClaw Docs: https://docs.openclaw.ai
- Segment Anything GitHub: https://github.com/facebookresearch/segment-anything
- Segment Anything Project: https://segment-anything.com
- MediaPipe Hands: https://developers.google.com/mediapipe/solutions/vision/hand_landmarker

## 可讲给评委的技术判断

1. AI 美甲试戴不应该全图生成。核心是“局部可控编辑”：手部和背景尽量保持原图，模型只在甲面 mask 内做款式迁移。
2. 手部细节还原可拆为三层：手部关键点/姿态、甲面精细 mask、局部重绘后的肤色/阴影/边界一致性评分。
3. 运营客服 Agent 不是普通 FAQ。它要从趋势、库存、预约、门店 SOP 和用户偏好中生成建议，并把高风险动作交给人工确认。
4. DeerFlow 适合作为统一执行层：Planner 拆任务，Vision/Stylist/Ops 子 Agent 专职执行，Sandbox 管文件和模型脚本，Memory 记录用户偏好与门店策略。
