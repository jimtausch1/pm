# Frontend baseline: current implementation

## Purpose

This frontend is a standalone NextJS Kanban demo application. It currently runs without a backend and keeps board state in local React state only.

## Stack and tooling

- NextJS 16 (App Router) with React 19 and TypeScript
- Tailwind CSS v4 for styling
- `@dnd-kit` for drag-and-drop behavior
- Unit tests with Vitest + Testing Library
- End-to-end tests with Playwright

Reference files:
- [package.json](C:/Repos/pm/frontend/package.json)
- [src/app/page.tsx](C:/Repos/pm/frontend/src/app/page.tsx)
- [src/components/KanbanBoard.tsx](C:/Repos/pm/frontend/src/components/KanbanBoard.tsx)
- [src/lib/kanban.ts](C:/Repos/pm/frontend/src/lib/kanban.ts)

## Functional baseline

### Board rendering
- [KanbanBoard](C:/Repos/pm/frontend/src/components/KanbanBoard.tsx) renders five columns from [initialData](C:/Repos/pm/frontend/src/lib/kanban.ts:16).
- The page entrypoint [Home](C:/Repos/pm/frontend/src/app/page.tsx:3) renders only this board component.

### Card interactions
- Drag-and-drop uses `DndContext` and sortable cards.
- Columns can be renamed inline.
- Cards can be created with title/details.
- Cards can be deleted.
- All interactions mutate in-memory state only; nothing persists across reload.

### Data model
- [kanban.ts](C:/Repos/pm/frontend/src/lib/kanban.ts) defines `Card`, `Column`, and `BoardData`.
- `moveCard` handles same-column reordering and cross-column moves.
- `createId` generates client-side IDs for new cards.

## Existing tests

- Unit tests:
  - [KanbanBoard.test.tsx](C:/Repos/pm/frontend/src/components/KanbanBoard.test.tsx)
  - [kanban.test.ts](C:/Repos/pm/frontend/src/lib/kanban.test.ts)
- E2E tests:
  - [kanban.spec.ts](C:/Repos/pm/frontend/tests/kanban.spec.ts)

Current tests verify:
- Five-column rendering
- Column rename
- Card add/remove
- Basic drag-and-drop between columns

## Integration assumptions for backend migration

- Current UI behavior should remain functionally equivalent during backend integration.
- New login, persistence, and AI features should layer onto existing components with minimal disruption.
- Tests should be extended, not replaced, so baseline interactions continue to be validated.
