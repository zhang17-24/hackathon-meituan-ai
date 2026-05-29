"use client";

import { useState } from "react";
import { PlusIcon, Trash2Icon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useNailModels,
  useAgentConfigs,
  useCreateNailModel,
  useDeleteNailModel,
  useUpdateAgentConfigs,
} from "@/core/nail-models";
import { useModels } from "@/core/models/hooks";
import { ModelFormDialog } from "./model-form-dialog";
import type { NailModelCreate } from "@/core/nail-models";

export function ModelSettingsPage() {
  const { data: nailModels = [], isLoading } = useNailModels();
  const { data: agentConfigs } = useAgentConfigs();
  const { models: allModels = [] } = useModels();
  const createModel = useCreateNailModel();
  const deleteModel = useDeleteNailModel();
  const updateAgents = useUpdateAgentConfigs();

  const [addOpen, setAddOpen] = useState(false);
  const [deletingName, setDeletingName] = useState<string | null>(null);

  const handleCreate = async (body: NailModelCreate) => {
    await createModel.mutateAsync(body);
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`确认删除模型 "${name}"？`)) return;
    setDeletingName(name);
    try {
      await deleteModel.mutateAsync(name);
    } finally {
      setDeletingName(null);
    }
  };

  const modelOptions = allModels.map((m) => ({
    name: m.name,
    display: m.display_name ?? m.name,
  }));

  return (
    <div className="space-y-6">
      {/* ── 已配置模型列表 ── */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold">已配置模型</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              支持千问、DeepSeek、豆包、Kimi 及自定义模型
            </p>
          </div>
          <Button size="sm" variant="outline" onClick={() => setAddOpen(true)}>
            <PlusIcon className="mr-1 size-3.5" />
            添加模型
          </Button>
        </div>

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-14 rounded-lg" />
            ))}
          </div>
        ) : nailModels.length === 0 ? (
          <div className="rounded-lg border border-dashed p-6 text-center">
            <p className="text-sm text-muted-foreground">
              暂无自定义模型
            </p>
            <p className="mt-1 text-xs text-muted-foreground/60">
              点击「添加模型」配置千问 / DeepSeek / 豆包 / Kimi
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {nailModels.map((m) => (
              <div
                key={m.name}
                className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2.5"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-sm font-medium">{m.display_name}</span>
                    <Badge
                      variant="outline"
                      className="px-1.5 py-0 text-[10px]"
                    >
                      {m.provider}
                    </Badge>
                    {m.supports_vision && (
                      <Badge
                        variant="outline"
                        className="border-emerald-500/30 px-1.5 py-0 text-[10px] text-emerald-500"
                      >
                        视觉
                      </Badge>
                    )}
                    {m.supports_thinking && (
                      <Badge
                        variant="outline"
                        className="border-violet-500/30 px-1.5 py-0 text-[10px] text-violet-500"
                      >
                        思考
                      </Badge>
                    )}
                    {!m.is_active && (
                      <Badge
                        variant="outline"
                        className="border-muted-foreground/30 px-1.5 py-0 text-[10px] text-muted-foreground"
                      >
                        已禁用
                      </Badge>
                    )}
                  </div>
                  <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                    {m.model_id}
                  </p>
                </div>
                <Button
                  size="icon"
                  variant="ghost"
                  className="size-7 shrink-0 text-destructive/70 hover:bg-destructive/10 hover:text-destructive"
                  disabled={deletingName === m.name}
                  onClick={() => handleDelete(m.name)}
                >
                  <Trash2Icon className="size-3.5" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Agent 默认模型绑定 ── */}
      <div>
        <h3 className="mb-3 text-sm font-semibold">Agent 默认模型绑定</h3>
        <div className="space-y-3 rounded-lg border bg-card p-3">
          {/* 主 Agent */}
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm font-medium">主 Agent（NailPlannerAgent）</p>
              <p className="mt-0.5 text-[11px] text-muted-foreground">
                处理用户意图和工具调度
              </p>
            </div>
            <Select
              value={agentConfigs?.main_agent ?? ""}
              onValueChange={(v) => updateAgents.mutate({ main_agent: v })}
            >
              <SelectTrigger className="h-8 w-44 text-xs">
                <SelectValue placeholder="选择模型…" />
              </SelectTrigger>
              <SelectContent>
                {modelOptions.map((m) => (
                  <SelectItem key={m.name} value={m.name} className="text-xs">
                    {m.display}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="h-px bg-border/40" />

          {/* 工具默认 */}
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm font-medium">工具默认模型</p>
              <p className="mt-0.5 text-[11px] text-muted-foreground">
                所有 LLM 工具的兜底模型，可在工具页单独覆盖
              </p>
            </div>
            <Select
              value={agentConfigs?.tool_default ?? ""}
              onValueChange={(v) => updateAgents.mutate({ tool_default: v })}
            >
              <SelectTrigger className="h-8 w-44 text-xs">
                <SelectValue placeholder="选择模型…" />
              </SelectTrigger>
              <SelectContent>
                {modelOptions.map((m) => (
                  <SelectItem key={m.name} value={m.name} className="text-xs">
                    {m.display}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <ModelFormDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onSave={handleCreate}
      />
    </div>
  );
}
