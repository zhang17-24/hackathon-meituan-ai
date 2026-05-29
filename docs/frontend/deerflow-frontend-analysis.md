# DeerFlow 前端深度分析 — NailFlow 组件设计参考

> 目标：在 DeerFlow 现有 workspace 基础上，以最小侵入的方式增加美甲 AI 试戴相关页面和组件。

---

## 一、技术栈与版本

| 技术 | 版本 | 说明 |
|------|------|------|
| Next.js | 16.2.6 | App Router，SSR + Client Components |
| React | 19.0 | 最新版，Server Actions 支持 |
| TypeScript | 5.x | 严格类型 |
| Tailwind CSS | 4.0 | CSS-first 配置，oklch 色彩空间 |
| shadcn/ui | latest | 41 个 Radix UI 无头组件 |
| TanStack Query | 5.90 | 服务端状态管理 |
| Sonner | - | Toast 通知系统 |
| LangGraph SDK | 1.5.3 | AI agent stream 集成 |

---

## 二、颜色系统（CSS Variables + oklch）

### 亮色主题（:root）
```css
--background: oklch(0.9855 0.0098 87.47)  /* 暖白底色 */
--foreground: oklch(0.145 0 0)             /* 近黑字色 */
--card: oklch(1 0.0098 87.47)              /* 纯白卡片 */
--primary: oklch(0 0 0)                    /* 黑色主色 */
--secondary: oklch(0.9455 0.0098 87.47)   /* 浅灰次级 */
--muted: oklch(0.97 0.0098 87.47)         /* 极浅灰 */
--muted-foreground: oklch(0.556 0 0)       /* 中灰文字 */
--accent: oklch(0.94 0.0098 87.47)        /* 强调背景 */
--border: oklch(0.922 0.0098 87.47)       /* 边框色 */
--sidebar: oklch(0.965 0.0098 87.47)      /* 侧边栏底色 */
```

### 暗色主题（.dark）
```css
--background: oklch(0.24 0.0036 106.64)   /* 暗棕底色 */
--foreground: oklch(0.985 0 0)             /* 白字 */
--card: oklch(0.238 0.0036 106.64)        /* 暗卡片 */
--muted: oklch(0.269 0.0036 106.64)       /* 暗灰 */
--muted-foreground: oklch(0.708 0 0)       /* 浅灰文字 */
--accent: oklch(0.32 0.0036 106.64)       /* 暗强调 */
--border: oklch(1 0 0 / 10%)              /* 10% 白色边框 */
--sidebar: oklch(0.245 0.0036 106.64)     /* 侧边栏深色 */
```

### 可用动画
- `fade-in`：1.1s 淡入
- `bouncing`：弹跳
- `wave`：波浪（4 steps）
- `aurora`：极光背景
- `shine`：光泽扫过

---

## 三、工作区页面布局结构

```
WorkspaceLayout.tsx (SSR 认证检查，重定向 login/setup)
└── WorkspaceContent.tsx (Client，SidebarProvider + QueryClientProvider)
    ├── WorkspaceSidebar.tsx
    │   ├── WorkspaceHeader.tsx       (Logo + 新对话按钮)
    │   ├── NailNav.tsx               ← 已有美甲导航
    │   ├── WorkspaceNavChatList.tsx  (搜索 + 历史对话)
    │   └── WorkspaceNavMenu.tsx      (底部：Agents/Settings/User)
    └── SidebarInset (主内容区，min-w-0)
        └── 页面内容 (children)
```

### SidebarInset 中的标准页面结构

DeerFlow 所有工作区页面遵循：
```tsx
<div className="flex h-full flex-col">
  {/* 顶部 header（可选） */}
  <header className="flex h-12 items-center border-b px-4 gap-2">
    <SidebarTrigger />
    <Separator orientation="vertical" />
    <Breadcrumb>...</Breadcrumb>
  </header>
  {/* 主体内容 */}
  <main className="flex-1 overflow-auto">
    ...
  </main>
</div>
```

---

## 四、已有 NailFlow 页面现状与问题

### 4.1 当前页面（workspace/nail/）

| 页面 | 路径 | 问题 |
|------|------|------|
| 试戴 | `/workspace/nail/tryon` | 缺少顶部 header/breadcrumb；无 WorkspaceHeader 集成；上传 UX 粗糙 |
| 运营看板 | `/workspace/nail/dashboard` | 无统计图表；数据展示过于简单 |
| 评分面板 | `/workspace/nail/evaluation` | 无进度状态；结果可视化弱 |

### 4.2 与 DeerFlow 风格的差距

1. **缺少顶部 header 条**：DeerFlow 所有页面有 `SidebarTrigger + Breadcrumb` 的 header
2. **没有 DeerFlow 的 WorkspaceContainer 包装**：需要用标准 flex 布局
3. **上传区域设计简陋**：DeerFlow 的上传使用 PromptInput 组件，有附件管理
4. **Agent 思考链展示**：当前只是 console.log 式文字，DeerFlow 有 `ChainOfThought` 组件
5. **结果展示**：需要类似 Artifacts 面板的效果

