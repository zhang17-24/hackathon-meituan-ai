"use client";

import { useEffect, useState, useCallback } from "react";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Breadcrumb, BreadcrumbItem, BreadcrumbList,
  BreadcrumbPage, BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useAuth } from "@/core/auth/AuthProvider";
import { canAccess, type NailRole } from "@/lib/nail-auth";
import { cn } from "@/lib/utils";
import { NailPageLayout } from "@/components/nail/nail-page-layout";

/* ── 类型 ── */
interface Signal { style_id: string; signal_type: string; count: number }
interface Proposal {
  id: string; title: string; content: string;
  status: string; created_at: string;
}
interface ProposalContent {
  reason?: string; target_user?: string;
  expected_metric?: string; risk?: string;
}

/* ── 信号类型颜色 ── */
const SIGNAL_COLORS: Record<string, string> = {
  save:   "text-rose-400 bg-rose-500/10 border-rose-400/20",
  order:  "text-emerald-400 bg-emerald-500/10 border-emerald-400/20",
  click:  "text-blue-400 bg-blue-500/10 border-blue-400/20",
  search: "text-amber-400 bg-amber-500/10 border-amber-400/20",
};
const SIGNAL_LABEL: Record<string, string> = {
  save: "收藏", order: "下单", click: "点击", search: "搜索",
};

