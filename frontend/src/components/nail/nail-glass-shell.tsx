"use client";

import type { ReactNode } from "react";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useAuth } from "@/core/auth/AuthProvider";
import { cn } from "@/lib/utils";

interface NailGlassShellProps {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  children: ReactNode;
  actions?: ReactNode;
  headerRight?: ReactNode;
  className?: string;
  hero?: boolean;
}

export function NailGlassShell({
  title,
  subtitle,
  eyebrow = "nailflow",
  children,
  actions,
  headerRight,
  className,
  hero = true,
}: NailGlassShellProps) {
  const { user } = useAuth();

  return (
    <div
      className={cn(
        "nail-shell flex h-full flex-col overflow-hidden",
        className,
      )}
    >
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="nail-sparkle nail-sparkle-a">✦</div>
        <div className="nail-sparkle nail-sparkle-b">♡</div>
        <div className="nail-sparkle nail-sparkle-c">✧</div>
      </div>

      <header className="nail-topbar relative z-10 mx-4 mt-4 flex h-14 shrink-0 items-center gap-3 rounded-3xl px-4">
        <SidebarTrigger className="-ml-1 text-pink-500 hover:bg-pink-100/70 hover:text-pink-600" />
        <Separator orientation="vertical" className="h-4 bg-pink-200/70" />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="hidden text-pink-400 sm:block">
              {eyebrow}
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden text-pink-300 sm:block" />
            <BreadcrumbItem>
              <BreadcrumbPage className="font-semibold text-[#5b1738]">
                {title}
              </BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <div className="ml-auto flex items-center gap-3">
          {headerRight}
          <div className="nail-pill hidden items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold text-[#4d1f36] sm:flex">
            <span className="text-lg">💎</span>
            <span>128 积分</span>
          </div>
          <div className="nail-pill flex items-center gap-2 rounded-full px-3 py-2 text-sm font-semibold text-[#4d1f36]">
            <span className="flex size-8 items-center justify-center rounded-full bg-gradient-to-br from-pink-400 to-fuchsia-400 text-sm font-bold text-white">
              {user?.email?.[0]?.toUpperCase() ?? "N"}
            </span>
            <span className="hidden sm:inline">User</span>
          </div>
        </div>
      </header>

      <main className="relative z-10 min-h-0 flex-1 overflow-auto px-4 pt-4 pb-6">
        <div className="mx-auto w-full max-w-6xl space-y-6">
          {hero && (
            <section className="relative py-3 text-center">
              <h1 className="nail-hero-title text-5xl font-extrabold tracking-normal md:text-6xl">
                {title}
              </h1>
              {subtitle && (
                <p className="mx-auto mt-4 max-w-2xl text-base leading-8 text-[#8b7180]">
                  {subtitle}
                </p>
              )}
              {actions && <div className="mt-6">{actions}</div>}
            </section>
          )}

          {children}
        </div>
      </main>
    </div>
  );
}
