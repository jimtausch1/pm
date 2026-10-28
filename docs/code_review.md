# Code review

Date: 2026-10-28. Scope: the whole repository at commit `2c077ce` (backend, frontend, Docker, scripts, tests).

All 11 backend tests and 10 frontend unit tests pass; ESLint and `tsc --noEmit` are clean. Findings marked **Verified** were reproduced against a temp database or through the API with FastAPI's `TestClient`.

## Summary

| # | Severity | Area | Finding |
|---|----------|------|---------|
| 1 | High (fixed) | Backend | Moving a card in front of two or more cards fails with HTTP 500 |
| 2 | Medium (fixed) | Security | API has no authentication and the container listens on all network interfaces |
| 3 | Medium (fixed) | Backend | A failed AI call leaves an orphan user message, and retrying duplicates it |
| 4 | Medium (fixed) | Backend | AI `create_card` with `"details": null` stores the text "None" |
| 5 | Medium (fixed) | Backend | AI JSON parsing is strict with no help from the API, so replies wrapped in code fences fail |
| 6 | Low | Frontend | Seed data with fake ids is shown and editable before the real board loads |
| 7 | Low | Backend | Every read creates a user and board for any username |
| 8 | Low | Backend | `_safe_file` uses a string prefix check |
| 9 | Low | Backend | HTTP status chosen by matching error text |
| 10 | Low | Build | Local database is copied into the Docker image; test output is tracked in git |
| 11 | Low | Tests | No test moves a card in front of multiple cards; e2e never touches the backend |

Simplification items follow the findings.

## Findings

### 1. Moving a card in front of two or more cards fails with HTTP 500 (High, Verified, Fixed)

Status: fixed. `move_card` now shifts destination rows through negative positions, and `test_move_card_to_top_of_column_with_multiple_cards` covers moves to the top of a multi-card column, both across and within columns.

`backend/app/database.py:421-428` opens a gap in the destination column with:

```sql
UPDATE cards SET position = position + 1 WHERE column_id = ? AND position >= ? AND id != ?
```

SQLite checks `UNIQUE(column_id, position)` row by row during an `UPDATE`. When two or more cards sit at or after the target, the first row moved to `n + 1` collides with the card already at `n + 1`, raising `sqlite3.IntegrityError`. The route only catches `ValueError`, so the client gets a 500.

Reproduced:
- Moving card 7 from Done to position 0 of In Progress (two cards) fails: `UNIQUE constraint failed: cards.column_id, cards.position`, HTTP 500.
- Moving the last card of a five-card column to position 0 of the same column fails the same way.
- Moving a card down within its column, deleting a card, and moving into a column with one or zero cards succeed.

Impact: dropping a card onto another card inserts it before that card (`moveCard` in `frontend/src/lib/kanban.ts`), so most drags into a column with two or more cards, and every upward reorder, fail. The UI shows "Unable to move card." and snaps back. AI `move_card` actions fail in the same cases.

The existing test (`test_move_card_across_columns`) moves into a column with only one card, so it never hits the collision.

Fix: shift the affected rows through a range that cannot collide, inside the existing transaction. For example, first set them to negative values, then flip them back:

```sql
UPDATE cards SET position = -(position + 2) WHERE column_id = ? AND position >= ? AND id != ?;
UPDATE cards SET position = -position - 1   WHERE column_id = ? AND position < -1;
```

The second statement turns `-(p + 2)` into `p + 1`, and skipping `-1` leaves the parked card alone. The `-1` shift in the source column already works because it runs in ascending order into freed slots. Add a test that moves a card to position 0 of a column with at least two cards, both within and across columns.

### 2. No API authentication, and the container listens on all network interfaces (Medium, Fixed)

Status: fixed. All three start scripts publish with `-p 127.0.0.1:8000:8000`. The API itself is still unauthenticated, which is the accepted MVP limit.

Login only exists in the browser (`frontend/src/app/page.tsx`, a `localStorage` flag). Every `/api` route trusts the `{username}` in the path. The start scripts publish with `-p 8000:8000` (`scripts/start.sh:14`, `start.ps1:17`, `start.bat:19`), which binds to all network interfaces. Anyone on the same network can read and change the board and call `/api/ai/*`, which spends the `OPENROUTER_API_KEY` credits.

The hardcoded login is an accepted MVP limit, but local-only is a stated requirement. Fix: publish with `-p 127.0.0.1:8000:8000` in all three start scripts.

### 3. Failed AI call leaves an orphan user message, and retrying duplicates it (Medium, Fixed)

Status: fixed. The user message is stored only after the AI reply parses; the current message is appended to the prompt in memory.

`send_ai_chat_message` (`backend/app/main.py`, `POST /api/ai/{username}/chat`) stores the user message before calling OpenRouter. If the call fails, or the reply breaks the contract (502), the message stays in history with no assistant reply. The frontend then puts the text back in the input (`KanbanBoard.tsx:325`) without reloading the chat context. When the user resends, the history holds the same message twice, and every later prompt carries both copies.

Fix: store the user message only after the AI reply has been parsed, and store both messages together.

### 4. AI `create_card` with `"details": null` stores the text "None" (Medium, Fixed)

Status: fixed. Non-string `details` is treated as empty, so the "No details yet." default applies.

