"use client";

import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { useUpdateTool } from "@/core/nail-models";
import type { ToolInfo } from "@/core/nail-models";
import { cn } from "@/lib/utils";

import { ModelSelectorInline } from "./model-selector-inline";

const GROUP_COLORS: Record<string, string> = {
  nail: "bg-pink-100 text-pink-500 border-pink-200",
  nail_ops: "bg-emerald-100 text-emerald-500 border-emerald-200",
  nail_dev: "bg-fuchsia-100 text-fuchsia-500 border-fuchsia-200",
  web: "bg-sky-100 text-sky-500 border-sky-200",
  file: "bg-amber-100 text-amber-500 border-amber-200",
  bash: "bg-violet-100 text-violet-500 border-violet-200",
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
        "rounded-3xl border border-pink-200/70 bg-white/58 px-4 py-4 shadow-sm transition-opacity",
        !tool.is_enabled && "opacity-50",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-sm font-bold text-[#34202d]">
              {tool.emoji} {tool.display_name}
            </span>
            <Badge
              variant="outline"
              className={cn(
                "rounded-full px-2 py-0 text-[10px] font-semibold",
                GROUP_COLORS[tool.group] ??
                  "border-border/40 text-muted-foreground",
              )}
            >
              {tool.group}
            </Badge>
            {tool.requires_llm && (
              <Badge
                variant="outline"
                className="rounded-full border-pink-200 px-2 py-0 text-[10px] text-[#8f7b88]"
              >
                LLM
              </Badge>
            )}
            {tool.requires_vision && (
              <Badge
                variant="outline"
                className="rounded-full border-emerald-200 px-2 py-0 text-[10px] text-emerald-500"
              >
                视觉
              </Badge>
            )}
          </div>
          <p className="mt-2 text-xs leading-relaxed text-[#8f7b88]">
            {tool.description}
          </p>
        </div>
        <Switch
          checked={tool.is_enabled}
          onCheckedChange={handleToggle}
          disabled={updateTool.isPending}
          className="mt-0.5 shrink-0 data-[state=checked]:bg-pink-500"
        />
      </div>

      {/* 需要 LLM 的工具显示模型选择器 */}
      {tool.requires_llm && tool.is_enabled && (
        <div className="mt-3 border-t border-pink-100 pt-3">
          <ModelSelectorInline
            value={tool.model_override}
            onChange={handleModelChange}
            requiresVision={tool.requires_vision}
          />
        </div>
      )}

      {/* 页面启用开关：只有 LLM 工具且已启用时显示 */}
      {tool.requires_llm && tool.is_enabled && (
        <div className="mt-2 flex items-center gap-3 border-t border-pink-100 pt-2">
          <span className="shrink-0 text-xs text-[#8f7b88]">页面</span>
          <div className="flex gap-3">
            {(["tryon", "ops", "eval"] as const).map((mode) => {
              const LABELS: Record<string, string> = {
                tryon: "试戴",
                ops: "运营",
                eval: "评分",
              };
              const isPageEnabled = tool.enabled_pages?.includes(mode) ?? true;
              return (
                <label
                  key={mode}
                  className="flex cursor-pointer items-center gap-1 select-none"
                >
                  <input
                    type="checkbox"
                    className="size-3 cursor-pointer rounded accent-pink-500"
                    checked={isPageEnabled}
                    onChange={() => {
                      const current = tool.enabled_pages ?? [
                        "tryon",
                        "ops",
                        "eval",
                      ];
                      const next = isPageEnabled
                        ? current.filter((p) => p !== mode)
                        : [...current, mode];
                      updateTool.mutate({
                        name: tool.name,
                        enabled_pages: next,
                      });
                    }}
                  />
                  <span className="text-xs text-[#5f4254]">{LABELS[mode]}</span>
                </label>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
