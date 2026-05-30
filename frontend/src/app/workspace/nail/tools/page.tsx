"use client";

import { useMemo, useState } from "react";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useTools } from "@/core/nail-models";
import { ToolCard } from "@/components/nail/tool-card";
import { cn } from "@/lib/utils";
import { Play, Copy, Sparkles, WandSparkles, ChevronDown } from "lucide-react";

type ExecutionStep = {
  id: string;
  toolName: string;
  displayName: string;
  action: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  durationMs: number;
  status: "success" | "warning" | "error";
};

const SAMPLE_PROMPTS = [
  "帮我识别这张手部照片里的指甲区域，并生成适合试戴的遮罩",
  "分析这款美甲风格，给出适合的试戴提示词并检查结果质量",
  "根据用户意图，自动串联试戴全流程并展示每一步执行结果",
];

function pickBestTools(intent: string, toolNames: string[]) {
  const text = intent.toLowerCase();
  const score = (name: string) => {
    if (text.includes("试戴") || text.includes("遮罩") || text.includes("手部")) {
      if (["hand_detect", "nail_mask", "image_generation", "quality_check"].includes(name)) return 3;
    }
    if (text.includes("风格") || text.includes("款式") || text.includes("提示词")) {
      if (["style_understanding", "prompt_builder", "image_generation"].includes(name)) return 3;
    }
    if (text.includes("运营") || text.includes("爆款") || text.includes("分析")) {
      if (["trend_query", "trend_discovery", "ops_analysis", "customer_service"].includes(name)) return 3;
    }
    if (text.includes("评价") || text.includes("评分") || text.includes("质检")) {
      if (["quality_check", "evaluation"].includes(name)) return 3;
    }
    if (text.includes("图片") || text.includes("生图") || text.includes("生成")) {
      if (["image_generation", "prompt_builder"].includes(name)) return 2;
    }
    return 0;
  };

  return toolNames
    .map((name) => ({ name, score: score(name) }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((x) => x.name);
}

function buildExecution(intent: string, tools: Array<{ name: string; display_name: string; description: string }>) {
  const toolNames = tools.map((t) => t.name);
  const selected = pickBestTools(intent, toolNames);
  const fallback = toolNames.slice(0, 1);
  const chain = selected.length > 0 ? selected : fallback;

  const toolMap = new Map(tools.map((t) => [t.name, t]));
  const steps: ExecutionStep[] = chain.map((toolName, index) => {
    const tool = toolMap.get(toolName)!;
    const input = {
      intent,
      step: index + 1,
      hint: tool.description,
    };
    const output = {
      summary: `${tool.display_name} 已根据意图完成模拟执行`,
      confidence: Math.max(72, 94 - index * 4),
      effect:
        toolName === "image_generation"
          ? "已生成结果图（模拟）"
          : toolName === "quality_check"
            ? "已输出质检结论（模拟）"
            : "已产出结构化结果（模拟）",
      raw: {
        tool: toolName,
        status: "ok",
        trace_id: `trace_${Date.now()}_${index}`,
      },
    };

    return {
      id: `step-${index + 1}`,
      toolName,
      displayName: tool.display_name,
      action: `调用 ${tool.display_name}`,
      input,
      output,
      durationMs: 260 + index * 180,
      status: index === chain.length - 1 ? "success" : "warning",
    };
  });

  return {
    plan: chain,
    steps,
    finalEffect:
      steps.length > 0
        ? `已完成 ${steps.map((s) => s.displayName).join(" → ")} 的测试执行链路`
        : "未匹配到工具，使用默认工具执行",
  };
}

export default function ToolsPage() {
  const { data: toolsData, isLoading } = useTools();
  const [search, setSearch] = useState("");
  const [intent, setIntent] = useState(SAMPLE_PROMPTS[0]);
  const [execution, setExecution] = useState<ReturnType<typeof buildExecution> | null>(null);
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  const matchesTool = (name: string, desc: string) =>
    !search ||
    name.toLowerCase().includes(search.toLowerCase()) ||
    desc.toLowerCase().includes(search.toLowerCase());

  const nailTools = (toolsData?.nail_tools ?? []).filter((t) =>
    matchesTool(t.display_name, t.description),
  );
  const builtinTools = (toolsData?.builtin_tools ?? []).filter((t) =>
    matchesTool(t.display_name, t.description),
  );

  const execTools = useMemo(
    () => [...(toolsData?.nail_tools ?? []), ...(toolsData?.builtin_tools ?? [])].filter((t) => t.is_enabled),
    [toolsData],
  );

  const onRun = () => {
    setExecution(buildExecution(intent, execTools.length > 0 ? execTools : [...(toolsData?.nail_tools ?? []), ...(toolsData?.builtin_tools ?? [])]));
    setExpandedStep(null);
  };

  const copyExecution = async () => {
    if (!execution) return;
    await navigator.clipboard.writeText(JSON.stringify(execution, null, 2));
  };

  return (
    <div className="flex h-full flex-col bg-background">
      <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mr-2 h-4" />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="hidden text-muted-foreground sm:block">
              NailFlow
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden sm:block" />
            <BreadcrumbItem>
              <BreadcrumbPage>工具管理 / 意图执行台</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <div className="ml-auto w-48">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索工具…"
            className="h-7 text-xs"
          />
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-6xl space-y-6 px-4 py-6">
          <section className="rounded-2xl border bg-card p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <WandSparkles className="size-4 text-rose-500" />
                  <h1 className="text-base font-semibold">意图驱动工具执行台</h1>
                  <Badge variant="secondary" className="text-[10px]">
                    测试模式
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  输入一句意图，系统会自动推断工具链，并展示完整的 tool call / tool result / 最终效果。
                </p>
              </div>
              <Button onClick={onRun} className="gap-2">
                <Play className="size-4" />
                运行意图
              </Button>
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-[1.6fr_0.9fr]">
              <div className="space-y-2">
                <Textarea
                  value={intent}
                  onChange={(e) => setIntent(e.target.value)}
                  className="min-h-28 resize-none"
                  placeholder="输入一句意图，例如：帮我识别这张图的美甲风格并完成试戴"
                />
                <div className="flex flex-wrap gap-2">
                  {SAMPLE_PROMPTS.map((sample) => (
                    <button
                      key={sample}
                      type="button"
                      onClick={() => setIntent(sample)}
                      className="rounded-full border px-3 py-1 text-xs text-muted-foreground transition hover:border-foreground/30 hover:text-foreground"
                    >
                      {sample}
                    </button>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl border bg-muted/30 p-4">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Sparkles className="size-4 text-amber-500" />
                  执行说明
                </div>
                <ul className="mt-3 space-y-2 text-xs leading-5 text-muted-foreground">
                  <li>• 解析意图关键词，自动匹配可用工具</li>
                  <li>• 逐步生成 tool call 与 tool result</li>
                  <li>• 支持复制完整执行轨迹用于调试</li>
                  <li>• 适合测试阶段验证工具链路与提示词效果</li>
                </ul>
              </div>
            </div>
          </section>

          <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
            <div className="space-y-3 rounded-2xl border bg-card p-4 shadow-sm">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold">执行可视化</h2>
                  <p className="text-xs text-muted-foreground">按步骤展开查看每次调用的输入、输出与耗时。</p>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={copyExecution} disabled={!execution} className="gap-2">
                    <Copy className="size-3.5" />
                    复制轨迹
                  </Button>
                </div>
              </div>

              {!execution ? (
                <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
                  点击“运行意图”后，这里会展示完整的执行链路。
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="rounded-xl border bg-muted/30 p-3">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <Badge variant="outline">Plan</Badge>
                      {execution.plan.map((tool) => (
                        <span key={tool} className="rounded-full bg-background px-2 py-1">
                          {tool}
                        </span>
                      ))}
                    </div>
                  </div>

                  {execution.steps.map((step, index) => {
                    const isOpen = expandedStep === step.id;
                    return (
                      <div key={step.id} className="rounded-xl border bg-background">
                        <button
                          type="button"
                          onClick={() => setExpandedStep(isOpen ? null : step.id)}
                          className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className={cn(
                                "flex size-8 items-center justify-center rounded-full text-xs font-semibold",
                                step.status === "success"
                                  ? "bg-emerald-500/10 text-emerald-500"
                                  : "bg-amber-500/10 text-amber-500",
                              )}
                            >
                              {index + 1}
                            </div>
                            <div>
                              <div className="text-sm font-medium">{step.action}</div>
                              <div className="text-xs text-muted-foreground">
                                {step.durationMs} ms · {step.status === "success" ? "完成" : "调试输出"}
                              </div>
                            </div>
                          </div>
                          <ChevronDown className={cn("size-4 transition", isOpen && "rotate-180")} />
                        </button>

                        {isOpen && (
                          <div className="border-t px-4 py-4">
                            <div className="grid gap-4 md:grid-cols-2">
                              <div>
                                <div className="mb-2 text-xs font-medium text-muted-foreground">tool call</div>
                                <pre className="overflow-auto rounded-lg bg-muted p-3 text-[11px] leading-5">
{JSON.stringify(step.input, null, 2)}
                                </pre>
                              </div>
                              <div>
                                <div className="mb-2 text-xs font-medium text-muted-foreground">tool result</div>
                                <pre className="overflow-auto rounded-lg bg-muted p-3 text-[11px] leading-5">
{JSON.stringify(step.output, null, 2)}
                                </pre>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}

                  <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
                    <div className="text-xs font-medium text-emerald-600">最终效果</div>
                    <div className="mt-1 text-sm">{execution.finalEffect}</div>
                  </div>
                </div>
              )}
            </div>

            <div className="space-y-3 rounded-2xl border bg-card p-4 shadow-sm">
              <div>
                <h2 className="text-sm font-semibold">当前可用工具</h2>
                <p className="text-xs text-muted-foreground">可按搜索过滤，也可直接把这些工具作为意图调度候选。</p>
              </div>
              {isLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-20 rounded-xl" />
                  ))}
                </div>
              ) : (
                <div className="space-y-6">
                  <section>
                    <div className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">NailFlow 工具</div>
                    {nailTools.length === 0 ? (
                      <p className="py-4 text-sm text-muted-foreground">没有匹配的工具</p>
                    ) : (
                      <div className="space-y-2">
                        {nailTools.map((t) => (
                          <ToolCard key={t.name} tool={t} />
                        ))}
                      </div>
                    )}
                  </section>
                  <section>
                    <div className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">DeerFlow 内置工具</div>
                    {builtinTools.length === 0 ? (
                      <p className="py-4 text-sm text-muted-foreground">没有匹配的工具</p>
                    ) : (
                      <div className="space-y-2">
                        {builtinTools.map((t) => (
                          <ToolCard key={t.name} tool={t} />
                        ))}
                      </div>
                    )}
                  </section>
                </div>
              )}
            </div>
          </section>
        </div>
      </ScrollArea>
    </div>
  );
}
