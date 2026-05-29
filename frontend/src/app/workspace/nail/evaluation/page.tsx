"use client";

import { useCallback, useEffect, useState } from "react";
import { Separator } from "@/components/ui/separator";
import { NailPageLayout } from "@/components/nail/nail-page-layout";
import { ToolTimeline } from "@/components/nail/tool-timeline";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Breadcrumb, BreadcrumbItem, BreadcrumbList,
  BreadcrumbPage, BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { SidebarTrigger } from "@/components/ui/sidebar";
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

/* ── 评分维度配置 ── */
const RUBRIC_CONFIG: Record<string, { label: string; max: number; color: string }> = {
  completeness:       { label: "完整性",   max: 30, color: "bg-blue-400/70"    },
  application_effect: { label: "应用效果", max: 25, color: "bg-rose-400/70"    },
  innovation:         { label: "创新性",   max: 20, color: "bg-violet-400/70"  },
  business_value:     { label: "商业价值", max: 15, color: "bg-emerald-400/70" },
  hard_constraints:   { label: "硬约束",   max: 10, color: "bg-amber-400/70"   },
};

const EFFORT_COLOR: Record<string, string> = {
  low:    "text-emerald-400 bg-emerald-500/10 border-emerald-400/20",
  medium: "text-amber-400 bg-amber-500/10 border-amber-400/20",
  high:   "text-red-400 bg-red-500/10 border-red-400/20",
};

