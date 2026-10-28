import json
import os
import tempfile
import uuid
from io import BytesIO
from unittest.mock import patch

from app.main import create_app


class _MockUrlOpenResponse:
    def __init__(self, payload_bytes: bytes):
        self._payload_bytes = payload_bytes

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def read(self) -> bytes:
        return self._payload_bytes


def _app_with_temp_db():
    db_path = os.path.join(tempfile.gettempdir(), f"pm-test-{uuid.uuid4()}.db")
    os.environ["PM_DB_PATH"] = db_path
    app = create_app()
    return app


def test_get_board_seeds_default_user_board():
    from fastapi.testclient import TestClient

    app = _app_with_temp_db()
    try:
        with TestClient(app) as client:
            response = client.get("/api/board/user")
            assert response.status_code == 200
            payload = response.json()
            assert payload["username"] == "user"
            assert len(payload["columns"]) == 5
            assert len(payload["cards"]) == 8
    finally:
        os.environ.pop("PM_DB_PATH", None)


def test_rename_column_and_get_board():
    from fastapi.testclient import TestClient

    app = _app_with_temp_db()
    try:
        with TestClient(app) as client:
            rename = client.patch(
                "/api/board/user/columns/col-backlog", json={"title": "Ideas"}
            )
            assert rename.status_code == 200

            board = client.get("/api/board/user").json()
            first_column = next(
                column for column in board["columns"] if column["key"] == "col-backlog"
            )
            assert first_column["title"] == "Ideas"
    finally:
        os.environ.pop("PM_DB_PATH", None)


def test_add_edit_delete_card():
    from fastapi.testclient import TestClient

    app = _app_with_temp_db()
    try:
        with TestClient(app) as client:
            add = client.post(
                "/api/board/user/columns/col-backlog/cards",
                json={"title": "New API Card", "details": "Created by test"},
            )
            assert add.status_code == 200
            card_id = add.json()["id"]

            update = client.patch(
                f"/api/board/user/cards/{card_id}",
                json={"title": "Updated API Card", "details": "Updated details"},
            )
            assert update.status_code == 200

            board = client.get("/api/board/user").json()
            updated_card = board["cards"][str(card_id)]
            assert updated_card["title"] == "Updated API Card"
            assert updated_card["details"] == "Updated details"

            delete = client.delete(f"/api/board/user/cards/{card_id}")
            assert delete.status_code == 200

            board_after_delete = client.get("/api/board/user").json()
            assert str(card_id) not in board_after_delete["cards"]
    finally:
        os.environ.pop("PM_DB_PATH", None)


def test_move_card_across_columns():
    from fastapi.testclient import TestClient

    app = _app_with_temp_db()
    try:
        with TestClient(app) as client:
            board = client.get("/api/board/user").json()
            source_column = next(
                column for column in board["columns"] if column["key"] == "col-backlog"
            )
            card_id = source_column["cardIds"][0]

            move = client.post(
                f"/api/board/user/cards/{card_id}/move",
                json={"targetColumnKey": "col-review", "targetPosition": 0},
            )
            assert move.status_code == 200

            next_board = client.get("/api/board/user").json()
            target_column = next(
                column for column in next_board["columns"] if column["key"] == "col-review"
            )
            assert target_column["cardIds"][0] == card_id
    finally:
        os.environ.pop("PM_DB_PATH", None)


def test_move_card_within_same_column_downward():
    from fastapi.testclient import TestClient

    app = _app_with_temp_db()
    try:
        with TestClient(app) as client:
            board = client.get("/api/board/user").json()
            backlog = next(
                column for column in board["columns"] if column["key"] == "col-backlog"
            )
            original_ids = list(backlog["cardIds"])
            assert len(original_ids) == 2

            card_to_move = original_ids[0]
            move = client.post(
                f"/api/board/user/cards/{card_to_move}/move",
                json={"targetColumnKey": "col-backlog", "targetPosition": 1},
            )
            assert move.status_code == 200

            updated_board = client.get("/api/board/user").json()
            updated_backlog = next(
                column
                for column in updated_board["columns"]
                if column["key"] == "col-backlog"
            )
            assert updated_backlog["cardIds"] == [original_ids[1], original_ids[0]]
    finally:
        os.environ.pop("PM_DB_PATH", None)


