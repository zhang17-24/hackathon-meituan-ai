import { fetch as apiFetch } from "@/core/api/fetcher";

/** Upload a file to a thread, returning the URL/path the backend assigns. */
export async function uploadTryonFile(threadId: string, file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const res = await apiFetch(`/api/threads/${threadId}/uploads`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`上传失败: ${res.statusText}`);
  const data = await res.json();
  return data.url ?? data.file_url ?? data.path ?? "";
}

/** Create a new agent thread. Returns thread_id. */
export async function createThread(): Promise<string> {
  const res = await apiFetch("/api/threads", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  if (!res.ok) throw new Error("创建会话失败");
  const thread = await res.json();
  return thread.thread_id ?? thread.id;
}

/** Start an SSE agent run on a thread, returning the readable stream body. */
export async function startAgentRun(
  threadId: string,
  body: Record<string, unknown>,
): Promise<ReadableStream<Uint8Array>> {
  const res = await apiFetch(`/api/threads/${threadId}/runs/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Agent 启动失败: ${res.statusText}`);
  return res.body!;
}