`_normalize_mutation` (`backend/app/main.py:305`) uses `str(raw_mutation.get("details", "")).strip()`. `get` returns `None` when the key is present with a `null` value, and `str(None)` is `"None"`. Models often send `null` for optional fields. The card is then saved with details "None", not the "No details yet." default.

Fix: treat a non-string `details` as `""`, as `edit_card` already does. AI-supplied titles and details also skip the 200 and 2000 character limits that the board routes enforce.

### 5. AI JSON parsing is strict with no help from the API (Medium, Fixed)

Status: fixed. Chat requests now send `"response_format": {"type": "json_object"}`.

`_parse_ai_response` runs `json.loads` on the raw reply, and any deviation returns 502. The only protection is a sentence in the system prompt ("Do not include markdown fences..."). Models do wrap JSON in fences from time to time, and the user then sees a generic error.

Fix: ask OpenRouter for JSON output (`"response_format": {"type": "json_object"}` in the request body). Optionally also strip a surrounding code fence before parsing.

### 6. Seed data with fake ids is shown and editable before the real board loads (Low)

`KanbanBoard` starts from `initialData` (`KanbanBoard.tsx:78`), which uses ids like `card-1`. Until `GET /api/board/user` returns, or for good if it fails, the user sees made-up cards. Dragging or deleting them sends requests such as `DELETE /api/board/user/cards/card-1`, which fail validation (422). Starting from an empty board and showing the existing loading and error text would avoid this.

### 7. Every read creates a user and board for any username (Low, Verified)

Every `BoardStore` method calls `ensure_user_board(username)` first, so `GET /api/board/<anything>` inserts a user and a seeded board. Confirmed: adding a card for `anybody-at-all` returns 200. Combined with finding 2, anyone who can reach the port can create unlimited rows. Each call also opens a second connection and runs extra queries.

Fix: create the board once at startup and on sign-in (the MVP has one user), and return 404 for unknown users.

### 8. `_safe_file` uses a string prefix check (Low)

`backend/app/main.py:72-76` checks `str(candidate).startswith(str(base_dir.resolve()))`. A sibling directory whose name starts with the same text (for example `static/frontend-old`) would pass the check. No such directory exists today. `candidate.is_relative_to(base_dir.resolve())` is the exact check.

### 9. HTTP status chosen by matching error text (Low)

`decide_ai_action` maps errors to 404 if the message contains "not found", and `update_card` returns 400 if the message contains "At least one field". Renaming a message silently changes the status code. A `NotFoundError(ValueError)` subclass in `database.py` would make this explicit.

### 10. Build and repo hygiene (Low)

- `Dockerfile` copies `backend/` wholesale, so the local `backend/data/pm.db` (board and chat history) ends up in the image. The runtime volume hides it, but anyone with the image can read it. Add `backend/data` to `.dockerignore`.
- `frontend/test-results/.last-run.json` is tracked in git. It is Playwright output and should be ignored.
- Backend dependencies are declared twice (`pyproject.toml` and `requirements.txt`) with no lockfile. Pick one source, for example `pyproject.toml` with `uv.lock` and `uv sync` in the Dockerfile, which also matches the "use uv" decision in `AGENTS.md`.

### 11. Test gaps (Low)

- No backend test moved a card in front of two or more cards (this hid finding 1; now covered).
- Playwright runs `next dev` with no backend, so drag-and-drop, persistence and the AI sidebar are never tested end to end. Running e2e against the Docker container (or uvicorn serving a build) would have caught finding 1.
- No tests cover `create_card` with `null` details or an orphaned chat message after an AI failure.

## Simplification

- `backend/app/main.py`: `_openrouter_connectivity_check` and `_openrouter_chat_completion` duplicate the request, error handling and JSON decoding code. The check can call `_openrouter_chat_completion([{"role": "user", "content": "2+2"}])`.
- `backend/app/main.py`: `GET /api/hello` is leftover scaffolding.
- `backend/app/main.py`: the `requiresConfirmation` field on pending actions is always `true` and the frontend never reads it.
- `frontend/src/components/KanbanBoard.tsx:66`: the `typeof window` branch in `fetchJson` is dead code, since calls only run in the browser. `fetch(url, init)` with a relative URL is enough.
- `frontend/src/components/KanbanBoard.tsx:97`: `useMemo(() => board.cards, [board.cards])` returns its input unchanged; use `board.cards` directly.
- `KanbanBoard.tsx` holds board state, chat state, nine handlers and the full sidebar markup in one 580-line component. Moving the sidebar into its own `AiSidebar` component would make both halves easier to follow.
- `database.py`: `with self._connect() as connection` commits or rolls back but does not close the connection; CPython closes it when the function returns, but `contextlib.closing` makes that explicit.

## What is working well

- AI changes are never applied without a per-action user approval, which contains the impact of prompt injection through card text or chat.
- AI output is validated field by field before it is stored, and the contract is covered by tests.
- SQL uses parameters throughout; foreign keys are on and cascades are defined.
- The static file route resolves paths and refuses traversal outside the static directories.
- The frontend is lint-clean against the React Compiler rules after the recent hook fixes.

## Recommended order

1. Done: move collision (finding 1) fixed and tested.
2. Done: container bound to `127.0.0.1` (finding 2).
3. Done: AI chat issues (findings 3, 4 and 5) fixed and tested.
4. The rest as time allows.
