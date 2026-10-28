import os
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from urllib import error as urllib_error
from urllib import request as urllib_request

from fastapi import FastAPI, HTTPException, Path as ApiPath, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .database import BoardStore, NotFoundError

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
STATIC_DIR = BACKEND_DIR / "static"
FRONTEND_DIR = STATIC_DIR / "frontend"
FRONTEND_INDEX_FILE = FRONTEND_DIR / "index.html"
FALLBACK_INDEX_FILE = STATIC_DIR / "index.html"
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "pm.db"
REPO_ROOT = BACKEND_DIR.parent
ENV_FILE_PATH = REPO_ROOT / ".env"
OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-120b"


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


class AiChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class AiActionDecisionRequest(BaseModel):
    approved: bool


SUPPORTED_MUTATION_TYPES = {"create_card", "edit_card", "move_card"}


def _load_env_file() -> None:
    if not ENV_FILE_PATH.exists():
        return

    for raw_line in ENV_FILE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        cleaned_key = key.strip()
        cleaned_value = value.strip().strip("'").strip('"')
        os.environ.setdefault(cleaned_key, cleaned_value)


def _safe_file(base_dir: Path, relative_path: str) -> Path | None:
    candidate = (base_dir / relative_path).resolve()
    if not candidate.is_relative_to(base_dir.resolve()):
        return None
    return candidate if candidate.is_file() else None


def _db_path() -> Path:
    configured = os.getenv("PM_DB_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_DB_PATH


def _openrouter_api_key() -> str:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENROUTER_API_KEY is not configured. Set it in the environment or .env file.",
        )
    return api_key


def _extract_openrouter_error_message(error_body: str) -> str:
    if not error_body:
        return "No response body"
    try:
        payload = json.loads(error_body)
    except json.JSONDecodeError:
        return error_body

    if isinstance(payload, dict):
        error_value = payload.get("error")
        if isinstance(error_value, dict):
            message = error_value.get("message")
            if isinstance(message, str) and message.strip():
                return message
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message
    return error_body


def _extract_openrouter_reply(payload: dict) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise HTTPException(
            status_code=502,
            detail="OpenRouter response was missing choices.",
        )

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise HTTPException(
            status_code=502,
            detail="OpenRouter response contained an invalid choice payload.",
        )

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise HTTPException(
            status_code=502,
            detail="OpenRouter response was missing message content.",
        )

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(
            status_code=502,
            detail="OpenRouter response contained empty message content.",
        )
    return content.strip()


def _openrouter_connectivity_check() -> dict[str, str]:
    request_body = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": "2+2"}],
    }
    request = urllib_request.Request(
        OPENROUTER_CHAT_COMPLETIONS_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_openrouter_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(request, timeout=20) as response:
            raw_response = response.read()
    except urllib_error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        message = _extract_openrouter_error_message(error_body)
        raise HTTPException(
            status_code=502,
            detail=f"OpenRouter request failed ({error.code}): {message}",
        ) from error
    except urllib_error.URLError as error:
        raise HTTPException(
            status_code=502,
            detail=f"OpenRouter request failed: {error.reason}",
        ) from error

    try:
        payload = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=502,
            detail="OpenRouter response was not valid JSON.",
        ) from error

    return {"model": OPENROUTER_MODEL, "reply": _extract_openrouter_reply(payload)}


def _openrouter_chat_completion(messages: list[dict[str, str]]) -> str:
    request_body = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    request = urllib_request.Request(
        OPENROUTER_CHAT_COMPLETIONS_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_openrouter_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(request, timeout=30) as response:
            raw_response = response.read()
    except urllib_error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        message = _extract_openrouter_error_message(error_body)
        raise HTTPException(
            status_code=502,
            detail=f"OpenRouter request failed ({error.code}): {message}",
        ) from error
    except urllib_error.URLError as error:
        raise HTTPException(
            status_code=502,
            detail=f"OpenRouter request failed: {error.reason}",
        ) from error

    try:
        payload = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=502,
            detail="OpenRouter response was not valid JSON.",
        ) from error

    return _extract_openrouter_reply(payload)


def _build_ai_messages(board: dict, recent_history: list[dict]) -> list[dict[str, str]]:
    system_instructions = (
        "You are an assistant for a project management Kanban board. "
        "Always respond as strict JSON with this exact top-level shape: "
        '{"reply":"string","mutations":[...]} . '
        "The reply field is always required and must be plain text for the user. "
        "The mutations field must be an array. Use an empty array when no changes are needed. "
        "Supported mutation types are create_card, edit_card, and move_card. "
        "For create_card provide: type, columnKey, title, details(optional). "
        "For edit_card provide: type, cardId, and at least one of title or details. "
        "For move_card provide: type, cardId, targetColumnKey, targetPosition (zero-based integer). "
        "Do not include markdown fences or extra keys outside this contract."
    )
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_instructions},
        {
            "role": "system",
            "content": f"Current board JSON:\n{json.dumps(board, separators=(',', ':'))}",
        },
    ]
    for history_item in recent_history:
        role = history_item.get("role")
        content = history_item.get("content")
        if role in {"user", "assistant", "system"} and isinstance(content, str):
            messages.append({"role": role, "content": content})
    return messages


