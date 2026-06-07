"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Breadcrumb, BreadcrumbItem, BreadcrumbList,
  BreadcrumbPage, BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/core/auth/AuthProvider";
import { listPosts, createPost, type PostOut } from "@/core/api/nail/community";
import type { NailRole } from "@/lib/nail-auth";
import { cn } from "@/lib/utils";
import { PlusIcon, HeartIcon, MessageCircleIcon, XIcon, ImageIcon } from "lucide-react";

/* ═══════════════════════════════════════════════════════════
   发帖弹窗
   ═══════════════════════════════════════════════════════════ */
function CreatePostDialog({
  open, onClose, onSuccess,
}: {
  open: boolean; onClose: () => void; onSuccess: () => void;
}) {
  const [content, setContent] = useState("");
  const [tags, setTags] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);

  const createMut = useMutation({
    mutationFn: createPost,
    onSuccess: () => { onSuccess(); onClose(); setContent(""); setTags(""); setFiles([]); setPreviews([]); },
  });

  const handleFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newFiles = Array.from(e.target.files ?? []);
    setFiles(prev => [...prev, ...newFiles]);
    newFiles.forEach(f => {
      const r = new FileReader();
      r.onload = () => setPreviews(prev => [...prev, r.result as string]);
      r.readAsDataURL(f);
    });
    e.target.value = "";
  };

  const removeFile = (i: number) => {
    setFiles(prev => prev.filter((_, idx) => idx !== i));
    setPreviews(prev => prev.filter((_, idx) => idx !== i));
  };

  const handleSubmit = () => {
    if (files.length === 0) return;
    const tagList = tags.split(/[,，]/).map(t => t.trim()).filter(Boolean);
    createMut.mutate({
      content,
      tags: JSON.stringify(tagList),
      style_refs: "[]",
      files,
    });
  };

  return (
    <Dialog open={open} onOpenChange={o => { if (!o) onClose(); }}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>发布帖子</DialogTitle></DialogHeader>
        <div className="space-y-4">
          {/* 图片上传 */}
          <div>
            <p className="text-sm font-medium mb-2">图片 <span className="text-rose-400">*</span></p>
            <div className="flex flex-wrap gap-2 mb-2">
              {previews.map((p, i) => (
                <div key={i} className="relative size-20 rounded-lg overflow-hidden border shrink-0">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={p} alt="" className="size-full object-cover" />
                  <button
                    className="absolute top-0.5 right-0.5 size-4 rounded-full bg-black/60 text-white flex items-center justify-center"
                    onClick={() => removeFile(i)}
                  >
                    <XIcon className="size-2.5" />
                  </button>
                </div>
              ))}
              <label className="size-20 rounded-lg border-2 border-dashed border-border/60 flex flex-col items-center justify-center cursor-pointer hover:border-rose-400/60 transition-colors shrink-0">
                <ImageIcon className="size-5 text-muted-foreground" />
                <span className="text-[10px] text-muted-foreground mt-0.5">添加图片</span>
                <input type="file" accept="image/*" multiple className="hidden" onChange={handleFiles} />
              </label>
            </div>
          </div>

          {/* 文字 */}
          <div>
            <p className="text-sm font-medium mb-1">描述</p>
            <Textarea
              placeholder="分享你的美甲心得..."
              rows={3}
              value={content}
              onChange={e => setContent(e.target.value)}
            />
          </div>

          {/* 标签 */}
          <div>
            <p className="text-sm font-medium mb-1">标签（逗号分隔）</p>
            <Input
              placeholder="如: 猫眼, 渐变, 法式"
              value={tags}
              onChange={e => setTags(e.target.value)}
            />
          </div>

          <Button
            onClick={handleSubmit}
            disabled={files.length === 0 || createMut.isPending}
            className="w-full bg-rose-500 hover:bg-rose-600 text-white"
          >
            {createMut.isPending ? "发布中..." : "发布"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/* ═══════════════════════════════════════════════════════════
   帖子卡片（2列瀑布流）
   ═══════════════════════════════════════════════════════════ */
function PostCard({ post }: { post: PostOut }) {
  const cover = post.images[0];
  return (
    <Link
      href={`/workspace/nail/community/${post.id}`}
      className="group block rounded-xl overflow-hidden border border-border/60 bg-card hover:shadow-md transition-all"
    >
      {cover ? (
        <div className="aspect-[3/4] overflow-hidden bg-muted/30">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={cover.url}
            alt=""
            className="size-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
          />
        </div>
      ) : (
        <div className="aspect-[3/4] bg-muted/20 flex items-center justify-center text-muted-foreground text-xs">
          无图片
        </div>
      )}
      <div className="p-2.5 space-y-1.5">
        {post.content && (
          <p className="text-xs text-foreground/80 leading-relaxed line-clamp-2">
            {post.content}
          </p>
        )}
        {post.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {post.tags.slice(0, 3).map((t, i) => (
              <span key={i} className="text-[10px] px-1.5 py-0.5 rounded-full bg-rose-50 text-rose-600 dark:bg-rose-950 dark:text-rose-400">
                #{t}
              </span>
            ))}
          </div>
        )}
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground pt-0.5">
          <span className="flex items-center gap-1">
            <HeartIcon className={cn("size-3", post.is_liked && "fill-rose-500 text-rose-500")} />
            {post.like_count}
          </span>
          <span className="flex items-center gap-1">
            <MessageCircleIcon className="size-3" />
            {post.comment_count}
          </span>
        </div>
      </div>
    </Link>
  );
}

/* ═══════════════════════════════════════════════════════════
   社区主页
   ═══════════════════════════════════════════════════════════ */
export default function CommunityPage() {
  const { user } = useAuth();
  const nailRole = (user as any)?.nail_role as NailRole ?? "user";
  const queryClient = useQueryClient();
  const [showDialog, setShowDialog] = useState(false);

  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = (() => {
    // infinite query via simple pagination
    const d = useQuery({
      queryKey: ["community-posts", 1],
      queryFn: () => listPosts(1, 100),
      staleTime: 30_000,
    });
    return { ...d, fetchNextPage: () => {}, hasNextPage: false, isFetchingNextPage: false };
  })();

  const posts = data?.posts ?? [];
  const isLoading_ = isLoading;

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
            <BreadcrumbItem><BreadcrumbPage>美甲社区</BreadcrumbPage></BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <div className="ml-auto flex items-center gap-2">
          <Button size="sm" onClick={() => setShowDialog(true)} className="h-7 text-xs gap-1 bg-rose-500 hover:bg-rose-600 text-white">
            <PlusIcon className="size-3" /> 发帖
          </Button>
          <Badge variant="outline" className={cn("text-[10px]", nailRole === "dev" && "border-blue-400/40 text-blue-400")}>
            {nailRole === "dev" ? "⚡ Dev" : nailRole === "ops" ? "📊 Ops" : "💅 User"}
          </Badge>
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-6xl px-4 py-6 space-y-4">
          {/* 标题 */}
          <div className="space-y-1">
            <h1 className="text-xl font-semibold tracking-tight">美甲社区</h1>
            <p className="text-sm text-muted-foreground">发现美甲灵感，分享你的美甲故事</p>
          </div>

          {/* 瀑布流卡片 */}
          {isLoading_ ? (
            <div className="grid grid-cols-4 gap-3">
              {[1, 2, 3, 4, 5, 6, 7, 8].map(i => (
                <Skeleton key={i} className="aspect-[3/4] rounded-xl" />
              ))}
            </div>
          ) : posts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
              <p className="text-4xl mb-3">💅</p>
              <p className="text-sm">暂无帖子，快来发布第一篇吧</p>
            </div>
          ) : (
            <div className="grid grid-cols-4 gap-3">
              {posts.map(p => <PostCard key={p.id} post={p} />)}
            </div>
          )}

          <div className="h-4" />
        </div>
      </ScrollArea>

      <CreatePostDialog
        open={showDialog}
        onClose={() => setShowDialog(false)}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ["community-posts"] })}
      />
    </div>
  );
}