/* ── 大圆环评分组件 ── */
function ScoreRing({ score }: { score: number }) {
  const r    = 52;
  const circ = 2 * Math.PI * r;
  const pct  = Math.min(score / 100, 1);
  const color =
    score >= 80 ? "#34d399" : score >= 60 ? "#fbbf24" : "#f87171";
  const grade =
    score >= 90 ? "优秀" : score >= 75 ? "良好" : score >= 60 ? "合格" : "待改进";

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="130" height="130" viewBox="0 0 130 130">
        {/* 轨道 */}
        <circle cx="65" cy="65" r={r}
          fill="none" stroke="currentColor" strokeWidth="8"
          className="text-muted/40"
        />
        {/* 进度弧 */}
        <circle cx="65" cy="65" r={r}
          fill="none" stroke={color} strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${pct * circ} ${circ}`}
          strokeDashoffset={circ / 4}
          style={{ transition: "stroke-dasharray 1s ease" }}
        />
        {/* 分数文字 */}
        <text x="65" y="60" textAnchor="middle" fontSize="28" fontWeight="800" fill={color}>
          {score}
        </text>
        <text x="65" y="76" textAnchor="middle" fontSize="11" fill="oklch(0.556 0 0)">
          / 100
        </text>
        <text x="65" y="92" textAnchor="middle" fontSize="12" fontWeight="600" fill={color}>
          {grade}
        </text>
      </svg>
    </div>
  );
}

/* ── 主页面 ── */
export default function EvaluationPage() {
  const { user } = useAuth();
  const nailRole = (user as any)?.nail_role as NailRole ?? "user";

  const [summary, setSummary] = useState(
    "完成了以下步骤：\n1. 试戴链路跑通（6个工具串联）\n2. 三端鉴权正常（nail_role贯穿JWT→Agent→前端）\n3. 运营端 ActionProposal 流程完整\n4. 5类降级场景验证通过\n\n未完成：生图API使用mock模式（未配置API key）",
  );
  const [result,  setResult]  = useState<EvalResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [log,     setLog]     = useState<string[]>([]);

  interface RunData {
    run_id: string;
    tool_chain: Array<{ tool: string; call_index: number; duration_ms: number; success: boolean }>;
    total_duration_ms: number;
  }
  const [latestRun, setLatestRun] = useState<RunData | null>(null);

  const fetchLatestRun = useCallback(() => {
    fetch("/api/nail/analytics/latest-run")
      .then((r) => r.json())
      .then((d) => setLatestRun(d.run ?? null))
      .catch(() => {});
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
          <div className="text-center space-y-2">
            <p className="text-muted-foreground text-sm">需要开发者权限</p>
            <Badge variant="outline" className="text-xs border-amber-400/40 text-amber-400">
              当前角色：{nailRole}
            </Badge>
          </div>
        </div>
      </div>
    );
  }

  const runEval = async () => {
    if (!summary.trim()) return;
    setLoading(true); setResult(null); setLog([]);

    try {
      const threadRes = await fetch("/api/v1/threads", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
      });
      const thread = await threadRes.json();
      const threadId = thread.thread_id ?? thread.id;

      const runRes = await fetch(`/api/v1/threads/${threadId}/runs/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input: { messages: [{ role: "user", content: `请使用 evaluation_tool 对以下运行打分：\n\n${summary}` }] },
          config: { configurable: { nail_role: "dev" } },
        }),
      });

      const reader  = runRes.body!.getReader();
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
              } catch { /* ignore */ }
            }
            /* 日志 */
            const msg = data.content ?? data.text ?? "";
            if (msg && typeof msg === "string" && msg.trim()) {
              setLog(p => [...p.slice(-15), msg.substring(0, 200)]);
            }
          } catch { /* ignore */ }
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "评分失败";
      setLog(p => [...p, `错误: ${msg}`]);
    } finally {
      setLoading(false);
    }
  };

  const panelContent = (
    <div className="flex h-full flex-col">
      <EvalHeader />

      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-2xl px-4 py-6 space-y-5">

          {/* 输入区 */}
          <div className="rounded-xl border border-border/60 bg-card overflow-hidden">
            <div className="px-4 py-3 border-b border-border/40">
              <h2 className="text-sm font-semibold">描述本次运行</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                告诉 EvaluationAgent 完成了哪些步骤、使用了哪些工具、遇到了什么问题
              </p>
            </div>
            <div className="p-3">
              <textarea
                value={summary}
                onChange={e => setSummary(e.target.value)}
                rows={5}
                className="w-full resize-none rounded-lg bg-muted/30 border border-border/40 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-blue-400/50 focus:bg-muted/40 transition-colors font-mono leading-relaxed"
                placeholder="描述本次运行情况..."
              />
              <div className="flex items-center justify-between mt-3">
                <p className="text-[11px] text-muted-foreground/60">
                  EvaluationAgent 会按赛题评分标准（完整性·效果·创新·商业·硬约束）打分
                </p>
                <Button
                  onClick={runEval}
                  disabled={loading || !summary.trim()}
                  size="sm"
                  className="bg-blue-600 hover:bg-blue-700 text-white h-8 px-4 text-xs"
                >
                  {loading ? (
                    <span className="flex items-center gap-1.5">
                      <span className="size-3 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                      评分中…
                    </span>
                  ) : "🚀 开始评分"}
                </Button>
              </div>
            </div>
          </div>

          {/* Agent 日志 */}
          {log.length > 0 && (
            <div className="rounded-xl border border-border/40 bg-muted/10 overflow-hidden">
              <div className="px-3 py-2 border-b border-border/30">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  Agent 输出
                </span>
              </div>
              <div className="max-h-40 overflow-y-auto px-4 py-3 space-y-1 font-mono">
                {log.map((l, i) => (
                  <p key={i} className="text-[11px] text-muted-foreground leading-relaxed">
                    <span className="text-blue-400/50 select-none mr-2">{i + 1}</span>{l}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* 评分结果 */}
          {result && (
            <div className="space-y-4">
              {/* 总分环 + 分项条 */}
              <div className="rounded-xl border border-border/60 bg-card p-5">
                <div className="flex flex-col sm:flex-row items-center gap-6">
                  <ScoreRing score={result.total_score} />
                  <div className="flex-1 w-full space-y-2.5">
                    {Object.entries(RUBRIC_CONFIG).map(([key, { label, max, color }]) => {
                      const val = result.rubric_scores?.[key] ?? 0;
                      const pct = (val / max) * 100;
                      return (
                        <div key={key} className="space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="text-xs text-muted-foreground">{label}</span>
                            <span className="text-xs font-semibold tabular-nums">
                              {val}
                              <span className="text-muted-foreground/60 font-normal">/{max}</span>
                            </span>
                          </div>
                          <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                            <div
                              className={cn("h-full rounded-full transition-all duration-700", color)}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* 必须修复 */}
              {result.blocking_issues?.length > 0 && (
                <div className="rounded-xl border border-red-500/20 bg-red-500/5 overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-2.5 border-b border-red-500/15">
                    <span className="text-xs font-semibold text-red-400 uppercase tracking-wide">
                      🚨 必须修复
                    </span>
                    <Badge className="text-[10px] bg-red-500/15 text-red-400 border-red-400/30">
                      {result.blocking_issues.length}
                    </Badge>
                  </div>
                  <ul className="px-4 py-3 space-y-2">
                    {result.blocking_issues.map((issue, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <span className="text-red-400 shrink-0 mt-0.5">✕</span>
                        <span className="text-foreground/80">{issue}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 下一步任务 */}
              {result.next_dev_tasks?.length > 0 && (
                <div className="rounded-xl border border-border/60 bg-card overflow-hidden">
                  <div className="px-4 py-2.5 border-b border-border/40">
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                      📋 下一步任务（按评分收益排序）
                    </span>
                  </div>
                  <div className="p-3 space-y-2">
                    {result.next_dev_tasks.slice(0, 5).map((task, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-3 rounded-lg border border-border/30 bg-muted/10 px-3 py-2.5"
                      >
                        <span className="text-xs font-bold text-emerald-400 font-mono min-w-[28px] text-right">
                          +{task.score_gain}
                        </span>
                        <span className="flex-1 text-sm text-foreground/80">{task.task}</span>
                        <span className={cn(
                          "text-[10px] font-medium rounded-full border px-2 py-0.5 shrink-0",
                          EFFORT_COLOR[task.effort] ?? EFFORT_COLOR.medium,
                        )}>
                          {task.effort}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 答辩证据 */}
              {result.demo_evidence?.length > 0 && (
                <div className="rounded-xl border border-border/60 bg-card overflow-hidden">
                  <div className="px-4 py-2.5 border-b border-border/40">
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                      🎯 答辩可展示证据
                    </span>
                  </div>
                  <ul className="px-4 py-3 space-y-1.5">
                    {result.demo_evidence.map((ev, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                        <span className="text-blue-400 shrink-0">✓</span>
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

  return (
    <NailPageLayout
      pageMode="eval"
      panel={panelContent}
    />
  );
}

/* ── Header ── */
function EvalHeader() {
  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-2 h-4" />
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem className="hidden sm:block text-muted-foreground">NailFlow</BreadcrumbItem>
          <BreadcrumbSeparator className="hidden sm:block" />
          <BreadcrumbItem>
            <BreadcrumbPage>EvaluationAgent</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
    </header>
  );
}