def _normalize_card_id(value: object, field_name: str) -> int:
    try:
        card_id = int(str(value))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=502,
            detail=f"AI mutation field '{field_name}' must be an integer card id.",
        ) from None
    if card_id < 1:
        raise HTTPException(
            status_code=502,
            detail=f"AI mutation field '{field_name}' must be >= 1.",
        )
    return card_id


def _normalize_required_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise HTTPException(
            status_code=502,
            detail=f"AI mutation field '{field_name}' must be a string.",
        )
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(
            status_code=502,
            detail=f"AI mutation field '{field_name}' cannot be empty.",
        )
    return cleaned


def _normalize_mutation(raw_mutation: object) -> dict:
    if not isinstance(raw_mutation, dict):
        raise HTTPException(status_code=502, detail="Each AI mutation must be an object.")

    mutation_type = _normalize_required_string(raw_mutation.get("type"), "type")
    if mutation_type not in SUPPORTED_MUTATION_TYPES:
        raise HTTPException(
            status_code=502,
            detail=f"Unsupported AI mutation type: {mutation_type}",
        )

    if mutation_type == "create_card":
        details = raw_mutation.get("details")
        return {
            "type": mutation_type,
            "columnKey": _normalize_required_string(
                raw_mutation.get("columnKey"), "columnKey"
            ),
            "title": _normalize_required_string(raw_mutation.get("title"), "title"),
            "details": details.strip() if isinstance(details, str) else "",
        }

    if mutation_type == "edit_card":
        title = raw_mutation.get("title")
        details = raw_mutation.get("details")
        normalized_title = title.strip() if isinstance(title, str) else None
        normalized_details = details.strip() if isinstance(details, str) else None
        if not normalized_title and not normalized_details:
            raise HTTPException(
                status_code=502,
                detail="AI edit_card mutation requires title or details.",
            )
        return {
            "type": mutation_type,
            "cardId": _normalize_card_id(raw_mutation.get("cardId"), "cardId"),
            "title": normalized_title if normalized_title else None,
            "details": normalized_details if normalized_details else None,
        }

    target_position = raw_mutation.get("targetPosition")
    if isinstance(target_position, bool):
        target_position = None
    try:
        normalized_target_position = int(target_position)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=502,
            detail="AI move_card mutation requires integer targetPosition.",
        ) from None
    if normalized_target_position < 0:
        raise HTTPException(
            status_code=502,
            detail="AI move_card mutation targetPosition must be >= 0.",
        )

    return {
        "type": mutation_type,
        "cardId": _normalize_card_id(raw_mutation.get("cardId"), "cardId"),
        "targetColumnKey": _normalize_required_string(
            raw_mutation.get("targetColumnKey"), "targetColumnKey"
        ),
        "targetPosition": normalized_target_position,
    }


def _parse_ai_response(raw_response: str) -> tuple[str, list[dict]]:
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=502,
            detail="AI response did not match the required JSON contract.",
        ) from error

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="AI response root must be a JSON object.")

    reply = parsed.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        raise HTTPException(
            status_code=502,
            detail="AI response must include a non-empty reply string.",
        )

    raw_mutations = parsed.get("mutations", [])
    if not isinstance(raw_mutations, list):
        raise HTTPException(status_code=502, detail="AI response mutations must be an array.")
    mutations = [_normalize_mutation(item) for item in raw_mutations]
    return reply.strip(), mutations


def _describe_mutation(mutation: dict) -> str:
    mutation_type = mutation["type"]
    if mutation_type == "create_card":
        return f"Create card '{mutation['title']}' in column '{mutation['columnKey']}'"
    if mutation_type == "edit_card":
        updated_fields: list[str] = []
        if mutation.get("title") is not None:
            updated_fields.append("title")
        if mutation.get("details") is not None:
            updated_fields.append("details")
        return f"Edit card {mutation['cardId']} ({' and '.join(updated_fields)})"
    return (
        f"Move card {mutation['cardId']} to '{mutation['targetColumnKey']}' "
        f"at position {mutation['targetPosition']}"
    )


