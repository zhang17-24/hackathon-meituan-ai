import { fetch as apiFetch } from "@/core/api/fetcher";

/* ── 类型 ── */

export interface PostImage {
  id: string;
  url: string;
  sort_order: number;
}

export interface StyleRef {
  name?: string;
  image_path?: string;
  style_id?: string;
}

export interface PostOut {
  id: string;
  user_id: string;
  content: string;
  tags: string[];
  style_refs: StyleRef[];
  images: PostImage[];
  like_count: number;
  comment_count: number;
  is_liked: boolean;
  created_at: string;
  updated_at: string;
}

export interface PostListOut {
  posts: PostOut[];
  page: number;
  size: number;
  total: number;
  has_more: boolean;
}

export interface Comment {
  id: string;
  user_id: string;
  content: string;
  parent_id: string | null;
  created_at: string;
}

export interface CommentListOut {
  comments: Comment[];
  page: number;
  size: number;
  total: number;
  has_more: boolean;
}

export interface LikeToggleOut {
  liked: boolean;
  like_count: number;
}

const C = "/api/community";

/* ── API ── */

export async function listPosts(page = 1, size = 20): Promise<PostListOut> {
  const res = await apiFetch(`${C}/posts?page=${page}&size=${size}`);
  if (!res.ok) throw new Error("加载帖子失败");
  return res.json();
}

export async function getPost(id: string): Promise<PostOut> {
  const res = await apiFetch(`${C}/posts/${id}`);
  if (!res.ok) throw new Error("帖子不存在");
  return res.json();
}

export async function createPost(params: {
  content?: string;
  tags?: string;
  style_refs?: string;
  files?: File[];
}): Promise<{ id: string; message: string }> {
  const fd = new FormData();
  fd.append("content", params.content ?? "");
  fd.append("tags", params.tags ?? "[]");
  fd.append("style_refs", params.style_refs ?? "[]");
  for (const f of params.files ?? []) {
    fd.append("files", f);
  }
  const res = await apiFetch(`${C}/posts`, { method: "POST", body: fd });
  if (!res.ok) throw new Error("发布失败");
  return res.json();
}

export async function deletePost(id: string): Promise<void> {
  const res = await apiFetch(`${C}/posts/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("删除失败");
}

export async function toggleLike(postId: string): Promise<LikeToggleOut> {
  const res = await apiFetch(`${C}/posts/${postId}/like`, { method: "POST" });
  if (!res.ok) throw new Error("操作失败");
  return res.json();
}

export async function listComments(postId: string, page = 1, size = 50): Promise<CommentListOut> {
  const res = await apiFetch(`${C}/posts/${postId}/comments?page=${page}&size=${size}`);
  if (!res.ok) throw new Error("加载评论失败");
  return res.json();
}

export async function createComment(postId: string, content: string, parentId?: string): Promise<Comment> {
  const res = await apiFetch(`${C}/posts/${postId}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, parent_id: parentId ?? null }),
  });
  if (!res.ok) throw new Error("评论失败");
  return res.json();
}