def test_move_card_to_top_of_column_with_multiple_cards():
    from fastapi.testclient import TestClient

    app = _app_with_temp_db()
    try:
        with TestClient(app) as client:
            def column_ids(key: str) -> list[int]:
                board = client.get("/api/board/user").json()
                return next(c for c in board["columns"] if c["key"] == key)["cardIds"]

            progress_ids = column_ids("col-progress")
            assert len(progress_ids) == 2
            done_card = column_ids("col-done")[0]

            move = client.post(
                f"/api/board/user/cards/{done_card}/move",
                json={"targetColumnKey": "col-progress", "targetPosition": 0},
            )
            assert move.status_code == 200
            assert column_ids("col-progress") == [done_card, *progress_ids]

            last_card = progress_ids[-1]
            move = client.post(
                f"/api/board/user/cards/{last_card}/move",
                json={"targetColumnKey": "col-progress", "targetPosition": 0},
            )
            assert move.status_code == 200
            assert column_ids("col-progress") == [last_card, done_card, progress_ids[0]]
    finally:
        os.environ.pop("PM_DB_PATH", None)


def test_ai_connectivity_check_success():
    from fastapi.testclient import TestClient

    app = _app_with_temp_db()
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    try:
        with patch("app.main.urllib_request.urlopen") as mock_urlopen:
            mock_response = mock_urlopen.return_value.__enter__.return_value
            mock_response.read.return_value = (
                b'{"choices":[{"message":{"content":"2+2 equals 4"}}]}'
            )

            with TestClient(app) as client:
                response = client.get("/api/ai/connectivity-check")
                assert response.status_code == 200
                payload = response.json()
                assert payload["model"] == "openai/gpt-oss-120b"
                assert payload["reply"] == "2+2 equals 4"
    finally:
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("PM_DB_PATH", None)


def test_ai_connectivity_check_missing_api_key():
    from fastapi.testclient import TestClient

    app = _app_with_temp_db()
    os.environ.pop("OPENROUTER_API_KEY", None)
    try:
        with patch("app.main._load_env_file", return_value=None):
            with TestClient(app) as client:
                response = client.get("/api/ai/connectivity-check")
                assert response.status_code == 500
                assert "OPENROUTER_API_KEY is not configured" in response.json()["detail"]
    finally:
        os.environ.pop("PM_DB_PATH", None)


def test_ai_connectivity_check_invalid_api_key():
    from fastapi.testclient import TestClient
    from urllib.error import HTTPError

    app = _app_with_temp_db()
    os.environ["OPENROUTER_API_KEY"] = "invalid-key"
    try:
        with patch("app.main.urllib_request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = HTTPError(
                url="https://openrouter.ai/api/v1/chat/completions",
                code=401,
                msg="Unauthorized",
                hdrs=None,
                fp=BytesIO(b'{"error":{"message":"Invalid API key"}}'),
            )
            with TestClient(app) as client:
                response = client.get("/api/ai/connectivity-check")
                assert response.status_code == 502
                assert "OpenRouter request failed (401)" in response.json()["detail"]
                assert "Invalid API key" in response.json()["detail"]
    finally:
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("PM_DB_PATH", None)


def test_ai_chat_requires_per_action_confirmation():
    from fastapi.testclient import TestClient

    app = _app_with_temp_db()
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    try:
        ai_reply = {
            "reply": "I can do two updates for you.",
            "mutations": [
                {
                    "type": "create_card",
                    "columnKey": "col-backlog",
                    "title": "AI added card",
                    "details": "Created by assistant",
                },
                {
                    "type": "move_card",
                    "cardId": 1,
                    "targetColumnKey": "col-done",
                    "targetPosition": 0,
                },
            ],
        }
        with patch("app.main.urllib_request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _MockUrlOpenResponse(
                json.dumps({"choices": [{"message": {"content": json.dumps(ai_reply)}}]}).encode(
                    "utf-8"
                )
            )

            with TestClient(app) as client:
                before_board = client.get("/api/board/user").json()
                before_done = next(
                    column
                    for column in before_board["columns"]
                    if column["key"] == "col-done"
                )
                assert 1 not in before_done["cardIds"]

                chat_response = client.post(
                    "/api/ai/user/chat",
                    json={"message": "Please add a card and move card one"},
                )
                assert chat_response.status_code == 200
                body = chat_response.json()
                assert len(body["pendingActions"]) == 2

                after_chat_board = client.get("/api/board/user").json()
                assert all(
                    card["title"] != "AI added card"
                    for card in after_chat_board["cards"].values()
                )
                done_after_chat = next(
                    column
                    for column in after_chat_board["columns"]
                    if column["key"] == "col-done"
                )
                assert 1 not in done_after_chat["cardIds"]

                first_action_id = body["pendingActions"][0]["id"]
                second_action_id = body["pendingActions"][1]["id"]

                first_confirm = client.post(
                    f"/api/ai/user/actions/{first_action_id}",
                    json={"approved": True},
                )
                assert first_confirm.status_code == 200
                assert first_confirm.json()["status"] == "applied"
                cards_after_first = first_confirm.json()["board"]["cards"].values()
                assert any(card["title"] == "AI added card" for card in cards_after_first)

                pending_after_first = client.get("/api/ai/user/chat").json()[
                    "pendingActions"
                ]
                assert len(pending_after_first) == 1
                assert pending_after_first[0]["id"] == second_action_id

                second_reject = client.post(
                    f"/api/ai/user/actions/{second_action_id}",
                    json={"approved": False},
                )
                assert second_reject.status_code == 200
                assert second_reject.json()["status"] == "rejected"
                pending_after_reject = client.get("/api/ai/user/chat").json()[
                    "pendingActions"
                ]
                assert pending_after_reject == []
    finally:
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("PM_DB_PATH", None)


