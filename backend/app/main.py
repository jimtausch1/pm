import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path as ApiPath
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .database import BoardStore

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
STATIC_DIR = BACKEND_DIR / "static"
FRONTEND_DIR = STATIC_DIR / "frontend"
FRONTEND_INDEX_FILE = FRONTEND_DIR / "index.html"
FALLBACK_INDEX_FILE = STATIC_DIR / "index.html"
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "pm.db"


class RenameColumnRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class AddCardRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(default="", max_length=2000)


class UpdateCardRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    details: str | None = Field(default=None, max_length=2000)


class MoveCardRequest(BaseModel):
    targetColumnKey: str = Field(min_length=1, max_length=80)
    targetPosition: int = Field(ge=0)


def _safe_file(base_dir: Path, relative_path: str) -> Path | None:
    candidate = (base_dir / relative_path).resolve()
    if not str(candidate).startswith(str(base_dir.resolve())):
        return None
    return candidate if candidate.is_file() else None


def _db_path() -> Path:
    configured = os.getenv("PM_DB_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_DB_PATH


@asynccontextmanager
async def _lifespan(app: FastAPI):
    store = BoardStore(_db_path())
    store.initialize()
    store.ensure_user_board("user")
    app.state.store = store
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Project Management MVP", lifespan=_lifespan)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/hello")
    def hello() -> dict[str, str]:
        return {"message": "Hello from FastAPI"}

    @app.get("/api/board/{username}")
    def get_board(
        username: Annotated[str, ApiPath(min_length=1, max_length=80)]
    ) -> dict:
        return app.state.store.get_board(username)

    @app.patch("/api/board/{username}/columns/{column_key}")
    def rename_column(
        username: Annotated[str, ApiPath(min_length=1, max_length=80)],
        column_key: Annotated[str, ApiPath(min_length=1, max_length=80)],
        payload: RenameColumnRequest,
    ) -> dict[str, str]:
        try:
            app.state.store.rename_column(username, column_key, payload.title.strip())
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"status": "ok"}

    @app.post("/api/board/{username}/columns/{column_key}/cards")
    def add_card(
        username: Annotated[str, ApiPath(min_length=1, max_length=80)],
        column_key: Annotated[str, ApiPath(min_length=1, max_length=80)],
        payload: AddCardRequest,
    ) -> dict[str, int]:
        try:
            card_id = app.state.store.add_card(
                username, column_key, payload.title.strip(), payload.details.strip()
            )
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"id": card_id}

    @app.patch("/api/board/{username}/cards/{card_id}")
    def update_card(
        username: Annotated[str, ApiPath(min_length=1, max_length=80)],
        card_id: Annotated[int, ApiPath(ge=1)],
        payload: UpdateCardRequest,
    ) -> dict[str, str]:
        title = payload.title.strip() if payload.title is not None else None
        details = payload.details.strip() if payload.details is not None else None
        try:
            app.state.store.update_card(username, card_id, title=title, details=details)
        except ValueError as error:
            message = str(error)
            status_code = 400 if "At least one field" in message else 404
            raise HTTPException(status_code=status_code, detail=message) from error
        return {"status": "ok"}

    @app.delete("/api/board/{username}/cards/{card_id}")
    def delete_card(
        username: Annotated[str, ApiPath(min_length=1, max_length=80)],
        card_id: Annotated[int, ApiPath(ge=1)],
    ) -> dict[str, str]:
        try:
            app.state.store.delete_card(username, card_id)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"status": "ok"}

    @app.post("/api/board/{username}/cards/{card_id}/move")
    def move_card(
        username: Annotated[str, ApiPath(min_length=1, max_length=80)],
        card_id: Annotated[int, ApiPath(ge=1)],
        payload: MoveCardRequest,
    ) -> dict[str, str]:
        try:
            app.state.store.move_card(
                username,
                card_id,
                payload.targetColumnKey,
                payload.targetPosition,
            )
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"status": "ok"}

    @app.get("/")
    def root() -> FileResponse:
        if FRONTEND_INDEX_FILE.exists():
            return FileResponse(FRONTEND_INDEX_FILE)
        return FileResponse(FALLBACK_INDEX_FILE)

    @app.get("/{file_path:path}")
    def static_files(file_path: str) -> FileResponse:
        if file_path.startswith("api/"):
            raise HTTPException(status_code=404)

        frontend_file = _safe_file(FRONTEND_DIR, file_path)
        if frontend_file:
            return FileResponse(frontend_file)

        fallback_file = _safe_file(STATIC_DIR, file_path)
        if fallback_file:
            return FileResponse(fallback_file)

        if FRONTEND_INDEX_FILE.exists():
            return FileResponse(FRONTEND_INDEX_FILE)

        raise HTTPException(status_code=404)

    return app


app = create_app()
