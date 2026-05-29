"use client";

import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { useUpdateTool } from "@/core/nail-models";
import { ModelSelectorInline } from "./model-selector-inline";
import type { ToolInfo } from "@/core/nail-models";
import { cn } from "@/lib/utils";

const GROUP_COLORS: Record<string, string> = {
  nail:     "bg-rose-500/10 text-rose-400 border-rose-400/20",
  nail_ops: "bg-emerald-500/10 text-emerald-400 border-emerald-400/20",
  nail_dev: "bg-blue-500/10 text-blue-400 border-blue-400/20",
  web:      "bg-sky-500/10 text-sky-400 border-sky-400/20",
  file:     "bg-amber-500/10 text-amber-400 border-amber-400/20",
  bash:     "bg-violet-500/10 text-violet-400 border-violet-400/20",
};

interface ToolCardProps {
  tool: ToolInfo;
}

export function ToolCard({ tool }: ToolCardProps) {
  const updateTool = useUpdateTool();

  const handleToggle = (enabled: boolean) => {
    updateTool.mutate({ name: tool.name, is_enabled: enabled });
  };

  const handleModelChange = (model: string | null) => {
    updateTool.mutate({ name: tool.name, model_name: model });
  };

  return (
    <div
      className={cn(
        "rounded-xl border bg-card px-4 py-3 transition-opacity",
        !tool.is_enabled && "opacity-50",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-sm font-semibold">
              {tool.emoji} {tool.display_name}
            </span>
            <Badge
              variant="outline"
              className={cn(
                "px-1.5 py-0 text-[10px]",
                GROUP_COLORS[tool.group] ?? "border-border/40 text-muted-foreground",
              )}
            >
              {tool.group}
            </Badge>
            {tool.requires_llm && (
              <Badge
                variant="outline"
                className="border-border/50 px-1.5 py-0 text-[10px] text-muted-foreground"
              >
                LLM
              </Badge>
            )}
            {tool.requires_vision && (
              <Badge
                variant="outline"
                className="border-emerald-400/20 px-1.5 py-0 text-[10px] text-emerald-400"
              >
                视觉
              </Badge>
            )}
          </div>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {tool.description}
          </p>
        </div>
        <Switch
          checked={tool.is_enabled}
          onCheckedChange={handleToggle}
          disabled={updateTool.isPending}
          className="mt-0.5 shrink-0"
        />
      </div>

      {/* 需要 LLM 的工具显示模型选择器 */}
      {tool.requires_llm && tool.is_enabled && (
        <div className="mt-3 border-t border-border/40 pt-3">
          <ModelSelectorInline
            value={tool.model_override}
            onChange={handleModelChange}
            requiresVision={tool.requires_vision}
          />
        </div>
      )}

      {/* 页面启用开关：只有 LLM 工具且已启用时显示 */}
      {tool.requires_llm && tool.is_enabled && (
        <div className="mt-2 flex items-center gap-3 border-t pt-2">
          <span className="text-xs text-muted-foreground shrink-0">页面</span>
          <div className="flex gap-3">
            {(["tryon", "ops", "eval"] as const).map((mode) => {
              const LABELS: Record<string, string> = { tryon: "试戴", ops: "运营", eval: "评分" };
              const isPageEnabled = tool.enabled_pages?.includes(mode) ?? true;
              return (
                <label key={mode} className="flex cursor-pointer items-center gap-1 select-none">
                  <input
                    type="checkbox"
                    className="size-3 cursor-pointer rounded"
                    checked={isPageEnabled}
                    onChange={() => {
                      const current = tool.enabled_pages ?? ["tryon", "ops", "eval"];
                      const next = isPageEnabled
                        ? current.filter((p) => p !== mode)
                        : [...current, mode];
                      updateTool.mutate({ name: tool.name, enabled_pages: next });
                    }}
                  />
                  <span className="text-xs">{LABELS[mode]}</span>
                </label>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