def test_ai_chat_sends_board_and_recent_history():
    from fastapi.testclient import TestClient

    app = _app_with_temp_db()
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    captured_payloads: list[dict] = []

    def _mock_openrouter(request, timeout=30):
        del timeout
        body = json.loads(request.data.decode("utf-8"))
        captured_payloads.append(body)
        call_index = len(captured_payloads)
        ai_contract = {"reply": f"reply-{call_index}", "mutations": []}
        response = {"choices": [{"message": {"content": json.dumps(ai_contract)}}]}
        return _MockUrlOpenResponse(json.dumps(response).encode("utf-8"))

    try:
        with patch("app.main.urllib_request.urlopen", side_effect=_mock_openrouter):
            with TestClient(app) as client:
                first = client.post("/api/ai/user/chat", json={"message": "first prompt"})
                assert first.status_code == 200
                second = client.post(
                    "/api/ai/user/chat", json={"message": "second prompt"}
                )
                assert second.status_code == 200

        assert len(captured_payloads) == 2
        second_messages = captured_payloads[1]["messages"]
        contents = [message["content"] for message in second_messages]
        assert any(content.startswith("Current board JSON:") for content in contents)
        assert "first prompt" in contents
        assert "reply-1" in contents
        assert contents.count("second prompt") == 1
        assert second_messages[-1] == {"role": "user", "content": "second prompt"}
        assert captured_payloads[1]["response_format"] == {"type": "json_object"}
    finally:
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("PM_DB_PATH", None)


def test_ai_chat_rejects_malformed_structured_response():
    from fastapi.testclient import TestClient

    app = _app_with_temp_db()
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    try:
        with patch("app.main.urllib_request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _MockUrlOpenResponse(
                b'{"choices":[{"message":{"content":"not json"}}]}'
            )

            with TestClient(app) as client:
                response = client.post("/api/ai/user/chat", json={"message": "hello"})
                assert response.status_code == 502
                assert "required JSON contract" in response.json()["detail"]
                assert client.get("/api/ai/user/chat").json()["messages"] == []
    finally:
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("PM_DB_PATH", None)


def test_ai_create_card_with_null_details_uses_default():
    from fastapi.testclient import TestClient

    app = _app_with_temp_db()
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    try:
        ai_reply = {
            "reply": "Adding it.",
            "mutations": [
                {"type": "create_card", "columnKey": "col-backlog", "title": "Null details", "details": None}
            ],
        }
        with patch("app.main.urllib_request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _MockUrlOpenResponse(
                json.dumps({"choices": [{"message": {"content": json.dumps(ai_reply)}}]}).encode(
                    "utf-8"
                )
            )
            with TestClient(app) as client:
                body = client.post("/api/ai/user/chat", json={"message": "add a card"}).json()
                action_id = body["pendingActions"][0]["id"]
                board = client.post(
                    f"/api/ai/user/actions/{action_id}", json={"approved": True}
                ).json()["board"]
                card = next(c for c in board["cards"].values() if c["title"] == "Null details")
                assert card["details"] == "No details yet."
    finally:
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("PM_DB_PATH", None)
