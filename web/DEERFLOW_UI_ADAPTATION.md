# DeerFlow 前端到 AI 美甲用户端的适配思路

## DeerFlow 可复用的交互模式

- `WorkspaceContainer`：全屏工作台结构，适合承载“对话 + 结果 + 状态”的长期任务。
- `WorkspaceSidebar`：侧边栏保留任务入口和历史记录；在美甲项目里转成试戴、灵感、预约、客服、方案。
- `InputBox`：附件上传、快捷建议和发送按钮；在美甲项目里转成上传手图、拍照、输入偏好。
- `MessageList`：流式对话和多轮追问；在美甲项目里转成美甲顾问客服。
- `ArtifactFileList`：Agent 生成的产物列表；在美甲项目里转成试戴图、门店确认、售后记录。
- `AgentGallery`：Agent 能力卡片；普通用户不需要看到技术名，转成修图师、搭配顾问、预约助手等角色。
- `SubtaskCard/TodoList`：执行步骤可视化；在美甲项目里转成识别手型、保留肤色、试戴款式、匹配门店。

## 普通用户页面原则

1. 第一屏直接完成核心任务：拍手图、选款式、看试戴。
2. 不暴露模型、token、thread、sandbox 等开发者概念。
3. Agent 状态要可见，但用生活语言表达，让用户知道 AI 正在做什么。
4. 结果页必须连到真实消费动作：收藏、问顾问、预约门店、售后留痕。
5. 手部细节还原要成为信任点：只改甲面，默认保留手纹、肤色、光照和背景。

## 当前前端路由

- `/`：AI 试戴主页面，上传/拍照、试戴进度、推荐款式、结果缩略图。
- `/styles`：灵感款式页，适合接款式搜索和个性化推荐。
- `/booking`：附近门店预约页，适合接美团门店、档期和价格。
- `/service`：美甲顾问客服页，适合接多轮客服 Agent。
- `/plans`：我的方案页，承载试戴图、收藏、预约和售后记录。

## 后续接 DeerFlow 的数据接口

建议前端统一消费一个 `Run` 模型：

```ts
type Run = {
  id: string;
  status: "queued" | "running" | "needs_confirm" | "done" | "failed";
  intent: "try_on" | "style_advice" | "booking" | "service";
  steps: Array<{
    id: string;
    title: string;
    detail: string;
    status: "waiting" | "running" | "done" | "failed";
  }>;
  artifacts: Array<{
    id: string;
    kind: "hand_image" | "style_image" | "tryon_result" | "booking_card";
    url: string;
    title: string;
  }>;
  messages: Array<{
    role: "user" | "assistant";
    content: string;
  }>;
};
```

这个结构能直接映射 DeerFlow 的 message、subtask、artifact，同时保留普通用户能理解的页面状态。
