"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { NailImageUploader } from "@/components/nail/image-uploader";
import { NailGlassShell } from "@/components/nail/nail-glass-shell";
import {
  NailProgressSteps,
  TRYON_STEPS,
  type StepStatus,
} from "@/components/nail/progress-steps";
import { NailResultPanel } from "@/components/nail/result-panel";
import { NailStyleGallery } from "@/components/nail/style-gallery";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { tryon as api } from "@/core/api/nail";
import { useAuth } from "@/core/auth/AuthProvider";
import type { FileInMessage } from "@/core/messages/utils";
import { uploadFiles } from "@/core/uploads/api";
import { cn } from "@/lib/utils";

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

interface ToolLogEntry {
  toolName: string;
  displayName: string;
  input: string;
  output: string;
  status: "running" | "done" | "error";
  time: string;
}

const FEATURE_STEPS = [
  ["🖐️", "手部检测"],
  ["✂️", "生成 mask"],
  ["🎨", "款式理解"],
  ["🖌️", "构建提示词"],
  ["⚡", "AI 生图"],
  ["🛡️", "质量评分"],
] as const;

const ACTIONS = [
  ["💅", "开始试戴"],
  ["💎", "查看爆款"],
  ["🫶", "猫眼款试戴"],
  ["💬", "咨询推荐"],
] as const;

const NAIL_TRYON_PROMPT =
  "请直接调用 unified_tryon_tool 进行一键 AI 美甲试戴，并尽快返回最终试戴结果图。以下两张附件分别是手图和款式图，请自动识别并完成试戴。";

const PENDING_NAIL_TRYON_STORAGE_KEY = "nail-pending-chat-tryon";

interface PendingChatTryonPayload {
  threadId: string;
  text: string;
  files: FileInMessage[];
  extraContext: {
    nail_role: string;
    nail_page_mode: "tryon";
  };
}

