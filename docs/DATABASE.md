# Database approach

## Scope

Persistence for the MVP, built so multi-user support can be added later without schema changes.

- Engine: SQLite via Python `sqlite3`, with `PRAGMA foreign_keys = ON` on every connection
- File: `backend/data/pm.db` (override with `PM_DB_PATH`)
- Code: `BoardStore` in [backend/app/database.py](../backend/app/database.py), the only data-access layer
- Schema artifact: [database-schema.json](./database-schema.json)

## Tables

- `users`: accounts, unique `username`.
- `boards`: one per user (`user_id` is `UNIQUE`), named "Main Board".
- `columns`: board-owned columns with a stable `key` (e.g. `col-backlog`), an editable `title` and a `position`. Unique on `(board_id, key)` and `(board_id, position)`.
- `cards`: column-owned cards with `title`, `details` (defaults to "No details yet.") and a `position`. Cards also store `board_id` so lookups can be scoped to the board. Unique on `(column_id, position)`.
- `chat_messages`: AI sidebar history per board; `role` is `user`, `assistant` or `system`. Indexed on `(board_id, created_at)`.
- `ai_actions`: AI-proposed mutations with `action_type`, `payload_json`, `status` (`pending`, `applied`, `rejected`, `failed`), an optional `error_message`, and a link to the assistant message that proposed them (`ON DELETE SET NULL`). Indexed on `(board_id, status, created_at)`.

All child tables cascade on delete from their board. The API refers to columns by `key` and to cards by numeric `id`.

## Initialization

- On backend startup, `initialize()` creates the data directory and runs `CREATE TABLE IF NOT EXISTS` for every table, so repeated starts are safe.
- Startup then calls `ensure_user_board("user")`.
- Other methods do not create users: an unknown username raises `NotFoundError` (HTTP 404).
- A new board is seeded with five columns (`col-backlog` Backlog, `col-discovery` Discovery, `col-progress` In Progress, `col-review` Review, `col-done` Done) and eight sample cards.

## Ordering

Columns and cards use zero-based integer `position`.

- Adding a card appends it at the end of its column.
- Deleting a card shifts later cards in that column up by one.
- Moving a card clamps the target position to the valid range and runs in one transaction. It parks the card at position `-1`, closes the gap in the source column, opens a gap in the destination column, then places the card. This keeps the unique `(column_id, position)` constraint satisfied at each step.

## MVP limits

Login is hardcoded (`user` / `password`) in the frontend, and there is no authentication on the API: the username in the URL selects the board.
