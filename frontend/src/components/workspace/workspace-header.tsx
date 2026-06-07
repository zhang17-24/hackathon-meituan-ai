"use client";

import { MessageSquarePlus } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { useI18n } from "@/core/i18n/hooks";
import { env } from "@/env";
import { cn } from "@/lib/utils";

export function WorkspaceHeader({ className }: { className?: string }) {
  const { t } = useI18n();
  const { state } = useSidebar();
  const pathname = usePathname();
  return (
    <>
      <div
        className={cn(
          "group/workspace-header flex h-12 flex-col justify-center",
          className,
        )}
      >
        {state === "collapsed" ? (
          <div className="group-has-data-[collapsible=icon]/sidebar-wrapper:-translate-y flex w-full cursor-pointer items-center justify-center">
            <div className="block pt-1 font-serif text-pink-500 group-hover/workspace-header:hidden">
              DF
            </div>
            <SidebarTrigger className="hidden pl-2 text-pink-500 group-hover/workspace-header:block" />
          </div>
        ) : (
          <div className="flex items-center justify-between gap-2 px-4 pt-3">
            {env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true" ? (
              <Link
                href="/"
                className="font-serif text-3xl font-bold text-pink-500"
              >
                nailflow
              </Link>
            ) : (
              <div className="cursor-default font-serif text-3xl font-bold text-pink-500">
                nailflow
              </div>
            )}
            <SidebarTrigger className="text-pink-500 hover:bg-pink-100/70 hover:text-pink-600" />
          </div>
        )}
      </div>
      <SidebarMenu className="px-5 pt-7">
        <SidebarMenuItem>
          <SidebarMenuButton
            isActive={pathname === "/workspace/chats/new"}
            asChild
            className="h-12 rounded-2xl border border-pink-200/60 bg-white/45 text-pink-500 shadow-sm hover:bg-pink-50 hover:text-pink-600 data-[active=true]:bg-pink-100 data-[active=true]:text-pink-600"
          >
            <Link href="/workspace/chats/new">
              <MessageSquarePlus size={16} />
              <span>{t.sidebar.newChat}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </>
  );
}
