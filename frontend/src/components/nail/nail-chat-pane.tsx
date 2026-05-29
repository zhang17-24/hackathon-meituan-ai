// frontend/src/components/nail/nail-chat-pane.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { useNailChat, type ChatMessage, type NailPageMode } from "@/core/nail-chat";
import { useQuery } from "@tanstack/react-query";

interface PageModeConfig {
  title: string;
  subtitle: string;
  suggestions: string[];
}

async function fetchPageModeConfig(mode: string): Promise<PageModeConfig> {
  const res = await fetch(`/api/nail/config/page-mode/${mode}`);
  if (!res.ok) throw new Error("Failed to load page mode config");
  return res.json();
}

interface NailChatPaneProps {
  pageMode: NailPageMode;
  ensureThread: () => Promise<string>;
  resetThread: () => void;
  extraConfig?: Record<string, unknown>;
  className?: string;
}

export function NailChatPane({
  pageMode,
  ensureThread,
  resetThread,
  extraConfig,
  className,
}: NailChatPaneProps) {
  const { messages, isLoading, error, sendMessage, stopStream, clearMessages } =
    useNailChat(pageMode, ensureThread, extraConfig);

  const { data: modeConfig } = useQuery({
    queryKey: ["nail-page-mode", pageMode],
    queryFn: () => fetchPageModeConfig(pageMode),
    staleTime: Infinity,
  });

  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    sendMessage(input.trim());
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={cn("flex h-full flex-col bg-background", className)}>
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-2">
        <div>
          <p className="text-sm font-semibold">{modeConfig?.title ?? "AI 分析"}</p>
          <p className="text-xs text-muted-foreground">{modeConfig?.subtitle ?? ""}</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs"
          onClick={() => { clearMessages(); resetThread(); }}
        >
          重置
        </Button>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 px-4 py-3">
        <div ref={scrollRef}>
          {messages.length === 0 && modeConfig?.suggestions && (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground mb-3">试试这些问题：</p>
              {modeConfig.suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => sendMessage(s)}
                  className="w-full rounded-lg border px-3 py-2 text-left text-xs hover:bg-accent transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          <div className="space-y-3 mt-2">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
          </div>
        </div>
      </ScrollArea>

      {error && (
        <div className="mx-4 mb-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600 dark:border-red-900 dark:bg-red-950 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Input */}
      <div className="border-t p-3">
        <div className="flex gap-2">
          <textarea
            className="flex-1 resize-none rounded-lg border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            rows={2}
            placeholder="输入消息… (Enter 发送)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />
          <div className="flex flex-col gap-1">
            {isLoading ? (
              <Button size="sm" variant="outline" onClick={stopStream} className="h-full text-xs">
                停止
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={handleSend}
                className="h-full text-xs"
                disabled={!input.trim()}
              >
                发送
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-3 py-2 text-sm",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground",
        )}
      >
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
        {message.isStreaming && (
          <span className="ml-1 inline-block h-3 w-1 animate-pulse bg-current opacity-70" />
        )}
      </div>
    </div>
  );
}
