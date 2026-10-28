# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Project requirements, coding standards and the color scheme are in `AGENTS.md` (root); follow it. Progress is tracked in `docs/PLAN.md`, and the schema is described in `docs/DATABASE.md` and `docs/database-schema.json`. Note that `frontend/AGENTS.md` describes the original frontend-only demo and is out of date.

## Commands

Run the full app (Docker, http://localhost:8000; SQLite data persists in `backend/data/`):

```
scripts/start.sh | scripts/start.ps1 | scripts/start.bat
scripts/stop.sh  | scripts/stop.ps1  | scripts/stop.bat
```

Frontend (run from `frontend/`):

```
npm run dev                 # Next dev server (no backend; /api calls fail)
npm run build               # static export to frontend/out
npm run lint
npm run test:unit           # Vitest
npx vitest run src/components/KanbanBoard.test.tsx   # single file
npx vitest run -t "adds and removes a card"          # single test by name
npm run test:e2e            # Playwright, starts its own dev server on :3101
```

Backend (run from `backend/`, imports are `app.*`):

```
pip install -r requirements-dev.txt   # in the container, uv is used instead
python -m pytest
python -m pytest tests/test_board_api.py -k <name>
uvicorn app.main:app --reload --port 8000   # shows backend/static/index.html placeholder unless a frontend build is in backend/static/frontend
```

## Architecture

Single container: the Dockerfile builds the Next.js app as a static export (`output: "export"`) and copies `frontend/out` to `backend/static/frontend`. FastAPI (`backend/app/main.py`) serves `/api/*` routes and a catch-all `/{file_path:path}` route that serves files from the static export, falling back to its `index.html`. The frontend calls the API with same-origin relative URLs, so frontend and backend only work together when served through FastAPI (Docker, or a local build copied into `backend/static/frontend`).

Backend:
- `main.py` builds the app in `create_app()`. On startup, `_lifespan` loads `.env` from the repo root into `os.environ`, opens `BoardStore` at `PM_DB_PATH` (default `backend/data/pm.db`), creates the tables if needed, and seeds the `user` board. Tests set `PM_DB_PATH` to a temp file and call `create_app()`.
- `database.py` has `BoardStore`, the only data-access layer (raw `sqlite3`). It handles users, the one board per user, columns and cards ordered by integer `position`, chat history and AI actions.
- All board routes are keyed by `username` in the path (`/api/board/{username}/...`). Columns are addressed by a column key, and cards by an integer id.

AI flow (OpenRouter, model `openai/gpt-oss-120b`, called with `urllib`):
1. `POST /api/ai/{username}/chat` sends the system contract, the current board JSON and recent chat history.
2. The model must return strict JSON `{"reply": str, "mutations": [...]}`, where each mutation is `create_card`, `edit_card` or `move_card`. `_parse_ai_response` and `_normalize_mutation` validate it; a violation returns 502.
3. Mutations are not applied directly. They are stored as pending `ai_actions`, and the user confirms or rejects each one via `POST /api/ai/{username}/actions/{action_id}`, which applies it and returns the updated board.

Frontend:
- `src/app/page.tsx` has the hardcoded login (`user`/`password`). The auth flag is kept in `localStorage` and read with `useSyncExternalStore`.
- `src/components/KanbanBoard.tsx` holds the board and AI sidebar state, all API calls (`fetchJson`) and the dnd-kit drag handling. Board edits update local state optimistically, then reload the board from the backend whether the request succeeds or fails; confirming an AI action uses the board returned by the server.
- `src/lib/kanban.ts` has the client-side types, `moveCard` and `toBoardData`, which converts the backend board shape into the UI's `BoardData`.
- The colors are CSS variables in `src/app/globals.css`, used through Tailwind v4 shorthand (`text-(--gray-text)`). `--navy-dark` and `--surface` are mapped to `text-foreground` and `bg-background`.
