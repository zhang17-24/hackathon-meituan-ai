"use client";

import { SparklesIcon } from "lucide-react";

import type { NailTryonProgress } from "@/core/threads/hooks";
import { cn } from "@/lib/utils";

const STAGE_LABELS: Record<string, string> = {
  style: "分析美甲款式",
  generating: "AI 生成试戴效果图",
  done: "试戴完成",
};

export function NailTryonProgressBar({
  progress,
  className,
}: {
  progress: NailTryonProgress;
  className?: string;
}) {
  const pct = Math.min(Math.max(progress.progress, 0), 100);
  const label =
    progress.message || STAGE_LABELS[progress.stage] || "正在试戴...";

  return (
    <div
      className={cn(
        "w-full rounded-2xl border border-pink-200/70 bg-white/70 p-3 shadow-sm backdrop-blur-sm",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2 text-sm font-semibold text-[#5b1738]">
          <SparklesIcon className="size-4 shrink-0 animate-pulse text-pink-500" />
          <span className="truncate">{label}</span>
        </div>
        <span className="shrink-0 text-xs font-bold text-pink-500">
          {pct}%
        </span>
      </div>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-pink-100/70">
        <div
          className="h-full rounded-full bg-gradient-to-r from-pink-400 to-fuchsia-400 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      {progress.stage === "generating" && (
        <p className="mt-1.5 text-[11px] text-[#b08a9e]">
          生图通常需要 1-2 分钟，请稍候，生成过程中无需其他操作
        </p>
      )}
    </div>
  );
}
