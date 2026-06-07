// frontend/src/core/ops-channel/api.ts
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type { OpsChannelResponse, OpsChannelUpdate, OpsTriggerResponse } from "./types";

const base = () => `${getBackendBaseURL()}/api/nail`;

export async function getOpsChannelConfig(): Promise<OpsChannelResponse> {
  const res = await fetch(`${base()}/config/ops-channel`);
  if (!res.ok) throw new Error(`读取运营通道配置失败: ${res.statusText}`);
  return res.json() as Promise<OpsChannelResponse>;
}

export async function updateOpsChannelConfig(
  body: OpsChannelUpdate,
): Promise<OpsChannelResponse> {
  const res = await fetch(`${base()}/config/ops-channel`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as Record<string, unknown>;
    throw new Error((err.detail as string) ?? "更新失败");
  }
  return res.json() as Promise<OpsChannelResponse>;
}

export async function triggerOpsJob(
  jobId: string,
  context?: Record<string, unknown>,
): Promise<OpsTriggerResponse> {
  const res = await fetch(`${base()}/ops/trigger/${encodeURIComponent(jobId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ context: context ?? {} }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as Record<string, unknown>;
    throw new Error((err.detail as string) ?? "触发失败");
  }
  return res.json() as Promise<OpsTriggerResponse>;
}
