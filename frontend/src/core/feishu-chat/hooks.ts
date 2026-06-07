// frontend/src/core/feishu-chat/hooks.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import * as api from "./api";
import type { FeishuChatUpdate, XhsConfigUpdate, ProactiveChatsUpdate } from "./types";

const FEISHU_CHAT_KEY = ["nail-feishu-chat"] as const;
const XHS_KEY = ["nail-xiaohongshu"] as const;
const PROACTIVE_CHATS_KEY = ["nail-proactive-chats"] as const;

export function useFeishuChat() {
  return useQuery({
    queryKey: FEISHU_CHAT_KEY,
    queryFn: api.getFeishuChatConfig,
    refetchOnWindowFocus: false,
  });
}

export function useUpdateFeishuChat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: FeishuChatUpdate) => api.updateFeishuChatConfig(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: FEISHU_CHAT_KEY });
    },
  });
}

export function useXhsConfig() {
  return useQuery({
    queryKey: XHS_KEY,
    queryFn: api.getXhsConfig,
    refetchOnWindowFocus: false,
  });
}

export function useUpdateXhsConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: XhsConfigUpdate) => api.updateXhsConfig(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: XHS_KEY });
    },
  });
}

export function useProactiveChats() {
  return useQuery({
    queryKey: PROACTIVE_CHATS_KEY,
    queryFn: api.getProactiveChats,
    refetchOnWindowFocus: false,
  });
}

export function useUpdateProactiveChats() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProactiveChatsUpdate) => api.updateProactiveChats(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: PROACTIVE_CHATS_KEY });
    },
  });
}
