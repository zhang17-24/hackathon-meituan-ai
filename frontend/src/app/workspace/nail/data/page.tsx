"use client";

import { useState } from "react";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Breadcrumb, BreadcrumbItem, BreadcrumbList,
  BreadcrumbPage, BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { SidebarTrigger } from "@/components/ui/sidebar";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useAuth } from "@/core/auth/AuthProvider";
import { canAccess, type NailRole } from "@/lib/nail-auth";
import { useQuery, useMutation } from "@tanstack/react-query";
import { data as dataApi } from "@/core/api/nail";
import type { QueryResult } from "@/core/api/nail/data";
import { NailPageLayout } from "@/components/nail/nail-page-layout";
import { ChevronDownIcon, ChevronRightIcon, DownloadIcon } from "lucide-react";

export default function DataPage() {
  const { user } = useAuth();
  const nailRole = (user as any)?.nail_role as NailRole ?? "user";

  const [question, setQuestion] = useState("");
  const [schemaOpen, setSchemaOpen] = useState(false);

  const { data: schema } = useQuery({
    queryKey: ["nail-data-schema"],
    queryFn: dataApi.fetchSchema,
    staleTime: 300_000,
    enabled: canAccess(nailRole, "ops"),
  });

  const queryMutation = useMutation({
    mutationFn: (q: string) => dataApi.executeQuery(q),
  });

  const handleQuery = () => {
    const q = question.trim();
    if (!q || queryMutation.isPending) return;
    queryMutation.mutate(q);
  };

  const handleExport = (result: QueryResult) => {
    const csv = dataApi.rowsToCSV(result.columns, result.rows);
    dataApi.downloadCSV(csv);
  };

  if (!canAccess(nailRole, "ops")) {
    return (
      <div className="flex h-full flex-col">
        <Header />
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center space-y-2">
            <p className="text-muted-foreground text-sm">需要运营或开发权限</p>
            <Badge variant="outline" className="text-xs border-amber-400/40 text-amber-400">
              当前角色：{nailRole}
            </Badge>
          </div>
        </div>
      </div>
    );
  }

  const result = queryMutation.data;

  const panelContent = (
    <div className="flex h-full flex-col">
      <Header />
      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-4xl px-4 py-6 space-y-4">

          {/* 表结构速查 */}
          <Collapsible open={schemaOpen} onOpenChange={setSchemaOpen}>
            <CollapsibleTrigger className="flex w-full items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
              {schemaOpen ? <ChevronDownIcon className="size-4" /> : <ChevronRightIcon className="size-4" />}
              表结构速查
              {schema && <span className="text-xs text-muted-foreground/60 ml-1">({Object.keys(schema.tables).length} 张表)</span>}
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-2">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 max-h-64 overflow-y-auto">
                {schema?.tables && Object.entries(schema.tables).map(([name, cols]) => (
                  <div key={name} className="rounded-lg border border-border/50 bg-muted/20 p-2.5">
                    <p className="text-xs font-semibold text-foreground/90 mb-1.5 font-mono">{name}</p>
                    <p className="text-[10px] text-muted-foreground leading-relaxed">
                      {cols.map(c => c.col).join(", ")}
                    </p>
                    <p className="text-[10px] text-muted-foreground/50 mt-0.5">{cols.length} 列</p>
                  </div>
                ))}
              </div>
            </CollapsibleContent>
          </Collapsible>

          <Separator />

          {/* 查询输入 */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground/80">
              自然语言查询
            </label>
            <Textarea
              placeholder="例如：查最近7天试戴次数最多的前10个款式"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleQuery();
                }
              }}
              rows={3}
              className="resize-none text-sm"
            />
            <Button
              onClick={handleQuery}
              disabled={!question.trim() || queryMutation.isPending}
              className="gap-1.5"
            >
              {queryMutation.isPending ? (
                <span className="size-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
              ) : null}
              查询
            </Button>
          </div>

          {/* 查询结果 */}
          {result && (
            <div className="space-y-3">
              <Separator />

              {result.sql && (
                <div className="rounded-lg border border-border/50 bg-muted/20 p-3">
                  <p className="text-[10px] text-muted-foreground mb-1 font-medium uppercase tracking-wide">执行的 SQL</p>
                  <code className="text-xs break-all text-foreground/80">{result.sql}</code>
                </div>
              )}

              {result.error && (
                <div className="rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3">
                  <p className="text-sm text-red-400">{result.error}</p>
                </div>
              )}

              {!result.error && (
                <>
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">
                      共 {result.row_count} 行 {result.columns.length} 列
                    </p>
                    {result.rows.length > 0 && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 text-xs gap-1"
                        onClick={() => handleExport(result)}
                      >
                        <DownloadIcon className="size-3" />
                        导出 CSV
                      </Button>
                    )}
                  </div>
                  {result.rows.length === 0 ? (
                    <p className="text-sm text-muted-foreground py-8 text-center">查询无结果</p>
                  ) : (
                    <div className="rounded-lg border border-border/60 overflow-auto max-h-[500px]">
                      <table className="w-full text-xs">
                        <thead className="bg-muted/30 sticky top-0">
                          <tr>
                            {result.columns.map((col) => (
                              <th key={col} className="text-left px-3 py-2 font-semibold text-muted-foreground whitespace-nowrap border-b border-border/40">
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/20">
                          {result.rows.map((row, ri) => (
                            <tr key={ri} className="hover:bg-muted/10">
                              {row.map((cell, ci) => (
                                <td key={ci} className="px-3 py-1.5 whitespace-nowrap text-foreground/80 max-w-[300px] truncate">
                                  {cell === null ? <span className="text-muted-foreground/50 italic">NULL</span> : String(cell)}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          <div className="h-4" />
        </div>
      </ScrollArea>
    </div>
  );

  return (
    <NailPageLayout pageMode="ops" panel={panelContent} />
  );
}

function Header() {
  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-2 h-4" />
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem className="hidden sm:block text-muted-foreground">NailFlow</BreadcrumbItem>
          <BreadcrumbSeparator className="hidden sm:block" />
          <BreadcrumbItem>
            <BreadcrumbPage>数据中心</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
    </header>
  );
}
