import { fetch as apiFetch } from "@/core/api/fetcher";

export interface PageModeConfig {
  title: string;
  subtitle: string;
  suggestions: string[];
}

export async function fetchPageModeConfig(mode: string): Promise<PageModeConfig> {
  const res = await apiFetch(`/api/nail/config/page-mode/${mode}`);
  if (!res.ok) throw new Error("加载页面配置失败");
  return res.json();
}
