"use client";

import { useState, useCallback } from "react";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { NailImageUploader } from "@/components/nail/image-uploader";
import { NailProgressSteps, TRYON_STEPS, type StepStatus } from "@/components/nail/progress-steps";
import { NailResultPanel } from "@/components/nail/result-panel";
import { useAuth } from "@/core/auth/AuthProvider";
import { type NailRole } from "@/lib/nail-auth";
import { cn } from "@/lib/utils";

/* ── 类型定义 ── */
interface TryonResult {
  resultPath: string;
  isMock: boolean;
  styleSummaryZh?: string;
  fitComment?: string;
  riskComment?: string;
  explanation?: string;
  scores?: {
    overall: number;
    boundary_score?: number;
    skin_tone_score?: number;
    lighting_score?: number;
    style_match_score?: number;
    natural_score?: number;
  };
}

/* ── 上传文件到后端 ── */
async function uploadFile(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/v1/uploads", { method: "POST", body: form });
  if (!res.ok) throw new Error(`上传失败: ${res.statusText}`);
  const data = await res.json();
  return data.url ?? data.file_url ?? data.path ?? "";
}

/* ── SSE 工具名 → 步骤 ID 映射 ── */
const TOOL_TO_STEP: Record<string, string> = {
  hand_detect_tool:        "detect",
  nail_mask_tool:          "mask",
  style_understanding_tool:"style",
  prompt_builder_tool:     "prompt",
  image_generation_tool:   "generate",
  quality_check_tool:      "quality",
};

