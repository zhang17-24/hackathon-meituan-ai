"use client";

import { cn } from "@/lib/utils";

export type StepStatus = "waiting" | "running" | "done" | "error";

export interface NailStep {
  id: string;
  label: string;
  icon: string;
  description?: string;
}

export const TRYON_STEPS: NailStep[] = [
  {
    id: "detect",
    icon: "🔍",
    label: "手部检测",
    description: "MediaPipe 识别手指位置",
  },
  {
    id: "mask",
    icon: "✂️",
    label: "甲面遮罩",
    description: "生成精准 mask 边界",
  },
  {
    id: "style",
    icon: "🎨",
    label: "款式解析",
    description: "AI 提取颜色与纹理",
  },
  {
    id: "prompt",
    icon: "✍️",
    label: "构建提示词",
    description: "翻译为生图指令",
  },
  {
    id: "generate",
    icon: "⚡",
    label: "AI 生图",
    description: "字节生图 API 渲染",
  },
  {
    id: "quality",
    icon: "✅",
    label: "质量评分",
    description: "双图对比综合打分",
  },
];

interface NailProgressStepsProps {
  steps: NailStep[];
  /** Map of step.id → status */
  statuses: Record<string, StepStatus>;
  className?: string;
}

function StepDot({ status }: { status: StepStatus }) {
  return (
    <div
      className={cn(
        "relative flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold shadow-sm transition-all duration-300",
        status === "done" &&
          "border-pink-400 bg-pink-100 text-pink-600 shadow-pink-200/70",
        status === "running" &&
          "animate-pulse border-fuchsia-300 bg-white/70 text-fuchsia-500 shadow-fuchsia-200/70",
        status === "error" && "border-red-400 bg-red-400/20 text-red-300",
        status === "waiting" && "border-pink-200/70 bg-white/45 text-pink-200",
      )}
    >
      {status === "done" && <span>✓</span>}
      {status === "running" && (
        <span className="animate-spin text-[10px]">◌</span>
      )}
      {status === "error" && <span>✕</span>}
      {status === "waiting" && (
        <span className="h-1.5 w-1.5 rounded-full bg-current" />
      )}
    </div>
  );
}

function ConnectorLine({ status }: { status: StepStatus }) {
  return (
    <div className="relative mx-1 h-1 flex-1 overflow-hidden rounded-full bg-pink-100/70">
      {status === "done" && (
        <div className="absolute inset-0 animate-[fade-in_0.4s_ease] bg-gradient-to-r from-pink-400/80 to-fuchsia-300/70" />
      )}
      {status === "running" && (
        <div
          className="absolute inset-0 bg-gradient-to-r from-transparent via-pink-400/60 to-transparent"
          style={{ animation: "shimmer-line 1.5s infinite linear" }}
        />
      )}
    </div>
  );
}

export function NailProgressSteps({
  steps,
  statuses,
  className,
}: NailProgressStepsProps) {
  const activeIndex = steps.findIndex((s) => statuses[s.id] === "running");
  const activeStep = activeIndex >= 0 ? steps[activeIndex] : null;

  return (
    <div className={cn("space-y-3", className)}>
      {/* 步骤轨道 */}
      <div className="flex items-center gap-0 px-1">
        {steps.map((step, i) => (
          <div key={step.id} className="flex min-w-0 flex-1 items-center">
            <StepDot status={statuses[step.id] ?? "waiting"} />
            {i < steps.length - 1 && (
              <ConnectorLine
                status={
                  statuses[steps[i + 1]?.id ?? ""] === "done" ||
                  statuses[steps[i + 1]?.id ?? ""] === "running"
                    ? "done"
                    : "waiting"
                }
              />
            )}
          </div>
        ))}
      </div>

      {/* 步骤标签 */}
      <div className="flex items-start gap-0 px-0.5">
        {steps.map((step) => {
          const status = statuses[step.id] ?? "waiting";
          return (
            <div key={step.id} className="min-w-0 flex-1 text-center">
              <p
                className={cn(
                  "truncate px-0.5 text-[10px] font-medium transition-colors",
                  status === "done" && "text-pink-600",
                  status === "running" && "font-semibold text-fuchsia-600",
                  status === "error" && "text-red-400",
                  status === "waiting" && "text-pink-300/70",
                )}
              >
                {step.icon} {step.label}
              </p>
            </div>
          );
        })}
      </div>

      {/* 当前步骤说明 */}
      {activeStep && (
        <div className="nail-glass-soft flex items-center gap-2 rounded-2xl px-3 py-2">
          <span className="text-sm">{activeStep.icon}</span>
          <div className="min-w-0">
            <span className="text-xs font-bold text-pink-600">
              {activeStep.label}
            </span>
            {activeStep.description && (
              <span className="ml-1.5 text-xs text-pink-400">
                — {activeStep.description}
              </span>
            )}
          </div>
          <div className="ml-auto flex gap-0.5">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="inline-block h-1 w-1 animate-bounce rounded-full bg-pink-500/70"
                style={{ animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </div>
        </div>
      )}

      {/* shimmer 动画 */}
      <style jsx>{`
        @keyframes shimmer-line {
          0% {
            transform: translateX(-100%);
          }
          100% {
            transform: translateX(300%);
          }
        }
      `}</style>
    </div>
  );
}
