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
  { id: "detect",    icon: "🔍", label: "手部检测",   description: "MediaPipe 识别手指位置" },
  { id: "mask",      icon: "✂️", label: "甲面遮罩",   description: "生成精准 mask 边界" },
  { id: "style",     icon: "🎨", label: "款式解析",   description: "AI 提取颜色与纹理" },
  { id: "prompt",    icon: "✍️", label: "构建提示词", description: "翻译为生图指令" },
  { id: "generate",  icon: "⚡", label: "AI 生图",    description: "字节生图 API 渲染" },
  { id: "quality",   icon: "✅", label: "质量评分",   description: "双图对比综合打分" },
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
        "relative flex-shrink-0 flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold border-2 transition-all duration-300",
        status === "done"    && "border-rose-400 bg-rose-400/20 text-rose-300",
        status === "running" && "border-rose-300 bg-rose-300/10 text-rose-200 animate-pulse",
        status === "error"   && "border-red-400 bg-red-400/20 text-red-300",
        status === "waiting" && "border-border/40 bg-muted/30 text-muted-foreground/40",
      )}
    >
      {status === "done"    && <span>✓</span>}
      {status === "running" && <span className="animate-spin text-[10px]">◌</span>}
      {status === "error"   && <span>✕</span>}
      {status === "waiting" && <span className="w-1.5 h-1.5 rounded-full bg-current" />}
    </div>
  );
}

function ConnectorLine({ status }: { status: StepStatus }) {
  return (
    <div className="flex-1 h-px mx-1 relative overflow-hidden rounded-full bg-border/30">
      {status === "done" && (
        <div className="absolute inset-0 bg-gradient-to-r from-rose-400/60 to-rose-300/40 animate-[fade-in_0.4s_ease]" />
      )}
      {status === "running" && (
        <div
          className="absolute inset-0 bg-gradient-to-r from-transparent via-rose-400/50 to-transparent"
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
          <div key={step.id} className="flex items-center flex-1 min-w-0">
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
            <div key={step.id} className="flex-1 min-w-0 text-center">
              <p
                className={cn(
                  "text-[10px] font-medium truncate px-0.5 transition-colors",
                  status === "done"    && "text-rose-400",
                  status === "running" && "text-rose-300 font-semibold",
                  status === "error"   && "text-red-400",
                  status === "waiting" && "text-muted-foreground/40",
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
        <div className="flex items-center gap-2 rounded-lg bg-rose-500/5 border border-rose-400/20 px-3 py-2">
          <span className="text-sm">{activeStep.icon}</span>
          <div className="min-w-0">
            <span className="text-xs font-semibold text-rose-300">
              {activeStep.label}
            </span>
            {activeStep.description && (
              <span className="text-xs text-muted-foreground ml-1.5">
                — {activeStep.description}
              </span>
            )}
          </div>
          <div className="ml-auto flex gap-0.5">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="inline-block w-1 h-1 rounded-full bg-rose-400/70 animate-bounce"
                style={{ animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </div>
        </div>
      )}

      {/* shimmer 动画 */}
      <style jsx>{`
        @keyframes shimmer-line {
          0%   { transform: translateX(-100%); }
          100% { transform: translateX(300%); }
        }
      `}</style>
    </div>
  );
}
