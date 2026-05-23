"use client";

import { useEffect, useMemo, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { createId, initialData, moveCard, type BoardData } from "@/lib/kanban";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export const KanbanBoard = () => {
  const [board, setBoard] = useState<BoardData>(() => initialData);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [isLoadingBoard, setIsLoadingBoard] = useState(true);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatError, setChatError] = useState<string | null>(null);
  const [isSendingChat, setIsSendingChat] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const cardsById = useMemo(() => board.cards, [board.cards]);

  const persistBoard = async (nextBoard: BoardData) => {
    try {
      const response = await fetch("/api/board", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(nextBoard),
      });
      if (!response.ok) {
        throw new Error("Save failed");
      }
      setSyncError(null);
    } catch {
      setSyncError("Could not save board changes. Try again.");
    }
  };

  useEffect(() => {
    const loadBoard = async () => {
      try {
        const response = await fetch("/api/board", { credentials: "include" });
        if (!response.ok) {
          throw new Error("Load failed");
        }
        const loadedBoard = (await response.json()) as BoardData;
        setBoard(loadedBoard);
        setSyncError(null);
      } catch {
        setSyncError("Could not load saved board data.");
      } finally {
        setIsLoadingBoard(false);
      }
    };

    void loadBoard();
  }, []);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!over || active.id === over.id) {
      return;
    }

    setBoard((prev) => {
      const next = {
        ...prev,
        columns: moveCard(prev.columns, active.id as string, over.id as string),
      };
      void persistBoard(next);
      return next;
    });
  };

  const handleRenameColumn = (columnId: string, title: string) => {
    setBoard((prev) => {
      const next = {
        ...prev,
        columns: prev.columns.map((column) =>
          column.id === columnId ? { ...column, title } : column
        ),
      };
      void persistBoard(next);
      return next;
    });
  };

  const handleAddCard = (columnId: string, title: string, details: string) => {
    const id = createId("card");
    setBoard((prev) => {
      const next = {
        ...prev,
        cards: {
          ...prev.cards,
          [id]: { id, title, details: details || "No details yet." },
        },
        columns: prev.columns.map((column) =>
          column.id === columnId
            ? { ...column, cardIds: [...column.cardIds, id] }
            : column
        ),
      };
      void persistBoard(next);
      return next;
    });
  };

  const handleDeleteCard = (columnId: string, cardId: string) => {
    setBoard((prev) => {
      const next = {
        ...prev,
        cards: Object.fromEntries(
          Object.entries(prev.cards).filter(([id]) => id !== cardId)
        ),
        columns: prev.columns.map((column) =>
          column.id === columnId
            ? {
                ...column,
                cardIds: column.cardIds.filter((id) => id !== cardId),
              }
            : column
        ),
      };
      void persistBoard(next);
      return next;
    });
  };

  const handleSendChat = async () => {
    const message = chatInput.trim();
    if (!message || isSendingChat) {
      return;
    }

    const priorConversation = chatMessages;
    setChatInput("");
    setChatError(null);
    setChatMessages((prev) => [...prev, { role: "user", content: message }]);
    setIsSendingChat(true);

    try {
      const response = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          message,
          conversation: priorConversation,
        }),
      });
      if (!response.ok) {
        throw new Error("Chat failed");
      }
      const result = (await response.json()) as {
        assistantMessage: string;
        board: BoardData;
      };
      if (result.board) {
        setBoard(result.board);
      }
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: result.assistantMessage },
      ]);
    } catch {
      setChatError("AI request failed. Try again.");
    } finally {
      setIsSendingChat(false);
    }
  };

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1500px] flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                Focus
              </p>
              <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                One board. Five columns. Zero clutter.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            {board.columns.map((column) => (
              <div
                key={column.id}
                className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                {column.title}
              </div>
            ))}
          </div>
          {isLoadingBoard ? (
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-[var(--gray-text)]">
              Loading saved board...
            </p>
          ) : null}
          {syncError ? (
            <p className="text-sm font-medium text-[var(--secondary-purple)]">{syncError}</p>
          ) : null}
        </header>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCorners}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <section className="grid gap-6 lg:grid-cols-5">
              {board.columns.map((column) => (
                <KanbanColumn
                  key={column.id}
                  column={column}
                  cards={column.cardIds.map((cardId) => board.cards[cardId])}
                  onRename={handleRenameColumn}
                  onAddCard={handleAddCard}
                  onDeleteCard={handleDeleteCard}
                />
              ))}
            </section>
            <DragOverlay>
              {activeCard ? (
                <div className="w-[260px]">
                  <KanbanCardPreview card={activeCard} />
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>

          <aside className="flex max-h-[780px] min-h-[520px] flex-col rounded-3xl border border-[var(--stroke)] bg-white/90 p-5 shadow-[var(--shadow)]">
            <h2 className="font-display text-2xl font-semibold text-[var(--navy-dark)]">
              AI Assistant
            </h2>
            <p className="mt-2 text-sm text-[var(--gray-text)]">
              Ask for card and column updates. Changes apply automatically.
            </p>

            <div className="mt-4 flex-1 space-y-3 overflow-y-auto rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] p-3">
              {chatMessages.length === 0 ? (
                <p className="text-sm text-[var(--gray-text)]">
                  No messages yet. Ask AI to update your board.
                </p>
              ) : (
                chatMessages.map((message, index) => (
                  <article
                    key={`${message.role}-${index}`}
                    className={
                      message.role === "user"
                        ? "ml-8 rounded-2xl bg-[var(--secondary-purple)]/10 px-3 py-2 text-sm text-[var(--navy-dark)]"
                        : "mr-8 rounded-2xl bg-[var(--primary-blue)]/10 px-3 py-2 text-sm text-[var(--navy-dark)]"
                    }
                  >
                    <p className="text-xs font-semibold uppercase tracking-[0.15em] text-[var(--gray-text)]">
                      {message.role}
                    </p>
                    <p className="mt-1 whitespace-pre-wrap">{message.content}</p>
                  </article>
                ))
              )}
            </div>

            {chatError ? (
              <p className="mt-3 text-sm font-medium text-[var(--secondary-purple)]">
                {chatError}
              </p>
            ) : null}

            <div className="mt-4 flex items-end gap-2">
              <textarea
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void handleSendChat();
                  }
                }}
                placeholder="Ask AI to update your board"
                className="min-h-[84px] flex-1 resize-none rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none focus:border-[var(--primary-blue)]"
              />
              <button
                type="button"
                onClick={() => void handleSendChat()}
                disabled={isSendingChat}
                className="rounded-xl bg-[var(--secondary-purple)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                {isSendingChat ? "Sending..." : "Send"}
              </button>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
};
