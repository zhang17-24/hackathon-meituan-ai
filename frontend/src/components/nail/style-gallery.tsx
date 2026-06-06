"use client";

import { useQuery } from "@tanstack/react-query";

import { Skeleton } from "@/components/ui/skeleton";
import { listGalleryStyles, type GalleryStyle } from "@/core/api/nail/styles";
import { cn } from "@/lib/utils";

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
  const {
    data: styles,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["nail-styles"],
    queryFn: listGalleryStyles,
    staleTime: 60_000,
  });

  if (error) {
    return (
      <p className="py-4 text-center text-xs font-medium text-pink-400">
        款式库加载失败，请刷新重试
      </p>
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center gap-2">
        <p className="pl-0.5 text-sm font-bold text-pink-600">
          🌸 试试热门风格
        </p>
        {styles && (
          <span className="rounded-full bg-white/55 px-2 py-0.5 text-[10px] font-semibold text-pink-400">
            {styles.length} 款可选
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
          {Array.from({ length: 10 }).map((_, i) => (
            <Skeleton
              key={i}
              className="aspect-square rounded-2xl bg-pink-100/60"
            />
          ))}
        </div>
      ) : (
        <div className="grid max-h-[320px] grid-cols-3 gap-2 overflow-y-auto pr-1 sm:grid-cols-5 lg:grid-cols-3 xl:grid-cols-4">
          {styles?.map((style) => {
            const isSelected = selectedUrl === style.url;
            return (
              <button
                key={style.id}
                type="button"
                disabled={disabled}
                onClick={() => onSelect(style)}
                className={cn(
                  "group relative aspect-square overflow-hidden rounded-2xl border-2 bg-white/45 transition-all duration-150",
                  "focus:outline-none focus-visible:ring-2 focus-visible:ring-pink-300",
                  isSelected
                    ? "scale-[1.02] border-pink-400 shadow-lg shadow-pink-300/35"
                    : "border-pink-200/70 hover:scale-[1.02] hover:border-pink-400/70 hover:shadow-md hover:shadow-pink-200/40",
                  disabled && "cursor-not-allowed opacity-50",
                )}
              >
                { }
                <img
                  src={style.url}
                  alt={style.name}
                  className="h-full w-full object-cover"
                  loading="lazy"
                />
                {/* 选中标记 */}
                {isSelected && (
                  <div className="absolute inset-0 flex items-center justify-center bg-pink-500/12">
                    <div className="rounded-full bg-gradient-to-r from-pink-500 to-fuchsia-400 px-2.5 py-1 text-[10px] font-bold text-white shadow">
                      ✓ 已选
                    </div>
                  </div>
                )}
                {/* hover 效果 */}
                <div className="absolute inset-0 bg-pink-950/0 transition-colors group-hover:bg-pink-950/10" />
              </button>
            );
          })}
        </div>
      )}

      {/* 分割线：或手动上传 */}
      <div className="flex items-center gap-2 py-1">
        <span className="h-px flex-1 bg-pink-200/70" />
        <span className="text-[10px] font-semibold text-pink-300">
          或手动上传
        </span>
        <span className="h-px flex-1 bg-pink-200/70" />
      </div>
    </div>
  );
}
