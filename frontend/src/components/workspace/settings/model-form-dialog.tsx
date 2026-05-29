"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  type NailModelCreate,
  type ModelProvider,
  PROVIDER_PRESETS,
} from "@/core/nail-models";
import { cn } from "@/lib/utils";

interface ModelFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (model: NailModelCreate) => Promise<void>;
  initialValues?: Partial<NailModelCreate & { name: string }>;
  title?: string;
}

const PROVIDERS: Array<{ id: ModelProvider; label: string; emoji: string }> = [
  { id: "qwen",     label: "千问 (Qwen)",   emoji: "🟣" },
  { id: "deepseek", label: "DeepSeek",      emoji: "🔵" },
  { id: "doubao",   label: "豆包 (Doubao)", emoji: "🟡" },
  { id: "kimi",     label: "Kimi",          emoji: "🌙" },
  { id: "custom",   label: "自定义",         emoji: "⚙️" },
];

const DEFAULT_FORM: NailModelCreate = {
  name: "",
  display_name: "",
  provider: "qwen",
  model_id: "",
  api_key: "",
  api_base: PROVIDER_PRESETS.qwen.api_base,
  use_class: PROVIDER_PRESETS.qwen.use_class,
  supports_vision: false,
  supports_thinking: false,
};

export function ModelFormDialog({
  open,
  onOpenChange,
  onSave,
  initialValues,
  title = "添加模型",
}: ModelFormDialogProps) {
  const [provider, setProvider] = useState<ModelProvider>(
    initialValues?.provider ?? "qwen",
  );
  const [form, setForm] = useState<NailModelCreate>({
    ...DEFAULT_FORM,
    ...initialValues,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // 重置表单当 dialog 关闭再打开
  useEffect(() => {
    if (open) {
      const p = initialValues?.provider ?? "qwen";
      setProvider(p);
      setForm({ ...DEFAULT_FORM, ...initialValues });
      setError("");
    }
  }, [open, initialValues]);

  // 切换提供商时自动填入 api_base 和 use_class
  useEffect(() => {
    if (provider !== "custom") {
      const preset = PROVIDER_PRESETS[provider];
      setForm((f) => ({
        ...f,
        provider,
        api_base: preset.api_base,
        use_class: preset.use_class,
      }));
    } else {
      setForm((f) => ({ ...f, provider: "custom" }));
    }
  }, [provider]);

  const preset = provider !== "custom" ? PROVIDER_PRESETS[provider] : null;
  const presetModels = preset?.models ?? [];

  const set = <K extends keyof NailModelCreate>(key: K, val: NailModelCreate[K]) =>
    setForm((f) => ({ ...f, [key]: val }));

  const handleSave = async () => {
    if (!form.name.trim()) { setError("名称不能为空"); return; }
    if (!form.display_name.trim()) { setError("显示名称不能为空"); return; }
    if (!form.model_id.trim()) { setError("模型 ID 不能为空"); return; }
    if (!form.api_base.trim()) { setError("API Base URL 不能为空"); return; }
    if (!form.use_class.trim()) { setError("Use Class 不能为空"); return; }
    setSaving(true);
    setError("");
    try {
      await onSave(form);
      onOpenChange(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* 提供商选择 */}
          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              选择提供商
            </p>
            <div className="flex flex-wrap gap-2">
              {PROVIDERS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setProvider(p.id)}
                  className={cn(
                    "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                    provider === p.id
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border text-muted-foreground hover:border-primary/50",
                  )}
                >
                  <span>{p.emoji}</span>
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {/* 名称 */}
            <div className="space-y-1">
              <label className="text-xs font-medium">名称（唯一 ID）</label>
              <Input
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                placeholder="如 qwen-max"
              />
            </div>
            {/* 显示名称 */}
            <div className="space-y-1">
              <label className="text-xs font-medium">显示名称</label>
              <Input
                value={form.display_name}
                onChange={(e) => set("display_name", e.target.value)}
                placeholder="如 通义千问 Max"
              />
            </div>
          </div>

          {/* 模型 ID */}
          <div className="space-y-1">
            <label className="text-xs font-medium">模型 ID</label>
            {presetModels.length > 0 && (
              <div className="mb-1.5 flex flex-wrap gap-1.5">
                {presetModels.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() =>
                      setForm((f) => ({
                        ...f,
                        model_id: m.id,
                        display_name: f.display_name || m.label,
                        name: f.name || m.id,
                        supports_vision: m.vision ?? false,
                        supports_thinking: m.thinking ?? false,
                      }))
                    }
                    className={cn(
                      "rounded border px-2 py-0.5 text-xs transition-colors",
                      form.model_id === m.id
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border text-muted-foreground hover:border-primary/50",
                    )}
                  >
                    {m.label}
                    {m.vision && (
                      <span className="ml-1 text-[10px] text-emerald-500">
                        视觉
                      </span>
                    )}
                    {m.thinking && (
                      <span className="ml-1 text-[10px] text-violet-500">
                        思考
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
            <Input
              value={form.model_id}
              onChange={(e) => set("model_id", e.target.value)}
              placeholder="如 qwen-max"
            />
          </div>

          {/* API Base URL */}
          <div className="space-y-1">
            <label className="text-xs font-medium">API Base URL</label>
            <Input
              value={form.api_base}
              onChange={(e) => set("api_base", e.target.value)}
            />
          </div>

          {/* API Key */}
          <div className="space-y-1">
            <label className="text-xs font-medium">API Key</label>
            <Input
              type="password"
              value={form.api_key ?? ""}
              onChange={(e) => set("api_key", e.target.value)}
              placeholder="sk-..."
            />
          </div>

          {/* Use Class（高级，折叠显示） */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              Use Class（高级）
            </label>
            <Input
              value={form.use_class}
              onChange={(e) => set("use_class", e.target.value)}
              className="font-mono text-xs"
            />
          </div>

          {/* 能力开关 */}
          <div className="flex gap-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <Switch
                checked={form.supports_vision}
                onCheckedChange={(v) => set("supports_vision", v)}
              />
              <span className="text-xs">支持视觉</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <Switch
                checked={form.supports_thinking}
                onCheckedChange={(v) => set("supports_thinking", v)}
              />
              <span className="text-xs">支持思考</span>
            </label>
          </div>

          {error && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {error}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "保存中…" : "保存"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
