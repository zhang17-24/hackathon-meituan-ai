"use client";

import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import { NailPageLayout } from "@/components/nail/nail-page-layout";
import { ToolTimeline } from "@/components/nail/tool-timeline";
import { Badge } from "@/components/ui/badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { fetch as apiFetch } from "@/core/api/fetcher";
import { tryon as api } from "@/core/api/nail";
import { useAuth } from "@/core/auth/AuthProvider";
import { canAccess, type NailRole } from "@/lib/nail-auth";
import { cn } from "@/lib/utils";

/* ── 类型 ── */
interface EvalResult {
  total_score: number;
  rubric_scores: Record<string, number>;
  blocking_issues: string[];
  next_dev_tasks: Array<{ task: string; score_gain: number; effort: string }>;
  demo_evidence: string[];
}
interface NailUser {
  nail_role?: NailRole;
}

/* ── 评分维度配置 ── */
const RUBRIC_CONFIG: Record<
  string,
  { label: string; max: number; color: string }
> = {
  completeness: { label: "完整性", max: 30, color: "bg-blue-400/70" },
  application_effect: { label: "应用效果", max: 25, color: "bg-rose-400/70" },
  innovation: { label: "创新性", max: 20, color: "bg-violet-400/70" },
  business_value: { label: "商业价值", max: 15, color: "bg-emerald-400/70" },
  hard_constraints: { label: "硬约束", max: 10, color: "bg-amber-400/70" },
};

const EFFORT_COLOR: Record<string, string> = {
  low: "text-emerald-400 bg-emerald-500/10 border-emerald-400/20",
  medium: "text-amber-400 bg-amber-500/10 border-amber-400/20",
  high: "text-red-400 bg-red-500/10 border-red-400/20",
};

