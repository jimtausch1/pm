'use client';

import { fetchJson } from '@/lib/api';
import type { BackendBoard } from '@/lib/kanban';
import { useCallback, useEffect, useState } from 'react';

type AiChatMessage = {
  id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  createdAt: string;
};

type AiPendingAction = {
  id: number;
  actionType: 'create_card' | 'edit_card' | 'move_card';
  payload: Record<string, unknown>;
  description: string;
  createdAt: string;
};

type AiChatContextResponse = {
  messages: AiChatMessage[];
  pendingActions: AiPendingAction[];
};

type AiActionDecisionResponse = {
  status: 'applied' | 'rejected';
  board?: BackendBoard;
};

type AiSidebarProps = {
  username: string;
  // Called with the updated board after an approval, or with no board when it should be reloaded.
  onBoardChange: (board?: BackendBoard) => void;
};

export const AiSidebar = ({ username, onBoardChange }: AiSidebarProps) => {
  const [chatMessages, setChatMessages] = useState<AiChatMessage[]>([]);
  const [pendingActions, setPendingActions] = useState<AiPendingAction[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(true);
  const [chatError, setChatError] = useState('');
  const [actingActionId, setActingActionId] = useState<number | null>(null);

  const loadAiContext = useCallback(async () => {
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
    void loadAiContext();
  }, [loadAiContext]);

  const handleSendChat = async () => {
    if (!chatInput.trim() || isChatLoading) {
      return;
    }

    const message = chatInput.trim();
    setChatInput('');
    setIsChatLoading(true);
    try {
      await fetchJson(`/api/ai/${encodeURIComponent(username)}/chat`, {
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
    if (actingActionId !== null) {
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
      if (approved) {
        onBoardChange(result.board);
      }
      await loadAiContext();
      setChatError('');
    } catch (decisionError) {
      setChatError(
        approved ? 'Unable to apply action right now.' : 'Unable to reject action right now.',
      );
      console.error(decisionError);
      if (approved) {
        onBoardChange();
      }
      await loadAiContext();
    } finally {
      setActingActionId(null);
    }
  };

  return (
    <aside className="flex max-h-[calc(100vh-8rem)] min-h-155 flex-col rounded-3xl border border-(--stroke) bg-(--surface-strong) p-5 shadow-(--shadow) xl:sticky xl:top-6 xl:h-[calc(100vh-3rem)] xl:max-h-none xl:min-h-0">
      <div className="border-b border-(--stroke) pb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-(--gray-text)">
          AI Assistant
        </p>
        <h2 className="mt-2 font-display text-2xl font-semibold text-foreground">Sidebar Chat</h2>
        <p className="mt-2 text-sm leading-6 text-(--gray-text)">
          Ask for card updates. Each proposed action requires approval before it is applied.
        </p>
      </div>

      <div className="mt-4 flex-1 overflow-y-auto pr-1">
        {isChatLoading && chatMessages.length === 0 ? (
          <p className="text-sm font-semibold text-(--gray-text)">Loading AI conversation...</p>
        ) : null}
        {chatError ? <p className="mb-3 text-sm font-semibold text-red-600">{chatError}</p> : null}
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
              <div key={action.id} className="rounded-xl border border-(--stroke) bg-background p-3">
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
          disabled={isChatLoading || !chatInput.trim()}
          className="mt-3 w-full rounded-full bg-(--secondary-purple) px-4 py-2 text-sm font-semibold uppercase tracking-wide text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isChatLoading ? 'Sending...' : 'Send'}
        </button>
      </div>
    </aside>
  );
};
