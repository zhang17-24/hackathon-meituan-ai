"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface QualityScores {
  overall: number;
  boundary_score?: number;
  skin_tone_score?: number;
  lighting_score?: number;
  style_match_score?: number;
  natural_score?: number;
}

interface NailResultPanelProps {
  originalUrl?: string;
  resultUrl?: string;
  isMock?: boolean;
  styleSummaryZh?: string;
  fitComment?: string;
  riskComment?: string;
  explanation?: string;
  scores?: QualityScores;
  className?: string;
}

const SCORE_LABELS: Record<string, string> = {
  boundary_score:    "边界清晰",
  skin_tone_score:   "肤色一致",
  lighting_score:    "光照匹配",
  style_match_score: "款式相符",
  natural_score:     "自然度",
};

function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round((value / 10) * 100);
  const color =
    value >= 8 ? "bg-emerald-400/70" : value >= 6 ? "bg-amber-400/70" : "bg-red-400/60";
  return (
    <div className="flex items-center gap-2">
      <span className="text-[11px] text-muted-foreground w-16 shrink-0 text-right">
        {label}
      </span>
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-700", color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[11px] font-semibold text-foreground/70 w-5 text-right tabular-nums">
        {value.toFixed(1)}
      </span>
    </div>
  );
}

function OverallRing({ score }: { score: number }) {
  const r = 26;
  const circ = 2 * Math.PI * r;
  const filled = (score / 10) * circ;
  const color =
    score >= 8 ? "#34d399" : score >= 6 ? "#fbbf24" : "#f87171";

  return (
    <div className="flex flex-col items-center">
      <svg width="70" height="70" viewBox="0 0 70 70">
        {/* track */}
        <circle
          cx="35" cy="35" r={r}
          fill="none" stroke="currentColor" strokeWidth="5"
          className="text-muted/50"
        />
        {/* filled arc */}
        <circle
          cx="35" cy="35" r={r}
          fill="none" stroke={color} strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circ}`}
          strokeDashoffset={circ / 4}
          style={{ transition: "stroke-dasharray 0.8s ease" }}
        />
        <text
          x="35" y="39"
          textAnchor="middle"
          fontSize="16"
          fontWeight="700"
          fill={color}
        >
          {score.toFixed(1)}
        </text>
      </svg>
      <span className="text-[11px] text-muted-foreground mt-0.5">综合评分</span>
    </div>
  );
}

export function NailResultPanel({
  originalUrl,
  resultUrl,
  isMock,
  styleSummaryZh,
  fitComment,
  riskComment,
  explanation,
  scores,
  className,
}: NailResultPanelProps) {
  const [view, setView] = useState<"result" | "compare" | "scores">("result");

  if (!resultUrl) return null;

  const detailScores = scores
    ? (["boundary_score", "skin_tone_score", "lighting_score", "style_match_score", "natural_score"] as const)
        .filter((k) => scores[k] !== undefined)
        .map((k) => ({ key: k, label: SCORE_LABELS[k] ?? k, value: scores[k]! }))
    : [];

  return (
    <div className={cn("rounded-xl border border-border/60 bg-card overflow-hidden", className)}>
      {/* ── 顶部工具栏 ── */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border/40 bg-muted/20">
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-semibold text-foreground/80">试戴结果</span>
          {isMock && (
            <Badge variant="outline" className="text-[10px] border-amber-400/40 text-amber-400 px-1.5 py-0">
              Mock
            </Badge>
          )}
          {styleSummaryZh && (
            <span className="text-[11px] text-muted-foreground hidden sm:block truncate max-w-40">
              · {styleSummaryZh}
            </span>
          )}
        </div>
        {/* 视图切换 */}
        <div className="flex gap-0.5 rounded-lg bg-muted/60 p-0.5">
          {(["result", "compare", "scores"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={cn(
                "px-2.5 py-1 rounded-md text-[11px] font-medium transition-all",
                view === v
                  ? "bg-background shadow-sm text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {v === "result"  && "结果"}
              {v === "compare" && "对比"}
              {v === "scores"  && "评分"}
            </button>
          ))}
        </div>
      </div>

      {/* ── 图像区 ── */}
      <div className="p-3">
        {view === "result" && (
          <div className="relative rounded-lg overflow-hidden bg-muted/30">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={resultUrl}
              alt="AI 试戴结果"
              className="w-full object-contain max-h-72 mx-auto block"
            />
          </div>
        )}

        {view === "compare" && originalUrl && (
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-lg overflow-hidden bg-muted/30 relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={originalUrl}
                alt="原始手图"
                className="w-full object-cover max-h-64"
              />
              <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/60 to-transparent py-1.5 px-2">
                <span className="text-[11px] text-white font-medium">原图</span>
              </div>
            </div>
            <div className="rounded-lg overflow-hidden bg-muted/30 relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={resultUrl}
                alt="试戴效果"
                className="w-full object-cover max-h-64"
              />
              <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-rose-900/60 to-transparent py-1.5 px-2">
                <span className="text-[11px] text-rose-100 font-medium">试戴后</span>
              </div>
            </div>
          </div>
        )}

        {view === "scores" && scores && (
          <div className="flex gap-4 items-start">
            <OverallRing score={scores.overall} />
            <div className="flex-1 space-y-2 pt-1">
              {detailScores.map(({ key, label, value }) => (
                <ScoreBar key={key} label={label} value={value} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── AI 解释文字 ── */}
      {(explanation || fitComment || riskComment) && (
        <div className="px-3 pb-3 space-y-2">
          <div className="h-px bg-border/30" />
          {explanation && (
            <p className="text-[12px] text-muted-foreground leading-relaxed">
              {explanation}
            </p>
          )}
          <div className="flex flex-wrap gap-1.5">
            {fitComment && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 text-[11px] text-emerald-400">
                ✓ {fitComment}
              </span>
            )}
            {riskComment && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 border border-amber-500/20 px-2.5 py-0.5 text-[11px] text-amber-400">
                ⚠ {riskComment}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
