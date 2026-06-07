"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

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
  boundary_score: "边界清晰",
  skin_tone_score: "肤色一致",
  lighting_score: "光照匹配",
  style_match_score: "款式相符",
  natural_score: "自然度",
};

function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round((value / 10) * 100);
  const color =
    value >= 8
      ? "bg-gradient-to-r from-pink-400 to-fuchsia-400"
      : value >= 6
        ? "bg-gradient-to-r from-rose-300 to-pink-400"
        : "bg-red-400/60";
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 shrink-0 text-right text-[11px] font-medium text-pink-400">
        {label}
      </span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-pink-100/80">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-700",
            color,
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-5 text-right text-[11px] font-bold text-pink-600 tabular-nums">
        {value.toFixed(1)}
      </span>
    </div>
  );
}

function OverallRing({ score }: { score: number }) {
  const r = 26;
  const circ = 2 * Math.PI * r;
  const filled = (score / 10) * circ;
  const color = score >= 8 ? "#ec4899" : score >= 6 ? "#fb7185" : "#f87171";

  return (
    <div className="flex flex-col items-center">
      <svg width="70" height="70" viewBox="0 0 70 70">
        {/* track */}
        <circle
          cx="35"
          cy="35"
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth="5"
          className="text-pink-100"
        />
        {/* filled arc */}
        <circle
          cx="35"
          cy="35"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circ}`}
          strokeDashoffset={circ / 4}
          style={{ transition: "stroke-dasharray 0.8s ease" }}
        />
        <text
          x="35"
          y="39"
          textAnchor="middle"
          fontSize="16"
          fontWeight="700"
          fill={color}
        >
          {score.toFixed(1)}
        </text>
      </svg>
      <span className="mt-0.5 text-[11px] font-semibold text-pink-400">
        综合评分
      </span>
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
    ? (
        [
          "boundary_score",
          "skin_tone_score",
          "lighting_score",
          "style_match_score",
          "natural_score",
        ] as const
      )
        .filter((k) => scores[k] !== undefined)
        .map((k) => ({
          key: k,
          label: SCORE_LABELS[k] ?? k,
          value: scores[k]!,
        }))
    : [];
  const hasAiCopy = [explanation, fitComment, riskComment].some(Boolean);

  return (
    <div
      className={cn("nail-glass-card overflow-hidden rounded-3xl", className)}
    >
      {/* ── 顶部工具栏 ── */}
      <div className="flex items-center justify-between border-b border-pink-200/50 bg-white/30 px-4 py-3">
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-bold text-pink-700">✨ 试戴结果</span>
          {isMock && (
            <Badge
              variant="outline"
              className="rounded-full border-pink-300/50 bg-white/55 px-2 py-0 text-[10px] text-pink-500"
            >
              Mock
            </Badge>
          )}
          {styleSummaryZh && (
            <span className="hidden max-w-40 truncate text-[11px] text-pink-400 sm:block">
              · {styleSummaryZh}
            </span>
          )}
        </div>
        {/* 视图切换 */}
        <div className="flex gap-0.5 rounded-full bg-white/55 p-1 shadow-inner shadow-pink-100">
          {(["result", "compare", "scores"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={cn(
                "rounded-full px-3 py-1 text-[11px] font-bold transition-all",
                view === v
                  ? "bg-gradient-to-r from-pink-500 to-fuchsia-400 text-white shadow-sm shadow-pink-300/50"
                  : "text-pink-400 hover:text-pink-600",
              )}
            >
              {v === "result" && "结果"}
              {v === "compare" && "对比"}
              {v === "scores" && "评分"}
            </button>
          ))}
        </div>
      </div>

      {/* ── 图像区 ── */}
      <div className="p-4">
        {view === "result" && (
          <div className="relative overflow-hidden rounded-3xl bg-white/45 shadow-inner shadow-pink-100">
            { }
            <img
              src={resultUrl}
              alt="AI 试戴结果"
              className="mx-auto block max-h-80 w-full object-contain"
            />
          </div>
        )}

        {view === "compare" && originalUrl && (
          <div className="grid grid-cols-2 gap-3">
            <div className="relative overflow-hidden rounded-3xl bg-white/45 shadow-inner shadow-pink-100">
              <img
                src={originalUrl}
                alt="原始手图"
                className="max-h-64 w-full object-contain bg-white/60"
              />
              <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-pink-950/60 to-transparent px-3 py-2">
                <span className="text-[11px] font-bold text-white">原图</span>
              </div>
            </div>
            <div className="relative overflow-hidden rounded-3xl bg-white/45 shadow-inner shadow-pink-100">
              <img
                src={resultUrl}
                alt="试戴效果"
                className="max-h-64 w-full object-contain bg-white/60"
              />
              <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-pink-700/70 to-transparent px-3 py-2">
                <span className="text-[11px] font-bold text-pink-50">
                  试戴后
                </span>
              </div>
            </div>
          </div>
        )}

        {view === "scores" && scores && (
          <div className="flex items-start gap-4">
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
      {hasAiCopy && (
        <div className="space-y-2 px-3 pb-3">
          <div className="h-px bg-pink-200/60" />
          {explanation && (
            <p className="text-[12px] leading-relaxed text-pink-500">
              {explanation}
            </p>
          )}
          <div className="flex flex-wrap gap-1.5">
            {fitComment && (
              <span className="inline-flex items-center gap-1 rounded-full border border-pink-300/50 bg-white/55 px-2.5 py-0.5 text-[11px] font-semibold text-pink-500">
                ✓ {fitComment}
              </span>
            )}
            {riskComment && (
              <span className="inline-flex items-center gap-1 rounded-full border border-rose-300/50 bg-white/55 px-2.5 py-0.5 text-[11px] font-semibold text-rose-500">
                ⚠ {riskComment}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
