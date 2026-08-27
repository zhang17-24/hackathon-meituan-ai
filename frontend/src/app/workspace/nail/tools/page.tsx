"use client";

import {
  ChevronDown,
  Copy,
  Play,
  SearchIcon,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import { useMemo, useState } from "react";

import { NailGlassShell } from "@/components/nail/nail-glass-shell";
import { ToolCard } from "@/components/nail/tool-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useTools } from "@/core/nail-models";
import { cn } from "@/lib/utils";

type ToolLite = {
  name: string;
  display_name: string;
  description?: string;
  is_enabled?: boolean;
};

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
    if (
      text.includes("试戴") ||
      text.includes("遮罩") ||
      text.includes("手部")
    ) {
      if (
        [
          "hand_detect",
          "nail_mask",
          "image_generation",
          "quality_check",
        ].includes(name)
      ) {
        return 3;
      }
    }
    if (
      text.includes("风格") ||
      text.includes("款式") ||
      text.includes("提示词")
    ) {
      if (
        ["style_understanding", "prompt_builder", "image_generation"].includes(
          name,
        )
      ) {
        return 3;
      }
    }
    if (
      text.includes("运营") ||
      text.includes("爆款") ||
      text.includes("分析")
    ) {
      if (
        [
          "trend_query",
          "trend_discovery",
          "ops_analysis",
          "customer_service",
        ].includes(name)
      ) {
        return 3;
      }
    }
    if (
      text.includes("评价") ||
      text.includes("评分") ||
      text.includes("质检")
    ) {
      if (["quality_check"].includes(name)) return 3;
    }
    if (
      text.includes("图片") ||
      text.includes("生图") ||
      text.includes("生成")
    ) {
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

function buildExecution(intent: string, tools: ToolLite[]) {
  const toolNames = tools.map((t) => t.name);
  const selected = pickBestTools(intent, toolNames);
  const fallback = toolNames.slice(0, 1);
  const chain = selected.length > 0 ? selected : fallback;

  const toolMap = new Map(tools.map((t) => [t.name, t]));
  const steps: ExecutionStep[] = chain.flatMap((toolName, index) => {
    const tool = toolMap.get(toolName);
    if (!tool) return [];
    const input = {
      intent,
      step: index + 1,
      hint: tool.description ?? "",
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

    return [
      {
        id: `step-${index + 1}`,
        toolName,
        displayName: tool.display_name,
        action: `调用 ${tool.display_name}`,
        input,
        output,
        durationMs: 260 + index * 180,
        status: index === chain.length - 1 ? "success" : "warning",
      },
    ];
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
  const [intent, setIntent] = useState<string>(SAMPLE_PROMPTS[0] ?? "");
  const [execution, setExecution] = useState<ReturnType<
    typeof buildExecution
  > | null>(null);
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  const matchesTool = (name?: string, desc?: string) =>
    !search ||
    (name ?? "").toLowerCase().includes(search.toLowerCase()) ||
    (desc ?? "").toLowerCase().includes(search.toLowerCase());

  const nailTools = (toolsData?.nail_tools ?? []).filter((t) =>
    matchesTool(t.display_name, t.description),
  );
  const builtinTools = (toolsData?.builtin_tools ?? []).filter((t) =>
    matchesTool(t.display_name, t.description),
  );

  const execTools = useMemo(
    () =>
      [
        ...(toolsData?.nail_tools ?? []),
        ...(toolsData?.builtin_tools ?? []),
      ].filter((t) => t.is_enabled),
    [toolsData],
  );

  const onRun = () => {
    setExecution(
      buildExecution(
        intent,
        execTools.length > 0
          ? execTools
          : [
              ...(toolsData?.nail_tools ?? []),
              ...(toolsData?.builtin_tools ?? []),
            ],
      ),
    );
    setExpandedStep(null);
  };

  const copyExecution = async () => {
    if (!execution) return;
    await navigator.clipboard.writeText(JSON.stringify(execution, null, 2));
  };

  return (
    <NailGlassShell
      title="工具管理 / 意图执行台"
      hero={false}
      headerRight={
        <div className="relative hidden w-64 lg:block">
          <SearchIcon className="absolute top-1/2 left-4 size-4 -translate-y-1/2 text-pink-300" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索工具..."
            className="h-11 rounded-full border-pink-200/70 bg-white/65 pl-11 text-sm shadow-sm placeholder:text-pink-300"
          />
        </div>
      }
    >
      <section className="nail-glass-card rounded-[2rem] p-5 md:p-7">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <div className="flex items-center gap-3">
              <WandSparkles className="size-7 text-pink-500" />
              <h1 className="text-3xl font-extrabold tracking-normal text-[#1f1b20]">
                意图驱动工具执行台
              </h1>
              <Badge className="rounded-full bg-pink-100 px-3 py-1 text-pink-500 hover:bg-pink-100">
                测试模式
              </Badge>
            </div>
            <p className="mt-3 text-sm font-medium text-[#766a74]">
              输入一句意图，系统会自动推断工具链，并展示完整的 tool call / tool
              result / 最终效果。
            </p>
          </div>
          <Button
            onClick={onRun}
            className="nail-primary-button h-14 rounded-2xl px-8 text-base font-bold"
          >
            <Play className="mr-2 size-5" />
            运行意图
          </Button>
        </div>

        <div className="mt-7 grid gap-5 lg:grid-cols-[1.45fr_0.8fr]">
          <div className="space-y-4">
            <Textarea
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              className="min-h-40 resize-none rounded-3xl border-pink-200/80 bg-white/58 p-5 text-base shadow-inner shadow-pink-100/60 placeholder:text-pink-300 focus-visible:ring-pink-300"
              placeholder="输入一句意图，例如：帮我识别这张图的美甲风格并完成试戴"
            />
            <div className="flex flex-wrap gap-3">
              {SAMPLE_PROMPTS.map((sample) => (
                <button
                  key={sample}
                  type="button"
                  onClick={() => setIntent(sample)}
                  className="nail-chip rounded-full px-4 py-2 text-sm font-medium"
                >
                  {sample}
                </button>
              ))}
            </div>
          </div>

          <div className="nail-glass-soft rounded-3xl p-6">
            <div className="flex items-center gap-3 text-lg font-bold text-pink-500">
              <Sparkles className="size-5" />
              执行说明
            </div>
            <ul className="mt-5 space-y-4 text-sm leading-6 text-[#8f7b88]">
              <li>• 解析意图关键词，自动匹配可用工具</li>
              <li>• 逐步生成 tool call 与 tool result</li>
              <li>• 支持复制完整执行轨迹用于调试</li>
              <li>• 适合测试阶段验证工具链路与提示词效果</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="nail-glass-card space-y-4 rounded-[2rem] p-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold text-[#1f1b20]">执行可视化</h2>
              <p className="mt-1 text-sm text-[#8f7b88]">
                按步骤展开查看每次调用的输入、输出与耗时。
              </p>
            </div>
            <Button
              variant="outline"
              onClick={copyExecution}
              disabled={!execution}
              className="nail-outline-button h-10 rounded-full px-5 font-semibold"
            >
              <Copy className="mr-2 size-4" />
              复制轨迹
            </Button>
          </div>

          {!execution ? (
            <div className="nail-dashed-zone flex min-h-56 flex-col items-center justify-center rounded-3xl p-6 text-center text-sm font-medium text-[#837583]">
              <div className="mb-3 text-5xl text-pink-300">✦</div>
              点击“运行意图”后，这里会展示完整的执行链路。
            </div>
          ) : (
            <div className="space-y-4">
              <div className="rounded-3xl border border-pink-200/70 bg-white/55 p-4">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <Badge
                    variant="outline"
                    className="rounded-full border-pink-200 text-pink-500"
                  >
                    Plan
                  </Badge>
                  {execution.plan.map((tool) => (
                    <span
                      key={tool}
                      className="rounded-full bg-pink-50 px-3 py-1 text-pink-600"
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              </div>

              {execution.steps.map((step, index) => {
                const isOpen = expandedStep === step.id;
                return (
                  <div
                    key={step.id}
                    className="overflow-hidden rounded-3xl border border-pink-200/70 bg-white/58"
                  >
                    <button
                      type="button"
                      onClick={() => setExpandedStep(isOpen ? null : step.id)}
                      className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
                    >
                      <div className="flex items-center gap-4">
                        <div
                          className={cn(
                            "flex size-10 items-center justify-center rounded-full text-sm font-bold",
                            step.status === "success"
                              ? "bg-emerald-100 text-emerald-500"
                              : "bg-pink-100 text-pink-500",
                          )}
                        >
                          {index + 1}
                        </div>
                        <div>
                          <div className="font-semibold text-[#34202d]">
                            {step.action}
                          </div>
                          <div className="mt-1 text-xs text-[#9a8994]">
                            {step.durationMs} ms ·{" "}
                            {step.status === "success" ? "完成" : "调试输出"}
                          </div>
                        </div>
                      </div>
                      <ChevronDown
                        className={cn(
                          "size-4 text-pink-400 transition",
                          isOpen && "rotate-180",
                        )}
                      />
                    </button>

                    {isOpen && (
                      <div className="border-t border-pink-100 px-5 py-4">
                        <div className="grid gap-4 md:grid-cols-2">
                          <div>
                            <div className="mb-2 text-xs font-bold tracking-wide text-pink-400 uppercase">
                              tool call
                            </div>
                            <pre className="max-h-64 overflow-auto rounded-2xl bg-pink-50/70 p-3 text-[11px] leading-5 text-[#5f4254]">
                              {JSON.stringify(step.input, null, 2)}
                            </pre>
                          </div>
                          <div>
                            <div className="mb-2 text-xs font-bold tracking-wide text-pink-400 uppercase">
                              tool result
                            </div>
                            <pre className="max-h-64 overflow-auto rounded-2xl bg-pink-50/70 p-3 text-[11px] leading-5 text-[#5f4254]">
                              {JSON.stringify(step.output, null, 2)}
                            </pre>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}

              <div className="rounded-3xl border border-emerald-200 bg-emerald-50/70 p-5">
                <div className="text-xs font-bold tracking-wide text-emerald-600 uppercase">
                  最终效果
                </div>
                <div className="mt-2 text-sm font-medium text-[#345246]">
                  {execution.finalEffect}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="nail-glass-card space-y-4 rounded-[2rem] p-5">
          <div className="lg:hidden">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索工具..."
              className="h-11 rounded-full border-pink-200 bg-white/65"
            />
          </div>
          <div>
            <h2 className="text-xl font-bold text-[#1f1b20]">当前可用工具</h2>
            <p className="mt-1 text-sm text-[#8f7b88]">
              可按搜索过滤，也可直接把这些工具作为意图调度候选。
            </p>
          </div>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-24 rounded-3xl bg-pink-100/60" />
              ))}
            </div>
          ) : (
            <div className="space-y-6">
              <section>
                <div className="mb-3 text-xs font-bold tracking-wide text-pink-500 uppercase">
                  NailFlow 工具
                </div>
                {nailTools.length === 0 ? (
                  <p className="py-4 text-sm text-[#8f7b88]">没有匹配的工具</p>
                ) : (
                  <div className="space-y-3">
                    {nailTools.map((t) => (
                      <ToolCard key={t.name} tool={t} />
                    ))}
                  </div>
                )}
              </section>
              <section>
                <div className="mb-3 text-xs font-bold tracking-wide text-pink-500 uppercase">
                  内置工具
                </div>
                {builtinTools.length === 0 ? (
                  <p className="py-4 text-sm text-[#8f7b88]">没有匹配的工具</p>
                ) : (
                  <div className="space-y-3">
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
    </NailGlassShell>
  );
}
