"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { NailGlassShell } from "@/components/nail/nail-glass-shell";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useI18n } from "@/core/i18n/hooks";
import { useThreads } from "@/core/threads/hooks";
import { pathOfThread, titleOfThread } from "@/core/threads/utils";
import { formatTimeAgo } from "@/core/utils/datetime";

export default function ChatsPage() {
  const { t } = useI18n();
  const { data: threads } = useThreads();
  const [search, setSearch] = useState("");

  useEffect(() => {
    document.title = `${t.pages.chats} - ${t.pages.appName}`;
  }, [t.pages.chats, t.pages.appName]);

  const filteredThreads = useMemo(() => {
    return threads?.filter((thread) => {
      return titleOfThread(thread).toLowerCase().includes(search.toLowerCase());
    });
  }, [threads, search]);
  return (
    <NailGlassShell
      title="对话"
      subtitle="回到你的灵感记录，继续每一次美甲灵感、试戴和工具执行。"
      hero={false}
      className="h-full"
    >
      <section className="nail-glass-card min-h-[calc(100vh-8rem)] overflow-hidden rounded-3xl p-5 md:p-7">
        <div className="flex size-full flex-col gap-5">
          <header className="flex shrink-0 flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <div className="text-sm font-semibold text-pink-500">
                nailflow
              </div>
              <h1 className="mt-2 text-3xl font-extrabold text-[#5b1738]">
                历史对话
              </h1>
              <p className="mt-2 text-sm text-[#a98799]">
                查看你和智能体的历史记录，点击任意对话即可继续。
              </p>
            </div>
            <Input
              type="search"
              className="nail-glass-soft h-12 w-full rounded-full border-pink-200/70 bg-white/58 px-5 text-base text-[#5b1738] placeholder:text-[#bd98aa] focus-visible:ring-pink-300/50 md:max-w-sm"
              placeholder={t.chats.searchChats}
              autoFocus
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </header>
          <main className="min-h-0 flex-1">
            <ScrollArea className="size-full">
              <div className="grid gap-3 pb-4">
                {filteredThreads?.map((thread) => (
                  <Link key={thread.thread_id} href={pathOfThread(thread)}>
                    <div className="nail-glass-soft group flex flex-col gap-2 rounded-3xl px-5 py-4 transition hover:-translate-y-0.5 hover:border-pink-300/70 hover:bg-white/72 hover:shadow-pink-200/30">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0 truncate text-base font-semibold text-[#5b1738]">
                          {titleOfThread(thread)}
                        </div>
                        <span className="rounded-full bg-pink-100/70 px-2.5 py-1 text-xs font-semibold text-pink-500 opacity-0 transition group-hover:opacity-100">
                          继续
                        </span>
                      </div>
                      {thread.updated_at && (
                        <div className="text-sm text-[#b08a9e]">
                          {formatTimeAgo(thread.updated_at)}
                        </div>
                      )}
                    </div>
                  </Link>
                ))}
                {filteredThreads?.length === 0 && (
                  <div className="nail-dashed-zone flex h-48 items-center justify-center rounded-3xl text-sm font-medium text-[#bd86a2]">
                    暂时没有找到匹配的对话
                  </div>
                )}
              </div>
            </ScrollArea>
          </main>
        </div>
      </section>
    </NailGlassShell>
  );
}
