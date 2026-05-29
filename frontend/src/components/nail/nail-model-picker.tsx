"use client";

import { BotIcon, Settings2Icon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useModels } from "@/core/models/hooks";
import { useAgentConfigs } from "@/core/nail-models";
import { cn } from "@/lib/utils";

interface NailModelPickerProps {
  /** 当前会话选中的模型名（来自 localStorage/settings） */
  value?: string;
  onChange: (model: string) => void;
  className?: string;
}

export function NailModelPicker({
  value,
  onChange,
  className,
}: NailModelPickerProps) {
  const { models = [] } = useModels();
  const { data: agentConfigs } = useAgentConfigs();

  // 无模型时不显示
  if (models.length === 0) return null;

  const defaultModelName = agentConfigs?.main_agent;
  const currentModel =
    models.find((m) => m.name === value) ??
    models.find((m) => m.name === defaultModelName) ??
    models[0];

  const isActive = (name: string) =>
    value ? value === name : name === defaultModelName;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={cn("h-7 gap-1.5 text-xs font-medium", className)}
        >
          <BotIcon className="size-3.5 text-muted-foreground" />
          {currentModel?.display_name ?? currentModel?.name ?? "选择模型"}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <p className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          当前会话主 Agent 模型
        </p>
        {models.map((m) => (
          <DropdownMenuItem
            key={m.name}
            onClick={() => onChange(m.name)}
            className="flex items-center justify-between text-xs"
          >
            <span
              className={cn(
                isActive(m.name) ? "font-semibold text-foreground" : "text-foreground/80",
              )}
            >
              {m.display_name ?? m.name}
            </span>
            <div className="flex gap-1">
              {m.supports_thinking && (
                <span className="text-[10px] text-violet-400">思考</span>
              )}
              {isActive(m.name) && (
                <span className="text-[10px] text-primary">✓</span>
              )}
            </div>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-xs text-muted-foreground"
          onClick={() => {
            // 触发打开 Settings 模型配置 tab
            document.dispatchEvent(
              new CustomEvent("nail:open-settings", {
                detail: { section: "models" },
              }),
            );
          }}
        >
          <Settings2Icon className="mr-1.5 size-3" />
          配置更多模型…
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
