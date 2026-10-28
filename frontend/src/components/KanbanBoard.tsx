'use client';

import { AiSidebar } from '@/components/AiSidebar';
import { KanbanCardPreview } from '@/components/KanbanCardPreview';
import { KanbanColumn } from '@/components/KanbanColumn';
import { fetchJson } from '@/lib/api';
import {
  createId,
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
  username: string;
  onLogout?: () => void;
};

export const KanbanBoard = ({ username, onLogout }: KanbanBoardProps) => {
  const [board, setBoard] = useState<BoardData>({ columns: [], cards: {} });
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');


  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    }),
  );

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

  useEffect(() => {
    void loadBoard();
  }, [loadBoard]);

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

  const handleBoardChange = (backendBoard?: BackendBoard) => {
    if (backendBoard) {
      setBoard(toBoardData(backendBoard));
    } else {
      void loadBoard();
    }
  };

  const activeCard = activeCardId ? board.cards[activeCardId] : null;

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

          <AiSidebar username={username} onBoardChange={handleBoardChange} />
        </div>
      </main>
    </div>
  );
};
