"use client";

import { useCallback, useRef, useState } from "react";

export interface ToolCallEntry {
  id: string;
  toolName: string;
  displayName: string;
  input: string;
  output: string;
  status: "running" | "done" | "error";
  time: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  reasoning?: string;
  toolCallEntries?: ToolCallEntry[];
  isStreaming?: boolean;
}

interface UseNailStreamOptions {
  nailRole: string;
  extraConfig?: Record<string, unknown>;
}

export function useNailStream(options: UseNailStreamOptions) {
  const { nailRole, extraConfig } = options;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string>("");
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (content: string, ensureThreadOrId: (() => Promise<string>) | string) => {
      if (!content.trim() || isStreaming) return;
      setError("");

      const userMsgId = crypto.randomUUID();
      const assistantId = crypto.randomUUID();

      setMessages((prev) => [
        ...prev,
        { id: userMsgId, role: "user", content },
        {
          id: assistantId,
          role: "assistant",
          content: "",
          reasoning: "",
          toolCallEntries: [],
          isStreaming: true,
        },
      ]);
      setIsStreaming(true);

      try {
        const threadId = typeof ensureThreadOrId === "function"
          ? await ensureThreadOrId()
          : ensureThreadOrId;

        abortRef.current = new AbortController();

        const res = await fetch(`/api/v1/threads/${threadId}/runs/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: abortRef.current.signal,
          body: JSON.stringify({
            input: { messages: [{ role: "user", content }] },
            config: {
              configurable: {
                nail_role: nailRole,
                ...extraConfig,
              },
            },
          }),
        });

        if (!res.ok) throw new Error(`运行失败: ${res.status}`);

        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let accumulatedContent = "";
        let accumulatedReasoning = "";
        const toolCallMap = new Map<string, ToolCallEntry>();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          for (const line of chunk.split("\n")) {
            if (!line.startsWith("data: ")) continue;
            try {
              const raw = JSON.parse(line.slice(6));

              const sseEvent = raw?.event;
              const payload = raw?.data;
              const isMessagesEvent = sseEvent === "messages";

              if (isMessagesEvent && Array.isArray(payload)) {
                const [msgType, msgPayload] = payload;

                if (msgType === "ai" || msgType === "AIMessageChunk") {
                  const text =
                    typeof msgPayload?.content === "string"
                      ? msgPayload.content
                      : "";
                  if (text) {
                    accumulatedContent += text;
                  }

                  const reasoning =
                    msgPayload?.additional_kwargs?.reasoning_content;
                  if (typeof reasoning === "string" && reasoning) {
                    accumulatedReasoning += reasoning;
                  }

                  const toolCalls = msgPayload?.tool_calls;
                  if (Array.isArray(toolCalls)) {
                    for (const tc of toolCalls) {
                      const id = tc.id || crypto.randomUUID();
                      if (!toolCallMap.has(id)) {
                        toolCallMap.set(id, {
                          id,
                          toolName: tc.name || "",
                          displayName: tc.name || "",
                          input:
                            typeof tc.args === "string"
                              ? tc.args
                              : JSON.stringify(tc.args ?? {}, null, 2),
                          output: "",
                          status: "running" as const,
                          time: new Date().toLocaleTimeString(),
                        });
                      }
                    }
                  }

                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === assistantId
                        ? {
                            ...m,
                            content: accumulatedContent,
                            reasoning: accumulatedReasoning || undefined,
                            toolCallEntries: Array.from(toolCallMap.values()),
                          }
                        : m
                    )
                  );
                }

                if (msgType === "tool" || msgType === "ToolMessage") {
                  const toolCallId = msgPayload?.tool_call_id;
                  const output =
                    typeof msgPayload?.content === "string"
                      ? msgPayload.content
                      : JSON.stringify(msgPayload?.content ?? "");

                  if (toolCallId) {
                    const existing = toolCallMap.get(toolCallId);
                    if (existing) {
                      existing.output = output;
                      existing.status = "done";
                    }
                  }

                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === assistantId
                        ? {
                            ...m,
                            toolCallEntries: Array.from(toolCallMap.values()),
                          }
                        : m
                    )
                  );
                }
              }
            } catch {
              // ignore non-JSON lines
            }
          }
        }

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, isStreaming: false } : m
          )
        );
      } catch (e: unknown) {
        if ((e as Error)?.name === "AbortError") return;
        const msg = (e as Error)?.message ?? "请求失败";
        setError(msg);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: m.content || `❌ ${msg}`, isStreaming: false }
              : m
          )
        );
      } finally {
        setIsStreaming(false);
      }
    },
    [isStreaming, nailRole, extraConfig]
  );

  const stopStream = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
    setMessages((prev) =>
      prev.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m))
    );
  }, []);

  const clearMessages = useCallback(() => setMessages([]), []);

  return { messages, isStreaming, error, sendMessage, stopStream, clearMessages };
}
