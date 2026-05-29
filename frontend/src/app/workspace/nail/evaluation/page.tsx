// frontend/src/app/workspace/nail/evaluation/page.tsx
"use client";

import { useState } from "react";
import { useAuth } from "@/core/auth/AuthProvider";
import { canAccess, type NailRole } from "@/lib/nail-auth";

interface EvalResult {
  total_score: number;
  rubric_scores: Record<string, number>;
  blocking_issues: string[];
  next_dev_tasks: Array<{ task: string; score_gain: number; effort: string }>;
  demo_evidence: string[];
}

export default function EvaluationPage() {
  const { user } = useAuth();
  const nailRole = (user as any)?.nail_role as NailRole ?? "user";

  const [summary, setSummary] = useState("");
  const [result, setResult] = useState<EvalResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [log, setLog] = useState<string[]>([]);

  if (!canAccess(nailRole, "dev")) {
    return <div className="p-6 text-muted-foreground">⚠️ 需要开发者权限</div>;
  }

  const runEvaluation = async () => {
    if (!summary.trim()) return;
    setLoading(true);
    setResult(null);
    setLog([]);

    try {
      const threadRes = await fetch("/api/v1/threads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      const thread = await threadRes.json();
      const threadId = thread.thread_id ?? thread.id;

      const runRes = await fetch(`/api/v1/threads/${threadId}/runs/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input: { messages: [{ role: "user", content: `请使用 evaluation_tool 对以下运行打分：${summary}` }] },
          config: { configurable: { nail_role: "dev" } },
        }),
      });

      const reader = runRes.body!.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.tool_name === "evaluation" || data.type === "tool_result") {
              const r = JSON.parse(data.content ?? "{}");
              if (r.total_score !== undefined) setResult(r);
            }
            const msg = data.content ?? data.text ?? "";
            if (msg && typeof msg === "string") setLog(p => [...p.slice(-10), msg.substring(0, 150)]);
          } catch {}
        }
      }
    } catch (e: any) {
      setLog(p => [...p, `错误: ${e.message}`]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen p-6 space-y-6">
      <h1 className="text-2xl font-bold">⚡ EvaluationAgent 评分</h1>

      <div className="rounded-lg border bg-card p-4 space-y-3">
        <textarea
          value={summary}
          onChange={e => setSummary(e.target.value)}
          placeholder="描述本次运行：完成了哪些步骤、工具调用情况、遇到的问题..."
          className="w-full rounded border p-3 text-sm min-h-28 bg-background resize-none"
        />
        <button
          onClick={runEvaluation}
          disabled={loading || !summary.trim()}
          className="rounded-lg bg-blue-600 px-4 py-2 text-white text-sm disabled:opacity-40 hover:bg-blue-700"
        >
          {loading ? "⏳ 评分中..." : "🚀 运行 EvaluationAgent"}
        </button>
      </div>

      {log.length > 0 && (
        <div className="rounded-lg border bg-gray-950 p-3">
          <p className="text-xs text-gray-400 mb-1">Agent 输出</p>
          {log.map((l, i) => <p key={i} className="text-xs text-gray-300 font-mono">{l}</p>)}
        </div>
      )}

      {result && (
        <div className="rounded-lg border bg-card p-4 space-y-4">
          <div className="text-center">
            <p className="text-5xl font-bold text-blue-600">{result.total_score}</p>
            <p className="text-muted-foreground text-sm">总分 / 100</p>
          </div>

          <div className="grid grid-cols-5 gap-2">
            {Object.entries(result.rubric_scores ?? {}).map(([k, v]) => (
              <div key={k} className="rounded-md bg-blue-50 p-2 text-center">
                <p className="text-xs text-muted-foreground truncate">{k}</p>
                <p className="font-bold text-blue-700">{v}</p>
              </div>
            ))}
          </div>

          {result.blocking_issues?.length > 0 && (
            <div className="rounded-md bg-red-50 border border-red-200 p-3">
              <p className="text-sm font-semibold text-red-600 mb-1">必须修复</p>
              <ul className="list-disc pl-4 text-sm text-red-700 space-y-1">
                {result.blocking_issues.map((i, idx) => <li key={idx}>{i}</li>)}
              </ul>
            </div>
          )}

          {result.next_dev_tasks?.length > 0 && (
            <div className="space-y-1">
              <p className="text-sm font-semibold">下一步任务（按评分收益）</p>
              {result.next_dev_tasks.slice(0, 5).map((t, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm rounded border p-2">
                  <span className="text-green-600 font-mono text-xs">+{t.score_gain}</span>
                  <span className="flex-1">{t.task}</span>
                  <span className="text-xs text-muted-foreground bg-gray-100 px-1 rounded">{t.effort}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
