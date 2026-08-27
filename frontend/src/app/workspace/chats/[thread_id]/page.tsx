"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { type PromptInputMessage } from "@/components/ai-elements/prompt-input";
import { NailModelPicker } from "@/components/nail/nail-model-picker";
import { NailTryonProgressBar } from "@/components/nail/nail-tryon-progress";
import { ArtifactTrigger } from "@/components/workspace/artifacts";
import {
  ChatBox,
  useSpecificChatMode,
  useThreadChat,
} from "@/components/workspace/chats";
import { ExportTrigger } from "@/components/workspace/export-trigger";
import { InputBox } from "@/components/workspace/input-box";
import {
  MessageList,
  MESSAGE_LIST_DEFAULT_PADDING_BOTTOM,
} from "@/components/workspace/messages";
import { ThreadContext } from "@/components/workspace/messages/context";
import { ThreadTitle } from "@/components/workspace/thread-title";
import { TodoList } from "@/components/workspace/todo-list";
import { TokenUsageIndicator } from "@/components/workspace/token-usage-indicator";
import { Welcome } from "@/components/workspace/welcome";
import { useI18n } from "@/core/i18n/hooks";
import { useModels } from "@/core/models/hooks";
import { useNotification } from "@/core/notification/hooks";
import { useLocalSettings, useThreadSettings } from "@/core/settings";
import {
  type NailTryonProgress,
  useThreadStream,
  useThreadTokenUsage,
} from "@/core/threads/hooks";
import { threadTokenUsageToTokenUsage } from "@/core/threads/token-usage";
import { textOfMessage } from "@/core/threads/utils";
import { env } from "@/env";
import { cn } from "@/lib/utils";

const PENDING_NAIL_TRYON_STORAGE_KEY = "nail-pending-chat-tryon";

type PendingChatTryonPayload = {
  threadId: string;
  text: string;
  files: {
    filename: string;
    size: number;
    path?: string;
    status?: "uploading" | "uploaded";
  }[];
  extraContext?: Record<string, unknown>;
};

