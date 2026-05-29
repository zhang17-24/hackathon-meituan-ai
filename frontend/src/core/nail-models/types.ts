// frontend/src/core/nail-models/types.ts
export type ModelProvider = "qwen" | "deepseek" | "doubao" | "kimi" | "custom";

export interface NailModelConfig {
  id: string;
  name: string;
  display_name: string;
  provider: ModelProvider;
  model_id: string;
  api_base: string;
  use_class: string;
  supports_vision: boolean;
  supports_thinking: boolean;
  is_active: boolean;
  created_at: string;
  source: "db" | "config";
}

export interface NailModelCreate {
  name: string;
  display_name: string;
  provider: ModelProvider;
  model_id: string;
  api_key?: string;
  api_base: string;
  use_class: string;
  supports_vision: boolean;
  supports_thinking: boolean;
}

export interface AgentConfigs {
  main_agent: string | null;
  tool_default: string | null;
}

export interface ToolInfo {
  name: string;
  display_name: string;
  emoji: string;
  description: string;
  group: string;
  requires_llm: boolean;
  requires_vision: boolean;
  is_enabled: boolean;
  model_override: string | null;
}

export interface ToolsResponse {
  nail_tools: ToolInfo[];
  builtin_tools: ToolInfo[];
}

/** 四大提供商预设配置 */
export const PROVIDER_PRESETS: Record<
  Exclude<ModelProvider, "custom">,
  {
    api_base: string;
    use_class: string;
    models: Array<{ id: string; label: string; vision?: boolean; thinking?: boolean }>;
  }
> = {
  qwen: {
    api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    use_class: "langchain_openai:ChatOpenAI",
    models: [
      { id: "qwen-max", label: "Qwen-Max" },
      { id: "qwen-plus", label: "Qwen-Plus" },
      { id: "qwen-turbo", label: "Qwen-Turbo" },
      { id: "qwen-vl-max", label: "Qwen-VL-Max", vision: true },
    ],
  },
  deepseek: {
    api_base: "https://api.deepseek.com/v1",
    use_class: "langchain_openai:ChatOpenAI",
    models: [
      { id: "deepseek-chat", label: "DeepSeek-Chat" },
      { id: "deepseek-reasoner", label: "DeepSeek-Reasoner", thinking: true },
    ],
  },
  doubao: {
    api_base: "https://ark.cn-beijing.volces.com/api/v3",
    use_class: "deerflow.models.patched_deepseek:PatchedChatDeepSeek",
    models: [
      { id: "doubao-seed-1-8-251228", label: "Doubao-Seed-1.8", vision: true, thinking: true },
      { id: "doubao-pro-32k-241215", label: "Doubao-Pro-32k" },
    ],
  },
  kimi: {
    api_base: "https://api.moonshot.cn/v1",
    use_class: "langchain_openai:ChatOpenAI",
    models: [
      { id: "moonshot-v1-8k", label: "Kimi-8k" },
      { id: "moonshot-v1-32k", label: "Kimi-32k" },
      { id: "moonshot-v1-128k", label: "Kimi-128k" },
    ],
  },
};
