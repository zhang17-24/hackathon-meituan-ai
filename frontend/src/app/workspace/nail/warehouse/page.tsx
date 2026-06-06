"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckIcon, PlusIcon, Trash2Icon } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { NailGlassShell } from "@/components/nail/nail-glass-shell";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { warehouse as api } from "@/core/api/nail";
import type { HandPhoto, StyleImage } from "@/core/api/nail/warehouse";
import { cn } from "@/lib/utils";

export default function WarehousePage() {
  const queryClient = useQueryClient();
  const handInputRef = useRef<HTMLInputElement>(null);
  const styleInputRef = useRef<HTMLInputElement>(null);

  const [selectedHand, setSelectedHand] = useState<HandPhoto | null>(null);
  const [selectedStyle, setSelectedStyle] = useState<StyleImage | null>(null);

  const { data: hands, isLoading: handsLoading } = useQuery({
    queryKey: ["warehouse-hands"],
    queryFn: api.listHands,
    staleTime: 30_000,
  });
  const { data: styles, isLoading: stylesLoading } = useQuery({
    queryKey: ["warehouse-styles"],
    queryFn: api.listStyles,
    staleTime: 30_000,
  });

  const handUpload = useMutation({
    mutationFn: api.uploadHand,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["warehouse-hands"] }),
  });
  const styleUpload = useMutation({
    mutationFn: api.uploadStyle,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["warehouse-styles"] }),
  });

  const handDelete = useMutation({
    mutationFn: api.deleteHand,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["warehouse-hands"] });
      setSelectedHand(null);
    },
  });
  const styleDelete = useMutation({
    mutationFn: api.deleteStyle,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["warehouse-styles"] });
      setSelectedStyle(null);
    },
  });

  const handleHandFile = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      if (f) handUpload.mutate(f);
      e.target.value = "";
    },
    [handUpload],
  );

  const handleStyleFile = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      if (f) styleUpload.mutate(f);
      e.target.value = "";
    },
    [styleUpload],
  );

  const goTryon = () => {
    if (!selectedHand) return;
    const params = new URLSearchParams();
    params.set("hand", selectedHand.url);
    if (selectedStyle) params.set("style", selectedStyle.url);
    window.location.href = `/workspace/nail/tryon?${params.toString()}`;
  };

  const styleCount = styles?.length ?? 0;
  const systemStyleCount = (styles ?? []).filter(
    (s) => s.source === "system",
  ).length;

  return (
    <NailGlassShell title="美甲仓库" hero={false}>
      <section className="nail-glass-card rounded-[2rem] p-5 md:p-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-4xl font-extrabold tracking-normal text-[#5b1738]">
              美甲仓库 <span className="text-pink-300">✦</span>
            </h1>
            <p className="mt-2 text-sm font-medium text-[#9d8794]">
              管理你的手图与款式图，选中后可一键试戴。
            </p>
          </div>
          {selectedHand && (
            <Button
              onClick={goTryon}
              className="nail-primary-button h-11 rounded-full px-6 font-semibold"
            >
              ✨ 去试戴
            </Button>
          )}
        </div>

        <div className="mt-8 space-y-8">
          <section className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold text-[#5b1738]">我的手图</h2>
                <p className="mt-1 text-sm text-[#a4939e]">
                  用于试戴的手部照片
                </p>
              </div>
              <Button
                variant="outline"
                className="nail-outline-button h-10 rounded-full px-5 font-semibold"
                disabled={handUpload.isPending}
                onClick={() => handInputRef.current?.click()}
              >
                <PlusIcon className="mr-2 size-4" />
                {handUpload.isPending ? "上传中…" : "上传"}
              </Button>
              <input
                ref={handInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleHandFile}
              />
            </div>

            {handsLoading ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton
                    key={i}
                    className="aspect-[1.35] rounded-3xl bg-pink-100/60"
                  />
                ))}
              </div>
            ) : (hands?.length ?? 0) === 0 ? (
              <button
                type="button"
                onClick={() => handInputRef.current?.click()}
                className="nail-dashed-zone flex min-h-40 w-full flex-col items-center justify-center rounded-[1.7rem] text-center"
              >
                <div className="mb-3 flex size-16 items-center justify-center rounded-2xl bg-pink-100/80 text-4xl shadow-lg shadow-pink-200/60">
                  🖼️
                </div>
                <p className="text-sm font-medium text-[#a4939e]">
                  暂无手图，点击「上传」添加
                </p>
              </button>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
                {hands?.map((h) => {
                  const isSel = selectedHand?.id === h.id;
                  return (
                    <div key={h.id} className="group relative">
                      <button
                        onClick={() => setSelectedHand(isSel ? null : h)}
                        className={cn(
                          "relative aspect-square w-full overflow-hidden rounded-3xl border-2 bg-white/55 transition-all",
                          isSel
                            ? "border-pink-400 shadow-xl shadow-pink-300/35"
                            : "border-pink-100 hover:border-pink-300 hover:shadow-lg hover:shadow-pink-200/40",
                        )}
                      >
                        <img
                          src={h.url}
                          alt={h.filename}
                          className="h-full w-full object-cover"
                        />
                        {isSel && (
                          <div className="absolute top-2 right-2 rounded-full bg-pink-500 p-1 text-white shadow">
                            <CheckIcon className="size-3" />
                          </div>
                        )}
                      </button>
                      <button
                        className="absolute top-2 left-2 rounded-full bg-white/80 p-1.5 text-pink-500 opacity-0 shadow transition-opacity group-hover:opacity-100"
                        onClick={() => handDelete.mutate(h.id)}
                        aria-label="删除手图"
                      >
                        <Trash2Icon className="size-3" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <div className="h-px bg-pink-200/60" />

          <section className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold text-[#5b1738]">美甲款式库</h2>
                <p className="mt-1 text-sm text-[#a4939e]">
                  系统内置 {systemStyleCount} 款 · 共 {styleCount} 款可选
                </p>
              </div>
              <Button
                variant="outline"
                className="nail-outline-button h-10 rounded-full px-5 font-semibold"
                disabled={styleUpload.isPending}
                onClick={() => styleInputRef.current?.click()}
              >
                <PlusIcon className="mr-2 size-4" />
                {styleUpload.isPending ? "上传中…" : "上传款式"}
              </Button>
              <input
                ref={styleInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleStyleFile}
              />
            </div>

            {stylesLoading ? (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
                {Array.from({ length: 12 }).map((_, i) => (
                  <Skeleton
                    key={i}
                    className="aspect-square rounded-3xl bg-pink-100/60"
                  />
                ))}
              </div>
            ) : (
              <div className="grid max-h-[560px] grid-cols-2 gap-4 overflow-y-auto pr-1 sm:grid-cols-4 lg:grid-cols-6">
                {styles?.map((s) => {
                  const isSel = selectedStyle?.id === s.id;
                  return (
                    <div key={s.id} className="group relative">
                      <button
                        onClick={() => setSelectedStyle(isSel ? null : s)}
                        className={cn(
                          "relative aspect-square w-full overflow-hidden rounded-3xl border-2 bg-white/55 transition-all",
                          isSel
                            ? "border-fuchsia-400 shadow-xl shadow-fuchsia-300/30"
                            : "border-pink-100 hover:border-pink-300 hover:shadow-lg hover:shadow-pink-200/40",
                        )}
                      >
                        <img
                          src={s.url}
                          alt={s.filename}
                          className="h-full w-full object-cover"
                          loading="lazy"
                        />
                        <span className="absolute bottom-2 left-2 rounded-full bg-black/45 px-2 py-1 text-[10px] font-semibold text-white">
                          {s.source === "system" ? "系统" : "上传"}
                        </span>
                        {isSel && (
                          <div className="absolute top-2 right-2 rounded-full bg-fuchsia-500 p-1 text-white shadow">
                            <CheckIcon className="size-3" />
                          </div>
                        )}
                      </button>
                      {s.source === "user" && (
                        <button
                          className="absolute top-2 left-2 rounded-full bg-white/80 p-1.5 text-pink-500 opacity-0 shadow transition-opacity group-hover:opacity-100"
                          onClick={() => styleDelete.mutate(s.id)}
                          aria-label="删除款式"
                        >
                          <Trash2Icon className="size-3" />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </section>
    </NailGlassShell>
  );
}
