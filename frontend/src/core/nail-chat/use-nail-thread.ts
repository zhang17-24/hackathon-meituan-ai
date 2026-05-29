// frontend/src/core/nail-chat/use-nail-thread.ts
"use client";

import { useCallback, useState } from "react";
import { useAuth } from "@/core/auth/AuthProvider";

export type NailPageMode = "tryon" | "ops" | "eval";

export function useNailThread(pageMode: NailPageMode) {
  const { user } = useAuth();
  const userId = (user as any)?.id ?? "anon";
  const storageKey = `nail_thread_${pageMode}_${userId}`;

  const [threadId, setThreadId] = useState<string>(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem(storageKey) ?? "";
  });

  const ensureThread = useCallback(async (): Promise<string> => {
    if (threadId) return threadId;
    const res = await fetch("/api/v1/threads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (!res.ok) throw new Error(`创建 thread 失败: ${res.status}`);
    const data = await res.json();
    const id: string = data.thread_id ?? data.id ?? "";
    if (id) {
      localStorage.setItem(storageKey, id);
      setThreadId(id);
    }
    return id;
  }, [threadId, storageKey]);

  const resetThread = useCallback(() => {
    localStorage.removeItem(storageKey);
    setThreadId("");
  }, [storageKey]);

  return { threadId, ensureThread, resetThread };
}
