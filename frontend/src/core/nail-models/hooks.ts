// frontend/src/core/nail-models/hooks.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "./api";
import type { NailModelCreate, AgentConfigs } from "./types";

export const NAIL_MODELS_KEY = ["nail-models"] as const;
export const AGENT_CONFIGS_KEY = ["nail-agent-configs"] as const;
export const TOOLS_KEY = ["nail-tools"] as const;
// 与 DeerFlow 的 useModels() 共用同一 queryKey，更新时双向失效
export const ALL_MODELS_KEY = ["models"] as const;

export function useNailModels() {
  return useQuery({
    queryKey: NAIL_MODELS_KEY,
    queryFn: api.listNailModels,
    refetchOnWindowFocus: false,
  });
}

export function useAgentConfigs() {
  return useQuery({
    queryKey: AGENT_CONFIGS_KEY,
    queryFn: api.getAgentConfigs,
    refetchOnWindowFocus: false,
  });
}

export function useTools() {
  return useQuery({
    queryKey: TOOLS_KEY,
    queryFn: api.listTools,
    refetchOnWindowFocus: false,
  });
}

export function useCreateNailModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: NailModelCreate) => api.createNailModel(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: NAIL_MODELS_KEY });
      void qc.invalidateQueries({ queryKey: ALL_MODELS_KEY });
    },
  });
}

export function useUpdateNailModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      name,
      body,
    }: {
      name: string;
      body: Partial<NailModelCreate> & { is_active?: boolean };
    }) => api.updateNailModel(name, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: NAIL_MODELS_KEY });
      void qc.invalidateQueries({ queryKey: ALL_MODELS_KEY });
    },
  });
}

export function useDeleteNailModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.deleteNailModel(name),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: NAIL_MODELS_KEY });
      void qc.invalidateQueries({ queryKey: ALL_MODELS_KEY });
    },
  });
}

export function useUpdateAgentConfigs() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (configs: Partial<AgentConfigs>) => api.updateAgentConfigs(configs),
    onSuccess: () => void qc.invalidateQueries({ queryKey: AGENT_CONFIGS_KEY }),
  });
}

export function useUpdateTool() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: {
      name: string;
      model_name?: string | null;
      is_enabled?: boolean;
      enabled_pages?: string[];
    }) => api.updateTool(args.name, { model_name: args.model_name, is_enabled: args.is_enabled, enabled_pages: args.enabled_pages }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: TOOLS_KEY }),
  });
}
