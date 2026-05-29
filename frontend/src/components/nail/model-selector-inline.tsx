"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useModels } from "@/core/models/hooks";
import { useAgentConfigs } from "@/core/nail-models";
import { cn } from "@/lib/utils";

interface ModelSelectorInlineProps {
  /** 当前选中的模型名，null 表示跟随全局 tool_default */
  value: string | null;
  onChange: (model: string | null) => void;
  /** 是否需要视觉能力（为 true 时对不支持视觉的模型显示警告） */
  requiresVision?: boolean;
  className?: string;
}

/** 根据模型名判断是否支持视觉（通过命名约定：含 vl / vision / seed） */
function isVisionModel(name: string) {
  const n = name.toLowerCase();
  return n.includes("vl") || n.includes("vision") || n.includes("seed");
}

export function ModelSelectorInline({
  value,
  onChange,
  requiresVision,
  className,
}: ModelSelectorInlineProps) {
  const { models = [] } = useModels();
  const { data: agentConfigs } = useAgentConfigs();

  const toolDefaultName = agentConfigs?.tool_default;
  const toolDefaultDisplay =
    models.find((m) => m.name === toolDefaultName)?.display_name ??
    toolDefaultName ??
    "未配置";

  return (
    <div className={cn("space-y-1", className)}>
      <p className="text-[11px] font-medium text-muted-foreground">模型绑定</p>
      <Select
        value={value ?? "__default__"}
        onValueChange={(v) => onChange(v === "__default__" ? null : v)}
      >
        <SelectTrigger className="h-7 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__default__" className="text-xs">
            <span className="text-muted-foreground">
              工具默认（{toolDefaultDisplay}）
            </span>
          </SelectItem>
          {models.map((m) => (
            <SelectItem key={m.name} value={m.name} className="text-xs">
              <span>{m.display_name ?? m.name}</span>
              {m.supports_thinking && (
                <span className="ml-1 text-[10px] text-violet-400">思考</span>
              )}
              {isVisionModel(m.name) && (
                <span className="ml-1 text-[10px] text-emerald-400">视觉</span>
              )}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {requiresVision && value && !isVisionModel(value) && (
        <p className="text-[10px] text-amber-500">
          ⚠️ 此工具需要视觉能力，建议选择名称含 vl/vision/seed 的模型
        </p>
      )}
    </div>
  );
}
