"use client";

import { Settings2Icon } from "lucide-react";
import { useEffect, useState } from "react";

import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";

import { SettingsDialog } from "./settings";

export function WorkspaceNavMenu() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const { open: isSidebarOpen } = useSidebar();

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
              className="h-12 cursor-pointer rounded-2xl text-[#655767] hover:bg-pink-50 hover:text-pink-600 data-[state=open]:bg-pink-100 data-[state=open]:text-pink-600"
            >
              {isSidebarOpen ? (
                <div className="flex w-full items-center gap-3 text-left text-sm font-semibold">
                  <Settings2Icon className="size-4" />
                  <span>设置</span>
                </div>
              ) : (
                <div className="flex size-full items-center justify-center">
                  <Settings2Icon className="size-4 text-pink-500" />
                </div>
              )}
            </SidebarMenuButton>
          ) : (
            <SidebarMenuButton size="lg" className="pointer-events-none">
              <div className="flex w-full items-center gap-2 text-left text-sm text-[#655767]">
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
