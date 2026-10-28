# Frontend scope

NextJS frontend for the Project Management MVP. It is built as a static export (`output: "export"`) and served by the FastAPI backend at `/`; all data comes from the backend `/api` routes via same-origin relative URLs.

## Stack and tooling

- NextJS 16 (App Router) with React 19 and TypeScript
- Tailwind CSS v4 for styling
- `@dnd-kit` for drag-and-drop behavior
- Unit tests with Vitest + Testing Library
- End-to-end tests with Playwright

## Structure

- [src/app/page.tsx](src/app/page.tsx): sign-in gate. Credentials are hardcoded (`user` / `password`); the signed-in flag is stored in `localStorage` and read with `useSyncExternalStore`. Once signed in it renders `KanbanBoard` with `username="user"`.
- [src/components/KanbanBoard.tsx](src/components/KanbanBoard.tsx): the board. Owns board state, the board API calls and the dnd-kit handlers, and renders `AiSidebar`.
- [src/components/AiSidebar.tsx](src/components/AiSidebar.tsx): chat, pending actions and approve/reject. Calls `onBoardChange` with the board returned by an approval, or with nothing to make the board reload.
- [src/lib/api.ts](src/lib/api.ts): `fetchJson`, shared by both components.
- [src/components/KanbanColumn.tsx](src/components/KanbanColumn.tsx), [KanbanCard.tsx](src/components/KanbanCard.tsx), [KanbanCardPreview.tsx](src/components/KanbanCardPreview.tsx), [NewCardForm.tsx](src/components/NewCardForm.tsx): presentational pieces; columns hold the inline title editor.
- [src/lib/kanban.ts](src/lib/kanban.ts): `Card`, `Column`, `BoardData` types, `moveCard` (same-column reorder and cross-column moves), `createId`, and `toBoardData`, which maps the backend board (column `key`, numeric card ids) to `BoardData` (column `id`, string card ids).

## Behavior

### Board
- Starts empty and loads `GET /api/board/{username}` on mount; the backend is the only source of board data.
- Rename column, add card, delete card and drag-and-drop move update local state optimistically, call the matching backend route, then reload the board whether the request succeeds or fails.
- Cards cannot be edited directly in the UI; edits happen through the AI sidebar.

### AI sidebar
- Loads chat history and pending actions from `GET /api/ai/{username}/chat`.
- Sending a message posts to the same route, then reloads the chat context.
- AI-proposed mutations (`create_card`, `edit_card`, `move_card`) appear as pending actions. Approving or rejecting one posts to `/api/ai/{username}/actions/{actionId}`; an approval replaces the board with the board returned by the server.
- Sending is disabled until a message is typed.

## Tests

- Unit (`npm run test:unit`):
  - [page.test.tsx](src/app/page.test.tsx): sign-in gate, invalid credentials, logout
  - [KanbanBoard.test.tsx](src/components/KanbanBoard.test.tsx): board load, rename (persisted), add/remove card, send button state
  - Both component tests stub `fetch` with the in-memory API in [src/test/fakeBackend.ts](src/test/fakeBackend.ts).
  - [kanban.test.ts](src/lib/kanban.test.ts): `moveCard`
- E2E (`npm run test:e2e`): [kanban.spec.ts](tests/kanban.spec.ts) covers board load, add card and move card (both checked after reload), moving in front of the top card of a multi-card column, drop-target highlight and logout. Playwright builds the static export and [tests/e2e-server.mjs](tests/e2e-server.mjs) serves it through the FastAPI backend on port 3101 with a fresh temp database (needs Python with the backend requirements installed; set `PYTHON` to override the interpreter). Tests share that database and run in file order.