/* ── 大圆环评分组件 ── */
function ScoreRing({ score }: { score: number }) {
  const r = 52;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(score / 100, 1);
  const color = score >= 80 ? "#34d399" : score >= 60 ? "#fbbf24" : "#f87171";
  const grade =
    score >= 90
      ? "优秀"
      : score >= 75
        ? "良好"
        : score >= 60
          ? "合格"
          : "待改进";

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="130" height="130" viewBox="0 0 130 130">
        {/* 轨道 */}
        <circle
          cx="65"
          cy="65"
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          className="text-muted/40"
        />
        {/* 进度弧 */}
        <circle
          cx="65"
          cy="65"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${pct * circ} ${circ}`}
          strokeDashoffset={circ / 4}
          style={{ transition: "stroke-dasharray 1s ease" }}
        />
        {/* 分数文字 */}
        <text
          x="65"
          y="60"
          textAnchor="middle"
          fontSize="28"
          fontWeight="800"
          fill={color}
        >
          {score}
        </text>
        <text
          x="65"
          y="76"
          textAnchor="middle"
          fontSize="11"
          fill="oklch(0.556 0 0)"
        >
          / 100
        </text>
        <text
          x="65"
          y="92"
          textAnchor="middle"
          fontSize="12"
          fontWeight="600"
          fill={color}
        >
          {grade}
        </text>
      </svg>
    </div>
  );
}

/* ── 主页面 ── */
export default function EvaluationPage() {
  const { user } = useAuth();
  const nailRole = (user as NailUser | null)?.nail_role ?? "user";

  const [summary, setSummary] = useState(
    "完成了以下步骤：\n1. 试戴链路跑通（6个工具串联）\n2. 三端鉴权正常（nail_role贯穿JWT→Agent→前端）\n3. 运营端 ActionProposal 流程完整\n4. 5类降级场景验证通过\n\n未完成：生图API使用mock模式（未配置API key）",
  );
  const [result, setResult] = useState<EvalResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [log, setLog] = useState<string[]>([]);

  /* ── 工具测试 ── */
  interface ToolInfo {
    name: string;
    description: string;
    params: Record<string, string>;
  }
  const { data: tools } = useQuery({
    queryKey: ["testable-tools"],
    queryFn: async () => {
      const res = await apiFetch("/api/nail/dev/tools");
      const d = await res.json();
      return (d.tools ?? []) as ToolInfo[];
    },
    staleTime: 60_000,
  });
  const [testToolName, setTestToolName] = useState("");
  const [testArgs, setTestArgs] = useState("{}");
  const [testResult, setTestResult] = useState<{
    success: boolean;
    result?: string;
    error?: string;
    traceback?: string;
  } | null>(null);
  const [testLoading, setTestLoading] = useState(false);

  const runTestTool = async () => {
    setTestLoading(true);
    setTestResult(null);
    try {
      let args: Record<string, unknown>;
      try {
        args = JSON.parse(testArgs);
      } catch {
        args = {};
      }
      const res = await apiFetch("/api/nail/dev/test-tool", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool_name: testToolName, args }),
      });
      const data = await res.json();
      setTestResult(data);
    } catch (e: unknown) {
      setTestResult({ success: false, error: String(e) });
    } finally {
      setTestLoading(false);
    }
  };

  const selectedTool = tools?.find((t) => t.name === testToolName);

  interface RunData {
    run_id: string;
    tool_chain: Array<{
      tool: string;
      call_index: number;
      duration_ms: number;
      success: boolean;
    }>;
    total_duration_ms: number;
  }
  const [latestRun, setLatestRun] = useState<RunData | null>(null);

  const fetchLatestRun = useCallback(() => {
    fetch("/api/nail/analytics/latest-run")
      .then((r) => r.json())
      .then((d) => setLatestRun(d.run ?? null))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    fetchLatestRun();
    const handler = () => fetchLatestRun();
    window.addEventListener("nail:refresh-dashboard", handler);
    return () => window.removeEventListener("nail:refresh-dashboard", handler);
  }, [fetchLatestRun]);

  if (!canAccess(nailRole, "dev")) {
    return (
      <div className="flex h-full flex-col">
        <EvalHeader />
        <div className="flex flex-1 items-center justify-center">
          <div className="space-y-2 text-center">
            <p className="text-muted-foreground text-sm">需要开发者权限</p>
            <Badge
              variant="outline"
              className="border-amber-400/40 text-xs text-amber-400"
            >
              当前角色：{nailRole}
            </Badge>
          </div>
        </div>
      </div>
    );
  }

  const runEval = async () => {
    if (!summary.trim()) return;
    setLoading(true);
    setResult(null);
    setLog([]);

    try {
      const threadId = await api.createThread();
      const stream = await api.startAgentRun(threadId, {
        input: {
          messages: [
            {
              role: "user",
              content: `请使用 evaluation_tool 对以下运行打分：\n\n${summary}`,
            },
          ],
        },
        config: { configurable: { nail_role: "dev" } },
      });
      const reader = stream.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            /* 捕获评分结果 */
            if (data.type === "tool_result") {
              try {
                const r = JSON.parse(data.content ?? "{}");
                if (r.total_score !== undefined) setResult(r);
              } catch {
                /* ignore */
              }
            }
            /* 日志 */
            const msg = data.content ?? data.text ?? "";
            if (msg && typeof msg === "string" && msg.trim()) {
              setLog((p) => [...p.slice(-15), msg.substring(0, 200)]);
            }
          } catch {
            /* ignore */
          }
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "评分失败";
      setLog((p) => [...p, `错误: ${msg}`]);
    } finally {
      setLoading(false);
    }
  };

  const panelContent = (
    <div className="flex h-full flex-col">
      <EvalHeader />

      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-2xl space-y-5 px-4 py-6">
          {/* 输入区 */}
          <div className="border-border/60 bg-card overflow-hidden rounded-xl border">
            <div className="border-border/40 border-b px-4 py-3">
              <h2 className="text-sm font-semibold">描述本次运行</h2>
              <p className="text-muted-foreground mt-0.5 text-xs">
                告诉 EvaluationAgent
                完成了哪些步骤、使用了哪些工具、遇到了什么问题
              </p>
            </div>
            <div className="p-3">
              <textarea
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                rows={5}
                className="bg-muted/30 border-border/40 text-foreground placeholder:text-muted-foreground/50 focus:bg-muted/40 w-full resize-none rounded-lg border px-3 py-2.5 font-mono text-sm leading-relaxed transition-colors focus:border-blue-400/50 focus:outline-none"
                placeholder="描述本次运行情况..."
              />
              <div className="mt-3 flex items-center justify-between">
                <p className="text-muted-foreground/60 text-[11px]">
                  EvaluationAgent
                  会按赛题评分标准（完整性·效果·创新·商业·硬约束）打分
                </p>
                <Button
                  onClick={runEval}
                  disabled={loading || !summary.trim()}
                  size="sm"
                  className="h-8 bg-blue-600 px-4 text-xs text-white hover:bg-blue-700"
                >
                  {loading ? (
                    <span className="flex items-center gap-1.5">
                      <span className="size-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                      评分中…
                    </span>
                  ) : (
                    "🚀 开始评分"
                  )}
                </Button>
              </div>
            </div>
          </div>

          {/* Agent 日志 */}
          {log.length > 0 && (
            <div className="border-border/40 bg-muted/10 overflow-hidden rounded-xl border">
              <div className="border-border/30 border-b px-3 py-2">
                <span className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
                  Agent 输出
                </span>
              </div>
              <div className="max-h-40 space-y-1 overflow-y-auto px-4 py-3 font-mono">
                {log.map((l, i) => (
                  <p
                    key={i}
                    className="text-muted-foreground text-[11px] leading-relaxed"
                  >
                    <span className="mr-2 text-blue-400/50 select-none">
                      {i + 1}
                    </span>
                    {l}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* ── 工具测试台 ── */}
          <div className="border-border/60 bg-card overflow-hidden rounded-xl border">
            <div className="border-border/40 border-b px-4 py-3">
              <h2 className="text-sm font-semibold">🔧 工具测试台</h2>
              <p className="text-muted-foreground mt-0.5 text-xs">
                直接调用单个工具进行测试，无需走完整 Agent 流程
              </p>
            </div>
            <div className="space-y-3 p-3">
              <div className="flex items-center gap-2">
                <select
                  value={testToolName}
                  onChange={(e) => {
                    setTestToolName(e.target.value);
                    setTestResult(null);
                  }}
                  className="bg-muted/30 border-border/40 flex-1 rounded-lg border px-3 py-1.5 text-sm focus:border-blue-400/50 focus:outline-none"
                >
                  <option value="">选择工具...</option>
                  {tools?.map((t) => (
                    <option key={t.name} value={t.name}>
                      {t.name}
                    </option>
                  ))}
                </select>
                <Button
                  size="sm"
                  disabled={!testToolName || testLoading}
                  onClick={runTestTool}
                  className="h-8 bg-violet-600 px-4 text-xs text-white hover:bg-violet-700"
                >
                  {testLoading ? "执行中…" : "▶ 执行"}
                </Button>
              </div>

              {selectedTool && (
                <div className="space-y-2">
                  <p className="text-muted-foreground text-xs">
                    {selectedTool.description}
                  </p>
                  <textarea
                    value={testArgs}
                    onChange={(e) => setTestArgs(e.target.value)}
                    rows={4}
                    className="bg-muted/30 border-border/40 w-full resize-none rounded-lg border px-3 py-2 font-mono text-xs focus:border-violet-400/50 focus:outline-none"
                    placeholder='{"image_path": "/path/to/image.jpg"}'
                  />
                </div>
              )}

              {testResult && (
                <div
                  className={cn(
                    "max-h-60 overflow-y-auto rounded-lg border p-3 font-mono text-xs",
                    testResult.success
                      ? "border-emerald-400/30 bg-emerald-500/5"
                      : "border-red-400/30 bg-red-500/5",
                  )}
                >
                  {testResult.success ? (
                    <pre className="break-all whitespace-pre-wrap text-emerald-400/90">
                      {testResult.result}
                    </pre>
                  ) : (
                    <div className="space-y-1">
                      <p className="font-semibold text-red-400">
                        ❌ {testResult.error}
                      </p>
                      {testResult.traceback && (
                        <details>
                          <summary className="cursor-pointer text-red-400/60">
                            Traceback
                          </summary>
                          <pre className="mt-1 whitespace-pre-wrap text-red-400/50">
                            {testResult.traceback}
                          </pre>
                        </details>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* 评分结果 */}
          {result && (
            <div className="space-y-4">
              {/* 总分环 + 分项条 */}
              <div className="border-border/60 bg-card rounded-xl border p-5">
                <div className="flex flex-col items-center gap-6 sm:flex-row">
                  <ScoreRing score={result.total_score} />
                  <div className="w-full flex-1 space-y-2.5">
                    {Object.entries(RUBRIC_CONFIG).map(
                      ([key, { label, max, color }]) => {
                        const val = result.rubric_scores?.[key] ?? 0;
                        const pct = (val / max) * 100;
                        return (
                          <div key={key} className="space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="text-muted-foreground text-xs">
                                {label}
                              </span>
                              <span className="text-xs font-semibold tabular-nums">
                                {val}
                                <span className="text-muted-foreground/60 font-normal">
                                  /{max}
                                </span>
                              </span>
                            </div>
                            <div className="bg-muted h-1.5 overflow-hidden rounded-full">
                              <div
                                className={cn(
                                  "h-full rounded-full transition-all duration-700",
                                  color,
                                )}
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          </div>
                        );
                      },
                    )}
                  </div>
                </div>
              </div>

              {/* 必须修复 */}
              {result.blocking_issues?.length > 0 && (
                <div className="overflow-hidden rounded-xl border border-red-500/20 bg-red-500/5">
                  <div className="flex items-center gap-2 border-b border-red-500/15 px-4 py-2.5">
                    <span className="text-xs font-semibold tracking-wide text-red-400 uppercase">
                      🚨 必须修复
                    </span>
                    <Badge className="border-red-400/30 bg-red-500/15 text-[10px] text-red-400">
                      {result.blocking_issues.length}
                    </Badge>
                  </div>
                  <ul className="space-y-2 px-4 py-3">
                    {result.blocking_issues.map((issue, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <span className="mt-0.5 shrink-0 text-red-400">✕</span>
                        <span className="text-foreground/80">{issue}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 下一步任务 */}
              {result.next_dev_tasks?.length > 0 && (
                <div className="border-border/60 bg-card overflow-hidden rounded-xl border">
                  <div className="border-border/40 border-b px-4 py-2.5">
                    <span className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
                      📋 下一步任务（按评分收益排序）
                    </span>
                  </div>
                  <div className="space-y-2 p-3">
                    {result.next_dev_tasks.slice(0, 5).map((task, i) => (
                      <div
                        key={i}
                        className="border-border/30 bg-muted/10 flex items-center gap-3 rounded-lg border px-3 py-2.5"
                      >
                        <span className="min-w-[28px] text-right font-mono text-xs font-bold text-emerald-400">
                          +{task.score_gain}
                        </span>
                        <span className="text-foreground/80 flex-1 text-sm">
                          {task.task}
                        </span>
                        <span
                          className={cn(
                            "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium",
                            EFFORT_COLOR[task.effort] ?? EFFORT_COLOR.medium,
                          )}
                        >
                          {task.effort}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 答辩证据 */}
              {result.demo_evidence?.length > 0 && (
                <div className="border-border/60 bg-card overflow-hidden rounded-xl border">
                  <div className="border-border/40 border-b px-4 py-2.5">
                    <span className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
                      🎯 答辩可展示证据
                    </span>
                  </div>
                  <ul className="space-y-1.5 px-4 py-3">
                    {result.demo_evidence.map((ev, i) => (
                      <li
                        key={i}
                        className="text-muted-foreground flex items-start gap-2 text-sm"
                      >
                        <span className="shrink-0 text-blue-400">✓</span>
                        {ev}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {latestRun && (
            <ToolTimeline
              toolChain={latestRun.tool_chain}
              totalDurationMs={latestRun.total_duration_ms}
              className="mt-4"
            />
          )}

          <div className="h-4" />
        </div>
      </ScrollArea>
    </div>
  );

  return <NailPageLayout pageMode="eval" panel={panelContent} />;
}

/* ── Header ── */
function EvalHeader() {
  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-2 h-4" />
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem className="text-muted-foreground hidden sm:block">
            NailFlow
          </BreadcrumbItem>
          <BreadcrumbSeparator className="hidden sm:block" />
          <BreadcrumbItem>
            <BreadcrumbPage>EvaluationAgent</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
    </header>
  );
}
