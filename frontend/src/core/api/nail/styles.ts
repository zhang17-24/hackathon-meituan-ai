import { fetch as apiFetch } from "@/core/api/fetcher";

export interface GalleryStyle {
  id: string;
  name: string;
  url: string;
  filename: string;
}

export async function listGalleryStyles(): Promise<GalleryStyle[]> {
  const res = await apiFetch("/api/nail/styles");
  if (!res.ok) throw new Error("加载款式失败");
  const data = await res.json();
  return data.styles ?? [];
}
