// frontend/src/core/api/nail/data.ts
import { fetch as apiFetch } from "@/core/api/fetcher";

export interface TableSchema {
  tables: Record<string, Array<{ col: string; type: string; note: string }>>;
  db_path: string;
}

export interface QueryResult {
  question: string;
  sql: string;
  columns: string[];
  rows: (string | number | null)[][];
  row_count: number;
  error: string | null;
}

export async function fetchSchema(): Promise<TableSchema> {
  const res = await apiFetch("/api/nail/data/schema");
  if (!res.ok) throw new Error("获取表结构失败");
  return res.json();
}

export async function executeQuery(question: string): Promise<QueryResult> {
  const res = await apiFetch("/api/nail/data/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error("查询失败");
  return res.json();
}

export function rowsToCSV(columns: string[], rows: QueryResult["rows"]): string {
  const escape = (v: unknown) => {
    if (v === null || v === undefined) return "";
    const s = String(v);
    if (s.includes(",") || s.includes('"') || s.includes("\n")) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };
  const header = columns.map(escape).join(",");
  const body = rows.map(r => r.map(escape).join(",")).join("\n");
  return header + "\n" + body;
}

export function downloadCSV(csv: string, filename = "query_result.csv") {
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
