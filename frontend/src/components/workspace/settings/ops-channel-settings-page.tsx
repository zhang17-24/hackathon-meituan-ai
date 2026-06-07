"use client";

import { useState } from "react";
import { SendIcon, RefreshCwIcon, CheckCircleIcon, XCircleIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { SettingsSection } from "./settings-section";
import { useOpsChannel, useUpdateOpsChannel, useTriggerOpsJob } from "@/core/ops-channel";

type TriggerResult = {
  text: string;
  ok?: boolean;
  deliveries?: Record<string, { ok: boolean; error: string }>;
};

function TriggerResultDisplay({ result }: { result: TriggerResult }) {
  return (
    <div className="mt-2 space-y-1 rounded-lg border border-pink-100/60 bg-pink-50/30 px-3 py-2">
      <div className={`flex items-center gap-1.5 text-xs font-medium ${result.ok === false ? "text-red-500" : "text-green-600"}`}>
        {result.ok === false ? <XCircleIcon className="size-3" /> : <CheckCircleIcon className="size-3" />}
        {result.text}
      </div>
      {result.deliveries && Object.keys(result.deliveries).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(result.deliveries).map(([ch, d]) => (
            <Badge key={ch} variant="outline" className={`text-[10px] ${d.ok ? "border-green-300 text-green-700" : "border-red-300 text-red-700"}`}>
              {ch}: {d.ok ? "✓" : "✗"} {d.error ? `(${d.error})` : ""}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

export function OpsChannelSettingsPage() {
  const { data, isLoading, error } = useOpsChannel();
  const updateCfg = useUpdateOpsChannel();
  const triggerJob = useTriggerOpsJob();
  const [triggerResults, setTriggerResults] = useState<Record<string, {
    text: string;
    ok?: boolean;
    deliveries?: Record<string, { ok: boolean; error: string }>;
  }>>({});

  if (isLoading) {
    return (
      <div className="space-y-6">
        <SettingsSection title="运营通道配置" description="NailOps Channel 龙虾化推送系统">
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-16 w-full rounded-xl" />
            ))}
          </div>
        </SettingsSection>
      </div>
    );
  }

  if (error) {
    return (
      <SettingsSection title="运营通道配置" description="NailOps Channel 龙虾化推送系统">
        <div className="flex items-center gap-2 text-sm text-red-500">
          <XCircleIcon className="size-4" />
          加载失败: {(error as Error).message}
        </div>
      </SettingsSection>
    );
  }

  const cfg = data?.config;
  if (!cfg) return null;

  const masterEnabled = cfg.enabled ?? true;
  const timezone = cfg.timezone ?? "Asia/Shanghai";
  const dailyJob = cfg.jobs?.daily_report;
  const alertJob = cfg.jobs?.trend_alert;
  const feishu = cfg.delivery?.channels?.feishu;
  const webPush = cfg.delivery?.channels?.web_push;

  const up = (patch: Record<string, unknown>) => {
    updateCfg.mutate(patch as never);
  };

  const handleTrigger = async (jobId: string) => {
    setTriggerResults((p) => ({ ...p, [jobId]: { text: "执行中..." } }));
    try {
      const res = await triggerJob.mutateAsync({ jobId });
      const deliveries = res.result?.deliveries ?? {};
      setTriggerResults((p) => ({
        ...p,
        [jobId]: {
          text: res.ok ? "执行成功" : "执行失败",
          ok: res.ok,
          deliveries,
        },
      }));
    } catch (e) {
      setTriggerResults((p) => ({
        ...p,
        [jobId]: { text: `失败: ${(e as Error).message}`, ok: false },
      }));
    }
  };

  return (
    <div className="space-y-6">
      {/* ── 基本设置 ── */}
      <SettingsSection title="📡 运营通道配置" description="定时日报、爆款告警等推送渠道设置">
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-xl border border-pink-100/60 bg-pink-50/40 px-4 py-3">
            <div>
              <div className="text-sm font-semibold text-[#5b1738]">启用运营通道</div>
              <div className="text-xs text-[#8f7b88]">关闭后所有定时推送暂停</div>
            </div>
            <Switch
              checked={masterEnabled}
              disabled={updateCfg.isPending}
              onCheckedChange={(v) => up({ enabled: v })}
            />
          </div>
        </div>
      </SettingsSection>

      {/* ── 定时任务 ── */}
      <SettingsSection title="⏰ 定时任务" description="配置日报和告警的触发条件">
        <div className="space-y-4">
          {/* daily_report */}
          <div className="rounded-xl border border-pink-100/60 bg-white/60 px-4 py-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-semibold text-[#5b1738]">日报推送</span>
                <Badge variant="outline" className="ml-2 text-[10px]">daily_report</Badge>
              </div>
              <Switch
                checked={dailyJob?.enabled ?? true}
                disabled={updateCfg.isPending}
                onCheckedChange={(v) =>
                  up({ jobs: { daily_report: { enabled: v } } })
                }
              />
            </div>
            <div className="mt-3 flex items-center gap-2">
              <label className="text-xs text-[#8f7b88] shrink-0">Cron:</label>
              <Input
                className="h-7 w-36 font-mono text-xs"
                value={dailyJob?.schedule ?? "0 9 * * *"}
                onChange={(e) =>
                  up({ jobs: { daily_report: { schedule: e.target.value } } })
                }
              />
            </div>
            <div className="mt-3 flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                className="text-xs"
                disabled={triggerJob.isPending}
                onClick={() => handleTrigger("daily_report")}
              >
                <SendIcon className="size-3" />
                立即触发日报
              </Button>
              {triggerResults["daily_report"] && (
                <TriggerResultDisplay result={triggerResults["daily_report"]} />
              )}
            </div>
          </div>

          {/* trend_alert */}
          <div className="rounded-xl border border-pink-100/60 bg-white/60 px-4 py-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-semibold text-[#5b1738]">爆款告警</span>
                <Badge variant="outline" className="ml-2 text-[10px]">trend_alert</Badge>
              </div>
              <Switch
                checked={alertJob?.enabled ?? true}
                disabled={updateCfg.isPending}
                onCheckedChange={(v) =>
                  up({ jobs: { trend_alert: { enabled: v } } })
                }
              />
            </div>
            <div className="mt-3 flex items-center gap-2">
              <label className="text-xs text-[#8f7b88] shrink-0">阈值:</label>
              <Input
                className="h-7 w-24 text-xs"
                type="number"
                step="0.5"
                value={alertJob?.threshold ?? 3.0}
                onChange={(e) =>
                  up({ jobs: { trend_alert: { threshold: Number(e.target.value) } } })
                }
              />
              <span className="text-xs text-[#8f7b88]">倍 (信号超出基线 N 倍时触发)</span>
            </div>
            <div className="mt-3 flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                className="text-xs"
                disabled={triggerJob.isPending}
                onClick={() => handleTrigger("trend_alert")}
              >
                <SendIcon className="size-3" />
                立即触发告警
              </Button>
              {triggerResults["trend_alert"] && (
                <TriggerResultDisplay result={triggerResults["trend_alert"]} />
              )}
            </div>
          </div>
        </div>
      </SettingsSection>

      {/* ── 推送渠道 ── */}
      <SettingsSection title="📨 推送渠道" description="Webhook 地址和渠道开关">
        <div className="space-y-4">
          {/* 飞书 */}
          <div className="rounded-xl border border-pink-100/60 bg-white/60 px-4 py-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-semibold text-[#5b1738]">飞书</span>
                <Badge variant="outline" className="ml-2 text-[10px]">webhook</Badge>
              </div>
              <Switch
                checked={feishu?.enabled ?? false}
                disabled={updateCfg.isPending}
                onCheckedChange={(v) =>
                  up({ delivery: { channels: { feishu: { enabled: v } } } })
                }
              />
            </div>
            <div className="mt-3">
              <label className="text-xs text-[#8f7b88]">Webhook URL:</label>
              <Input
                className="mt-1 h-8 font-mono text-xs"
                placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
                value={feishu?.config?.webhook_url ?? ""}
                onChange={(e) =>
                  up({ delivery: { channels: { feishu: { config: { webhook_url: e.target.value } } } } })
                }
              />
              <p className="mt-1 text-[11px] text-[#8f7b88]">
                飞书群 → 设置 → 机器人 → 添加自定义机器人 → 复制 Webhook 地址
              </p>
            </div>
          </div>

          {/* WebPush */}
          <div className="rounded-xl border border-pink-100/60 bg-white/60 px-4 py-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-semibold text-[#5b1738]">Web 看板</span>
                <Badge variant="outline" className="ml-2 text-[10px]">web_push</Badge>
              </div>
              <div className="flex items-center gap-2">
                {webPush?.enabled !== false ? (
                  <Badge variant="default" className="bg-green-500 text-[10px]">已启用</Badge>
                ) : (
                  <Badge variant="outline" className="text-[10px]">已禁用</Badge>
                )}
              </div>
            </div>
            <p className="mt-2 text-xs text-[#8f7b88]">
              推送消息存入内存队列，运营看板可实时拉取。无需额外配置。
            </p>
          </div>
        </div>
      </SettingsSection>

      {/* ── 保存状态 ── */}
      {updateCfg.isPending && (
        <div className="flex items-center gap-2 text-sm text-pink-600">
          <RefreshCwIcon className="size-4 animate-spin" />
          保存中...
        </div>
      )}
      {updateCfg.isSuccess && !updateCfg.isPending && (
        <div className="flex items-center gap-2 text-sm text-green-600">
          <CheckCircleIcon className="size-4" />
          配置已保存 (config.yaml 已更新)
        </div>
      )}
      {updateCfg.isError && (
        <div className="flex items-center gap-2 text-sm text-red-500">
          <XCircleIcon className="size-4" />
          保存失败: {(updateCfg.error as Error).message}
        </div>
      )}
    </div>
  );
}
