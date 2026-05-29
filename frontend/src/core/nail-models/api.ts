// frontend/src/core/nail-models/api.ts
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import type { NailModelConfig, NailModelCreate, AgentConfigs, ToolsResponse } from "./types";

const base = () => `${getBackendBaseURL()}/api/nail/config`;

export async function listNailModels(): Promise<NailModelConfig[]> {
  const res = await fetch(`${base()}/models`);
  if (!res.ok) throw new Error(`列出模型失败: ${res.statusText}`);
  const data = await res.json();
  return (data.models ?? []) as NailModelConfig[];
}

export async function createNailModel(body: NailModelCreate): Promise<void> {
  const res = await fetch(`${base()}/models`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as Record<string, unknown>;
    throw new Error((err.detail as string) ?? "创建失败");
  }
}

export async function updateNailModel(
  name: string,
  body: Partial<NailModelCreate> & { is_active?: boolean },
): Promise<void> {
  const res = await fetch(`${base()}/models/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as Record<string, unknown>;
    throw new Error((err.detail as string) ?? "更新失败");
  }
}

export async function deleteNailModel(name: string): Promise<void> {
  const res = await fetch(`${base()}/models/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("删除失败");
}

export async function getAgentConfigs(): Promise<AgentConfigs> {
  const res = await fetch(`${base()}/agents`);
  if (!res.ok) throw new Error("读取 Agent 配置失败");
  return res.json() as Promise<AgentConfigs>;
}

export async function updateAgentConfigs(configs: Partial<AgentConfigs>): Promise<void> {
  const res = await fetch(`${base()}/agents`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(configs),
  });
  if (!res.ok) throw new Error("更新 Agent 配置失败");
}

export async function listTools(): Promise<ToolsResponse> {
  const res = await fetch(`${base()}/tools`);
  if (!res.ok) throw new Error("读取工具列表失败");
  return res.json() as Promise<ToolsResponse>;
}

export async function updateTool(
  toolName: string,
  body: { model_name?: string | null; is_enabled?: boolean },
): Promise<void> {
  const res = await fetch(`${base()}/tools/${encodeURIComponent(toolName)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("更新工具配置失败");
}
