# Database approach

## Scope

This document defines the persistence approach for MVP and the path to future multi-user support.

- Schema artifact: [database-schema.json](./database-schema.json)
- Database engine: SQLite
- Database file target: `backend/data/pm.db`

## MVP model

- Authentication is hardcoded (`user` / `password`) in MVP UI logic.
- Persistence still uses a `users` table to keep the model future-ready.
- Exactly one board per user is enforced by:
  - application logic, and
  - a unique index on `boards.user_id`.

## Core entities

- `users`: logical account records.
- `boards`: one board for each user (MVP).
- `columns`: ordered, board-owned columns with editable titles.
- `cards`: ordered, column-owned cards with title/details.
- `chat_messages`: AI sidebar history context per board.
- `ai_actions`: pending/applied/rejected AI mutation requests that require user confirmation.

## Ordering strategy

- Columns and cards use integer `position`.
- Each board enforces unique `(board_id, position)` for columns.
- Each column enforces unique `(column_id, position)` for cards.
- Reorder operations update positions in a transaction.

## Initialization strategy

- On backend startup, if the SQLite file or required tables do not exist, create them.
- Seed one user (`username = "user"`) and one board with five default columns if missing.
- Keep initialization idempotent to support repeated container starts.

## Why this fits MVP and future phases

- Keeps MVP implementation simple and local.
- Supports current required operations (rename/move/edit/add/delete cards).
- Stores AI conversation context and per-action confirmation state for safe mutation flows.
- Avoids schema rewrites when real auth/multi-user is introduced later.
