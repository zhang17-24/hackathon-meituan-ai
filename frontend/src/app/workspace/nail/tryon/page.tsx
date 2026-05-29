// frontend/src/app/workspace/nail/tryon/page.tsx
"use client";

import { useState } from "react";
import { useAuth } from "@/core/auth/AuthProvider";
import type { NailRole } from "@/lib/nail-auth";

export default function TryonPage() {
  const { user } = useAuth();
  const nailRole = (user as any)?.nail_role as NailRole ?? "user";

  const [handFile, setHandFile] = useState<File | null>(null);
  const [styleFile, setStyleFile] = useState<File | null>(null);
  const [handPreview, setHandPreview] = useState<string>("");
  const [stylePreview, setStylePreview] = useState<string>("");
  const [result, setResult] = useState<{ path: string; mock: boolean } | null>(null);
  const [loading, setLoading] = useState(false);
  const [agentLog, setAgentLog] = useState<string[]>([]);
  const [error, setError] = useState<string>("");

  const handleFile = (file: File, type: "hand" | "style") => {
    const url = URL.createObjectURL(file);
    if (type === "hand") { setHandFile(file); setHandPreview(url); }
    else { setStyleFile(file); setStylePreview(url); }
  };

  const uploadFile = async (file: File): Promise<string> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/v1/uploads", { method: "POST", body: form });
    if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
    const data = await res.json();
    return data.url ?? data.file_url ?? data.path ?? "";
  };

  const startTryon = async () => {
    if (!handFile || !styleFile) return;
    setLoading(true);
    setAgentLog([]);
    setResult(null);
    setError("");

    try {
      const [handUrl, styleUrl] = await Promise.all([uploadFile(handFile), uploadFile(styleFile)]);

      // 创建 thread
      const threadRes = await fetch("/api/v1/threads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      const thread = await threadRes.json();
      const threadId = thread.thread_id ?? thread.id;

      // SSE 流式运行
      const runRes = await fetch(`/api/v1/threads/${threadId}/runs/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input: { messages: [{ role: "user", content: `请帮我试戴美甲款式。手图：${handUrl}，款式图：${styleUrl}` }] },
          config: { configurable: { nail_role: nailRole } },
        }),
      });

      if (!runRes.ok) throw new Error(`Run failed: ${runRes.statusText}`);

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
            // 捕获 agent 思考内容
            const content = data.content ?? data.text ?? data.delta ?? "";
            if (content && typeof content === "string") {
              setAgentLog((prev) => [...prev.slice(-20), content.substring(0, 200)]);
            }
            // 捕获生成结果
            if (data.type === "tool_result" && data.tool_name === "image_generation") {
              const r = JSON.parse(data.content ?? "{}");
              if (r.result_path) {
                setResult({ path: `/api/nail/image?path=${encodeURIComponent(r.result_path)}`, mock: r.is_mock ?? false });
              }
            }
          } catch { /* ignore parse errors */ }
        }
      }
    } catch (e: any) {
      setError(e.message ?? "试戴失败，请重试");
      setAgentLog((prev) => [...prev, `错误: ${e.message}`]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="mx-auto max-w-4xl">
        <h1 className="mb-6 text-2xl font-bold text-pink-600">💅 AI 美甲试戴</h1>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {/* 上传区 */}
          <div className="space-y-4">
            <h2 className="font-semibold text-sm text-muted-foreground">第一步：上传图片</h2>

            {/* 手图上传 */}
            <label className="block cursor-pointer rounded-lg border-2 border-dashed border-pink-200 p-4 text-center hover:border-pink-400 transition-colors">
              {handPreview ? (
                <img src={handPreview} alt="手图" className="mx-auto max-h-36 rounded object-contain" />
              ) : (
                <div className="py-6 text-muted-foreground text-sm">
                  <p className="text-2xl mb-2">🤚</p>
                  <p>点击上传手图</p>
                  <p className="text-xs mt-1">正面手背，光线充足</p>
                </div>
              )}
              <input type="file" className="hidden" accept="image/*" onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0], "hand")} />
            </label>

            {/* 款式图上传 */}
            <label className="block cursor-pointer rounded-lg border-2 border-dashed border-pink-200 p-4 text-center hover:border-pink-400 transition-colors">
              {stylePreview ? (
                <img src={stylePreview} alt="款式" className="mx-auto max-h-36 rounded object-contain" />
              ) : (
                <div className="py-6 text-muted-foreground text-sm">
                  <p className="text-2xl mb-2">💅</p>
                  <p>点击上传款式图</p>
                </div>
              )}
              <input type="file" className="hidden" accept="image/*" onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0], "style")} />
            </label>

            <button
              onClick={startTryon}
              disabled={loading || !handFile || !styleFile}
              className="w-full rounded-lg bg-pink-500 py-3 text-white font-medium disabled:opacity-40 hover:bg-pink-600 transition-colors"
            >
              {loading ? "🔮 AI 试戴中..." : "✨ 开始 AI 试戴"}
            </button>

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">{error}</div>
            )}
          </div>

          {/* 结果区 */}
          <div className="space-y-4">
            <h2 className="font-semibold text-sm text-muted-foreground">试戴结果</h2>
            <div className="min-h-48 rounded-lg border-2 border-dashed border-gray-200 bg-gray-50 flex items-center justify-center">
              {result ? (
                <div className="w-full p-2">
                  <img src={result.path} alt="试戴结果" className="mx-auto max-h-72 rounded-lg object-contain shadow-sm" />
                  {result.mock && (
                    <p className="mt-2 text-center text-xs text-amber-600 bg-amber-50 py-1 rounded">
                      ⚠️ Mock 模式（未配置生图 API）
                    </p>
                  )}
                </div>
              ) : loading ? (
                <div className="text-center text-muted-foreground">
                  <p className="text-3xl mb-2 animate-pulse">🎨</p>
                  <p className="text-sm">AI 正在工作中...</p>
                </div>
              ) : (
                <div className="text-center text-muted-foreground text-sm">
                  <p className="text-3xl mb-2">🖼️</p>
                  <p>上传图片后点击试戴</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Agent 思考链（ops/dev 可见） */}
        {(nailRole === "ops" || nailRole === "dev") && agentLog.length > 0 && (
          <div className="mt-6 rounded-lg border bg-gray-950 p-4">
            <p className="mb-2 text-xs font-medium text-gray-400">Agent 思考链</p>
            <div className="max-h-40 overflow-y-auto space-y-1">
              {agentLog.map((log, i) => (
                <p key={i} className="text-xs text-gray-300 font-mono">{log}</p>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
