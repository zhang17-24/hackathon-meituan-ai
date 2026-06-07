// frontend/src/core/feishu-chat/api.ts
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type {
  FeishuChatResponse,
  FeishuChatUpdate,
  XhsConfigResponse,
  XhsConfigUpdate,
  ProactiveChatsResponse,
  ProactiveChatsUpdate,
} from "./types";

const base = () => `${getBackendBaseURL()}/api/nail/config`;

export async function getFeishuChatConfig(): Promise<FeishuChatResponse> {
  const res = await fetch(`${base()}/feishu-chat`);
  if (!res.ok) throw new Error("读取飞书配置失败");
  return res.json() as Promise<FeishuChatResponse>;
}

export async function updateFeishuChatConfig(
  body: FeishuChatUpdate,
): Promise<FeishuChatResponse> {
  const res = await fetch(`${base()}/feishu-chat`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("更新飞书配置失败");
  return res.json() as Promise<FeishuChatResponse>;
}

export async function getXhsConfig(): Promise<XhsConfigResponse> {
  const res = await fetch(`${base()}/xiaohongshu`);
  if (!res.ok) throw new Error("读取小红书配置失败");
  return res.json() as Promise<XhsConfigResponse>;
}

export async function updateXhsConfig(
  body: XhsConfigUpdate,
): Promise<XhsConfigResponse> {
  const res = await fetch(`${base()}/xiaohongshu`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("更新小红书配置失败");
  return res.json() as Promise<XhsConfigResponse>;
}

export async function getProactiveChats(): Promise<ProactiveChatsResponse> {
  const res = await fetch(`${base()}/proactive-chats`);
  if (!res.ok) throw new Error("读取定时聊天配置失败");
  return res.json() as Promise<ProactiveChatsResponse>;
}

export async function updateProactiveChats(
  body: ProactiveChatsUpdate,
): Promise<ProactiveChatsResponse> {
  const res = await fetch(`${base()}/proactive-chats`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("更新定时聊天配置失败");
  return res.json() as Promise<ProactiveChatsResponse>;
}
