// frontend/src/components/workspace/nail-nav.tsx
"use client";

import {
  BoxIcon,
  ChartNoAxesColumnIcon,
  DatabaseIcon,
  HeartIcon,
  SparklesIcon,
  WrenchIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import type { ComponentType } from "react";

import { useAuth } from "@/core/auth/AuthProvider";
import { canAccess, type NailRole } from "@/lib/nail-auth";
import { cn } from "@/lib/utils";

interface NailNavItem {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  requiredRole: NailRole;
}

const NAV_ITEMS: NailNavItem[] = [
  {
    href: "/workspace/chats/new?mode=nail",
    label: "AI 试戴",
    icon: SparklesIcon,
    requiredRole: "user",
  },
  {
    href: "/workspace/nail/warehouse",
    label: "美甲仓库",
    icon: BoxIcon,
    requiredRole: "user",
  },
  {
    href: "/workspace/nail/tools",
    label: "工具管理",
    icon: WrenchIcon,
    requiredRole: "user",
  },
  {
    href: "/workspace/nail/dashboard",
    label: "运营看板",
    icon: ChartNoAxesColumnIcon,
    requiredRole: "ops",
  },
  {
    href: "/workspace/nail/data",
    label: "数据中心",
    icon: DatabaseIcon,
    requiredRole: "ops",
  },
  {
    href: "/workspace/nail/evaluation",
    label: "评分面板",
    icon: HeartIcon,
    requiredRole: "dev",
  },
];

export function NailNav() {
  const { user } = useAuth();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const nailRole = user?.nail_role ?? "user";

  const visibleItems = NAV_ITEMS.filter((item) =>
    canAccess(nailRole, item.requiredRole),
  );

  if (visibleItems.length === 0) return null;

  /** 判断某个 nav item 是否激活（支持带 query string 的链接） */
  const isItemActive = (href: string) => {
    const [hrefPath, hrefQuery] = href.split("?");
    if (hrefQuery) {
      const params = new URLSearchParams(hrefQuery);
      return (
        (pathname.startsWith("/workspace/chats") || pathname === hrefPath) &&
        params.get("mode") === searchParams.get("mode")
      );
    }
    return pathname === hrefPath;
  };

  return (
    <div className="px-5 py-4">
      <p className="mb-3 px-1 text-sm font-semibold text-pink-500">NailFlow</p>
      <div className="space-y-2">
        {visibleItems.map((item) => {
          const isActive = isItemActive(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold transition-all",
                isActive
                  ? "bg-gradient-to-r from-pink-100 to-pink-200/70 text-pink-600 shadow-lg shadow-pink-200/45"
                  : "text-[#655767] hover:bg-pink-50/80 hover:text-pink-600",
              )}
            >
              <span
                className={cn(
                  "flex size-7 items-center justify-center rounded-xl bg-white/55 text-pink-500 shadow-sm",
                  isActive && "bg-white/70",
                )}
              >
                <Icon className="size-4" />
              </span>
              <span>{item.label}</span>
              {isActive && <span className="ml-auto text-pink-300">✦</span>}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
