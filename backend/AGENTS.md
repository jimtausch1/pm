# Backend scope

This folder contains the FastAPI backend for the Project Management MVP.

Current phase-2 baseline includes:
- [app/main.py](C:/Repos/pm/backend/app/main.py): FastAPI app with:
  - `GET /` serving static frontend output
  - `GET /api/health`
  - `GET /api/hello`
  - `GET /api/board/{username}`
  - `PATCH /api/board/{username}/columns/{column_key}`
  - `POST /api/board/{username}/columns/{column_key}/cards`
  - `PATCH /api/board/{username}/cards/{card_id}`
  - `DELETE /api/board/{username}/cards/{card_id}`
  - `POST /api/board/{username}/cards/{card_id}/move`
- [app/database.py](C:/Repos/pm/backend/app/database.py): SQLite initialization, default board seeding, and board mutation operations.
- [tests/test_board_api.py](C:/Repos/pm/backend/tests/test_board_api.py): backend unit tests for create/edit/delete/move/rename operations.
- [pyproject.toml](C:/Repos/pm/backend/pyproject.toml): backend dependency definition.

Next phases add frontend API wiring and AI routes.