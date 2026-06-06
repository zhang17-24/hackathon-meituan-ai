"use client";

import { BotIcon, MessagesSquare } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { useI18n } from "@/core/i18n/hooks";
import { cn } from "@/lib/utils";

export function WorkspaceNavChatList() {
  const { t } = useI18n();
  const pathname = usePathname();
  const items = [
    {
      href: "/workspace/chats",
      label: t.sidebar.chats,
      icon: MessagesSquare,
      active: pathname === "/workspace/chats",
    },
    {
      href: "/workspace/agents",
      label: t.sidebar.agents,
      icon: BotIcon,
      active: pathname.startsWith("/workspace/agents"),
    },
  ];

  return (
    <SidebarGroup className="px-5 pt-3">
      <div className="mb-3 h-px bg-pink-200/60" />
      <SidebarMenu className="space-y-2">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <SidebarMenuItem key={item.href}>
              <Link
                href={item.href}
                className={cn(
                  "group flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold transition-all",
                  item.active
                    ? "bg-gradient-to-r from-pink-100 to-pink-200/70 text-pink-600 shadow-lg shadow-pink-200/45"
                    : "text-[#655767] hover:bg-pink-50/80 hover:text-pink-600",
                )}
              >
                <span
                  className={cn(
                    "flex size-7 items-center justify-center rounded-xl bg-white/55 text-pink-500 shadow-sm",
                    item.active && "bg-white/70",
                  )}
                >
                  <Icon className="size-4" />
                </span>
                <span>{item.label}</span>
              </Link>
            </SidebarMenuItem>
          );
        })}
      </SidebarMenu>
    </SidebarGroup>
  );
}
