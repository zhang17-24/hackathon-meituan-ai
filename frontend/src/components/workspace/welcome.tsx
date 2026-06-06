"use client";

import { useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { cn } from "@/lib/utils";

import { AuroraText } from "../ui/aurora-text";

let waved = false;

/** 美甲试戴模式的欢迎说明，告知用户如何通过对话界面使用 */
function NailWelcome() {
  return (
    <div className="flex flex-col items-center gap-3">
      {/* 标题 */}
      <div className="flex items-center gap-2 text-2xl font-bold">
        <span className="animate-wave inline-block">💅</span>
        <AuroraText colors={["#f9a8d4", "#ec4899", "#be185d"]}>
          AI 美甲试戴
        </AuroraText>
      </div>

      {/* 副标题 */}
      <p className="text-muted-foreground max-w-sm text-center text-sm leading-relaxed">
        上传手图和款式图，AI
        将自动分析手型、生成甲面遮罩、理解款式风格，最终生成精准试戴效果。
      </p>

      {/* 操作提示 */}
      <div className="mt-1 flex flex-col items-center gap-1.5">
        <div className="flex items-center gap-2 rounded-full border border-rose-200/60 bg-rose-50/50 px-4 py-1.5 text-xs text-rose-600 dark:border-rose-800/40 dark:bg-rose-950/20 dark:text-rose-400">
          <span>📎</span>
          <span>点击输入框的附件按钮上传手图和款式图，然后发送消息</span>
        </div>
        <p className="text-muted-foreground/60 text-[11px]">
          也可以直接输入「帮我试戴猫眼款式」，AI 会引导你上传图片
        </p>
      </div>

      {/* 工具链说明 */}
      <div className="text-muted-foreground/70 mt-2 grid grid-cols-3 gap-2 text-center text-[11px]">
        {[
          { icon: "🔍", label: "手部检测" },
          { icon: "✂️", label: "生成 mask" },
          { icon: "🎨", label: "款式理解" },
          { icon: "✍️", label: "构建提示词" },
          { icon: "⚡", label: "AI 生图" },
          { icon: "✅", label: "质量评分" },
        ].map(({ icon, label }) => (
          <div
            key={label}
            className="bg-muted/40 flex items-center gap-1 rounded-md px-2 py-1"
          >
            <span>{icon}</span>
            <span>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Welcome({
  className,
  mode,
}: {
  className?: string;
  mode?: "ultra" | "pro" | "thinking" | "flash";
}) {
  const searchParams = useSearchParams();
  const isNailMode = searchParams.get("mode") === "nail";
  useEffect(() => {
    waved = true;
  }, []);

  // nail 模式：显示美甲专属欢迎界面
  if (isNailMode) {
    return (
      <div
        className={cn(
          "mx-auto flex w-full flex-col items-center justify-center gap-2 px-8 py-4",
          className,
        )}
      >
        <NailWelcome />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "mx-auto flex w-full flex-col items-center justify-center gap-4 px-8 py-4 text-center",
        className,
      )}
    >
      <div className="text-4xl font-extrabold tracking-normal md:text-5xl">
        {searchParams.get("mode") === "skill" ? (
          <span className="nail-hero-title">✨ 创建你的专属 Skill ✨</span>
        ) : (
          <div className="flex items-center gap-2">
            <div className={cn("inline-block", !waved ? "animate-wave" : "")}>
              {mode === "ultra" ? "🚀" : "👋"}
            </div>
            <span className="nail-hero-title">你好，欢迎回来！</span>
          </div>
        )}
      </div>
      {searchParams.get("mode") === "skill" ? (
        <div className="max-w-2xl text-sm leading-7 text-[#8b7180]">
          <p>
            用自然语言描述你想要的能力，DeerFlow 会帮助你整理成可复用的 Skill。
          </p>
        </div>
      ) : (
        <div className="max-w-2xl text-sm leading-7 text-[#8b7180]">
          <p>
            欢迎使用 DeerFlow，一个完全开源的超级智能体。通过内置和自定义的
            Skills，DeerFlow 可以帮你搜索网络、分析数据，还能为你生成幻灯片、
            图片、视频、播客及网页等，几乎可以做任何事情。
          </p>
        </div>
      )}
    </div>
  );
}