---

## 五、DeerFlow 可复用组件清单

### 5.1 直接可用的 shadcn 组件
```
Button, Card, Badge, Progress, Separator, Skeleton
ScrollArea, Tabs, Tooltip
Dialog, Sheet（侧拉抽屉）
```

### 5.2 DeerFlow 专属可复用
```
WorkspaceHeader（布局标准 header）
SidebarTrigger（折叠按钮）
Breadcrumb（面包屑）
ChainOfThought（思考链展示）
Loader（加载状态）
Shimmer（闪光骨架屏）
```

### 5.3 核心 Hook
```typescript
useAuth()           // 获取用户和 nail_role
canAccess()         // 权限检查
useI18n()           // 国际化（目前不支持美甲词条，暂时用硬编码中文）
```

---

## 六、需要新建的组件规划

### 6.1 试戴页面重构（最高优先级）

**文件**：`frontend/src/app/workspace/nail/tryon/page.tsx`

**需要新建/修改的组件**：

| 组件 | 路径 | 描述 |
|------|------|------|
| `NailTryonCanvas` | `components/nail/tryon-canvas.tsx` | 核心试戴画布：双图上传+结果展示 |
| `NailImageUploader` | `components/nail/image-uploader.tsx` | 美观的图片上传区，含拖放 |
| `NailProgressSteps` | `components/nail/progress-steps.tsx` | 6步工具链进度动画 |
| `NailResultPanel` | `components/nail/result-panel.tsx` | 结果图+质量评分+中文解释 |
| `NailAgentThinking` | `components/nail/agent-thinking.tsx` | 复用/适配 ChainOfThought |

### 6.2 运营看板增强

**文件**：`frontend/src/app/workspace/nail/dashboard/page.tsx`

| 组件 | 描述 |
|------|------|
| `NailTrendChart` | 7天趋势折线/柱状图（用 recharts 或 canvas） |
| `NailSignalBadges` | 款式热度 badge 网格，按热度排序 |
| `NailProposalCard` | ActionProposal 卡片，含确认/拒绝动画 |

### 6.3 评分面板增强

**文件**：`frontend/src/app/workspace/nail/evaluation/page.tsx`

| 组件 | 描述 |
|------|------|
| `NailScoreRing` | 圆形进度环显示总分 |
| `NailRubricBars` | 五维评分条形动画 |
| `NailTaskList` | 下一步任务列表，含优先级排序 |

---

## 七、设计约束与原则

### 7.1 必须遵守
- 使用 DeerFlow 的 CSS 变量（`bg-background`、`text-foreground` 等）
- 深色/亮色主题均需支持（`.dark` 类已在 `workspace-content.tsx` 自动注入）
- 组件必须是 `"use client"` 指令（DeerFlow 通用模式）
- 所有页面包裹在标准 `flex h-full flex-col` 结构中
- 顶部必须有 `SidebarTrigger + Separator + Breadcrumb` header 条

### 7.2 美学方向（NailFlow 专属）
- 在 DeerFlow 的中性设计系统中加入**柔和玫瑰粉**作为 nail 品牌色
- 品牌色变量：`--nail-primary: oklch(0.65 0.18 350)` （玫瑰粉）
- 试戴结果展示用**大图优先**布局，强调视觉对比
- 工具链进度使用**有序步骤动画**，体现 AI 工作过程的透明感

### 7.3 组件复用约定
```typescript
// 标准 nail 组件文件头
"use client";

import { cn } from "@/lib/utils";
import { useAuth } from "@/core/auth/AuthProvider";
import type { NailRole } from "@/lib/nail-auth";
// ... 其他 shadcn 组件
```

---

## 八、页面 Header 标准模板

所有 nail 页面的 header 应如下：

```tsx
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import {
  Breadcrumb, BreadcrumbList, BreadcrumbItem,
  BreadcrumbPage, BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

// header 模板
<header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
  <SidebarTrigger className="-ml-1" />
  <Separator orientation="vertical" className="mr-2 h-4" />
  <Breadcrumb>
    <BreadcrumbList>
      <BreadcrumbItem>NailFlow</BreadcrumbItem>
      <BreadcrumbSeparator />
      <BreadcrumbItem>
        <BreadcrumbPage>AI 美甲试戴</BreadcrumbPage>
      </BreadcrumbItem>
    </BreadcrumbList>
  </Breadcrumb>
</header>
```

---

## 九、开发顺序建议

1. **先改页面结构**（加 header，修复布局）→ 试戴/看板/评分三页
2. **新建核心组件**：`NailImageUploader` + `NailProgressSteps` + `NailResultPanel`
3. **增强运营看板**：`NailTrendChart` + `NailProposalCard`
4. **增强评分页**：`NailScoreRing` + `NailRubricBars`

---

*此文档基于 DeerFlow frontend 代码库分析生成，2026-05-29*
