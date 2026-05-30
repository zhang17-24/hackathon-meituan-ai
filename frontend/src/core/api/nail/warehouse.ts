import { fetch as apiFetch } from "@/core/api/fetcher";

export interface HandPhoto {
  id: string;
  filename: string;
  url: string;
  created_at: string;
}

export interface StyleImage {
  id: string;
  filename: string;
  url: string;
  category: string;
  source: string;
  tags: string[];
  created_at: string;
}

const W = "/api/nail/warehouse";

export async function listHands(): Promise<HandPhoto[]> {
  const res = await apiFetch(`${W}/hands`);
  if (!res.ok) throw new Error("加载手图失败");
  const d = await res.json();
  return d.hands ?? [];
}

export async function uploadHand(file: File): Promise<HandPhoto> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await apiFetch(`${W}/hands`, { method: "POST", body: fd });
  if (!res.ok) throw new Error("上传手图失败");
  return res.json();
}

export async function deleteHand(id: string): Promise<void> {
  await apiFetch(`${W}/hands/${id}`, { method: "DELETE" });
}

export async function listStyles(): Promise<StyleImage[]> {
  const res = await apiFetch(`${W}/styles`);
  if (!res.ok) throw new Error("加载款式失败");
  const d = await res.json();
  return d.styles ?? [];
}

export async function uploadStyle(file: File): Promise<StyleImage> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("category", "user");
  fd.append("tags", "[]");
  const res = await apiFetch(`${W}/styles`, { method: "POST", body: fd });
  if (!res.ok) throw new Error("上传款式失败");
  return res.json();
}

export async function deleteStyle(id: string): Promise<void> {
  await apiFetch(`${W}/styles/${id}`, { method: "DELETE" });
}