/* ── 主页面 ── */
export default function DashboardPage() {
  const { user } = useAuth();
  const nailRole = (user as any)?.nail_role as NailRole ?? "user";

  const [signals,   setSignals]   = useState<Signal[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [summary,   setSummary]   = useState<Record<string, number>>({});
  const [loading,   setLoading]   = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    try {
      const [dash, props] = await Promise.all([
        fetch("/api/nail/dashboard?days=7").then(r => r.json()),
        fetch("/api/nail/proposals?status=pending").then(r => r.json()),
      ]);
      setSignals(dash.signals ?? []);
      setSummary(dash.proposal_summary ?? {});
      setProposals(props.proposals ?? []);
    } catch { /* ignore */ } finally {
      setLoading(false); setRefreshing(false);
    }
  }, []);

  useEffect(() => { if (canAccess(nailRole, "ops")) fetchData(); }, [nailRole, fetchData]);

  // 监听 Agent 工具调用完成后的刷新信号
  useEffect(() => {
    const handler = () => fetchData(true);
    window.addEventListener("nail:refresh-dashboard", handler);
    return () => window.removeEventListener("nail:refresh-dashboard", handler);
  }, [fetchData]);

  const confirm = async (id: string, status: "approved" | "rejected") => {
    await fetch(`/api/nail/proposals/${id}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    setProposals(prev => prev.filter(p => p.id !== id));
    setSummary(prev => ({
      ...prev,
      pending: Math.max(0, (prev.pending ?? 0) - 1),
      [status]: (prev[status] ?? 0) + 1,
    }));
  };

  if (!canAccess(nailRole, "ops")) {
    return (
      <div className="flex h-full flex-col">
        <Header />
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center space-y-2">
            <p className="text-muted-foreground text-sm">需要运营或开发权限</p>
            <Badge variant="outline" className="text-xs border-amber-400/40 text-amber-400">
              当前角色：{nailRole}
            </Badge>
          </div>
        </div>
      </div>
    );
  }

  /* ── 按款式聚合信号 ── */
  const styleMap: Record<string, Record<string, number>> = {};
  signals.forEach(({ style_id, signal_type, count }) => {
    if (!styleMap[style_id]) styleMap[style_id] = {};
    styleMap[style_id][signal_type] = (styleMap[style_id][signal_type] ?? 0) + count;
  });
  const styles = Object.entries(styleMap)
    .map(([id, types]) => ({ id, total: Object.values(types).reduce((a, b) => a + b, 0), types }))
    .sort((a, b) => b.total - a.total);

  const panelContent = (
    <div className="h-full overflow-auto">
      <div className="flex h-full flex-col">
        <Header
          extra={
            <Button
              variant="ghost" size="sm"
              onClick={() => fetchData(true)}
              disabled={refreshing}
              className="text-xs text-muted-foreground h-7"
            >
              {refreshing ? (
                <span className="size-3 rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground animate-spin mr-1" />
              ) : "↻"}
              刷新
            </Button>
          }
        />

        <ScrollArea className="flex-1">
          <div className="mx-auto max-w-3xl px-4 py-6 space-y-5">

            {/* ── 汇总统计 ── */}
            <div className="grid grid-cols-3 gap-3">
              {[
                { key: "pending",  label: "待确认", color: "text-amber-400",   bg: "bg-amber-500/5   border-amber-400/20"   },
                { key: "approved", label: "已执行", color: "text-emerald-400", bg: "bg-emerald-500/5 border-emerald-400/20" },
                { key: "rejected", label: "已拒绝", color: "text-muted-foreground", bg: "bg-muted/30 border-border/30" },
              ].map(({ key, label, color, bg }) => (
                <div key={key} className={cn("rounded-xl border p-3 text-center", bg)}>
                  {loading ? (
                    <Skeleton className="h-7 w-8 mx-auto mb-1 rounded" />
                  ) : (
                    <p className={cn("text-2xl font-bold tabular-nums", color)}>
                      {summary[key] ?? 0}
                    </p>
                  )}
                  <p className="text-[11px] text-muted-foreground mt-0.5">{label}</p>
                </div>
              ))}
            </div>

            {/* ── 近 7 天款式热度 ── */}
            <section className="rounded-xl border border-border/60 bg-card overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-border/40">
                <h2 className="text-sm font-semibold">近 7 天款式热度</h2>
                <span className="text-[11px] text-muted-foreground">按信号总量排序</span>
              </div>
              <div className="p-3">
                {loading ? (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {Array.from({ length: 8 }).map((_, i) => (
                      <Skeleton key={i} className="h-16 rounded-lg" />
                    ))}
                  </div>
                ) : styles.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-6 text-center">暂无信号数据</p>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {styles.slice(0, 8).map(({ id, total, types }) => (
                      <div
                        key={id}
                        className="rounded-lg border border-border/40 bg-muted/20 px-3 py-2.5 space-y-1.5"
                      >
                        <p className="text-[13px] font-medium text-foreground/90 truncate">{id}</p>
                        <div className="flex flex-wrap gap-1">
                          {Object.entries(types).map(([type, cnt]) => (
                            <span
                              key={type}
                              className={cn(
                                "inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-medium",
                                SIGNAL_COLORS[type] ?? "text-muted-foreground bg-muted/30 border-border/30",
                              )}
                            >
                              {SIGNAL_LABEL[type] ?? type} {cnt}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>

            {/* ── 待确认运营方案 ── */}
            <section className="rounded-xl border border-border/60 bg-card overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-border/40">
                <h2 className="text-sm font-semibold">待确认运营方案</h2>
                {proposals.length > 0 && (
                  <Badge className="bg-amber-500/15 text-amber-400 border-amber-400/30 text-[10px] h-4.5 px-1.5">
                    {proposals.length}
                  </Badge>
                )}
              </div>
              <div className="p-3 space-y-2.5">
                {loading ? (
                  Array.from({ length: 2 }).map((_, i) => (
                    <Skeleton key={i} className="h-28 rounded-xl" />
                  ))
                ) : proposals.length === 0 ? (
                  <div className="py-8 text-center">
                    <p className="text-sm text-muted-foreground">暂无待确认方案</p>
                    <p className="text-[11px] text-muted-foreground/60 mt-1">
                      运营 Agent 生成新方案后会出现在这里
                    </p>
                  </div>
                ) : (
                  proposals.map(p => <ProposalCard key={p.id} proposal={p} onConfirm={confirm} />)
                )}
              </div>
            </section>

            <div className="h-4" />
          </div>
        </ScrollArea>
      </div>
    </div>
  );

  return (
    <NailPageLayout
      pageMode="ops"
      panel={panelContent}
    />
  );
}

/* ── 提案卡片 ── */
function ProposalCard({
  proposal,
  onConfirm,
}: {
  proposal: Proposal;
  onConfirm: (id: string, status: "approved" | "rejected") => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState<"approved" | "rejected" | null>(null);

  let content: ProposalContent = {};
  try { content = JSON.parse(proposal.content); } catch { /* ignore */ }

  const handle = async (status: "approved" | "rejected") => {
    setConfirming(true);
    await onConfirm(proposal.id, status);
    setConfirmed(status);
  };

  return (
    <div
      className={cn(
        "rounded-xl border p-4 space-y-3 transition-opacity duration-300",
        confirmed ? "opacity-50 pointer-events-none" : "border-border/50 bg-muted/10",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-foreground leading-snug">{proposal.title}</h3>
        <span className="text-[10px] text-muted-foreground/60 shrink-0 mt-0.5">
          {new Date(proposal.created_at).toLocaleDateString("zh", { month: "short", day: "numeric" })}
        </span>
      </div>

      {content.reason && (
        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">{content.reason}</p>
      )}

      <div className="flex flex-wrap gap-1.5">
        {content.target_user && (
          <span className="text-[10px] rounded-full border border-border/40 bg-muted/30 px-2 py-0.5 text-muted-foreground">
            👥 {content.target_user}
          </span>
        )}
        {content.expected_metric && (
          <span className="text-[10px] rounded-full border border-emerald-400/30 bg-emerald-500/5 px-2 py-0.5 text-emerald-400">
            📈 {content.expected_metric}
          </span>
        )}
        {content.risk && (
          <span className="text-[10px] rounded-full border border-amber-400/30 bg-amber-500/5 px-2 py-0.5 text-amber-400">
            ⚠ {content.risk}
          </span>
        )}
      </div>

      {confirmed ? (
        <p className={cn(
          "text-xs font-medium",
          confirmed === "approved" ? "text-emerald-400" : "text-muted-foreground",
        )}>
          {confirmed === "approved" ? "✓ 已确认执行" : "已拒绝"}
        </p>
      ) : (
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => handle("approved")}
            disabled={confirming}
            className="h-7 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            ✓ 确认执行
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => handle("rejected")}
            disabled={confirming}
            className="h-7 text-xs border-border/50 text-muted-foreground hover:text-foreground"
          >
            拒绝
          </Button>
        </div>
      )}
    </div>
  );
}

/* ── 复用 Header ── */
function Header({ extra }: { extra?: React.ReactNode }) {
  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-2 h-4" />
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem className="hidden sm:block text-muted-foreground">NailFlow</BreadcrumbItem>
          <BreadcrumbSeparator className="hidden sm:block" />
          <BreadcrumbItem>
            <BreadcrumbPage>运营看板</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      {extra && <div className="ml-auto">{extra}</div>}
    </header>
  );
}
