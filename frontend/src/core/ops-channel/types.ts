// frontend/src/core/ops-channel/types.ts

export interface OpsChannelConfig {
  enabled: boolean;
  timezone: string;
  jobs: {
    daily_report?: {
      enabled: boolean;
      schedule: string;
    };
    trend_alert?: {
      enabled: boolean;
      threshold: number;
    };
  };
  delivery: {
    channels: {
      feishu?: {
        adapter: string;
        enabled: boolean;
        config: {
          webhook_url: string;
        };
      };
      web_push?: {
        adapter: string;
        enabled: boolean;
        config: Record<string, unknown>;
      };
      [key: string]: OpsChannelEntry | undefined;
    };
  };
  sessions?: {
    ttl_minutes: number;
    max_per_channel: number;
  };
}

export interface OpsChannelEntry {
  adapter: string;
  enabled: boolean;
  config: Record<string, unknown>;
}

export interface OpsChannelResponse {
  config: OpsChannelConfig;
  message: string;
}

export interface OpsTriggerResponse {
  message: string;
  job_id: string;
  ok: boolean;
  result: {
    task_ok: boolean;
    task_error: string;
    deliveries: Record<string, { ok: boolean; error: string }>;
    result_data: Record<string, unknown>;
  };
}

export interface OpsChannelUpdate {
  enabled?: boolean;
  timezone?: string;
  jobs?: Record<string, unknown>;
  delivery?: Record<string, unknown>;
  sessions?: Record<string, unknown>;
}
