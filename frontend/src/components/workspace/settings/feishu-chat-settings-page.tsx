"use client";

import { useState } from "react";
import { PlusIcon, Trash2Icon, RefreshCwIcon, CheckCircleIcon, XCircleIcon, SendIcon, HelpCircleIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { SettingsSection } from "./settings-section";
import {
  useFeishuChat,
  useUpdateFeishuChat,
  useXhsConfig,
  useUpdateXhsConfig,
  useProactiveChats,
  useUpdateProactiveChats,
} from "@/core/feishu-chat";
import { useTriggerOpsJob } from "@/core/ops-channel";
import type { ProactiveChatItem } from "@/core/feishu-chat/types";

/* ── 触发结果展示 ── */
function TriggerBadge({ result }: { result: { text: string; ok?: boolean } }) {
  return (
    <span className={`inline-flex items-center gap-1 text-xs ${result.ok === false ? "text-red-500" : "text-green-600"}`}>
      {result.ok === false ? <XCircleIcon className="size-3" /> : <CheckCircleIcon className="size-3" />}
      {result.text}
    </span>
  );
}

/* ── 飞书双向对话配置 ── */
function FeishuChatSection() {
  const { data, isLoading } = useFeishuChat();
  const updateCfg = useUpdateFeishuChat();

  if (isLoading) return <Skeleton className="h-32 w-full rounded-xl" />;

  const cfg = data?.config;
  const up = (patch: Record<string, unknown>) => updateCfg.mutate(patch as never);

  return (
    <div className="rounded-xl border border-border/60 bg-card px-4 py-3 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-sm font-semibold">飞书双向对话</span>
          <Badge variant="outline" className="ml-2 text-[10px]">WebSocket</Badge>
        </div>
        <Switch
          checked={cfg?.enabled ?? false}
          disabled={updateCfg.isPending}
          onCheckedChange={(v) => up({ enabled: v })}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        启用后，飞书群成员 @机器人 即可与 AI 运营助手实时对话。需在飞书开发者后台创建应用。
      </p>

      <div className="grid gap-2 sm:grid-cols-2">
        <div>
          <label className="text-xs text-muted-foreground">App ID</label>
          <Input
            className="mt-1 h-8 font-mono text-xs"
            placeholder="cli_xxxxxxxx"
            value={cfg?.app_id ?? ""}
            onChange={(e) => up({ app_id: e.target.value })}
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground">App Secret</label>
          <Input
            className="mt-1 h-8 font-mono text-xs"
            type="password"
            placeholder="••••••••"
            value={cfg?.app_secret ?? ""}
            onChange={(e) => up({ app_secret: e.target.value })}
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <label className="text-xs text-muted-foreground">仅响应 @机器人:</label>
        <Switch
          checked={cfg?.mention_only ?? true}
          disabled={updateCfg.isPending}
          onCheckedChange={(v) => up({ mention_only: v })}
        />
      </div>

      {/* 保存状态 */}
      {updateCfg.isPending && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <RefreshCwIcon className="size-3 animate-spin" /> 保存中...
        </div>
      )}
    </div>
  );
}

