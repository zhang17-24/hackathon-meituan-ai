import { fetch as apiFetch } from "@/core/api/fetcher";

export interface DashboardData {
  signals: Array<Record<string, unknown>>;
  proposal_summary: Record<string, number>;
  top_styles: Array<Record<string, unknown>>;
  days: number;
}

export async function fetchDashboard(days = 7): Promise<DashboardData> {
  const res = await apiFetch(`/api/nail/dashboard?days=${days}`);
  if (!res.ok) throw new Error("加载看板失败");
  return res.json();
}

export async function confirmProposal(id: string, status: "approved" | "rejected"): Promise<void> {
  const res = await apiFetch(`/api/nail/proposals/${id}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error("操作失败");
}
