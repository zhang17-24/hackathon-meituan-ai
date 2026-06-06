"use client";

import { BotIcon, MessageSquareIcon, Trash2Icon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useDeleteAgent } from "@/core/agents";
import type { Agent } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";

interface AgentCardProps {
  agent: Agent;
}

export function AgentCard({ agent }: AgentCardProps) {
  const { t } = useI18n();
  const router = useRouter();
  const deleteAgent = useDeleteAgent();
  const [deleteOpen, setDeleteOpen] = useState(false);

  function handleChat() {
    router.push(`/workspace/agents/${agent.name}/chats/new`);
  }

  async function handleDelete() {
    try {
      await deleteAgent.mutateAsync(agent.name);
      toast.success(t.agents.deleteSuccess);
      setDeleteOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <>
      <Card className="nail-glass-soft group flex flex-col rounded-3xl border-pink-200/70 transition-all hover:-translate-y-0.5 hover:shadow-xl hover:shadow-pink-200/40">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-pink-100 text-pink-500 shadow-sm">
                <BotIcon className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <CardTitle className="truncate text-base text-[#5b1738]">
                  {agent.name}
                </CardTitle>
                {agent.model && (
                  <Badge
                    variant="secondary"
                    className="mt-0.5 rounded-full bg-pink-100 text-xs text-pink-500"
                  >
                    {agent.model}
                  </Badge>
                )}
              </div>
            </div>
          </div>
          {agent.description && (
            <CardDescription className="mt-2 line-clamp-2 text-sm text-[#8f7b88]">
              {agent.description}
            </CardDescription>
          )}
        </CardHeader>

        {(agent.tool_groups?.length ?? agent.skills?.length ?? 0) > 0 && (
          <CardContent className="pt-0 pb-3">
            <div className="flex flex-wrap gap-1">
              {agent.tool_groups?.map((group) => (
                <Badge
                  key={`tg:${group}`}
                  variant="outline"
                  className="rounded-full border-pink-200 text-xs text-pink-500"
                >
                  {group}
                </Badge>
              ))}
              {agent.skills?.map((skill) => (
                <Badge
                  key={`sk:${skill}`}
                  variant="secondary"
                  className="rounded-full bg-fuchsia-100 text-xs text-fuchsia-500"
                >
                  {skill}
                </Badge>
              ))}
            </div>
          </CardContent>
        )}

        <CardFooter className="mt-auto flex items-center justify-between gap-2 pt-3">
          <Button
            size="sm"
            className="nail-primary-button flex-1 rounded-full"
            onClick={handleChat}
          >
            <MessageSquareIcon className="mr-1.5 h-3.5 w-3.5" />
            {t.agents.chat}
          </Button>
          <div className="flex gap-1">
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 shrink-0 rounded-full text-rose-500 hover:bg-rose-100 hover:text-rose-600"
              onClick={() => setDeleteOpen(true)}
              title={t.agents.delete}
            >
              <Trash2Icon className="h-3.5 w-3.5" />
            </Button>
          </div>
        </CardFooter>
      </Card>

      {/* Delete Confirm */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent className="nail-glass-card rounded-3xl border-pink-200/70">
          <DialogHeader>
            <DialogTitle className="text-[#5b1738]">
              {t.agents.delete}
            </DialogTitle>
            <DialogDescription className="text-[#8f7b88]">
              {t.agents.deleteConfirm}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              className="nail-outline-button rounded-full"
              onClick={() => setDeleteOpen(false)}
              disabled={deleteAgent.isPending}
            >
              {t.common.cancel}
            </Button>
            <Button
              variant="destructive"
              className="rounded-full"
              onClick={handleDelete}
              disabled={deleteAgent.isPending}
            >
              {deleteAgent.isPending ? t.common.loading : t.common.delete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
