"use client";

import { Settings2Icon } from "lucide-react";
import { useEffect, useState } from "react";

import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useI18n } from "@/core/i18n/hooks";

import { SettingsDialog } from "./settings";

export function WorkspaceNavMenu() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const { open: isSidebarOpen } = useSidebar();
  const { t } = useI18n();

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <>
      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        defaultSection="appearance"
      />
      <SidebarMenu className="w-full">
        <SidebarMenuItem>
          {mounted ? (
            <SidebarMenuButton
              size="lg"
              onClick={() => setSettingsOpen(true)}
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground cursor-pointer"
            >
              {isSidebarOpen ? (
                <div className="text-muted-foreground flex w-full items-center gap-2 text-left text-sm">
                  <Settings2Icon className="size-4" />
                  <span>设置</span>
                </div>
              ) : (
                <div className="flex size-full items-center justify-center">
                  <Settings2Icon className="text-muted-foreground size-4" />
                </div>
              )}
            </SidebarMenuButton>
          ) : (
            <SidebarMenuButton size="lg" className="pointer-events-none">
              <div className="text-muted-foreground flex w-full items-center gap-2 text-left text-sm">
                <Settings2Icon className="size-4" />
                <span>设置</span>
              </div>
            </SidebarMenuButton>
          )}
        </SidebarMenuItem>
      </SidebarMenu>
    </>
  );
}
