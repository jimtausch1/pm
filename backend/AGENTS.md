# Backend scope

This folder contains the FastAPI backend for the Project Management MVP.

Current phase-2 baseline includes:
- [app/main.py](C:/Repos/pm/backend/app/main.py): FastAPI app with:
  - `GET /` serving static frontend output
  - `GET /api/health`
  - `GET /api/hello`
  - `GET /api/ai/connectivity-check`
  - `GET /api/ai/{username}/chat`
  - `POST /api/ai/{username}/chat`
  - `POST /api/ai/{username}/actions/{action_id}`
  - `GET /api/board/{username}`
  - `PATCH /api/board/{username}/columns/{column_key}`
  - `POST /api/board/{username}/columns/{column_key}/cards`
  - `PATCH /api/board/{username}/cards/{card_id}`
  - `DELETE /api/board/{username}/cards/{card_id}`
  - `POST /api/board/{username}/cards/{card_id}/move`
- [app/database.py](C:/Repos/pm/backend/app/database.py): SQLite initialization, board persistence, chat history, and pending AI mutation actions.
- [tests/test_board_api.py](C:/Repos/pm/backend/tests/test_board_api.py): backend unit tests for board operations, OpenRouter integration behavior, and AI mutation confirmation flow.
- [pyproject.toml](C:/Repos/pm/backend/pyproject.toml): backend dependency definition.

Next phase adds the frontend sidebar experience on top of these AI routes.