import os
import tempfile
import uuid

from app.main import create_app


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