export default function ChatPage() {
  const { t } = useI18n();
  const { threadId, setThreadId, isNewThread, setIsNewThread, isMock } =
    useThreadChat();
  // `isNewThread` tracks whether the backend has the thread yet — gates the
  // SDK's history fetch (see issue #2746).  `isWelcomeMode` is the visual
  // welcome layout (centered input, hero, quick actions); we flip it to false
  // the moment the user submits so the UI animates immediately, even though
  // `isNewThread` stays true until the backend actually creates the thread.
  const [isWelcomeMode, setIsWelcomeMode] = useState(isNewThread);
  const [settings, setSettings] = useThreadSettings(threadId);
  const [localSettings, setLocalSettings] = useLocalSettings();
  const { tokenUsageEnabled } = useModels();
  const threadTokenUsage = useThreadTokenUsage(
    isNewThread || isMock ? undefined : threadId,
    { enabled: tokenUsageEnabled && !isMock },
  );
  const backendTokenUsage = threadTokenUsageToTokenUsage(threadTokenUsage.data);
  const mountedRef = useRef(false);
  const autoSendPendingTryonRef = useRef<string | null>(null);
  useSpecificChatMode();

  useEffect(() => {
    mountedRef.current = true;
  }, []);

  // Keep welcome layout in sync when navigating between threads (sidebar
  // clicks, "new chat" button).  Submitting in /chats/new flips the layout
  // via onSend below — `isNewThread` stays true until onStart, so this effect
  // is harmless during the submit transition.
  useEffect(() => {
    setIsWelcomeMode(isNewThread);
  }, [isNewThread]);

  const { showNotification } = useNotification();

  const [tryonProgress, setTryonProgress] = useState<NailTryonProgress | null>(
    null,
  );

  const {
    thread,
    pendingUsageMessages,
    sendMessage,
    isUploading,
    isHistoryLoading,
    hasMoreHistory,
    loadMoreHistory,
  } = useThreadStream({
    threadId: isNewThread ? undefined : threadId,
    context: settings.context,
    isMock,
    onTryonProgress: setTryonProgress,
    // onSend only animates the UI; do NOT flip `isNewThread` here — the
    // LangGraph SDK eagerly fetches /history the moment it receives a
    // thread id and assumes the thread exists on the backend (issue #2746).
    onSend: () => {
      setIsWelcomeMode(false);
    },
    onStart: (createdThreadId) => {
      setThreadId(createdThreadId);
      setIsNewThread(false);
      // ! Important: Never use next.js router for navigation in this case, otherwise it will cause the thread to re-mount and lose all states. Use native history API instead.
      history.replaceState(null, "", `/workspace/chats/${createdThreadId}`);
    },
    onFinish: (state) => {
      setTryonProgress(null);
      if (document.hidden || !document.hasFocus()) {
        let body = "Conversation finished";
        const lastMessage = state.messages.at(-1);
        if (lastMessage) {
          const textContent = textOfMessage(lastMessage);
          if (textContent) {
            body =
              textContent.length > 200
                ? textContent.substring(0, 200) + "..."
                : textContent;
          }
        }
        showNotification(state.title, { body });
      }
    },
  });

  const handleSubmit = useCallback(
    (message: PromptInputMessage) => {
      const sendPromise = sendMessage(threadId, message);
      if (message.files.length > 0) {
        return sendPromise;
      }
      void sendPromise;
    },
    [sendMessage, threadId],
  );
  const handleStop = useCallback(async () => {
    await thread.stop();
  }, [thread]);

  useEffect(() => {
    if (typeof window === "undefined" || !threadId) {
      return;
    }
    if (autoSendPendingTryonRef.current === threadId) {
      return;
    }

    const rawPayload = window.sessionStorage.getItem(
      PENDING_NAIL_TRYON_STORAGE_KEY,
    );
    if (!rawPayload) {
      return;
    }

    let payload: PendingChatTryonPayload | null = null;
    try {
      payload = JSON.parse(rawPayload) as PendingChatTryonPayload;
    } catch {
      window.sessionStorage.removeItem(PENDING_NAIL_TRYON_STORAGE_KEY);
      return;
    }

    if (payload.threadId !== threadId) {
      return;
    }

    autoSendPendingTryonRef.current = threadId;
    window.sessionStorage.removeItem(PENDING_NAIL_TRYON_STORAGE_KEY);
    setIsWelcomeMode(false);

    void sendMessage(
      threadId,
      {
        text: payload.text,
        files: [],
      },
      payload.extraContext,
      {
        additionalKwargs: payload.files.length > 0 ? { files: payload.files } : {},
      },
    ).catch(() => {
      autoSendPendingTryonRef.current = null;
      window.sessionStorage.setItem(
        PENDING_NAIL_TRYON_STORAGE_KEY,
        rawPayload,
      );
    });
  }, [sendMessage, threadId]);

  const tokenUsageInlineMode = tokenUsageEnabled
    ? localSettings.tokenUsage.inlineMode
    : "off";
  const hasTodos = (thread.values.todos?.length ?? 0) > 0;

  return (
    <ThreadContext.Provider value={{ thread, isMock }}>
      <ChatBox threadId={threadId}>
        <div
          className={cn(
            "nail-shell relative flex size-full min-h-0 justify-between overflow-hidden",
          )}
        >
          <div className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="nail-sparkle nail-sparkle-a">✦</div>
            <div className="nail-sparkle nail-sparkle-b">♡</div>
            <div className="nail-sparkle nail-sparkle-c">✧</div>
            <div className="absolute right-[-6rem] bottom-[-7rem] h-72 w-[42rem] rotate-[-10deg] rounded-[100%] border border-pink-200/40 bg-pink-200/30 blur-2xl" />
            <div className="absolute right-[-2rem] bottom-[-4rem] h-44 w-[34rem] rotate-[-8deg] rounded-[100%] border border-white/70 bg-white/35 blur-xl" />
          </div>
          <header
            className={cn(
              "absolute top-0 right-0 left-0 z-30 flex h-12 shrink-0 items-center px-4",
              isWelcomeMode
                ? "bg-background/0 pt-6 backdrop-blur-none"
                : "nail-topbar mx-4 mt-4 h-14 rounded-3xl px-4",
            )}
          >
            <div
              className={cn(
                "flex w-full items-center text-sm font-semibold text-[#5b1738]",
                isWelcomeMode && "opacity-0",
              )}
            >
              <ThreadTitle threadId={threadId} thread={thread} />
            </div>
            <div className="flex items-center gap-2">
              {!isWelcomeMode && (
                <NailModelPicker
                  className="nail-outline-button h-9 rounded-full border-pink-200/70 px-3 text-pink-500"
                  value={settings.context.model_name}
                  onChange={(model) =>
                    setSettings("context", {
                      ...settings.context,
                      model_name: model,
                    })
                  }
                />
              )}
              <TokenUsageIndicator
                threadId={isNewThread ? undefined : threadId}
                backendUsage={backendTokenUsage}
                enabled={tokenUsageEnabled}
                messages={thread.messages}
                pendingMessages={pendingUsageMessages}
                preferences={localSettings.tokenUsage}
                onPreferencesChange={(preferences) =>
                  setLocalSettings("tokenUsage", preferences)
                }
                className="nail-pill h-9 border-pink-200/70 px-3 py-2 text-sm font-semibold text-[#8a4c6f] hover:bg-white/70"
              />
              {!isWelcomeMode && (
                <>
                  <ExportTrigger threadId={threadId} />
                  <ArtifactTrigger />
                </>
              )}
            </div>
          </header>
          <main className="flex min-h-0 max-w-full grow flex-col">
            <div className="flex min-h-0 flex-1 justify-center">
              <MessageList
                className={cn(
                  "size-full",
                  !isWelcomeMode && "chat-pink-message-list pt-20",
                )}
                threadId={threadId}
                thread={thread}
                paddingBottom={MESSAGE_LIST_DEFAULT_PADDING_BOTTOM}
                hasMoreHistory={hasMoreHistory}
                loadMoreHistory={loadMoreHistory}
                isHistoryLoading={isHistoryLoading}
                tokenUsageInlineMode={tokenUsageInlineMode}
              />
            </div>
            <div
              className={cn(
                "right-0 bottom-0 left-0 z-30 flex justify-center px-4",
                isWelcomeMode ? "absolute" : "relative shrink-0 pb-4",
              )}
            >
              <div
                className={cn(
                  "relative w-full",
                  isWelcomeMode && "-translate-y-[calc(50vh-80px)]",
                  isWelcomeMode ? "max-w-3xl" : "max-w-(--container-width-md)",
                )}
              >
                {hasTodos && (
                  <div
                    className={cn(
                      "right-0 left-0 z-0",
                      isWelcomeMode ? "absolute -top-4" : "relative",
                    )}
                  >
                    <div
                      className={cn(
                        "right-0 bottom-0 left-0",
                        isWelcomeMode ? "absolute" : "relative",
                      )}
                    >
                      <TodoList
                        className="nail-chat-todo"
                        todos={thread.values.todos ?? []}
                        hidden={false}
                      />
                    </div>
                  </div>
                )}
                {tryonProgress && !isWelcomeMode && (
                  <NailTryonProgressBar
                    progress={tryonProgress}
                    className="mb-3"
                  />
                )}
                {mountedRef.current ? (
                  <InputBox
                    className={cn(
                      "w-full",
                      isWelcomeMode && "new-chat-welcome-input -translate-y-4",
                      !isWelcomeMode && "chat-detail-input",
                    )}
                    isWelcomeMode={isWelcomeMode}
                    threadId={threadId}
                    autoFocus={isWelcomeMode}
                    status={
                      thread.error
                        ? "error"
                        : thread.isLoading
                          ? "streaming"
                          : "ready"
                    }
                    context={settings.context}
                    extraHeader={
                      isWelcomeMode && <Welcome mode={settings.context.mode} />
                    }
                    disabled={
                      isMock ||
                      env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true" ||
                      isUploading
                    }
                    onContextChange={(context) =>
                      setSettings("context", context)
                    }
                    onSubmit={handleSubmit}
                    onStop={handleStop}
                  />
                ) : (
                  <div
                    aria-hidden="true"
                    className={cn(
                      "bg-background/5 h-32 w-full rounded-2xl",
                      isWelcomeMode && "-translate-y-4",
                    )}
                  />
                )}
                {env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true" && (
                  <div className="text-muted-foreground/67 w-full translate-y-12 text-center text-xs">
                    {t.common.notAvailableInDemoMode}
                  </div>
                )}
              </div>
            </div>
          </main>
        </div>
      </ChatBox>
    </ThreadContext.Provider>
  );
}
