// frontend/src/core/nail-chat/use-nail-chat.ts
"use client";

import { useCallback, useRef, useState } from "react";
import { useAuth } from "@/core/auth/AuthProvider";
import type { NailPageMode } from "./use-nail-thread";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

export function useNailChat(
  pageMode: NailPageMode,
  ensureThread: () => Promise<string>,
  extraConfig?: Record<string, unknown>,
) {
  const { user } = useAuth();
  const nailRole = (user as any)?.nail_role ?? "user";

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return;
      setError("");

      const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content };
      setMessages((prev) => [...prev, userMsg]);

      const assistantId = crypto.randomUUID();
      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: "assistant", content: "", isStreaming: true },
      ]);
      setIsLoading(true);

      try {
        const threadId = await ensureThread();
        abortRef.current = new AbortController();

        const res = await fetch(`/api/v1/threads/${threadId}/runs/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: abortRef.current.signal,
          body: JSON.stringify({
            input: {
              messages: [{ role: "user", content }],
            },
            config: {
              configurable: {
                nail_role: nailRole,
                nail_page_mode: pageMode,
                ...extraConfig,
              },
            },
          }),
        });

        if (!res.ok) throw new Error(`运行失败: ${res.status}`);

        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let accumulated = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          for (const line of chunk.split("\n")) {
            if (!line.startsWith("data: ")) continue;
            try {
              const data = JSON.parse(line.slice(6));
              const text: string =
                data?.content ??
                data?.text ??
                (typeof data === "string" ? data : "");
              if (text) {
                accumulated += text;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: accumulated }
                      : m,
                  ),
                );
              }
              if (data?.type === "tool_result" && typeof window !== "undefined") {
                window.dispatchEvent(new CustomEvent("nail:refresh-dashboard"));
              }
            } catch {
              // 忽略非 JSON 行
            }
          }
        }

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, isStreaming: false } : m,
          ),
        );
      } catch (e: unknown) {
        if ((e as Error)?.name === "AbortError") return;
        const msg = (e as Error)?.message ?? "请求失败";
        setError(msg);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: `❌ ${msg}`, isStreaming: false }
              : m,
          ),
        );
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, ensureThread, nailRole, pageMode, extraConfig],
  );

  const stopStream = useCallback(() => {
    abortRef.current?.abort();
    setIsLoading(false);
    setMessages((prev) =>
      prev.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m)),
    );
  }, []);

  const clearMessages = useCallback(() => setMessages([]), []);

  return { messages, isLoading, error, sendMessage, stopStream, clearMessages };
}
