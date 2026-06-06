import { ChevronUpIcon, ListTodoIcon } from "lucide-react";
import { useState } from "react";

import type { Todo } from "@/core/todos";
import { cn } from "@/lib/utils";

import {
  QueueItem,
  QueueItemContent,
  QueueItemIndicator,
  QueueList,
} from "../ai-elements/queue";

export function TodoList({
  className,
  todos,
  collapsed: controlledCollapsed,
  hidden = false,
  onToggle,
}: {
  className?: string;
  todos: Todo[];
  collapsed?: boolean;
  hidden?: boolean;
  onToggle?: () => void;
}) {
  const [internalCollapsed, setInternalCollapsed] = useState(true);
  const isControlled = controlledCollapsed !== undefined;
  const collapsed = isControlled ? controlledCollapsed : internalCollapsed;

  const handleToggle = () => {
    if (isControlled) {
      onToggle?.();
    } else {
      setInternalCollapsed((prev) => !prev);
    }
  };

  return (
    <div
      className={cn(
        "flex h-fit w-full origin-bottom translate-y-4 flex-col overflow-hidden rounded-t-3xl border border-b-0 border-pink-200/70 bg-white/58 shadow-lg shadow-pink-200/20 backdrop-blur-sm transition-all duration-200 ease-out",
        hidden ? "pointer-events-none translate-y-8 opacity-0" : "",
        className,
      )}
    >
      <header
        className={cn(
          "flex min-h-9 shrink-0 cursor-pointer items-center justify-between bg-pink-50/70 px-4 text-sm transition-all duration-300 ease-out",
        )}
        onClick={handleToggle}
      >
        <div className="text-pink-500">
          <div className="flex items-center justify-center gap-2">
            <ListTodoIcon className="size-4" />
            <div>To-dos</div>
          </div>
        </div>
        <div>
          <ChevronUpIcon
            className={cn(
              "size-4 text-pink-400 transition-transform duration-300 ease-out",
              collapsed ? "" : "rotate-180",
            )}
          />
        </div>
      </header>
      <main
        className={cn(
          "flex grow bg-pink-50/45 px-2 transition-all duration-300 ease-out",
          collapsed ? "h-0 pb-3" : "h-28 pb-4",
        )}
      >
        <QueueList className="mt-0 w-full rounded-t-2xl bg-white/70">
          {todos.map((todo, i) => (
            <QueueItem key={i + (todo.content ?? "")}>
              <div className="flex items-center gap-2">
                <QueueItemIndicator
                  className={todo.status === "in_progress" ? "bg-pink-400" : ""}
                  completed={todo.status === "completed"}
                />
                <QueueItemContent
                  className={
                    todo.status === "in_progress" ? "text-pink-500" : ""
                  }
                  completed={todo.status === "completed"}
                >
                  {todo.content}
                </QueueItemContent>
              </div>
            </QueueItem>
          ))}
        </QueueList>
      </main>
    </div>
  );
}