def _apply_ai_mutation(store: BoardStore, username: str, mutation: dict) -> None:
    mutation_type = mutation["type"]
    if mutation_type == "create_card":
        store.add_card(
            username,
            mutation["columnKey"],
            mutation["title"],
            mutation.get("details", ""),
        )
        return
    if mutation_type == "edit_card":
        store.update_card(
            username,
            int(mutation["cardId"]),
            mutation.get("title"),
            mutation.get("details"),
        )
        return
    store.move_card(
        username,
        int(mutation["cardId"]),
        mutation["targetColumnKey"],
        int(mutation["targetPosition"]),
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _load_env_file()
    store = BoardStore(_db_path())
    store.initialize()
    store.ensure_user_board("user")
    app.state.store = store
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Project Management MVP", lifespan=_lifespan)

    @app.exception_handler(NotFoundError)
    def not_found(_request: Request, error: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/hello")
    def hello() -> dict[str, str]:
        return {"message": "Hello from FastAPI"}

    @app.get("/api/ai/connectivity-check")
    def ai_connectivity_check() -> dict[str, str]:
        return _openrouter_connectivity_check()

    @app.get("/api/ai/{username}/chat")
    def get_ai_chat_context(
        username: Annotated[str, ApiPath(min_length=1, max_length=80)]
    ) -> dict:
        messages = app.state.store.get_recent_chat_messages(username, limit=50)
        pending_actions = app.state.store.list_pending_ai_actions(username)
        return {
            "messages": messages,
            "pendingActions": [
                {
                    "id": action["id"],
                    "actionType": action["actionType"],
                    "payload": action["payload"],
                    "description": _describe_mutation(action["payload"]),
                    "createdAt": action["createdAt"],
                }
                for action in pending_actions
            ],
        }

    @app.post("/api/ai/{username}/chat")
    def send_ai_chat_message(
        username: Annotated[str, ApiPath(min_length=1, max_length=80)],
        payload: AiChatRequest,
    ) -> dict:
        user_message = payload.message.strip()
        if not user_message:
            raise HTTPException(status_code=400, detail="Message cannot be empty.")

        board = app.state.store.get_board(username)
        history = app.state.store.get_recent_chat_messages(username, limit=19)
        ai_messages = _build_ai_messages(board, history)
        ai_messages.append({"role": "user", "content": user_message})
        ai_raw_response = _openrouter_chat_completion(ai_messages)
        ai_reply, mutations = _parse_ai_response(ai_raw_response)

        # Store the user message only once the AI reply is valid, so failures leave no orphans.
        app.state.store.add_chat_message(username, "user", user_message)
        assistant_message_id = app.state.store.add_chat_message(
            username, "assistant", ai_reply
        )

        pending_actions: list[dict] = []
        for mutation in mutations:
            action_id = app.state.store.create_ai_action(
                username, mutation["type"], mutation, assistant_message_id
            )
            pending_actions.append(
                {
                    "id": action_id,
                    "actionType": mutation["type"],
                    "payload": mutation,
                    "description": _describe_mutation(mutation),
                    "requiresConfirmation": True,
                }
            )

        return {
            "reply": ai_reply,
            "pendingActions": pending_actions,
        }

    @app.post("/api/ai/{username}/actions/{action_id}")
    def decide_ai_action(
        username: Annotated[str, ApiPath(min_length=1, max_length=80)],
        action_id: Annotated[int, ApiPath(ge=1)],
        payload: AiActionDecisionRequest,
    ) -> dict:
        action = app.state.store.get_ai_action(username, action_id)
        if action["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail="Action has already been decided.",
            )

        if not payload.approved:
            app.state.store.set_ai_action_status(username, action_id, "rejected")
            return {"status": "rejected"}

        try:
            _apply_ai_mutation(app.state.store, username, action["payload"])
        except NotFoundError as error:
            app.state.store.set_ai_action_status(
                username, action_id, "failed", error_message=str(error)
            )
            raise

        app.state.store.set_ai_action_status(username, action_id, "applied")
        return {"status": "applied", "board": app.state.store.get_board(username)}

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
        app.state.store.rename_column(username, column_key, payload.title.strip())
        return {"status": "ok"}

    @app.post("/api/board/{username}/columns/{column_key}/cards")
    def add_card(
        username: Annotated[str, ApiPath(min_length=1, max_length=80)],
        column_key: Annotated[str, ApiPath(min_length=1, max_length=80)],
        payload: AddCardRequest,
    ) -> dict[str, int]:
        card_id = app.state.store.add_card(
            username, column_key, payload.title.strip(), payload.details.strip()
        )
        return {"id": card_id}

    @app.patch("/api/board/{username}/cards/{card_id}")
    def update_card(
        username: Annotated[str, ApiPath(min_length=1, max_length=80)],
        card_id: Annotated[int, ApiPath(ge=1)],
        payload: UpdateCardRequest,
    ) -> dict[str, str]:
        title = payload.title.strip() if payload.title is not None else None
        details = payload.details.strip() if payload.details is not None else None
        if title is None and details is None:
            raise HTTPException(status_code=400, detail="At least one field must be provided.")
        app.state.store.update_card(username, card_id, title=title, details=details)
        return {"status": "ok"}

    @app.delete("/api/board/{username}/cards/{card_id}")
    def delete_card(
        username: Annotated[str, ApiPath(min_length=1, max_length=80)],
        card_id: Annotated[int, ApiPath(ge=1)],
    ) -> dict[str, str]:
        app.state.store.delete_card(username, card_id)
        return {"status": "ok"}

    @app.post("/api/board/{username}/cards/{card_id}/move")
    def move_card(
        username: Annotated[str, ApiPath(min_length=1, max_length=80)],
        card_id: Annotated[int, ApiPath(ge=1)],
        payload: MoveCardRequest,
    ) -> dict[str, str]:
        app.state.store.move_card(
            username, card_id, payload.targetColumnKey, payload.targetPosition
        )
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
