"use client";

import { useState, use } from "react";
import Link from "next/link";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  Breadcrumb, BreadcrumbItem, BreadcrumbList,
  BreadcrumbPage, BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/core/auth/AuthProvider";
import { getPost, toggleLike, listComments, createComment, type PostOut, type Comment } from "@/core/api/nail/community";
import { uploadStyle } from "@/core/api/nail/warehouse";
import type { NailRole } from "@/lib/nail-auth";
import { cn } from "@/lib/utils";
import { HeartIcon, MessageCircleIcon, ArrowLeftIcon, SparklesIcon, BookmarkIcon, SendIcon } from "lucide-react";

/* ═══════════════════════════════════════════════════════════
   帖子详情页
   ═══════════════════════════════════════════════════════════ */
export default function PostDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { user } = useAuth();
  const nailRole = (user as any)?.nail_role as NailRole ?? "user";
  const queryClient = useQueryClient();

  const [activeImageIdx, setActiveImageIdx] = useState(0);
  const [commentText, setCommentText] = useState("");
  const [saveState, setSaveState] = useState<Record<string, "idle" | "saving" | "saved">>({});

  /* 帖子数据 */
  const { data: post, isLoading } = useQuery({
    queryKey: ["community-post", id],
    queryFn: () => getPost(id),
    staleTime: 30_000,
  });

  /* 评论 */
  const { data: commentsData } = useQuery({
    queryKey: ["comments", id],
    queryFn: () => listComments(id),
    staleTime: 10_000,
  });
  const comments = commentsData?.comments ?? [];

  /* 点赞 */
  const likeMut = useMutation({
    mutationFn: () => toggleLike(id) as Promise<{ liked: boolean; like_count: number }>,
    onSuccess: (result) => {
      queryClient.setQueryData(["community-post", id], (old: PostOut | undefined) => {
        if (!old) return old;
        return { ...old, is_liked: result.liked, like_count: result.like_count };
      });
      queryClient.invalidateQueries({ queryKey: ["community-posts"] });
    },
  });

  /* 评论 */
  const commentMut = useMutation({
    mutationFn: (content: string) => createComment(id, content),
    onSuccess: () => {
      setCommentText("");
      queryClient.invalidateQueries({ queryKey: ["comments", id] });
      queryClient.invalidateQueries({ queryKey: ["community-post", id] });
    },
  });

  /* 收藏到仓库 */
  const saveToWarehouse = async (imageUrl: string) => {
    const key = imageUrl.slice(-20);
    setSaveState(prev => ({ ...prev, [key]: "saving" }));
    try {
      const resp = await fetch(imageUrl);
      const blob = await resp.blob();
      const file = new File([blob], `community-style-${Date.now()}.jpg`, { type: "image/jpeg" });
      await uploadStyle(file);
      setSaveState(prev => ({ ...prev, [key]: "saved" }));
      setTimeout(() => setSaveState(prev => ({ ...prev, [key]: "idle" })), 2000);
    } catch {
      setSaveState(prev => ({ ...prev, [key]: "idle" }));
    }
  };

  /* 一键试戴 */
  const tryonUrl = (imageUrl: string) => {
    return `/workspace/nail/tryon?style=${encodeURIComponent(imageUrl)}`;
  };

  if (isLoading) {
    return (
      <div className="flex h-full flex-col">
        <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Skeleton className="h-4 w-32" />
        </header>
        <div className="mx-auto max-w-2xl px-4 py-6 space-y-4">
          <Skeleton className="aspect-[4/3] rounded-xl" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </div>
    );
  }

  if (!post) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
        帖子不存在或已被删除
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mr-2 h-4" />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="hidden sm:block text-muted-foreground">nailflow</BreadcrumbItem>
            <BreadcrumbSeparator className="hidden sm:block" />
            <BreadcrumbItem>
              <Link href="/workspace/nail/community" className="text-muted-foreground hover:text-foreground text-xs">
                美甲社区
              </Link>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem><BreadcrumbPage className="text-xs">帖子详情</BreadcrumbPage></BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <div className="ml-auto">
          <Badge variant="outline" className={cn("text-[10px]", nailRole === "dev" && "border-blue-400/40 text-blue-400")}>
            {nailRole === "dev" ? "⚡ Dev" : "💅 User"}
          </Badge>
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-2xl px-4 py-6 space-y-5">

          {/* 图片轮播 */}
          {post.images.length > 0 && (
            <div className="space-y-2">
              <div className="aspect-[4/3] rounded-xl overflow-hidden bg-muted/20 relative">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={post.images[activeImageIdx]?.url}
                  alt=""
                  className="size-full object-cover"
                />
                {/* 左右切换 */}
                {post.images.length > 1 && (
                  <>
                    <button
                      className="absolute left-2 top-1/2 -translate-y-1/2 size-8 rounded-full bg-black/40 text-white flex items-center justify-center text-sm hover:bg-black/60"
                      onClick={() => setActiveImageIdx(i => (i - 1 + post.images.length) % post.images.length)}
                    >
                      ‹
                    </button>
                    <button
                      className="absolute right-2 top-1/2 -translate-y-1/2 size-8 rounded-full bg-black/40 text-white flex items-center justify-center text-sm hover:bg-black/60"
                      onClick={() => setActiveImageIdx(i => (i + 1) % post.images.length)}
                    >
                      ›
                    </button>
                    <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-1.5">
                      {post.images.map((_, i) => (
                        <span
                          key={i}
                          className={cn(
                            "size-1.5 rounded-full transition-all",
                            i === activeImageIdx ? "bg-white w-4" : "bg-white/50"
                          )}
                        />
                      ))}
                    </div>
                  </>
                )}
              </div>
              {/* 缩略图条 */}
              {post.images.length > 1 && (
                <div className="flex gap-2 overflow-x-auto pb-1">
                  {post.images.map((img, i) => (
                    <button
                      key={img.id}
                      onClick={() => setActiveImageIdx(i)}
                      className={cn(
                        "size-14 rounded-lg overflow-hidden border-2 shrink-0 transition-all",
                        i === activeImageIdx ? "border-rose-400" : "border-transparent opacity-60"
                      )}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={img.url} alt="" className="size-full object-cover" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 内容 */}
          {post.content && (
            <p className="text-sm leading-relaxed text-foreground/85 whitespace-pre-wrap">
              {post.content}
            </p>
          )}

          {/* 标签 */}
          {post.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {post.tags.map((t, i) => (
                <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-rose-50 text-rose-600 dark:bg-rose-950 dark:text-rose-400">
                  #{t}
                </span>
              ))}
            </div>
          )}

          {/* 操作按钮：收藏到仓库 + 一键试戴 */}
          <div className="flex gap-2">
            {post.images[0] && (() => {
              const coverUrl = post.images[0]!.url;
              const stateKey = coverUrl.slice(-20);
              return (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 text-xs gap-1"
                  onClick={() => saveToWarehouse(coverUrl)}
                  disabled={saveState[stateKey] === "saving" || saveState[stateKey] === "saved"}
                >
                  {saveState[stateKey] === "saved" ? (
                    <>✅ 已收藏</>
                  ) : (
                    <><BookmarkIcon className="size-3" /> 收藏到仓库</>
                  )}
                </Button>
                <Link href={tryonUrl(coverUrl)}>
                  <Button size="sm" className="h-8 text-xs gap-1 bg-rose-500 hover:bg-rose-600 text-white">
                    <SparklesIcon className="size-3" /> 一键试戴
                  </Button>
                </Link>
              </>
            )})()}
          </div>

          <Separator />

          {/* 点赞 + 评论数 */}
          <div className="flex items-center gap-4">
            <button
              onClick={() => likeMut.mutate()}
              className={cn(
                "flex items-center gap-1.5 text-sm transition-colors",
                post.is_liked ? "text-rose-500" : "text-muted-foreground hover:text-rose-500"
              )}
            >
              <HeartIcon className={cn("size-4", post.is_liked && "fill-rose-500")} />
              <span>{post.like_count} 赞</span>
            </button>
            <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <MessageCircleIcon className="size-4" />
              <span>{post.comment_count} 评论</span>
            </span>
            <span className="ml-auto text-[11px] text-muted-foreground/60">
              {post.created_at?.slice(0, 10)}
            </span>
          </div>

          <Separator />

          {/* 评论列表 */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold">评论 ({commentsData?.total ?? 0})</h3>
            {comments.length === 0 ? (
              <p className="text-xs text-muted-foreground py-4 text-center">暂无评论，来说点什么吧</p>
            ) : (
              <div className="space-y-3">
                {comments.map(c => (
                  <div key={c.id} className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-foreground/80">{c.user_id.slice(0, 8)}</span>
                      <span className="text-[10px] text-muted-foreground/60">{c.created_at?.slice(0, 10)}</span>
                    </div>
                    <p className="text-sm text-foreground/70 pl-1">{c.content}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 发表评论 */}
          <div className="flex gap-2 pt-1">
            <Textarea
              placeholder="写下你的评论..."
              value={commentText}
              onChange={e => setCommentText(e.target.value)}
              rows={2}
              className="min-h-0 text-sm"
            />
            <Button
              size="icon"
              className="shrink-0 bg-rose-500 hover:bg-rose-600 text-white h-auto"
              disabled={!commentText.trim() || commentMut.isPending}
              onClick={() => commentMut.mutate(commentText.trim())}
            >
              {commentMut.isPending ? (
                <span className="size-3 rounded-full border-2 border-white/30 border-t-white animate-spin" />
              ) : (
                <SendIcon className="size-4" />
              )}
            </Button>
          </div>

          <div className="h-8" />
        </div>
      </ScrollArea>
    </div>
  );
}
