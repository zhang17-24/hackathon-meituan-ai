"use client";

import { BotIcon, PlusIcon } from "lucide-react";
import { useRouter } from "next/navigation";

import { NailGlassShell } from "@/components/nail/nail-glass-shell";
import { Button } from "@/components/ui/button";
import { useAgents } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";

import { AgentCard } from "./agent-card";

export function AgentGallery() {
  const { t } = useI18n();
  const { agents, isLoading } = useAgents();
  const router = useRouter();

  const handleNewAgent = () => {
    router.push("/workspace/agents/new");
  };

  return (
    <NailGlassShell title={t.agents.title} hero={false}>
      <section className="nail-glass-card rounded-[2rem] p-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-4xl font-extrabold text-[#5b1738]">
              {t.agents.title} <span className="text-pink-300">✦</span>
            </h1>
            <p className="mt-2 text-sm font-medium text-[#8f7b88]">
              {t.agents.description}
            </p>
          </div>
          <Button
            className="nail-primary-button rounded-full px-6"
            onClick={handleNewAgent}
          >
            <PlusIcon className="mr-1.5 h-4 w-4" />
            {t.agents.newAgent}
          </Button>
        </div>

        {/* Content */}
        <div className="mt-8">
          {isLoading ? (
            <div className="flex h-40 items-center justify-center text-sm text-[#8f7b88]">
              {t.common.loading}
            </div>
          ) : agents.length === 0 ? (
            <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-pink-100 text-pink-500 shadow-lg shadow-pink-200/60">
                <BotIcon className="h-8 w-8" />
              </div>
              <div>
                <p className="font-bold text-[#5b1738]">
                  {t.agents.emptyTitle}
                </p>
                <p className="mt-1 text-sm text-[#8f7b88]">
                  {t.agents.emptyDescription}
                </p>
              </div>
              <Button
                variant="outline"
                className="nail-outline-button mt-2 rounded-full"
                onClick={handleNewAgent}
              >
                <PlusIcon className="mr-1.5 h-4 w-4" />
                {t.agents.newAgent}
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {agents.map((agent) => (
                <AgentCard key={agent.name} agent={agent} />
              ))}
            </div>
          )}
        </div>
      </section>
    </NailGlassShell>
  );
}
