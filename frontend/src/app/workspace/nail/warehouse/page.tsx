"use client";

import { useState, useCallback, useRef } from "react";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/core/auth/AuthProvider";
import { warehouse as api } from "@/core/api/nail";
import type { HandPhoto, StyleImage } from "@/core/api/nail/warehouse";
import { type NailRole } from "@/lib/nail-auth";
import { cn } from "@/lib/utils";
import { PlusIcon, Trash2Icon, CheckIcon } from "lucide-react";

/* ═══════════════════════════════════════════════════════ */

export default function WarehousePage() {
  const { user } = useAuth();
  const nailRole = (user as any)?.nail_role as NailRole ?? "user";
  const queryClient = useQueryClient();
  const handInputRef = useRef<HTMLInputElement>(null);
  const styleInputRef = useRef<HTMLInputElement>(null);

  /* 选中状态 — 用于聊天的输入 */
  const [selectedHand, setSelectedHand] = useState<HandPhoto | null>(null);
  const [selectedStyle, setSelectedStyle] = useState<StyleImage | null>(null);

  /* 查询 */
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

  /* 上传 */
  const handUpload = useMutation({
    mutationFn: api.uploadHand,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["warehouse-hands"] }),
  });
  const styleUpload = useMutation({
    mutationFn: api.uploadStyle,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["warehouse-styles"] }),
  });

  /* 删除 */
  const handDelete = useMutation({
    mutationFn: api.deleteHand,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["warehouse-hands"] });
      setSelectedHand(null);
    },
  });
  const styleDelete = useMutation({
    mutationFn: api.deleteStyle,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["warehouse-styles"] });
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

  /* 跳转试戴：带着选中的手图和款式 */
  const goTryon = () => {
    if (!selectedHand) return;
    const params = new URLSearchParams();
    params.set("hand", selectedHand.url);
    if (selectedStyle) params.set("style", selectedStyle.url);
    window.location.href = `/workspace/nail/tryon?${params.toString()}`;
  };

  return (
    <div className="flex h-full flex-col">
      {/* ── Header ── */}
      <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mr-2 h-4" />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="hidden sm:block text-muted-foreground">NailFlow</BreadcrumbItem>
            <BreadcrumbSeparator className="hidden sm:block" />
            <BreadcrumbItem><BreadcrumbPage>美甲仓库</BreadcrumbPage></BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <div className="ml-auto flex items-center gap-2">
          {selectedHand && (
            <Button size="sm" onClick={goTryon} className="h-7 text-xs bg-rose-500 hover:bg-rose-600 text-white">
              ✨ 去试戴
            </Button>
          )}
          <Badge variant="outline" className={cn("text-[10px]", nailRole === "dev" && "border-blue-400/40 text-blue-400")}>
            {nailRole === "dev" ? "⚡ Dev" : "💅 User"}
          </Badge>
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-4xl px-4 py-6 space-y-6">

          {/* ── 标题 ── */}
          <div className="space-y-1">
            <h1 className="text-xl font-semibold tracking-tight">美甲仓库</h1>
            <p className="text-sm text-muted-foreground">
              管理你的手图与款式图，选中后可一键试戴。
            </p>
          </div>

          {/* ═══════ 手图区（小栏，横向滚动） ═══════ */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold">我的手图</h2>
                <p className="text-xs text-muted-foreground">用于试戴的手部照片</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs gap-1"
                disabled={handUpload.isPending}
                onClick={() => handInputRef.current?.click()}
              >
                <PlusIcon className="size-3" />
                {handUpload.isPending ? "上传中…" : "上传"}
              </Button>
              <input ref={handInputRef} type="file" accept="image/*" className="hidden" onChange={handleHandFile} />
            </div>

            {handsLoading ? (
              <div className="flex gap-2 overflow-x-auto pb-2">
                {[1, 2, 3].map((i) => <Skeleton key={i} className="w-24 h-24 shrink-0 rounded-lg" />)}
              </div>
            ) : (hands?.length ?? 0) === 0 ? (
              <div className="flex items-center justify-center h-24 rounded-xl border-2 border-dashed border-border/60 text-xs text-muted-foreground">
                暂无手图，点击「上传」添加
              </div>
            ) : (
              <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1">
                {hands?.map((h) => {
                  const isSel = selectedHand?.id === h.id;
                  return (
                    <div key={h.id} className="relative group shrink-0">
                      <button
                        onClick={() => setSelectedHand(isSel ? null : h)}
                        className={cn(
                          "w-24 h-24 rounded-lg overflow-hidden border-2 transition-all",
                          isSel ? "border-rose-400 ring-1 ring-rose-400/40" : "border-border/60 hover:border-rose-400/60",
                        )}
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={h.url} alt={h.filename} className="w-full h-full object-cover" />
                        {isSel && (
                          <div className="absolute top-1 right-1 rounded-full bg-rose-500 text-white p-0.5">
                            <CheckIcon className="size-2.5" />
                          </div>
                        )}
                      </button>
                      <button
                        className="absolute top-1 left-1 p-0.5 rounded bg-black/50 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => handDelete.mutate(h.id)}
                      >
                        <Trash2Icon className="size-2.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <Separator />

          {/* ═══════ 款式图区（大栏，网格） ═══════ */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold">美甲款式库</h2>
                <p className="text-xs text-muted-foreground">
                  系统内置 {(styles ?? []).filter(s => s.source === "system").length} 款 + 你的上传
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs gap-1"
                disabled={styleUpload.isPending}
                onClick={() => styleInputRef.current?.click()}
              >
                <PlusIcon className="size-3" />
                {styleUpload.isPending ? "上传中…" : "上传款式"}
              </Button>
              <input ref={styleInputRef} type="file" accept="image/*" className="hidden" onChange={handleStyleFile} />
            </div>

            {stylesLoading ? (
              <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
                {Array.from({ length: 12 }).map((_, i) => (
                  <Skeleton key={i} className="aspect-square rounded-lg" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-4 sm:grid-cols-6 gap-2 max-h-[500px] overflow-y-auto pr-1">
                {styles?.map((s) => {
                  const isSel = selectedStyle?.id === s.id;
                  return (
                    <div key={s.id} className="relative group">
                      <button
                        onClick={() => setSelectedStyle(isSel ? null : s)}
                        className={cn(
                          "w-full aspect-square rounded-lg overflow-hidden border-2 transition-all",
                          isSel ? "border-violet-400 ring-1 ring-violet-400/40" : "border-border/60 hover:border-violet-400/60",
                        )}
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={s.url} alt={s.filename} className="w-full h-full object-cover" loading="lazy" />
                        {isSel && (
                          <div className="absolute top-1 right-1 rounded-full bg-violet-500 text-white p-0.5">
                            <CheckIcon className="size-2.5" />
                          </div>
                        )}
                      </button>
                      {s.source === "user" && (
                        <button
                          className="absolute top-1 left-1 p-0.5 rounded bg-black/50 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={() => styleDelete.mutate(s.id)}
                        >
                          <Trash2Icon className="size-2.5" />
                        </button>
                      )}
                      {s.source === "system" && (
                        <span className="absolute bottom-1 left-1 text-[9px] bg-black/50 text-white px-1 rounded">
                          系统
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <div className="h-4" />
        </div>
      </ScrollArea>
    </div>
  );
}
