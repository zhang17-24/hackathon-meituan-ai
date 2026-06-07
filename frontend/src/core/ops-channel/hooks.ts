// frontend/src/core/ops-channel/hooks.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import * as api from "./api";
import type { OpsChannelUpdate } from "./types";

export const OPS_CHANNEL_KEY = ["nail-ops-channel"] as const;

export function useOpsChannel() {
  return useQuery({
    queryKey: OPS_CHANNEL_KEY,
    queryFn: api.getOpsChannelConfig,
    refetchOnWindowFocus: false,
  });
}

export function useUpdateOpsChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OpsChannelUpdate) => api.updateOpsChannelConfig(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: OPS_CHANNEL_KEY });
    },
  });
}

export function useTriggerOpsJob() {
  return useMutation({
    mutationFn: ({
      jobId,
      context,
    }: {
      jobId: string;
      context?: Record<string, unknown>;
    }) => api.triggerOpsJob(jobId, context),
  });
}