export default function TryonPage() {
  const { user } = useAuth();
  const nailRole = user?.nail_role ?? "user";
  const router = useRouter();
  const searchParams = useSearchParams();

  const [handFile, setHandFile] = useState<File | null>(null);
  const [styleFile, setStyleFile] = useState<File | null>(null);
  const [handPreview, setHandPreview] = useState("");
  const [stylePreview, setStylePreview] = useState("");
  const [galleryStylePath, setGalleryStylePath] = useState("");
  const [warehouseHandPath, setWarehouseHandPath] = useState("");

  useEffect(() => {
    const handParam = searchParams.get("hand");
    const styleParam = searchParams.get("style");
    if (handParam) {
      setHandPreview(handParam);
      const pathMatch = /[?&]path=([^&]+)/.exec(handParam);
      const p = pathMatch?.[1];
      if (p) setWarehouseHandPath(decodeURIComponent(p));
    }
    if (styleParam) {
      setStylePreview(styleParam);
      const pathMatch = /[?&]path=([^&]+)/.exec(styleParam);
      const p = pathMatch?.[1];
      if (p) setGalleryStylePath(decodeURIComponent(p));
    }
  }, [searchParams]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [stepStatuses, setStepStatuses] = useState<Record<string, StepStatus>>(
    {},
  );
  const [agentLog, setAgentLog] = useState<string[]>([]);
  const [toolLogs, setToolLogs] = useState<ToolLogEntry[]>([]);
  const [showToolLogs, setShowToolLogs] = useState(false);
  const [result, setResult] = useState<TryonResult | null>(null);

  const fileFromPreviewUrl = useCallback(
    async (url: string, fallbackName: string) => {
      const response = await window.fetch(url);
      if (!response.ok) {
        throw new Error("加载图片失败，请重试");
      }
      const blob = await response.blob();
      return new File([blob], fallbackName, {
        type: blob.type || "image/jpeg",
      });
    },
    [],
  );

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
      const threadId = await api.createThread();
      const resolvedHandFile =
        handFile ??
        (await fileFromPreviewUrl(handPreview, "hand-image.jpg"));
      const resolvedStyleFile =
        styleFile ??
        (await fileFromPreviewUrl(stylePreview, "style-image.jpg"));

      const uploadResponse = await uploadFiles(threadId, [
        resolvedHandFile,
        resolvedStyleFile,
      ]);

      const pendingPayload: PendingChatTryonPayload = {
        threadId,
        text: NAIL_TRYON_PROMPT,
        files: uploadResponse.files.map((info) => ({
          filename: info.filename,
          size: info.size,
          path: info.virtual_path,
          status: "uploaded" as const,
        })),
        extraContext: {
          nail_role: nailRole,
          nail_page_mode: "tryon",
        },
      };

      window.sessionStorage.setItem(
        PENDING_NAIL_TRYON_STORAGE_KEY,
        JSON.stringify(pendingPayload),
      );
      router.push(`/workspace/chats/${threadId}?mode=nail`);
      return;
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "试戴失败，请重试");
      setStepStatuses((prev) => {
        const next = { ...prev };
        Object.keys(next).forEach((k) => {
          if (next[k] === "running") next[k] = "error";
        });
        return next;
      });
    } finally {
      setLoading(false);
    }
  };

  const hasHandInput = handFile !== null || warehouseHandPath.length > 0;
  const hasStyleInput = styleFile !== null || galleryStylePath.length > 0;
  const canStart = hasHandInput && hasStyleInput && !loading;
  const hasSteps = Object.keys(stepStatuses).length > 0;
  const showLog =
    (nailRole === "ops" || nailRole === "dev") && agentLog.length > 0;

  return (
    <NailGlassShell
      title="AI 美甲试戴"
      subtitle="上传手图和款式图，AI 将自动分析手型、生成甲面遮罩、理解款式风格，最终生成精准试戴效果。"
      actions={
        <div className="mx-auto inline-flex max-w-full items-center gap-2 rounded-full border border-pink-200/70 bg-white/55 px-5 py-3 text-sm font-semibold text-pink-500 shadow-sm">
          <span>📎</span>
          <span>点击下方上传框添加手图和款式图，然后开始试戴</span>
        </div>
      }
    >
      <div className="flex flex-wrap justify-center gap-4">
        {FEATURE_STEPS.map(([icon, label]) => (
          <div
            key={label}
            className="nail-chip rounded-full px-5 py-3 text-sm font-semibold"
          >
            <span className="mr-2 text-lg">{icon}</span>
            {label}
          </div>
        ))}
      </div>

      <section className="nail-glass-card rounded-[2rem] p-4 md:p-6">
        <div className="nail-dashed-zone rounded-[1.7rem] p-4 md:p-5">
          <div className="grid gap-4 lg:grid-cols-[1fr_1fr_1.25fr]">
            <NailImageUploader
              label="上传手图"
              sublabel="正面手背，光线充足"
              icon="🤚"
              accentColor="rose"
              previewUrl={handPreview}
              fileName={handFile?.name}
              disabled={loading}
              onFile={(file, url) => {
                setHandFile(file);
                setHandPreview(url);
              }}
            />
            <NailImageUploader
              label="上传款式图"
              sublabel="选择你喜欢的美甲参考"
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
            <div className="nail-glass-soft rounded-3xl p-4">
              <NailStyleGallery
                selectedUrl={
                  galleryStylePath
                    ? `/api/nail/image?path=${encodeURIComponent(galleryStylePath)}`
                    : null
                }
                disabled={loading}
                onSelect={(style) => {
                  const path = style.url.replace("/api/nail/image?path=", "");
                  setGalleryStylePath(path);
                  setStyleFile(null);
                  setStylePreview(
                    `/api/nail/image?path=${encodeURIComponent(path)}`,
                  );
                }}
              />
            </div>
          </div>
        </div>
      </section>

      <section className="nail-glass-card rounded-[2rem] p-4 md:p-6">
        <div className="nail-dashed-zone flex min-h-48 flex-col justify-between rounded-[1.6rem] p-6">
          <p className="text-base font-medium text-[#9d8a96]">
            今天我能为你做些什么？
          </p>
          <div className="flex items-end justify-between gap-4">
            <span className="text-2xl text-[#8d8290]">📎</span>
            <Button
              onClick={startTryon}
              disabled={!canStart}
              className="nail-primary-button size-12 rounded-full p-0 text-xl"
              aria-label="开始 AI 试戴"
            >
              {loading ? (
                <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              ) : (
                "↑"
              )}
            </Button>
          </div>
        </div>
      </section>

      <div className="grid gap-5 md:grid-cols-4">
        {ACTIONS.map(([icon, label], index) => (
          <Button
            key={label}
            onClick={index === 0 ? startTryon : undefined}
            disabled={index === 0 && !canStart}
            variant="outline"
            className="nail-outline-button h-16 rounded-3xl text-base font-semibold"
          >
            <span className="mr-3 text-2xl">{icon}</span>
            {label}
          </Button>
        ))}
      </div>

      {hasSteps && (
        <section className="nail-glass-card rounded-3xl p-5">
          <p className="mb-3 text-xs font-bold tracking-wide text-pink-500 uppercase">
            工具链进度
          </p>
          <NailProgressSteps steps={TRYON_STEPS} statuses={stepStatuses} />
        </section>
      )}

      {error && (
        <div className="rounded-3xl border border-rose-200 bg-white/60 px-5 py-4 text-sm font-medium text-rose-500 shadow-sm">
          ⚠ {error}
        </div>
      )}

      {toolLogs.length > 0 && (
        <section className="nail-glass-card overflow-hidden rounded-3xl">
          <button
            className="flex w-full items-center justify-between border-b border-pink-200/50 px-5 py-3 text-left"
            onClick={() => setShowToolLogs(!showToolLogs)}
          >
            <span className="text-xs font-bold tracking-wide text-pink-500 uppercase">
              工具执行日志 ({toolLogs.length})
            </span>
            <span className="text-xs text-pink-400">
              {showToolLogs ? "收起 ▲" : "展开 ▼"}
            </span>
          </button>
          {showToolLogs && (
            <div className="max-h-80 divide-y divide-pink-100/80 overflow-y-auto">
              {toolLogs.map((entry, i) => (
                <div
                  key={`${entry.toolName}-${i}`}
                  className="space-y-2 px-4 py-3"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-[#5b1738]">
                      {entry.displayName}
                    </span>
                    <Badge
                      variant="outline"
                      className={cn(
                        "rounded-full px-2 py-0 text-[10px]",
                        entry.status === "running" &&
                          "border-pink-200 text-pink-500",
                        entry.status === "done" &&
                          "border-emerald-200 text-emerald-500",
                        entry.status === "error" &&
                          "border-red-200 text-red-500",
                      )}
                    >
                      {entry.status === "running"
                        ? "执行中"
                        : entry.status === "done"
                          ? "完成"
                          : "失败"}
                    </Badge>
                    <span className="ml-auto text-[10px] text-pink-300">
                      {entry.time}
                    </span>
                  </div>
                  {entry.input && (
                    <pre className="max-h-24 overflow-auto rounded-2xl bg-white/55 p-3 text-[10px] text-[#755667]">
                      {entry.input}
                    </pre>
                  )}
                  {entry.output && (
                    <pre className="max-h-24 overflow-auto rounded-2xl bg-white/55 p-3 text-[10px] text-[#755667]">
                      {entry.output}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

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

      {showLog && (
        <section className="nail-glass-card overflow-hidden rounded-3xl">
          <div className="flex items-center justify-between border-b border-pink-200/50 px-5 py-3">
            <span className="text-xs font-bold tracking-wide text-pink-500 uppercase">
              Agent 思考链
            </span>
            <Badge
              variant="outline"
              className="rounded-full border-pink-200 text-pink-500"
            >
              {nailRole === "dev" ? "Dev 可见" : "Ops 可见"}
            </Badge>
          </div>
          <div className="max-h-48 space-y-1 overflow-y-auto px-5 py-4 font-mono">
            {agentLog.map((line, i) => (
              <p
                key={`${line}-${i}`}
                className="text-[11px] leading-relaxed text-[#8f7082]"
              >
                <span className="mr-2 text-pink-400 select-none">{i + 1}</span>
                {line}
              </p>
            ))}
          </div>
        </section>
      )}
    </NailGlassShell>
  );
}
