'use client';

import { KanbanCardPreview } from '@/components/KanbanCardPreview';
import { KanbanColumn } from '@/components/KanbanColumn';
import {
  createId,
  initialData,
  moveCard,
  toBoardData,
  type BackendBoard,
  type BoardData,
} from '@/lib/kanban';
import {
  closestCorners,
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from '@dnd-kit/core';
import { useCallback, useEffect, useMemo, useState } from 'react';

type KanbanBoardProps = {
  username?: string;
  onLogout?: () => void;
};

type ChatRole = 'user' | 'assistant' | 'system';

type AiChatMessage = {
  id: number;
  role: ChatRole;
  content: string;
  createdAt: string;
};

type AiPendingAction = {
  id: number;
  actionType: 'create_card' | 'edit_card' | 'move_card';
  payload: Record<string, unknown>;
  description: string;
  createdAt?: string;
  requiresConfirmation?: boolean;
};

type AiChatContextResponse = {
  messages: AiChatMessage[];
  pendingActions: AiPendingAction[];
};

type AiSendMessageResponse = {
  reply: string;
  pendingActions: AiPendingAction[];
};

type AiActionDecisionResponse = {
  status: 'applied' | 'rejected';
  board?: BackendBoard;
};

const fetchJson = async <T,>(url: string, init?: RequestInit): Promise<T> => {
  const requestUrl =
    typeof window !== 'undefined'
      ? new URL(url, window.location.origin).toString()
      : `http://localhost${url}`;
  const response = await fetch(requestUrl, init);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
};

export const KanbanBoard = ({ username, onLogout }: KanbanBoardProps) => {
  const [board, setBoard] = useState<BoardData>(() => initialData);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(username));
  const [error, setError] = useState('');

  const [chatMessages, setChatMessages] = useState<AiChatMessage[]>([]);
  const [pendingActions, setPendingActions] = useState<AiPendingAction[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(Boolean(username));
  const [chatError, setChatError] = useState('');
  const [actingActionId, setActingActionId] = useState<number | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    }),
  );

  const cardsById = useMemo(() => board.cards, [board.cards]);
  const overColumnId = useMemo(() => {
    if (!overId) {
      return null;
    }
    if (board.columns.some((column) => column.id === overId)) {
      return overId;
    }
    return board.columns.find((column) => column.cardIds.includes(overId))?.id ?? null;
  }, [board.columns, overId]);

  const loadBoard = useCallback(async () => {
    if (!username) {
      return;
    }
    setIsLoading(true);
    try {
      const backendBoard = await fetchJson<BackendBoard>(
        `/api/board/${encodeURIComponent(username)}`,
      );
      setBoard(toBoardData(backendBoard));
      setError('');
    } catch (loadError) {
      setError('Unable to load board data.');
      console.error(loadError);
    } finally {
      setIsLoading(false);
    }
  }, [username]);

  const loadAiContext = useCallback(async () => {
    if (!username) {
      return;
    }
    setIsChatLoading(true);
    try {
      const context = await fetchJson<AiChatContextResponse>(
        `/api/ai/${encodeURIComponent(username)}/chat`,
      );
      setChatMessages(context.messages);
      setPendingActions(context.pendingActions);
      setChatError('');
    } catch (contextError) {
      setChatError('Unable to load AI conversation.');
      console.error(contextError);
    } finally {
      setIsChatLoading(false);
    }
  }, [username]);

  useEffect(() => {
    void loadBoard();
    void loadAiContext();
  }, [loadBoard, loadAiContext]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(String(event.active.id));
    setOverId(String(event.active.id));
  };

  const handleDragOver = (event: DragOverEvent) => {
    setOverId(event.over ? String(event.over.id) : null);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);
    setOverId(null);

    if (!over || active.id === over.id) {
      return;
    }

    const activeId = String(active.id);
    const nextOverId = String(over.id);

    const nextColumns = moveCard(board.columns, activeId, nextOverId);
    setBoard((prev) => ({ ...prev, columns: nextColumns }));

    if (!username) {
      return;
    }

    const targetColumn = nextColumns.find((column) => column.cardIds.includes(activeId));
    if (!targetColumn) {
      return;
    }
    const targetPosition = targetColumn.cardIds.indexOf(activeId);

    try {
      await fetchJson<{ status: string }>(
        `/api/board/${encodeURIComponent(username)}/cards/${activeId}/move`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            targetColumnKey: targetColumn.id,
            targetPosition,
          }),
        },
      );
      await loadBoard();
    } catch (moveError) {
      setError('Unable to move card.');
      console.error(moveError);
      await loadBoard();
    }
  };

  const handleRenameColumn = async (columnId: string, title: string) => {
    setBoard((prev) => ({
      ...prev,
      columns: prev.columns.map((column) =>
        column.id === columnId ? { ...column, title } : column,
      ),
    }));

    if (!username) {
      return;
    }

    try {
      await fetchJson<{ status: string }>(
        `/api/board/${encodeURIComponent(username)}/columns/${columnId}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title }),
        },
      );
      setError('');
    } catch (renameError) {
      setError('Unable to rename column.');
      console.error(renameError);
      await loadBoard();
    }
  };

  const handleAddCard = async (columnId: string, title: string, details: string) => {
    const tempId = createId('temp-card');
    setBoard((prev) => ({
      ...prev,
      cards: {
        ...prev.cards,
        [tempId]: {
          id: tempId,
          title,
          details: details || 'No details yet.',
        },
      },
      columns: prev.columns.map((column) =>
        column.id === columnId ? { ...column, cardIds: [...column.cardIds, tempId] } : column,
      ),
    }));

    if (!username) {
      return;
    }

    try {
      await fetchJson<{ id: number }>(
        `/api/board/${encodeURIComponent(username)}/columns/${columnId}/cards`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title, details }),
        },
      );
      await loadBoard();
      setError('');
    } catch (addError) {
      setError('Unable to persist new card right now.');
      console.error(addError);
      await loadBoard();
    }
  };

  const handleDeleteCard = async (columnId: string, cardId: string) => {
    setBoard((prev) => ({
      ...prev,
      cards: Object.fromEntries(Object.entries(prev.cards).filter(([id]) => id !== cardId)),
      columns: prev.columns.map((column) =>
        column.id === columnId
          ? {
              ...column,
              cardIds: column.cardIds.filter((id) => id !== cardId),
            }
          : column,
      ),
    }));

    if (!username) {
      return;
    }

    try {
      await fetchJson<{ status: string }>(
        `/api/board/${encodeURIComponent(username)}/cards/${cardId}`,
        {
          method: 'DELETE',
        },
      );
      await loadBoard();
      setError('');
    } catch (deleteError) {
      setError('Unable to persist card deletion right now.');
      console.error(deleteError);
      await loadBoard();
    }
  };

  const handleSendChat = async () => {
    if (!username || !chatInput.trim() || isChatLoading) {
      return;
    }

    const message = chatInput.trim();
    setChatInput('');
    setIsChatLoading(true);
    try {
      await fetchJson<AiSendMessageResponse>(`/api/ai/${encodeURIComponent(username)}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      await loadAiContext();
      setChatError('');
    } catch (sendError) {
      setChatInput(message);
      setChatError('Unable to send message to AI right now.');
      console.error(sendError);
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleDecideAction = async (actionId: number, approved: boolean) => {
    if (!username || actingActionId !== null) {
      return;
    }
    setActingActionId(actionId);
    try {
      const result = await fetchJson<AiActionDecisionResponse>(
        `/api/ai/${encodeURIComponent(username)}/actions/${actionId}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ approved }),
        },
      );
      if (approved && result.board) {
        setBoard(toBoardData(result.board));
      } else if (approved) {
        await loadBoard();
      }
      await loadAiContext();
      setChatError('');
    } catch (decisionError) {
      setChatError(
        approved ? 'Unable to apply action right now.' : 'Unable to reject action right now.',
      );
      console.error(decisionError);
      if (approved) {
        await loadBoard();
      }
      await loadAiContext();
    } finally {
      setActingActionId(null);
    }
  };

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-105 w-105 -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,rgba(32,157,215,0.25)_0%,rgba(32,157,215,0.05)_55%,transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-130 w-130 translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,rgba(117,57,145,0.18)_0%,rgba(117,57,145,0.05)_55%,transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-420 flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-4xl border border-(--stroke) bg-white/80 p-8 shadow-(--shadow) backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-(--gray-text)">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-foreground">
                Kanban Studio
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-(--gray-text)">
                Keep momentum visible. Rename columns, drag cards between stages, and capture quick
                notes without getting buried in settings.
              </p>
            </div>
            <div className="rounded-2xl border border-(--stroke) bg-background px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-(--gray-text)">
                Focus
              </p>
              <p className="mt-2 text-lg font-semibold text-(--primary-blue)">
                One board. Five columns. Zero clutter.
              </p>
              {onLogout ? (
                <button
                  type="button"
                  onClick={onLogout}
                  className="mt-4 rounded-full bg-(--secondary-purple) px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110"
                >
                  Log out
                </button>
              ) : null}
            </div>
          </div>
          {isLoading ? (
            <p className="text-sm font-semibold text-(--gray-text)">Loading board...</p>
          ) : null}
          {error ? (
            <p role="alert" className="text-sm font-semibold text-red-600">
              {error}
            </p>
          ) : null}
          <div className="flex flex-wrap items-center gap-4">
            {board.columns.map((column) => (
              <div
                key={column.id}
                className="flex items-center gap-2 rounded-full border border-(--stroke) px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-foreground"
              >
                <span className="h-2 w-2 rounded-full bg-(--accent-yellow)" />
                {column.title}
              </div>
            ))}
          </div>
        </header>

        <div className="grid gap-6">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCorners}
            onDragStart={handleDragStart}
            onDragOver={handleDragOver}
            onDragCancel={() => {
              setActiveCardId(null);
              setOverId(null);
            }}
            onDragEnd={(event) => {
              void handleDragEnd(event);
            }}
          >
            <section className="grid grid-flow-col auto-cols-[minmax(280px,1fr)] gap-6 overflow-x-auto pb-2">
              {board.columns.map((column) => (
                <KanbanColumn
                  key={column.id}
                  column={column}
                  cards={column.cardIds.map((cardId) => board.cards[cardId]).filter(Boolean)}
                  isDropTarget={Boolean(activeCardId) && overColumnId === column.id}
                  onRename={handleRenameColumn}
                  onAddCard={handleAddCard}
                  onDeleteCard={handleDeleteCard}
                />
              ))}
            </section>
            <DragOverlay>
              {activeCard ? (
                <div className="w-65">
                  <KanbanCardPreview card={activeCard} />
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>

          <aside className="flex max-h-[calc(100vh-8rem)] min-h-155 flex-col rounded-3xl border border-(--stroke) bg-(--surface-strong) p-5 shadow-(--shadow)">
            <div className="border-b border-(--stroke) pb-4">
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-(--gray-text)">
                AI Assistant
              </p>
              <h2 className="mt-2 font-display text-2xl font-semibold text-foreground">
                Sidebar Chat
              </h2>
              <p className="mt-2 text-sm leading-6 text-(--gray-text)">
                Ask for card updates. Each proposed action requires approval before it is applied.
              </p>
            </div>

            <div className="mt-4 flex-1 overflow-y-auto pr-1">
              {isChatLoading && chatMessages.length === 0 ? (
                <p className="text-sm font-semibold text-(--gray-text)">
                  Loading AI conversation...
                </p>
              ) : null}
              {chatError ? (
                <p className="mb-3 text-sm font-semibold text-red-600">{chatError}</p>
              ) : null}
              {chatMessages.length === 0 && !isChatLoading ? (
                <p className="rounded-2xl border border-dashed border-(--stroke) px-4 py-3 text-sm text-(--gray-text)">
                  No conversation yet. Ask AI to create, edit, or move cards.
                </p>
              ) : null}
              <div className="space-y-3">
                {chatMessages.map((message) => (
                  <div
                    key={message.id}
                    className={`rounded-2xl border px-4 py-3 text-sm leading-6 ${
                      message.role === 'user'
                        ? 'ml-6 border-(--primary-blue) bg-[rgba(32,157,215,0.08)] text-foreground'
                        : 'mr-6 border-(--stroke) bg-background text-(--gray-text)'
                    }`}
                  >
                    <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.2em]">
                      {message.role === 'user' ? 'You' : message.role}
                    </p>
                    <p>{message.content}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-4 border-t border-(--stroke) pt-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--gray-text)">
                Pending actions
              </p>
              <div className="mt-2 space-y-2">
                {pendingActions.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-(--stroke) px-3 py-2 text-xs text-(--gray-text)">
                    No actions awaiting approval.
                  </p>
                ) : (
                  pendingActions.map((action) => (
                    <div
                      key={action.id}
                      className="rounded-xl border border-(--stroke) bg-background p-3"
                    >
                      <p className="text-sm font-semibold text-foreground">{action.description}</p>
                      <div className="mt-2 flex gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            void handleDecideAction(action.id, true);
                          }}
                          disabled={actingActionId !== null}
                          className="rounded-full bg-(--secondary-purple) px-3 py-1 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {actingActionId === action.id ? 'Applying...' : 'Approve'}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            void handleDecideAction(action.id, false);
                          }}
                          disabled={actingActionId !== null}
                          className="rounded-full border border-(--stroke) px-3 py-1 text-xs font-semibold uppercase tracking-wide text-(--gray-text) transition hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Reject
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="mt-4">
              <label
                htmlFor="ai-chat-input"
                className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-(--gray-text)"
              >
                Message
              </label>
              <textarea
                id="ai-chat-input"
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                className="min-h-23 w-full resize-none rounded-xl border border-(--stroke) bg-white px-3 py-2 text-sm text-foreground outline-none transition focus:border-(--primary-blue)"
                placeholder="Move card 3 to Review and rename it for QA handoff."
              />
              <button
                type="button"
                onClick={() => {
                  void handleSendChat();
                }}
                disabled={!username || isChatLoading || !chatInput.trim()}
                className="mt-3 w-full rounded-full bg-(--secondary-purple) px-4 py-2 text-sm font-semibold uppercase tracking-wide text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isChatLoading ? 'Sending...' : 'Send'}
              </button>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
};
