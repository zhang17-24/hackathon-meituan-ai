"use client";

import { useState, useCallback, useEffect } from "react";
import { useSearchParams } from "next/navigation";
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
import { NailStyleGallery } from "@/components/nail/style-gallery";
import { NailProgressSteps, TRYON_STEPS, type StepStatus } from "@/components/nail/progress-steps";
import { NailResultPanel } from "@/components/nail/result-panel";
import { useAuth } from "@/core/auth/AuthProvider";
import { tryon as api } from "@/core/api/nail";
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
  const searchParams = useSearchParams();

  /* 图片状态 */
  const [handFile,    setHandFile]    = useState<File | null>(null);
  const [styleFile,   setStyleFile]   = useState<File | null>(null);
  const [handPreview, setHandPreview] = useState<string>("");
  const [stylePreview,setStylePreview]= useState<string>("");
  const [galleryStylePath, setGalleryStylePath] = useState<string>("");
  const [warehouseHandPath, setWarehouseHandPath] = useState<string>("");  // 从仓库预选的手图服务端路径

  /* 从仓库跳转过来时，预填手图/款式 URL */
  useEffect(() => {
    const handParam = searchParams.get("hand");
    const styleParam = searchParams.get("style");
    if (handParam) {
      setHandPreview(handParam);
      const pathMatch = handParam.match(/[?&]path=([^&]+)/);
      const p = pathMatch?.[1];
      if (p) setWarehouseHandPath(decodeURIComponent(p));
    }
    if (styleParam) {
      setStylePreview(styleParam);
      const pathMatch = styleParam.match(/[?&]path=([^&]+)/);
      const p = pathMatch?.[1];
      if (p) setGalleryStylePath(decodeURIComponent(p));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* 运行状态 */
  const [loading, setLoading]   = useState(false);
  const [error,   setError]     = useState<string>("");
  const [stepStatuses, setStepStatuses] = useState<Record<string, StepStatus>>({});
  const [agentLog, setAgentLog] = useState<string[]>([]);

  /* 工具调试日志 */
  interface ToolLogEntry {
    toolName: string;
    displayName: string;
    input: string;
    output: string;
    status: "running" | "done" | "error";
    time: string;
  }
  const [toolLogs, setToolLogs] = useState<ToolLogEntry[]>([]);
  const [showToolLogs, setShowToolLogs] = useState(false);

  const TOOL_DISPLAY: Record<string, string> = {
    hand_detect_tool: "🔍 手部检测",
    nail_mask_tool: "✂️ 甲面遮罩",
    style_understanding_tool: "🎨 款式理解",
    prompt_builder_tool: "✍️ 提示词构建",
    image_generation_tool: "⚡ AI 生图",
    quality_check_tool: "✅ 质量评分",
  };
  const [result, setResult] = useState<TryonResult | null>(null);

  /* 设置步骤状态的工具函数 */
  const setStep = useCallback((stepId: string, status: StepStatus) => {
    setStepStatuses(prev => ({ ...prev, [stepId]: status }));
  }, []);

  /* ── 开始试戴 ── */
  const startTryon = async () => {
    if (!handFile && !warehouseHandPath) return;
    if (!styleFile && !galleryStylePath) return;
    setLoading(true);
    setError("");
    setResult(null);
    setAgentLog([]);
    setStepStatuses({});
    setToolLogs([]);
    setShowToolLogs(true);

    try {
      /* 1. 创建 thread */
      const threadId = await api.createThread();

      /* 2. 上传/获取手图和款式路径 */
      let handRef: string;
      if (warehouseHandPath) {
        handRef = warehouseHandPath;
      } else {
        handRef = await api.uploadTryonFile(threadId, handFile!);
      }
      let styleRef: string;
      if (galleryStylePath) {
        styleRef = galleryStylePath;
      } else {
        styleRef = await api.uploadTryonFile(threadId, styleFile!);
      }

      /* 3. 发起 SSE 流式运行 */
      const stream = await api.startAgentRun(threadId, {
        input: {
          messages: [{
            role: "user",
            content: `请帮我进行 AI 美甲试戴。\n手图：${handRef}\n款式图：${styleRef}`,
          }],
        },
        config: { configurable: { nail_role: nailRole } },
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

            /* 工具调用开始 → 步骤 running + 记录日志 */
            if (data.type === "tool_call_start" || data.type === "tool_call") {
              const toolName = data.tool_name ?? data.name ?? "";
              const stepId = TOOL_TO_STEP[toolName];
              if (stepId) setStep(stepId, "running");
              const displayName = TOOL_DISPLAY[toolName] ?? toolName;
              const input = typeof data.input === "string" ? data.input : JSON.stringify(data.input ?? data.args ?? {}, null, 2);
              setToolLogs(prev => [...prev, {
                toolName, displayName, input: input?.substring(0, 500) ?? "",
                output: "", status: "running",
                time: new Date().toLocaleTimeString(),
              }]);
            }

            /* 工具结果 → 步骤 done + 更新日志 */
            if (data.type === "tool_result") {
              const toolName = data.tool_name ?? "";
              const stepId   = TOOL_TO_STEP[toolName];
              if (stepId) setStep(stepId, "done");
              const output = typeof data.content === "string" ? data.content : JSON.stringify(data.content ?? "", null, 2);
              setToolLogs(prev => prev.map(e =>
                e.toolName === toolName && e.status === "running"
                  ? { ...e, output: output?.substring(0, 800) ?? "", status: data.error ? "error" : "done" }
                  : e
              ));

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

  const canStart = (handFile || warehouseHandPath) && (styleFile || galleryStylePath) && !loading;
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

          {/* ── 上传区：手图 ── */}
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

          {/* ── 款式选择区：画廊 + 手动上传 ── */}
          <div className="rounded-xl border border-border/60 bg-muted/10 p-4 space-y-3">
            <NailStyleGallery
              selectedUrl={galleryStylePath ? `/api/nail/image?path=${encodeURIComponent(galleryStylePath)}` : null}
              disabled={loading}
              onSelect={(style) => {
                setGalleryStylePath(style.url.replace("/api/nail/image?path=", ""));
                setStyleFile(null);
                setStylePreview(`/api/nail/image?path=${encodeURIComponent(style.url.replace("/api/nail/image?path=", ""))}`);
              }}
            />

            {/* 手动上传款式图 */}
            <NailImageUploader
              label="上传自定义款式图"
              sublabel="或上传你自己的美甲参考图"
              icon="💅"
              accentColor="lavender"
              previewUrl={galleryStylePath ? "" : stylePreview}
              fileName={galleryStylePath ? "" : styleFile?.name}
              disabled={loading}
              onFile={(file, url) => {
                setStyleFile(file);
                setStylePreview(url);
                setGalleryStylePath("");
              }}
            />
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
            {(handFile || styleFile || galleryStylePath || warehouseHandPath) && !loading && (
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground text-xs"
                onClick={() => {
                  setHandFile(null); setHandPreview("");
                  setStyleFile(null); setStylePreview("");
                  setGalleryStylePath("");
                  setWarehouseHandPath("");
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

          {/* ── 工具执行日志 ── */}
          {toolLogs.length > 0 && (
            <div className="rounded-xl border border-border/60 bg-muted/10 overflow-hidden">
              <button
                className="flex w-full items-center justify-between px-4 py-2 border-b border-border/30 hover:bg-muted/20 transition-colors"
                onClick={() => setShowToolLogs(!showToolLogs)}
              >
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  🔧 工具执行日志 ({toolLogs.length})
                </span>
                <span className="text-[10px] text-muted-foreground">{showToolLogs ? "收起 ▲" : "展开 ▼"}</span>
              </button>
              {showToolLogs && (
                <div className="max-h-80 overflow-y-auto divide-y divide-border/20">
                  {toolLogs.map((entry, i) => (
                    <div key={i} className="px-3 py-2 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium">{entry.displayName}</span>
                        <span className={cn(
                          "text-[10px] rounded-full px-1.5 py-0.5",
                          entry.status === "running" && "bg-amber-500/10 text-amber-500",
                          entry.status === "done" && "bg-emerald-500/10 text-emerald-500",
                          entry.status === "error" && "bg-red-500/10 text-red-500",
                        )}>
                          {entry.status === "running" ? "执行中" : entry.status === "done" ? "完成" : "失败"}
                        </span>
                        <span className="text-[10px] text-muted-foreground/50 ml-auto">{entry.time}</span>
                      </div>
                      {entry.input && (
                        <details className="text-[11px]">
                          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">输入</summary>
                          <pre className="mt-1 whitespace-pre-wrap break-all bg-muted/30 rounded p-1.5 text-[10px] max-h-24 overflow-y-auto">{entry.input}</pre>
                        </details>
                      )}
                      {entry.output && (
                        <details className="text-[11px]" open={entry.status === "error"}>
                          <summary className={cn("cursor-pointer hover:text-foreground", entry.status === "error" ? "text-red-400" : "text-muted-foreground")}>
                            {entry.status === "error" ? "❌ 错误输出" : "输出"}
                          </summary>
                          <pre className="mt-1 whitespace-pre-wrap break-all bg-muted/30 rounded p-1.5 text-[10px] max-h-24 overflow-y-auto">{entry.output}</pre>
                        </details>
                      )}
                    </div>
                  ))}
                </div>
              )}
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
