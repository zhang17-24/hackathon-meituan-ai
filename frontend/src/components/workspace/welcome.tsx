"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo } from "react";

import { useI18n } from "@/core/i18n/hooks";
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
      <p className="text-muted-foreground text-sm max-w-sm text-center leading-relaxed">
        上传手图和款式图，AI 将自动分析手型、生成甲面遮罩、理解款式风格，最终生成精准试戴效果。
      </p>

      {/* 操作提示 */}
      <div className="mt-1 flex flex-col items-center gap-1.5">
        <div className="flex items-center gap-2 rounded-full border border-rose-200/60 bg-rose-50/50 px-4 py-1.5 text-xs text-rose-600 dark:border-rose-800/40 dark:bg-rose-950/20 dark:text-rose-400">
          <span>📎</span>
          <span>点击输入框的附件按钮上传手图和款式图，然后发送消息</span>
        </div>
        <p className="text-muted-foreground/60 text-[11px]">
          也可以直接输入"帮我试戴猫眼款式"，AI 会引导你上传图片
        </p>
      </div>

      {/* 工具链说明 */}
      <div className="mt-2 grid grid-cols-3 gap-2 text-center text-[11px] text-muted-foreground/70">
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
            className="flex items-center gap-1 rounded-md bg-muted/40 px-2 py-1"
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
  const { t } = useI18n();
  const searchParams = useSearchParams();
  const isNailMode = searchParams.get("mode") === "nail";
  const isUltra = useMemo(() => mode === "ultra", [mode]);
  const colors = useMemo(() => {
    if (isUltra) {
      return ["#efefbb", "#e9c665", "#e3a812"];
    }
    return ["var(--color-foreground)"];
  }, [isUltra]);
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
        "mx-auto flex w-full flex-col items-center justify-center gap-2 px-8 py-4 text-center",
        className,
      )}
    >
      <div className="text-2xl font-bold">
        {searchParams.get("mode") === "skill" ? (
          `✨ ${t.welcome.createYourOwnSkill} ✨`
        ) : (
          <div className="flex items-center gap-2">
            <div className={cn("inline-block", !waved ? "animate-wave" : "")}>
              {isUltra ? "🚀" : "👋"}
            </div>
            <AuroraText colors={colors}>{t.welcome.greeting}</AuroraText>
          </div>
        )}
      </div>
      {searchParams.get("mode") === "skill" ? (
        <div className="text-muted-foreground text-sm">
          {t.welcome.createYourOwnSkillDescription.includes("\n") ? (
            <pre className="font-sans whitespace-pre">
              {t.welcome.createYourOwnSkillDescription}
            </pre>
          ) : (
            <p>{t.welcome.createYourOwnSkillDescription}</p>
          )}
        </div>
      ) : (
        <div className="text-muted-foreground text-sm">
          {t.welcome.description.includes("\n") ? (
            <pre className="font-sans whitespace-pre">
              {t.welcome.description}
            </pre>
          ) : (
            <p>{t.welcome.description}</p>
          )}
        </div>
      )}
    </div>
  );
}