/* ── 定时主动聊天列表 ── */
function ProactiveChatsSection() {
  const { data, isLoading } = useProactiveChats();
  const updateChats = useUpdateProactiveChats();
  const [editing, setEditing] = useState<ProactiveChatItem | null>(null);
  const [showForm, setShowForm] = useState(false);

  if (isLoading) return <Skeleton className="h-24 w-full rounded-xl" />;

  const chats: ProactiveChatItem[] = data?.proactive_chats ?? [];

  const save = (items: ProactiveChatItem[]) => {
    updateChats.mutate({ proactive_chats: items });
  };

  const handleAdd = () => {
    const newItem: ProactiveChatItem = {
      id: `chat_${Date.now()}`,
      enabled: true,
      schedule: "0 9 * * *",
      prompt: "",
      targets: [{ channel: "feishu", chat_id: "" }],
    };
    setEditing(newItem);
    setShowForm(true);
  };

  const handleSave = () => {
    if (!editing) return;
    const exists = chats.findIndex((c) => c.id === editing.id);
    const updated = exists >= 0
      ? chats.map((c) => (c.id === editing.id ? editing : c))
      : [...chats, editing];
    save(updated);
    setShowForm(false);
    setEditing(null);
  };

  const handleDelete = (id: string) => {
    save(chats.filter((c) => c.id !== id));
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-sm font-semibold">定时主动聊天</span>
          <Badge variant="outline" className="ml-2 text-[10px]">proactive_chat</Badge>
        </div>
        <Button size="sm" variant="outline" className="h-7 text-xs" onClick={handleAdd}>
          <PlusIcon className="size-3" /> 添加
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        设置定时任务，AI 在指定时间主动向飞书群发送消息（如每日运营早报），群成员可继续追问。
      </p>

      {chats.length === 0 && !showForm && (
        <div className="rounded-lg border border-dashed px-4 py-6 text-center text-xs text-muted-foreground">
          暂无定时聊天任务，点击"添加"创建
        </div>
      )}

      {chats.map((chat) => (
        <div key={chat.id} className="rounded-lg border border-border/60 bg-muted/10 px-3 py-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">{chat.id}</span>
              <Switch
                checked={chat.enabled}
                onCheckedChange={(v) =>
                  save(chats.map((c) => (c.id === chat.id ? { ...c, enabled: v } : c)))
                }
              />
            </div>
            <div className="flex items-center gap-1">
              <Button
                size="sm" variant="ghost" className="h-6 px-1.5 text-xs"
                onClick={() => { setEditing({ ...chat }); setShowForm(true); }}
              >
                编辑
              </Button>
              <Button
                size="sm" variant="ghost" className="h-6 px-1.5 text-xs text-red-500"
                onClick={() => handleDelete(chat.id)}
              >
                <Trash2Icon className="size-3" />
              </Button>
            </div>
          </div>
          <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
            <span>cron: <code className="bg-muted/60 px-1 rounded">{chat.schedule}</code></span>
            <span>目标: {chat.targets?.[0]?.chat_id || <span className="text-red-400">未设置</span>}</span>
          </div>
        </div>
      ))}

      {/* 编辑弹窗 (内联) */}
      {showForm && editing && (
        <div className="rounded-xl border border-rose-200/60 bg-rose-50/30 px-4 py-3 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-rose-700">
              {chats.find((c) => c.id === editing.id) ? "编辑" : "新增"}定时聊天
            </span>
            <Button size="sm" variant="ghost" className="h-6 text-xs" onClick={() => { setShowForm(false); setEditing(null); }}>
              取消
            </Button>
          </div>

          <div className="grid gap-2 sm:grid-cols-3">
            <div>
              <label className="text-xs">任务 ID</label>
              <Input
                className="mt-1 h-8 text-xs"
                value={editing.id}
                onChange={(e) => setEditing({ ...editing, id: e.target.value })}
              />
            </div>
            <div>
              <label className="text-xs">Cron 表达式</label>
              <Input
                className="mt-1 h-8 font-mono text-xs"
                placeholder="0 9 * * *"
                value={editing.schedule}
                onChange={(e) => setEditing({ ...editing, schedule: e.target.value })}
              />
            </div>
            <div>
              <label className="text-xs">飞书群 ID (chat_id)</label>
              <Input
                className="mt-1 h-8 font-mono text-xs"
                placeholder="oc_xxxxxxxx"
                value={editing.targets?.[0]?.chat_id ?? ""}
                onChange={(e) => setEditing({
                  ...editing,
                  targets: [{ channel: "feishu", chat_id: e.target.value }],
                })}
              />
            </div>
          </div>

          <div>
            <label className="text-xs">Prompt (AI 将在定时触发时以这段文字作为第一条消息)</label>
            <Textarea
              className="mt-1 text-xs"
              rows={4}
              placeholder="请生成今日运营早报：分析近24小时趋势信号，识别新增爆款和异常波动..."
              value={editing.prompt}
              onChange={(e) => setEditing({ ...editing, prompt: e.target.value })}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Switch
                checked={editing.enabled}
                onCheckedChange={(v) => setEditing({ ...editing, enabled: v })}
              />
              <span className="text-xs text-muted-foreground">启用</span>
            </div>
            <Button size="sm" className="h-8 text-xs bg-rose-500 hover:bg-rose-600" onClick={handleSave}>
              <CheckCircleIcon className="size-3" /> 保存
            </Button>
          </div>
        </div>
      )}

      {updateChats.isPending && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <RefreshCwIcon className="size-3 animate-spin" /> 保存中...
        </div>
      )}
    </div>
  );
}

