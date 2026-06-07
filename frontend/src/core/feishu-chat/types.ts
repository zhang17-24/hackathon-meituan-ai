// frontend/src/core/feishu-chat/types.ts

export interface FeishuChatConfig {
  enabled: boolean;
  app_id: string;
  app_secret: string;
  mention_only: boolean;
}

export interface FeishuChatResponse {
  config: FeishuChatConfig;
  message: string;
}

export interface FeishuChatUpdate {
  enabled?: boolean;
  app_id?: string;
  app_secret?: string;
  mention_only?: boolean;
}

export interface XhsConfig {
  enabled: boolean;
  cookie: string;
}

export interface XhsConfigResponse {
  config: XhsConfig;
  message: string;
}

export interface XhsConfigUpdate {
  enabled?: boolean;
  cookie?: string;
}

export interface ProactiveChatTarget {
  channel: string;
  chat_id: string;
}

export interface ProactiveChatItem {
  id: string;
  enabled: boolean;
  schedule: string;
  prompt: string;
  targets: ProactiveChatTarget[];
}

export interface ProactiveChatsResponse {
  proactive_chats: ProactiveChatItem[];
  message: string;
}

export interface ProactiveChatsUpdate {
  proactive_chats: ProactiveChatItem[];
}
