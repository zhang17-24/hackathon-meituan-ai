"use client";

import {
  BellIcon,
  BrainIcon,
  CpuIcon,
  PaletteIcon,
  SparklesIcon,
  UserIcon,
  WrenchIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AccountSettingsPage } from "@/components/workspace/settings/account-settings-page";
import { AppearanceSettingsPage } from "@/components/workspace/settings/appearance-settings-page";
import { MemorySettingsPage } from "@/components/workspace/settings/memory-settings-page";
import { ModelSettingsPage } from "@/components/workspace/settings/model-settings-page";
import { NotificationSettingsPage } from "@/components/workspace/settings/notification-settings-page";
import { SkillSettingsPage } from "@/components/workspace/settings/skill-settings-page";
import { ToolSettingsPage } from "@/components/workspace/settings/tool-settings-page";
import { useI18n } from "@/core/i18n/hooks";
import { cn } from "@/lib/utils";

type SettingsSection =
  | "account"
  | "models"
  | "appearance"
  | "memory"
  | "tools"
  | "skills"
  | "notification";

type SettingsDialogProps = React.ComponentProps<typeof Dialog> & {
  defaultSection?: SettingsSection;
};

export function SettingsDialog(props: SettingsDialogProps) {
  const { defaultSection = "appearance", ...dialogProps } = props;
  const { t } = useI18n();
  const [activeSection, setActiveSection] =
    useState<SettingsSection>(defaultSection);

  useEffect(() => {
    // When opening the dialog, ensure the active section follows the caller's intent.
    // This allows triggers like "About" to open the dialog directly on that page.
    if (dialogProps.open) {
      setActiveSection(defaultSection);
    }
  }, [defaultSection, dialogProps.open]);

  const sections = useMemo(
    () => [
      {
        id: "account",
        label: t.settings.sections.account,
        icon: UserIcon,
      },
      {
        id: "models",
        label: "模型配置",
        icon: CpuIcon,
      },
      {
        id: "appearance",
        label: t.settings.sections.appearance,
        icon: PaletteIcon,
      },
      {
        id: "notification",
        label: t.settings.sections.notification,
        icon: BellIcon,
      },
      {
        id: "memory",
        label: t.settings.sections.memory,
        icon: BrainIcon,
      },
      { id: "tools", label: t.settings.sections.tools, icon: WrenchIcon },
      { id: "skills", label: t.settings.sections.skills, icon: SparklesIcon },
    ],
    [
      t.settings.sections.account,
      t.settings.sections.appearance,
      t.settings.sections.memory,
      t.settings.sections.tools,
      t.settings.sections.skills,
      t.settings.sections.notification,
    ],
  );
  return (
    <Dialog
      {...dialogProps}
      onOpenChange={(open) => props.onOpenChange?.(open)}
    >
      <DialogContent
        className="nail-settings-dialog nail-glass-card flex h-[75vh] max-h-[calc(100vh-2rem)] flex-col rounded-[2rem] border-pink-200/70 p-6 sm:max-w-5xl md:max-w-6xl"
        aria-describedby={undefined}
      >
        <DialogHeader className="gap-1">
          <DialogTitle className="nail-hero-title text-2xl font-extrabold">
            {t.settings.title}
          </DialogTitle>
          <p className="text-sm text-[#8f7b88]">{t.settings.description}</p>
        </DialogHeader>
        <div className="grid min-h-0 flex-1 gap-4 md:grid-cols-[220px_minmax(0,1fr)]">
          <nav className="nail-glass-soft min-h-0 overflow-y-auto rounded-3xl p-3">
            <ul className="space-y-2 pr-1">
              {sections.map(({ id, label, icon: Icon }) => {
                const active = activeSection === id;
                return (
                  <li key={id}>
                    <button
                      type="button"
                      onClick={() => setActiveSection(id as SettingsSection)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-semibold transition-all",
                        active
                          ? "bg-gradient-to-r from-pink-100 to-pink-200/70 text-pink-600 shadow-md shadow-pink-200/45"
                          : "text-[#655767] hover:bg-pink-50/80 hover:text-pink-600",
                      )}
                    >
                      <span
                        className={cn(
                          "flex size-8 items-center justify-center rounded-xl bg-white/55 text-pink-500 shadow-sm",
                          active && "bg-white/75",
                        )}
                      >
                        <Icon className="size-4" />
                      </span>
                      <span>{label}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>
          <ScrollArea className="nail-glass-soft h-full min-h-0 rounded-3xl">
            <div className="space-y-8 p-6">
              {activeSection === "account" && <AccountSettingsPage />}
              {activeSection === "models" && <ModelSettingsPage />}
              {activeSection === "appearance" && <AppearanceSettingsPage />}
              {activeSection === "memory" && <MemorySettingsPage />}
              {activeSection === "tools" && <ToolSettingsPage />}
              {activeSection === "skills" && (
                <SkillSettingsPage
                  onClose={() => props.onOpenChange?.(false)}
                />
              )}
              {activeSection === "notification" && <NotificationSettingsPage />}
            </div>
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
}
