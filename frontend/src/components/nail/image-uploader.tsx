"use client";

import { useCallback, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface NailImageUploaderProps {
  label: string;
  sublabel?: string;
  icon: string;
  accept?: string;
  onFile: (file: File, previewUrl: string) => void;
  previewUrl?: string;
  fileName?: string;
  disabled?: boolean;
  className?: string;
  accentColor?: "rose" | "lavender";
}

export function NailImageUploader({
  label,
  sublabel,
  icon,
  accept = "image/*",
  onFile,
  previewUrl,
  fileName,
  disabled = false,
  className,
  accentColor = "rose",
}: NailImageUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFile = useCallback(
    (file: File) => {
      if (!file.type.startsWith("image/")) return;
      const url = URL.createObjectURL(file);
      onFile(file, url);
    },
    [onFile],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  };

  const isRose = accentColor === "rose";

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label={`上传${label}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => e.key === "Enter" && !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className={cn(
        "group relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed transition-all duration-200 select-none",
        "min-h-[160px] cursor-pointer overflow-hidden",
        previewUrl
          ? isRose
            ? "border-rose-400/40 bg-rose-500/5"
            : "border-violet-400/40 bg-violet-500/5"
          : "border-border/60 bg-muted/30",
        isDragging
          ? isRose
            ? "border-rose-400 bg-rose-500/10 scale-[1.01]"
            : "border-violet-400 bg-violet-500/10 scale-[1.01]"
          : "",
        !previewUrl && !isDragging && !disabled
          ? isRose
            ? "hover:border-rose-400/60 hover:bg-rose-500/5"
            : "hover:border-violet-400/60 hover:bg-violet-500/5"
          : "",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={handleChange}
        disabled={disabled}
      />

      {previewUrl ? (
        /* ── 预览状态 ── */
        <div className="relative w-full h-full flex flex-col">
          <div className="relative flex-1 overflow-hidden rounded-lg m-1.5">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={previewUrl}
              alt={label}
              className="w-full h-full object-cover object-center"
              style={{ maxHeight: 140 }}
            />
            {/* 悬浮覆盖层 */}
            <div className="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg">
              <span className="text-white text-xs font-medium bg-black/60 px-3 py-1 rounded-full">
                点击更换
              </span>
            </div>
          </div>
          {fileName && (
            <p className="px-3 pb-2 text-[11px] text-muted-foreground truncate text-center">
              {fileName}
            </p>
          )}
          {/* 角落标签 */}
          <div
            className={cn(
              "absolute top-2.5 left-2.5 flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold",
              isRose
                ? "bg-rose-500/90 text-white"
                : "bg-violet-500/90 text-white",
            )}
          >
            <span>{icon}</span>
            <span>{label}</span>
          </div>
        </div>
      ) : (
        /* ── 空状态 ── */
        <div className="flex flex-col items-center gap-2.5 px-4 py-6 text-center">
          <div
            className={cn(
              "flex items-center justify-center w-11 h-11 rounded-full text-2xl transition-transform duration-200",
              "group-hover:scale-110",
              isRose
                ? "bg-rose-500/10 group-hover:bg-rose-500/15"
                : "bg-violet-500/10 group-hover:bg-violet-500/15",
            )}
          >
            {icon}
          </div>
          <div>
            <p
              className={cn(
                "text-sm font-medium",
                isRose ? "text-rose-400/80" : "text-violet-400/80",
              )}
            >
              {label}
            </p>
            {sublabel && (
              <p className="mt-0.5 text-[11px] text-muted-foreground">
                {sublabel}
              </p>
            )}
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground/60">
            <span className="inline-block w-6 border-t border-dashed border-muted-foreground/30" />
            拖放或点击上传
            <span className="inline-block w-6 border-t border-dashed border-muted-foreground/30" />
          </div>
        </div>
      )}
    </div>
  );
}
