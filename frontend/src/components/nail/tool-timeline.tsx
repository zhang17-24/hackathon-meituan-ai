// frontend/src/components/nail/tool-timeline.tsx
"use client";

import { cn } from "@/lib/utils";

interface ToolCall {
  tool: string;
  call_index: number;
  duration_ms: number;
  success: boolean;
}

interface ToolTimelineProps {
  toolChain: ToolCall[];
  totalDurationMs: number;
  className?: string;
}

const TOOL_EMOJI: Record<string, string> = {
  hand_detect_tool:         "🖐",
  nail_mask_tool:           "✂️",
  style_understanding_tool: "🎨",
  prompt_builder_tool:      "📝",
  image_generation_tool:    "🖼️",
  quality_check_tool:       "✅",
  evaluation_tool:          "📊",
  trend_query_tool:         "📈",
  ops_analysis_tool:        "💡",
  nail_run_query_tool:      "🔍",
  user_pref_analytics_tool: "📉",
};

export function ToolTimeline({ toolChain, totalDurationMs, className }: ToolTimelineProps) {
  if (!toolChain || toolChain.length === 0) {
    return (
      <div className={cn("rounded-lg border bg-muted/30 p-4 text-center text-xs text-muted-foreground", className)}>
        暂无工具调用记录
      </div>
    );
  }

  const maxDuration = Math.max(...toolChain.map((t) => Math.abs(t.duration_ms)), 1);

  return (
    <div className={cn("rounded-lg border bg-card p-3 space-y-1.5", className)}>
      <p className="text-xs font-semibold text-muted-foreground mb-2">工具调用时序</p>
      {toolChain.map((call) => {
        const pct = Math.min((Math.abs(call.duration_ms) / maxDuration) * 100, 100);
        const label = call.tool.replace("_tool", "").replace(/_/g, " ");
        const emoji = TOOL_EMOJI[call.tool] ?? "⚙️";
        const msText =
          call.duration_ms < 0
            ? "失败"
            : call.duration_ms >= 1000
              ? `${(call.duration_ms / 1000).toFixed(1)}s`
              : `${call.duration_ms}ms`;

        return (
          <div key={`${call.tool}-${call.call_index}`} className="flex items-center gap-2">
            <span className="w-5 text-base">{emoji}</span>
            <span className="w-28 truncate text-xs text-foreground/80">{label}</span>
            <div className="relative h-4 flex-1 rounded-sm bg-muted overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-sm transition-all",
                  call.success ? "bg-primary/60" : "bg-destructive/60",
                )}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span
              className={cn(
                "w-14 text-right text-xs tabular-nums",
                call.success ? "text-muted-foreground" : "text-destructive",
              )}
            >
              {msText}
            </span>
            <span className="text-xs">{call.success ? "✓" : "✗"}</span>
          </div>
        );
      })}
      <div className="border-t pt-1.5 flex justify-between text-xs text-muted-foreground">
        <span>{toolChain.length} 个工具</span>
        <span>
          总计{" "}
          {totalDurationMs >= 1000
            ? `${(totalDurationMs / 1000).toFixed(1)}s`
            : `${totalDurationMs}ms`}
          {toolChain.every((t) => t.success) ? " ✓ 全部成功" : " ⚠️ 有失败"}
        </span>
      </div>
    </div>
  );
}
