// frontend/src/components/workspace/nail-nav.tsx
"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useAuth } from "@/core/auth/AuthProvider";
import { canAccess, type NailRole } from "@/lib/nail-auth";

interface NailNavItem {
  href: string;
  label: string;
  emoji: string;
  requiredRole: NailRole;
}

const NAV_ITEMS: NailNavItem[] = [
  // 试戴功能进入带 nail 模式的新对话（复用 DeerFlow 对话界面）
  { href: "/workspace/chats/new?mode=nail", label: "AI 试戴",  emoji: "💅", requiredRole: "user" },
  { href: "/workspace/nail/tools",          label: "工具管理", emoji: "🔧", requiredRole: "user" },
  { href: "/workspace/nail/dashboard",      label: "运营看板", emoji: "📊", requiredRole: "ops" },
  { href: "/workspace/nail/evaluation",     label: "评分面板", emoji: "⚡", requiredRole: "dev" },
];

export function NailNav() {
  const { user } = useAuth();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const nailRole = (user as any)?.nail_role as NailRole ?? "user";

  const visibleItems = NAV_ITEMS.filter((item) => canAccess(nailRole, item.requiredRole));

  if (visibleItems.length === 0) return null;

  /** 判断某个 nav item 是否激活（支持带 query string 的链接） */
  const isItemActive = (href: string) => {
    const [hrefPath, hrefQuery] = href.split("?");
    if (hrefQuery) {
      const params = new URLSearchParams(hrefQuery);
      // 路径匹配（/workspace/chats/new 前缀）+ mode 参数匹配
      return (
        (pathname.startsWith("/workspace/chats") || pathname === hrefPath) &&
        params.get("mode") === searchParams.get("mode")
      );
    }
    return pathname === hrefPath;
  };

  return (
    <div className="px-2 py-2">
      <p className="text-muted-foreground mb-1 px-2 text-xs font-medium">NailFlow</p>
      <div className="space-y-0.5">
        {visibleItems.map((item) => {
          const isActive = isItemActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors ${
                isActive
                  ? "bg-accent text-accent-foreground"
                  : "hover:bg-accent/50 text-muted-foreground hover:text-foreground"
              }`}
            >
              <span>{item.emoji}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