/* ── 小红书配置 ── */
function XhsConfigSection() {
  const { data, isLoading } = useXhsConfig();
  const updateCfg = useUpdateXhsConfig();

  if (isLoading) return <Skeleton className="h-24 w-full rounded-xl" />;

  const cfg = data?.config;
  const up = (patch: Record<string, unknown>) => updateCfg.mutate(patch as never);

  return (
    <div className="rounded-xl border border-border/60 bg-card px-4 py-3 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-sm font-semibold">小红书数据</span>
          <Badge variant="outline" className="ml-2 text-[10px]">XHS</Badge>
        </div>
        <Switch
          checked={cfg?.enabled ?? false}
          disabled={updateCfg.isPending}
          onCheckedChange={(v) => up({ enabled: v })}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        启用后，AI 运营助手可搜索小红书美甲帖子补充外部趋势数据。需填写小红书 Cookie（从浏览器开发者工具获取）。
      </p>
      <div>
        <label className="text-xs text-muted-foreground">Cookie (可选，不填则仅用搜索引擎摘要)</label>
        <Input
          className="mt-1 h-8 font-mono text-xs"
          placeholder="abRequestId=xxx; a1=xxx; webId=xxx; ..."
          value={cfg?.cookie ?? ""}
          onChange={(e) => up({ cookie: e.target.value })}
        />
        <p className="mt-1 text-[11px] text-muted-foreground">
          打开 xiaohongshu.com → F12 → Application → Cookies → 复制所有 cookie
        </p>
      </div>

      {updateCfg.isPending && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <RefreshCwIcon className="size-3 animate-spin" /> 保存中...
        </div>
      )}
    </div>
  );
}

/* ── 快速测试 ── */
function TestFeishuSection() {
  const [result, setResult] = useState<{ text: string; ok?: boolean } | null>(null);
  const triggerJob = useTriggerOpsJob();

  const handleTest = async () => {
    setResult({ text: "测试中..." });
    try {
      const res = await triggerJob.mutateAsync({ jobId: "daily_report" });
      setResult({ text: res.ok ? "测试执行成功" : "执行失败", ok: res.ok });
    } catch (e) {
      setResult({ text: `失败: ${(e as Error).message}`, ok: false });
    }
  };

  return (
    <div className="rounded-xl border border-border/60 bg-card px-4 py-3 space-y-2">
      <div>
        <span className="text-sm font-semibold">快速测试</span>
        <Badge variant="outline" className="ml-2 text-[10px]">test</Badge>
      </div>
      <p className="text-xs text-muted-foreground">
        手动触发一次日报推送到所有已配置的渠道，验证飞书/WebPush 投递是否正常。
      </p>
      <div className="flex items-center gap-3">
        <Button size="sm" variant="outline" className="text-xs" disabled={triggerJob.isPending} onClick={handleTest}>
          <SendIcon className="size-3" /> 触发日报测试
        </Button>
        {result && <TriggerBadge result={result} />}
      </div>
    </div>
  );
}

