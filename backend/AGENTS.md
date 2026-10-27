# Backend scope

This folder contains the FastAPI backend for the Project Management MVP.

Current phase-2 baseline includes:
- [app/main.py](C:/Repos/pm/backend/app/main.py): FastAPI app with:
  - `GET /` serving [static/index.html](C:/Repos/pm/backend/static/index.html)
  - `GET /api/health`
  - `GET /api/hello`
- [pyproject.toml](C:/Repos/pm/backend/pyproject.toml): backend dependency definition.

Next phases add authentication, SQLite persistence, and AI routes.