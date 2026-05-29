// frontend/src/app/workspace/nail/dashboard/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/core/auth/AuthProvider";
import { canAccess, type NailRole } from "@/lib/nail-auth";

interface Signal { style_id: string; signal_type: string; count: number; }
interface Proposal { id: string; title: string; content: string; status: string; created_at: string; }

export default function DashboardPage() {
  const { user } = useAuth();
  const nailRole = (user as any)?.nail_role as NailRole ?? "user";

  const [signals, setSignals] = useState<Signal[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [summary, setSummary] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!canAccess(nailRole, "ops")) return;
    Promise.all([
      fetch("/api/nail/dashboard?days=7").then(r => r.json()),
      fetch("/api/nail/proposals?status=pending").then(r => r.json()),
    ]).then(([dash, props]) => {
      setSignals(dash.signals ?? []);
      setSummary(dash.proposal_summary ?? {});
      setProposals(props.proposals ?? []);
    }).finally(() => setLoading(false));
  }, [nailRole]);

  const confirm = async (id: string, status: "approved" | "rejected") => {
    await fetch(`/api/nail/proposals/${id}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    setProposals(prev => prev.filter(p => p.id !== id));
  };

  if (!canAccess(nailRole, "ops")) {
    return <div className="p-6 text-muted-foreground">⚠️ 需要运营或开发权限</div>;
  }

  return (
    <div className="min-h-screen p-6 space-y-6">
      <h1 className="text-2xl font-bold">📊 运营看板</h1>

      {loading ? (
        <p className="text-muted-foreground">加载中...</p>
      ) : (
        <>
          {/* 趋势信号 */}
          <div className="rounded-lg border bg-card p-4">
            <h2 className="font-semibold mb-3 text-sm">近 7 天款式热度</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {signals.slice(0, 8).map((s, i) => (
                <div key={i} className="rounded-md bg-pink-50 p-2 text-sm">
                  <p className="font-medium text-pink-700 truncate">{s.style_id}</p>
                  <p className="text-muted-foreground text-xs">{s.signal_type}: {s.count}</p>
                </div>
              ))}
              {signals.length === 0 && <p className="text-muted-foreground text-sm col-span-4">暂无信号数据</p>}
            </div>
          </div>

          {/* 提案状态 */}
          <div className="rounded-lg border bg-card p-4">
            <h2 className="font-semibold mb-3 text-sm">方案状态汇总</h2>
            <div className="flex gap-4">
              {Object.entries(summary).map(([status, count]) => (
                <div key={status} className="text-center">
                  <p className="text-2xl font-bold">{count}</p>
                  <p className="text-xs text-muted-foreground">{status}</p>
                </div>
              ))}
            </div>
          </div>

          {/* 待确认提案 */}
          <div className="rounded-lg border bg-card p-4">
            <h2 className="font-semibold mb-3 text-sm">待确认运营方案 ({proposals.length})</h2>
            <div className="space-y-3">
              {proposals.map(p => {
                let content: any = {};
                try { content = JSON.parse(p.content); } catch {}
                return (
                  <div key={p.id} className="rounded-md border p-3">
                    <p className="font-medium text-sm">{p.title}</p>
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{content.reason ?? ""}</p>
                    <div className="flex gap-2 mt-2">
                      <button onClick={() => confirm(p.id, "approved")} className="rounded px-3 py-1 bg-green-500 text-white text-xs hover:bg-green-600">确认执行</button>
                      <button onClick={() => confirm(p.id, "rejected")} className="rounded px-3 py-1 bg-red-400 text-white text-xs hover:bg-red-500">拒绝</button>
                    </div>
                  </div>
                );
              })}
              {proposals.length === 0 && <p className="text-muted-foreground text-sm">暂无待确认方案</p>}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