/* ── 教程弹窗 ── */
function TutorialDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>飞书双向对话配置教程</DialogTitle>
          <DialogDescription>按步骤操作，10 分钟完成配置</DialogDescription>
        </DialogHeader>

        <div className="space-y-6 text-sm">
          {/* Step 1 */}
          <div>
            <h4 className="font-semibold text-foreground">第一步：创建飞书应用</h4>
            <ol className="mt-2 space-y-2 text-muted-foreground list-decimal pl-4">
              <li>打开 <a href="https://open.feishu.cn" target="_blank" rel="noopener noreferrer" className="text-blue-500 underline">飞书开发者后台</a> → 创建企业自建应用（名称随意，如「美甲运营助手」）</li>
              <li>左侧菜单 →「凭证与基础信息」→ 复制 <strong className="text-foreground">App ID</strong>（cli_xxx）和 <strong className="text-foreground">App Secret</strong></li>
              <li>左侧菜单 →「应用能力」→「机器人」→ 开启「启用机器人」</li>
            </ol>
          </div>

          {/* Step 2 */}
          <div>
            <h4 className="font-semibold text-foreground">第二步：配置事件与权限</h4>
            <ol className="mt-2 space-y-2 text-muted-foreground list-decimal pl-4">
              <li>左侧菜单 →「事件订阅」→ 订阅事件：搜索 <code className="bg-muted px-1 rounded text-xs">im.message.receive_v1</code> 并勾选</li>
              <li>左侧菜单 →「权限管理」→ 搜索并开通：
                <ul className="mt-1 ml-4 space-y-1 list-disc">
                  <li><code className="bg-muted px-1 rounded text-xs">im:message</code> — 获取消息</li>
                  <li><code className="bg-muted px-1 rounded text-xs">im:message:send_as_bot</code> — 以机器人身份发消息</li>
                  <li><code className="bg-muted px-1 rounded text-xs">im:chat</code> — 获取群信息</li>
                </ul>
              </li>
            </ol>
          </div>

          {/* Step 3 */}
          <div>
            <h4 className="font-semibold text-foreground">第三步：发布应用</h4>
            <ol className="mt-2 space-y-2 text-muted-foreground list-decimal pl-4">
              <li>左侧菜单 →「版本管理与发布」→「创建版本」→ 填写版本号（如 1.0.0）→ 保存</li>
              <li>点击「申请发布」→ 飞书管理员审批通过（你自己的企业通常秒批）</li>
              <li>飞书客户端 → 目标群 → 群设置 → 群机器人 → 添加机器人 → 搜索你的应用名 → 添加</li>
            </ol>
          </div>

          {/* Step 4 */}
          <div>
            <h4 className="font-semibold text-foreground">第四步：填写本页配置</h4>
            <ol className="mt-2 space-y-2 text-muted-foreground list-decimal pl-4">
              <li>打开「飞书双向对话」开关，填入 App ID 和 App Secret</li>
              <li>在项目根目录 <code className="bg-muted px-1 rounded text-xs">.env</code> 文件中设置环境变量：
                <pre className="mt-1 bg-muted/60 rounded-md p-2 text-xs font-mono">FEISHU_APP_ID=cli_xxxxxxxx{"\n"}FEISHU_APP_SECRET=你的AppSecret</pre>
              </li>
              <li>重启后端服务，看到日志 <code className="bg-muted px-1 rounded text-xs">FeishuMonitor started</code> 即成功</li>
            </ol>
          </div>

          {/* Step 5 */}
          <div>
            <h4 className="font-semibold text-foreground">第五步：测试</h4>
            <ol className="mt-2 space-y-2 text-muted-foreground list-decimal pl-4">
              <li>在配置了机器人的飞书群里 @机器人 发消息</li>
              <li>例如：<code className="bg-muted px-1 rounded text-xs">@美甲运营助手 最近7天什么款式最火？</code></li>
              <li>机器人会自动调用趋势分析工具并回复结果</li>
            </ol>
          </div>

          {/* 定时聊天 */}
          <div>
            <h4 className="font-semibold text-foreground">定时主动聊天</h4>
            <ol className="mt-2 space-y-2 text-muted-foreground list-decimal pl-4">
              <li>在「定时主动聊天」区域点「添加」</li>
              <li>填写 cron 表达式（如 <code className="bg-muted px-1 rounded text-xs">0 9 * * *</code> 表示每天 9:00）</li>
              <li>飞书群 ID 获取方法：飞书客户端 → 群设置 → 群信息 → 复制群 ID</li>
              <li>填写 Prompt（AI 在定时触发时发送的第一条消息内容）</li>
            </ol>
          </div>

          {/* 小红书 */}
          <div>
            <h4 className="font-semibold text-foreground">小红书搜索</h4>
            <ol className="mt-2 space-y-2 text-muted-foreground list-decimal pl-4">
              <li>打开开关，填入小红书 Cookie</li>
              <li>获取方法：浏览器打开 xiaohongshu.com → F12 → Application → Cookies → 复制全部 cookie 值</li>
              <li>不填 Cookie 也可使用（仅用搜索引擎摘要，数据较粗）</li>
              <li>Agent 在做趋势分析时会自动调用 <code className="bg-muted px-1 rounded text-xs">xiaohongshu_search_tool</code></li>
            </ol>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/* ── 主入口 ── */
export function FeishuChatSettingsPage() {
  const { error: feishuErr } = useFeishuChat();
  const { error: xhsErr } = useXhsConfig();
  const { error: chatErr } = useProactiveChats();
  const [tutorialOpen, setTutorialOpen] = useState(false);

  const errs = [feishuErr, xhsErr, chatErr].filter(Boolean);
  if (errs.length > 0) {
    return (
      <SettingsSection title="飞书对话与数据" description="双向对话 + 定时主动聊天 + 小红书">
        <div className="flex items-center gap-2 text-sm text-red-500">
          <XCircleIcon className="size-4" />
          加载失败: {errs.map((e) => (e as Error).message).join(", ")}
        </div>
      </SettingsSection>
    );
  }

  return (
    <div className="space-y-6">
      <SettingsSection
        title="飞书对话与数据"
        description="飞书双向 AI 对话、定时主动聊天、小红书搜索配置"
        rightAction={
          <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setTutorialOpen(true)}>
            <HelpCircleIcon className="size-4" />
            配置教程
          </Button>
        }
      >
        <TutorialDialog open={tutorialOpen} onOpenChange={setTutorialOpen} />
        <div className="space-y-4">
          <FeishuChatSection />
          <ProactiveChatsSection />
          <XhsConfigSection />
          <TestFeishuSection />
        </div>
      </SettingsSection>
    </div>
  );
}
