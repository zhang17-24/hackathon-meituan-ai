// frontend/src/components/nail/nail-page-layout.tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { BotIcon, XIcon } from "lucide-react";
import { NailChatPane } from "./nail-chat-pane";
import { useNailThread, type NailPageMode } from "@/core/nail-chat";

interface NailPageLayoutProps {
  /** 页面模式，控制 Agent 提示词和工具集 */
  pageMode: NailPageMode;
  /** 左侧数据面板内容 */
  panel: React.ReactNode;
  /** 额外的 configurable 参数传给 Agent */
  extraConfig?: Record<string, unknown>;
  className?: string;
}

export function NailPageLayout({
  pageMode,
  panel,
  extraConfig,
  className,
}: NailPageLayoutProps) {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const { threadId, ensureThread, resetThread } = useNailThread(pageMode);

  return (
    <div className={cn("relative flex h-full flex-col overflow-hidden", className)}>
      {/* 主内容区：面板 + Chat 滑入 */}
      <div className="flex min-h-0 flex-1">
        {/* 左侧：数据面板 */}
        <div
          className={cn(
            "min-h-0 overflow-auto transition-all duration-300",
            isChatOpen ? "w-[60%]" : "w-full",
          )}
        >
          {panel}
        </div>

        {/* 右侧：Chat 面板（宽度动画滑入） */}
        <div
          className={cn(
            "flex flex-col border-l bg-background transition-all duration-300 overflow-hidden",
            isChatOpen ? "w-[40%]" : "w-0",
          )}
        >
          {isChatOpen && (
            <>
              {/* Chat 关闭按钮 */}
              <div className="flex items-center justify-end border-b px-2 py-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7"
                  onClick={() => setIsChatOpen(false)}
                  aria-label="关闭 AI 分析"
                >
                  <XIcon className="size-4" />
                </Button>
              </div>
              {/* Chat 主体 */}
              <div className="min-h-0 flex-1 overflow-hidden">
                <NailChatPane
                  pageMode={pageMode}
                  ensureThread={ensureThread}
                  resetThread={resetThread}
                  extraConfig={extraConfig}
                  className="h-full"
                />
              </div>
            </>
          )}
        </div>
      </div>

      {/* AI 分析按钮（右下角浮动，只在 Chat 关闭时显示） */}
      {!isChatOpen && (
        <div className="absolute right-6 bottom-6 z-20">
          <Button
            onClick={() => setIsChatOpen(true)}
            className="h-11 gap-2 rounded-full shadow-lg"
          >
            <BotIcon className="size-4" />
            AI 分析
          </Button>
        </div>
      )}
    </div>
  );
}
