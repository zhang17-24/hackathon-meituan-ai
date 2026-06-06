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
      onKeyDown={(e) =>
        e.key === "Enter" && !disabled && inputRef.current?.click()
      }
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className={cn(
        "group relative flex flex-col items-center justify-center rounded-3xl border-2 border-dashed transition-all duration-200 select-none",
        "min-h-[170px] cursor-pointer overflow-hidden bg-white/45 shadow-sm backdrop-blur-md",
        previewUrl
          ? isRose
            ? "border-pink-400/50"
            : "border-fuchsia-300/50"
          : "border-pink-300/60",
        isDragging
          ? isRose
            ? "scale-[1.01] border-pink-400 bg-pink-100/60"
            : "scale-[1.01] border-fuchsia-400 bg-fuchsia-100/50"
          : "",
        !previewUrl && !isDragging && !disabled
          ? isRose
            ? "hover:border-pink-400/80 hover:bg-pink-50/70"
            : "hover:border-fuchsia-400/80 hover:bg-fuchsia-50/60"
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
        <div className="relative flex h-full w-full flex-col">
          <div className="relative m-2 flex-1 overflow-hidden rounded-2xl">
            { }
            <img
              src={previewUrl}
              alt={label}
              className="h-full w-full object-cover object-center"
              style={{ maxHeight: 140 }}
            />
            {/* 悬浮覆盖层 */}
            <div className="absolute inset-0 flex items-center justify-center rounded-2xl bg-pink-950/40 opacity-0 transition-opacity group-hover:opacity-100">
              <span className="rounded-full bg-white/85 px-3 py-1 text-xs font-semibold text-pink-600 shadow-sm">
                点击更换
              </span>
            </div>
          </div>
          {fileName && (
            <p className="truncate px-3 pb-2 text-center text-[11px] text-pink-400">
              {fileName}
            </p>
          )}
          {/* 角落标签 */}
          <div
            className={cn(
              "absolute top-3 left-3 flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-semibold shadow-sm",
              isRose
                ? "bg-pink-500/90 text-white"
                : "bg-fuchsia-500/85 text-white",
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
              "flex h-14 w-14 items-center justify-center rounded-2xl text-3xl shadow-lg transition-transform duration-200",
              "group-hover:scale-110",
              isRose
                ? "bg-pink-100/80 shadow-pink-200/60 group-hover:bg-pink-100"
                : "bg-fuchsia-100/70 shadow-fuchsia-200/50 group-hover:bg-fuchsia-100",
            )}
          >
            {icon}
          </div>
          <div>
            <p
              className={cn(
                "text-sm font-bold",
                isRose ? "text-pink-600" : "text-fuchsia-600",
              )}
            >
              {label}
            </p>
            {sublabel && (
              <p className="mt-1 text-[11px] text-pink-400">{sublabel}</p>
            )}
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-pink-300">
            <span className="inline-block w-6 border-t border-dashed border-pink-200" />
            拖放或点击上传
            <span className="inline-block w-6 border-t border-dashed border-pink-200" />
          </div>
        </div>
      )}
    </div>
  );
}