/* ══════════════════════════════════════════════════════════ */
export default function TryonPage() {
  const { user } = useAuth();
  const nailRole = (user as any)?.nail_role as NailRole ?? "user";

  /* 图片状态 */
  const [handFile,    setHandFile]    = useState<File | null>(null);
  const [styleFile,   setStyleFile]   = useState<File | null>(null);
  const [handPreview, setHandPreview] = useState<string>("");
  const [stylePreview,setStylePreview]= useState<string>("");

  /* 运行状态 */
  const [loading, setLoading]   = useState(false);
  const [error,   setError]     = useState<string>("");
  const [stepStatuses, setStepStatuses] = useState<Record<string, StepStatus>>({});
  const [agentLog, setAgentLog] = useState<string[]>([]);

  /* 结果 */
  const [result, setResult] = useState<TryonResult | null>(null);

  /* 设置步骤状态的工具函数 */
  const setStep = useCallback((stepId: string, status: StepStatus) => {
    setStepStatuses(prev => ({ ...prev, [stepId]: status }));
  }, []);

  /* ── 开始试戴 ── */
  const startTryon = async () => {
    if (!handFile || !styleFile) return;
    setLoading(true);
    setError("");
    setResult(null);
    setAgentLog([]);
    setStepStatuses({});

    try {
      /* 1. 上传图片 */
      const [handUrl, styleUrl] = await Promise.all([
        uploadFile(handFile),
        uploadFile(styleFile),
      ]);

      /* 2. 创建 thread */
      const threadRes = await fetch("/api/v1/threads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!threadRes.ok) throw new Error("创建会话失败");
      const thread = await threadRes.json();
      const threadId = thread.thread_id ?? thread.id;

      /* 3. 发起 SSE 流式运行 */
      const runRes = await fetch(`/api/v1/threads/${threadId}/runs/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input: {
            messages: [{
              role: "user",
              content: `请帮我进行 AI 美甲试戴。\n手图：${handUrl}\n款式图：${styleUrl}`,
            }],
          },
          config: { configurable: { nail_role: nailRole } },
        }),
      });

      if (!runRes.ok) throw new Error(`Agent 启动失败: ${runRes.statusText}`);

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

            /* 工具调用开始 → 步骤 running */
            if (data.type === "tool_call_start" || data.type === "tool_call") {
              const toolName = data.tool_name ?? data.name ?? "";
              const stepId = TOOL_TO_STEP[toolName];
              if (stepId) setStep(stepId, "running");
            }

            /* 工具结果 → 步骤 done，解析关键数据 */
            if (data.type === "tool_result") {
              const toolName = data.tool_name ?? "";
              const stepId   = TOOL_TO_STEP[toolName];
              if (stepId) setStep(stepId, "done");

              if (toolName === "image_generation_tool") {
                const r = JSON.parse(data.content ?? "{}");
                if (r.result_path) {
                  setResult(prev => ({
                    ...prev,
                    resultPath: `/api/nail/image?path=${encodeURIComponent(r.result_path)}`,
                    isMock: r.is_mock ?? false,
                  } as TryonResult));
                }
              }

              if (toolName === "quality_check_tool") {
                try {
                  const q = JSON.parse(data.content ?? "{}");
                  setResult(prev => prev ? ({
                    ...prev,
                    scores:       { overall: q.overall, ...q.scores },
                    fitComment:   q.fit_comment,
                    riskComment:  q.risk_comment,
                    explanation:  q.explanation_zh,
                  }) : prev);
                } catch { /* ignore */ }
              }

              if (toolName === "prompt_builder_tool") {
                try {
                  const p = JSON.parse(data.content ?? "{}");
                  setResult(prev => prev ? ({
                    ...prev,
                    styleSummaryZh: p.style_summary_zh,
                  }) : { resultPath: "", isMock: false, styleSummaryZh: p.style_summary_zh });
                } catch { /* ignore */ }
              }
            }

            /* 消息/思考内容 → Agent 日志 */
            const content = data.content ?? data.text ?? data.delta ?? "";
            if (content && typeof content === "string" && content.trim()) {
              setAgentLog(prev => [...prev.slice(-30), content.substring(0, 300)]);
            }

          } catch { /* 忽略非 JSON 行 */ }
        }
      }

      /* 若 result 还是空（全 mock），设置一个空结果占位 */
      setResult(prev => prev ?? { resultPath: "", isMock: true });

    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "试戴失败，请重试";
      setError(msg);
      /* 将 running 步骤标记为 error */
      setStepStatuses(prev => {
        const next = { ...prev };
        Object.keys(next).forEach(k => { if (next[k] === "running") next[k] = "error"; });
        return next;
      });
    } finally {
      setLoading(false);
    }
  };

  const canStart = handFile && styleFile && !loading;
  const hasSteps = Object.keys(stepStatuses).length > 0;
  const showLog  = (nailRole === "ops" || nailRole === "dev") && agentLog.length > 0;

  /* ══════ JSX ══════ */
  return (
    <div className="flex h-full flex-col">

      {/* ── 顶部 Header（DeerFlow 标准样式）── */}
      <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mr-2 h-4" />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="hidden sm:block text-muted-foreground">
              NailFlow
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden sm:block" />
            <BreadcrumbItem>
              <BreadcrumbPage>AI 美甲试戴</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>

        {/* 角色徽章 */}
        <div className="ml-auto">
          <Badge
            variant="outline"
            className={cn(
              "text-[10px] font-semibold px-2 py-0.5",
              nailRole === "dev" && "border-blue-400/40 text-blue-400",
              nailRole === "ops" && "border-emerald-400/40 text-emerald-400",
              nailRole === "user" && "border-rose-400/40 text-rose-400",
            )}
          >
            {nailRole === "dev" ? "⚡ Dev" : nailRole === "ops" ? "📊 Ops" : "💅 User"}
          </Badge>
        </div>
      </header>

      {/* ── 主体内容 ── */}
      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-3xl px-4 py-6 space-y-6">

          {/* 标题区 */}
          <div className="space-y-1">
            <h1 className="text-xl font-semibold tracking-tight">
              AI 美甲试戴
            </h1>
            <p className="text-sm text-muted-foreground">
              上传手图与款式图，AI 自动生成精准试戴效果，仅修改甲面区域。
            </p>
          </div>

          {/* ── 上传区 ── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-muted-foreground pl-0.5">
                手图 <span className="text-rose-400">*</span>
              </p>
              <NailImageUploader
                label="上传手图"
                sublabel="正面手背，光线充足"
                icon="🤚"
                accentColor="rose"
                previewUrl={handPreview}
                fileName={handFile?.name}
                disabled={loading}
                onFile={(file, url) => { setHandFile(file); setHandPreview(url); }}
              />
            </div>
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-muted-foreground pl-0.5">
                款式图 <span className="text-violet-400">*</span>
              </p>
              <NailImageUploader
                label="上传款式图"
                sublabel="参考美甲效果图"
                icon="💅"
                accentColor="lavender"
                previewUrl={stylePreview}
                fileName={styleFile?.name}
                disabled={loading}
                onFile={(file, url) => { setStyleFile(file); setStylePreview(url); }}
              />
            </div>
          </div>

          {/* ── 操作按钮 ── */}
          <div className="flex items-center gap-3">
            <Button
              onClick={startTryon}
              disabled={!canStart}
              className={cn(
                "px-6 transition-all duration-200",
                canStart
                  ? "bg-rose-500 hover:bg-rose-600 text-white shadow-sm shadow-rose-500/30"
                  : "",
              )}
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="size-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                  AI 试戴中…
                </span>
              ) : (
                <span className="flex items-center gap-1.5">
                  ✨ 开始 AI 试戴
                </span>
              )}
            </Button>
            {(handFile || styleFile) && !loading && (
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground text-xs"
                onClick={() => {
                  setHandFile(null); setHandPreview("");
                  setStyleFile(null); setStylePreview("");
                  setResult(null); setError(""); setStepStatuses({});
                }}
              >
                清空重来
              </Button>
            )}
          </div>

          {/* ── 工具链进度 ── */}
          {hasSteps && (
            <div className="rounded-xl border border-border/60 bg-muted/20 p-4">
              <p className="text-xs font-semibold text-muted-foreground mb-3 uppercase tracking-wide">
                工具链进度
              </p>
              <NailProgressSteps steps={TRYON_STEPS} statuses={stepStatuses} />
            </div>
          )}

          {/* ── 错误提示 ── */}
          {error && (
            <div className="flex items-start gap-2.5 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3">
              <span className="text-red-400 mt-0.5 shrink-0">⚠</span>
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          {/* ── 试戴结果 ── */}
          {result?.resultPath && (
            <NailResultPanel
              originalUrl={handPreview}
              resultUrl={result.resultPath}
              isMock={result.isMock}
              styleSummaryZh={result.styleSummaryZh}
              fitComment={result.fitComment}
              riskComment={result.riskComment}
              explanation={result.explanation}
              scores={result.scores}
            />
          )}

          {/* ── Agent 思考链（ops/dev 专属）── */}
          {showLog && (
            <div className="rounded-xl border border-border/40 bg-muted/10 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2 border-b border-border/30">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  Agent 思考链
                </span>
                <Badge variant="outline" className="text-[10px] text-muted-foreground">
                  {nailRole === "dev" ? "Dev 可见" : "Ops 可见"}
                </Badge>
              </div>
              <div className="max-h-48 overflow-y-auto px-4 py-3 space-y-1 font-mono">
                {agentLog.map((line, i) => (
                  <p key={i} className="text-[11px] text-muted-foreground leading-relaxed">
                    <span className="text-rose-400/50 select-none mr-2">{i + 1}</span>
                    {line}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* 底部 padding */}
          <div className="h-4" />
        </div>
      </ScrollArea>
    </div>
  );
}
