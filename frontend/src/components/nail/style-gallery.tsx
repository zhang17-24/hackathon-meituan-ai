"use client";

import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { listGalleryStyles, type GalleryStyle } from "@/core/api/nail/styles";

type NailStyle = GalleryStyle;

interface NailStyleGalleryProps {
  selectedUrl: string | null;
  onSelect: (style: NailStyle) => void;
  disabled?: boolean;
  className?: string;
}

export function NailStyleGallery({
  selectedUrl,
  onSelect,
  disabled = false,
  className,
}: NailStyleGalleryProps) {
  const { data: styles, isLoading, error } = useQuery({
    queryKey: ["nail-styles"],
    queryFn: listGalleryStyles,
    staleTime: 60_000,
  });

  if (error) {
    return (
      <p className="text-xs text-muted-foreground py-4 text-center">
        款式库加载失败，请刷新重试
      </p>
    );
  }

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-center gap-2">
        <p className="text-xs font-medium text-muted-foreground pl-0.5">
          选择美甲款式
        </p>
        {styles && (
          <span className="text-[10px] text-muted-foreground/60">
            {styles.length} 款可选
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <Skeleton key={i} className="aspect-square rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 max-h-[320px] overflow-y-auto pr-1">
          {styles?.map((style) => {
            const isSelected = selectedUrl === style.url;
            return (
              <button
                key={style.id}
                type="button"
                disabled={disabled}
                onClick={() => onSelect(style)}
                className={cn(
                  "group relative aspect-square rounded-lg overflow-hidden border-2 transition-all duration-150",
                  "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  isSelected
                    ? "border-rose-400 shadow-sm shadow-rose-500/20 scale-[1.02]"
                    : "border-border/60 hover:border-violet-400/60 hover:scale-[1.02]",
                  disabled && "cursor-not-allowed opacity-50",
                )}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={style.url}
                  alt={style.name}
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
                {/* 选中标记 */}
                {isSelected && (
                  <div className="absolute inset-0 bg-rose-500/10 flex items-center justify-center">
                    <div className="rounded-full bg-rose-500 text-white text-[10px] font-bold px-2 py-0.5 shadow">
                      ✓ 已选
                    </div>
                  </div>
                )}
                {/* hover 效果 */}
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors" />
              </button>
            );
          })}
        </div>
      )}

      {/* 分割线：或手动上传 */}
      <div className="flex items-center gap-2 py-1">
        <span className="h-px flex-1 bg-border/60" />
        <span className="text-[10px] text-muted-foreground/50">或</span>
        <span className="h-px flex-1 bg-border/60" />
      </div>
    </div>
  );
}
