"use client";

import { useState } from "react";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useTools } from "@/core/nail-models";
import { ToolCard } from "@/components/nail/tool-card";

export default function ToolsPage() {
  const { data: toolsData, isLoading } = useTools();
  const [search, setSearch] = useState("");

  const matchesTool = (name: string, desc: string) =>
    !search ||
    name.toLowerCase().includes(search.toLowerCase()) ||
    desc.toLowerCase().includes(search.toLowerCase());

  const nailTools = (toolsData?.nail_tools ?? []).filter((t) =>
    matchesTool(t.display_name, t.description),
  );
  const builtinTools = (toolsData?.builtin_tools ?? []).filter((t) =>
    matchesTool(t.display_name, t.description),
  );

  return (
    <div className="flex h-full flex-col">
      {/* ── Header ── */}
      <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mr-2 h-4" />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="hidden text-muted-foreground sm:block">
              NailFlow
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden sm:block" />
            <BreadcrumbItem>
              <BreadcrumbPage>工具管理</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <div className="ml-auto w-48">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索工具…"
            className="h-7 text-xs"
          />
        </div>
      </header>

      {/* ── 内容 ── */}
      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-2xl space-y-8 px-4 py-6">

          {/* NailFlow 专属工具 */}
          <section>
            <div className="mb-3">
              <h2 className="text-sm font-semibold">NailFlow 工具</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                美甲试戴专属工具链（nail / nail_ops / nail_dev 三组，按角色权限启用）
              </p>
            </div>
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-20 rounded-xl" />
                ))}
              </div>
            ) : nailTools.length === 0 ? (
              <p className="py-4 text-sm text-muted-foreground">
                没有匹配的工具
              </p>
            ) : (
              <div className="space-y-2">
                {nailTools.map((t) => (
                  <ToolCard key={t.name} tool={t} />
                ))}
              </div>
            )}
          </section>

          {/* DeerFlow 内置工具 */}
          <section>
            <div className="mb-3">
              <h2 className="text-sm font-semibold">DeerFlow 内置工具</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                网页搜索、文件操作、命令执行等通用工具
              </p>
            </div>
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 rounded-xl" />
                ))}
              </div>
            ) : builtinTools.length === 0 ? (
              <p className="py-4 text-sm text-muted-foreground">
                没有匹配的工具
              </p>
            ) : (
              <div className="space-y-2">
                {builtinTools.map((t) => (
                  <ToolCard key={t.name} tool={t} />
                ))}
              </div>
            )}
          </section>

          <div className="h-4" />
        </div>
      </ScrollArea>
    </div>
  );
}
