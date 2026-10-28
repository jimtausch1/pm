# Backend scope

FastAPI backend for the Project Management MVP. It serves the static NextJS export at `/` and the JSON API under `/api`.

## Structure

- [app/main.py](app/main.py): `create_app()` with all routes, OpenRouter calls (`urllib`, model `openai/gpt-oss-120b`), AI response validation and mutation handling. The module-level `app` is what uvicorn runs.
- [app/database.py](app/database.py): `BoardStore`, the only data-access layer (raw `sqlite3`, foreign keys on). Missing users, columns, cards and actions raise `NotFoundError`, which an exception handler in `create_app()` turns into a 404. Covers users, one board per user, columns, cards, chat messages and AI actions.
- [static/index.html](static/index.html): placeholder page shown when no frontend build is present. The Docker build copies the frontend export to `static/frontend/`.
- [tests/test_board_api.py](tests/test_board_api.py): API tests using `TestClient` with a temp database; OpenRouter is mocked by patching `urlopen`.

## Startup

The `_lifespan` handler loads `.env` from the repo root into `os.environ` (existing variables win), opens the database at `PM_DB_PATH` (default `data/pm.db`), creates tables if missing, and seeds user `user` (the only user; any other username gets 404) with five columns (`col-backlog`, `col-discovery`, `col-progress`, `col-review`, `col-done`) and eight sample cards. Initialization is idempotent.

## Routes

- `GET /api/health`
- `GET /api/ai/connectivity-check`: one test prompt to OpenRouter; requires `OPENROUTER_API_KEY`.
- Board (columns addressed by key, cards by integer id):
  - `GET /api/board/{username}`
  - `PATCH /api/board/{username}/columns/{column_key}`: rename
  - `POST /api/board/{username}/columns/{column_key}/cards`: add card
  - `PATCH /api/board/{username}/cards/{card_id}`: edit title/details
  - `DELETE /api/board/{username}/cards/{card_id}`
  - `POST /api/board/{username}/cards/{card_id}/move`: `targetColumnKey`, zero-based `targetPosition`
- AI chat:
  - `GET /api/ai/{username}/chat`: last 50 messages plus pending actions
  - `POST /api/ai/{username}/chat`: see AI flow
  - `POST /api/ai/{username}/actions/{action_id}`: `{"approved": bool}`
- `GET /` and `GET /{file_path:path}`: static files from `static/frontend/`, then `static/`, falling back to the frontend `index.html`.

## AI flow

1. `POST /api/ai/{username}/chat` sends a system contract, the current board JSON, the last 19 stored messages and the new message to OpenRouter, requesting JSON output (`response_format`).
2. The model must reply with strict JSON `{"reply": str, "mutations": [...]}`. Mutations are `create_card` (`columnKey`, `title`, `details?`), `edit_card` (`cardId`, `title?`, `details?`) and `move_card` (`cardId`, `targetColumnKey`, `targetPosition`). A response that breaks the contract returns 502.
3. Only once the reply is valid are the user message and the reply stored, and each mutation becomes a pending `ai_actions` row. Nothing is applied yet.
4. The action decision route marks an action `rejected`, or applies it and marks it `applied` (returning the updated board). If applying fails, the action is marked `failed` and the route returns 404. Deciding an action that is no longer pending returns 409.

## Tests

Run from `backend/`: `python -m pytest`. Coverage: board seeding, rename, add/edit/delete card, moves across and within columns (including to the top of a multi-card column), unknown users (404), connectivity check (success, missing key, invalid key), per-action confirmation, the board and history sent to the AI, rejection of malformed AI responses (with no message stored), `null` details on AI-created cards, and AI actions on deleted cards (marked `failed`).
