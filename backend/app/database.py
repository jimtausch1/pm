import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_COLUMNS: list[tuple[str, str]] = [
    ("col-backlog", "Backlog"),
    ("col-discovery", "Discovery"),
    ("col-progress", "In Progress"),
    ("col-review", "Review"),
    ("col-done", "Done"),
]

DEFAULT_CARDS: list[tuple[str, str, int]] = [
    (
        "Align roadmap themes",
        "Draft quarterly themes with impact statements and metrics.",
        0,
    ),
    (
        "Gather customer signals",
        "Review support tags, sales notes, and churn feedback.",
        0,
    ),
    (
        "Prototype analytics view",
        "Sketch initial dashboard layout and key drill-downs.",
        1,
    ),
    ("Refine status language", "Standardize column labels and tone across the board.", 2),
    ("Design card layout", "Add hierarchy and spacing for scanning dense lists.", 2),
    ("QA micro-interactions", "Verify hover, focus, and loading states.", 3),
    ("Ship marketing page", "Final copy approved and asset pack delivered.", 4),
    ("Close onboarding sprint", "Document release notes and share internally.", 4),
]


class NotFoundError(Exception):
    pass


class BoardStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        # Commits on success, rolls back on error, and always closes the connection.
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS boards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS columns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    board_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
                    UNIQUE(board_id, key),
                    UNIQUE(board_id, position)
                );

                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    board_id INTEGER NOT NULL,
                    column_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT 'No details yet.',
                    position INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
                    FOREIGN KEY (column_id) REFERENCES columns(id) ON DELETE CASCADE,
                    UNIQUE(column_id, position)
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    board_id INTEGER NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_chat_messages_board_id_created_at
                ON chat_messages(board_id, created_at);

                CREATE TABLE IF NOT EXISTS ai_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    board_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending', 'applied', 'rejected', 'failed')),
                    assistant_message_id INTEGER,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
                    FOREIGN KEY (assistant_message_id) REFERENCES chat_messages(id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_ai_actions_board_id_status_created_at
                ON ai_actions(board_id, status, created_at);
                """
            )
            connection.commit()

    def _get_or_create_user(self, connection: sqlite3.Connection, username: str) -> int:
        row = connection.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row:
            return int(row["id"])

        cursor = connection.execute(
            "INSERT INTO users (username) VALUES (?)",
            (username,),
        )
        return int(cursor.lastrowid)

    def _seed_board(
        self, connection: sqlite3.Connection, board_id: int
    ) -> dict[str, int]:
        column_ids: dict[str, int] = {}
        for position, (key, title) in enumerate(DEFAULT_COLUMNS):
            cursor = connection.execute(
                "INSERT INTO columns (board_id, key, title, position) VALUES (?, ?, ?, ?)",
                (board_id, key, title, position),
            )
            column_ids[key] = int(cursor.lastrowid)

        per_column_positions: dict[int, int] = {}
        for title, details, column_index in DEFAULT_CARDS:
            column_key = DEFAULT_COLUMNS[column_index][0]
            column_id = column_ids[column_key]
            position = per_column_positions.get(column_id, 0)
            connection.execute(
                """
                INSERT INTO cards (board_id, column_id, title, details, position)
                VALUES (?, ?, ?, ?, ?)
                """,
                (board_id, column_id, title, details, position),
            )
            per_column_positions[column_id] = position + 1

        return column_ids

    def _get_or_create_board(self, connection: sqlite3.Connection, user_id: int) -> int:
        row = connection.execute(
            "SELECT id FROM boards WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row:
            return int(row["id"])

        cursor = connection.execute(
            "INSERT INTO boards (user_id, name) VALUES (?, ?)",
            (user_id, "Main Board"),
        )
        board_id = int(cursor.lastrowid)
        self._seed_board(connection, board_id)
        return board_id

    def ensure_user_board(self, username: str) -> None:
        with self._connect() as connection:
            user_id = self._get_or_create_user(connection, username)
            self._get_or_create_board(connection, user_id)
            connection.commit()

    def _board_for_user(
        self, connection: sqlite3.Connection, username: str
    ) -> tuple[int, int]:
        row = connection.execute(
            """
            SELECT u.id AS user_id, b.id AS board_id
            FROM users u
            JOIN boards b ON b.user_id = u.id
            WHERE u.username = ?
            """,
            (username,),
        ).fetchone()
        if not row:
            raise NotFoundError("Board not found for user.")
        return int(row["user_id"]), int(row["board_id"])

    def get_board(self, username: str) -> dict:
        with self._connect() as connection:
            _, board_id = self._board_for_user(connection, username)

            columns_rows = connection.execute(
                """
                SELECT id, key, title, position
                FROM columns
                WHERE board_id = ?
                ORDER BY position ASC
                """,
                (board_id,),
            ).fetchall()

            cards_rows = connection.execute(
                """
                SELECT id, column_id, title, details, position
                FROM cards
                WHERE board_id = ?
                ORDER BY column_id ASC, position ASC
                """,
                (board_id,),
            ).fetchall()

            cards: dict[str, dict] = {}
            cards_by_column: dict[int, list[int]] = {}
            for card in cards_rows:
                card_id = int(card["id"])
                column_id = int(card["column_id"])
                cards[str(card_id)] = {
                    "id": card_id,
                    "title": str(card["title"]),
                    "details": str(card["details"]),
                    "columnId": column_id,
                    "position": int(card["position"]),
                }
                cards_by_column.setdefault(column_id, []).append(card_id)

            columns = [
                {
                    "id": int(column["id"]),
                    "key": str(column["key"]),
                    "title": str(column["title"]),
                    "position": int(column["position"]),
                    "cardIds": cards_by_column.get(int(column["id"]), []),
                }
                for column in columns_rows
            ]

            return {
                "username": username,
                "boardId": board_id,
                "columns": columns,
                "cards": cards,
            }

    def rename_column(self, username: str, column_key: str, title: str) -> None:
        with self._connect() as connection:
            _, board_id = self._board_for_user(connection, username)
            result = connection.execute(
                """
                UPDATE columns
                SET title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE board_id = ? AND key = ?
                """,
                (title, board_id, column_key),
            )
            if result.rowcount == 0:
                raise NotFoundError("Column not found.")
            connection.commit()

    def add_card(
        self, username: str, column_key: str, title: str, details: str
    ) -> int:
        with self._connect() as connection:
            _, board_id = self._board_for_user(connection, username)
            column = connection.execute(
                "SELECT id FROM columns WHERE board_id = ? AND key = ?",
                (board_id, column_key),
            ).fetchone()
            if not column:
                raise NotFoundError("Column not found.")

            column_id = int(column["id"])
            next_position_row = connection.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 AS next_position FROM cards WHERE column_id = ?",
                (column_id,),
            ).fetchone()
            next_position = int(next_position_row["next_position"])

            cursor = connection.execute(
                """
                INSERT INTO cards (board_id, column_id, title, details, position)
                VALUES (?, ?, ?, ?, ?)
                """,
                (board_id, column_id, title, details or "No details yet.", next_position),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def update_card(
        self,
        username: str,
        card_id: int,
        title: str | None,
        details: str | None,
    ) -> None:
        if title is None and details is None:
            raise ValueError("At least one field must be provided.")

        with self._connect() as connection:
            _, board_id = self._board_for_user(connection, username)
            card = connection.execute(
                "SELECT id FROM cards WHERE id = ? AND board_id = ?",
                (card_id, board_id),
            ).fetchone()
            if not card:
                raise NotFoundError("Card not found.")

            connection.execute(
                """
                UPDATE cards
                SET
                    title = COALESCE(?, title),
                    details = COALESCE(?, details),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND board_id = ?
                """,
                (title, details, card_id, board_id),
            )
            connection.commit()

    def delete_card(self, username: str, card_id: int) -> None:
        with self._connect() as connection:
            _, board_id = self._board_for_user(connection, username)
            card = connection.execute(
                "SELECT id, column_id, position FROM cards WHERE id = ? AND board_id = ?",
                (card_id, board_id),
            ).fetchone()
            if not card:
                raise NotFoundError("Card not found.")

            column_id = int(card["column_id"])
            removed_position = int(card["position"])
            connection.execute("DELETE FROM cards WHERE id = ? AND board_id = ?", (card_id, board_id))
            connection.execute(
                """
                UPDATE cards
                SET position = position - 1, updated_at = CURRENT_TIMESTAMP
                WHERE column_id = ? AND position > ?
                """,
                (column_id, removed_position),
            )
            connection.commit()

    def move_card(
        self, username: str, card_id: int, target_column_key: str, target_position: int
    ) -> None:
        with self._connect() as connection:
            _, board_id = self._board_for_user(connection, username)

            card = connection.execute(
                "SELECT id, column_id, position FROM cards WHERE id = ? AND board_id = ?",
                (card_id, board_id),
            ).fetchone()
            if not card:
                raise NotFoundError("Card not found.")

            target_column = connection.execute(
                "SELECT id FROM columns WHERE board_id = ? AND key = ?",
                (board_id, target_column_key),
            ).fetchone()
            if not target_column:
                raise NotFoundError("Target column not found.")

            source_column_id = int(card["column_id"])
            source_position = int(card["position"])
            destination_column_id = int(target_column["id"])

            destination_size_row = connection.execute(
                "SELECT COUNT(*) AS card_count FROM cards WHERE column_id = ?",
                (destination_column_id,),
            ).fetchone()
            destination_size = int(destination_size_row["card_count"])

            max_target = destination_size - 1 if source_column_id == destination_column_id else destination_size
            bounded_target = min(max(target_position, 0), max(max_target, 0))

            if source_column_id == destination_column_id and bounded_target == source_position:
                return

            connection.execute("BEGIN")
            try:
                connection.execute(
                    """
                    UPDATE cards
                    SET position = -1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND board_id = ?
                    """,
                    (card_id, board_id),
                )

                connection.execute(
                    """
                    UPDATE cards
                    SET position = position - 1, updated_at = CURRENT_TIMESTAMP
                    WHERE column_id = ? AND position > ?
                    """,
                    (source_column_id, source_position),
                )

                # SQLite checks UNIQUE(column_id, position) per row, so shifting up in place
                # collides. Move the rows to negative positions first, then to position + 1.
                connection.execute(
                    """
                    UPDATE cards
                    SET position = -(position + 2), updated_at = CURRENT_TIMESTAMP
                    WHERE column_id = ? AND position >= ? AND id != ?
                    """,
                    (destination_column_id, bounded_target, card_id),
                )
                connection.execute(
                    """
                    UPDATE cards
                    SET position = -position - 1
                    WHERE column_id = ? AND position < -1
                    """,
                    (destination_column_id,),
                )

                connection.execute(
                    """
                    UPDATE cards
                    SET column_id = ?, position = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND board_id = ?
                    """,
                    (destination_column_id, bounded_target, card_id, board_id),
                )
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

    def add_chat_message(self, username: str, role: str, content: str) -> int:
        with self._connect() as connection:
            _, board_id = self._board_for_user(connection, username)
            cursor = connection.execute(
                """
                INSERT INTO chat_messages (board_id, role, content)
                VALUES (?, ?, ?)
                """,
                (board_id, role, content),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def get_recent_chat_messages(self, username: str, limit: int = 20) -> list[dict]:
        with self._connect() as connection:
            _, board_id = self._board_for_user(connection, username)
            rows = connection.execute(
                """
                SELECT id, role, content, created_at
                FROM chat_messages
                WHERE board_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (board_id, limit),
            ).fetchall()

            ordered_rows = list(reversed(rows))
            return [
                {
                    "id": int(row["id"]),
                    "role": str(row["role"]),
                    "content": str(row["content"]),
                    "createdAt": str(row["created_at"]),
                }
                for row in ordered_rows
            ]

    def create_ai_action(
        self,
        username: str,
        action_type: str,
        payload: dict,
        assistant_message_id: int,
    ) -> int:
        with self._connect() as connection:
            _, board_id = self._board_for_user(connection, username)
            cursor = connection.execute(
                """
                INSERT INTO ai_actions (
                    board_id,
                    action_type,
                    payload_json,
                    status,
                    assistant_message_id
                )
                VALUES (?, ?, ?, 'pending', ?)
                """,
                (board_id, action_type, json.dumps(payload), assistant_message_id),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def get_ai_action(self, username: str, action_id: int) -> dict:
        with self._connect() as connection:
            _, board_id = self._board_for_user(connection, username)
            row = connection.execute(
                """
                SELECT
                    id,
                    action_type,
                    payload_json,
                    status,
                    assistant_message_id,
                    error_message,
                    created_at,
                    updated_at
                FROM ai_actions
                WHERE id = ? AND board_id = ?
                """,
                (action_id, board_id),
            ).fetchone()
            if not row:
                raise NotFoundError("AI action not found.")

            return {
                "id": int(row["id"]),
                "actionType": str(row["action_type"]),
                "payload": json.loads(str(row["payload_json"])),
                "status": str(row["status"]),
                "assistantMessageId": (
                    int(row["assistant_message_id"])
                    if row["assistant_message_id"] is not None
                    else None
                ),
                "errorMessage": str(row["error_message"])
                if row["error_message"] is not None
                else None,
                "createdAt": str(row["created_at"]),
                "updatedAt": str(row["updated_at"]),
            }

    def list_pending_ai_actions(self, username: str) -> list[dict]:
        with self._connect() as connection:
            _, board_id = self._board_for_user(connection, username)
            rows = connection.execute(
                """
                SELECT id, action_type, payload_json, created_at
                FROM ai_actions
                WHERE board_id = ? AND status = 'pending'
                ORDER BY id ASC
                """,
                (board_id,),
            ).fetchall()

            return [
                {
                    "id": int(row["id"]),
                    "actionType": str(row["action_type"]),
                    "payload": json.loads(str(row["payload_json"])),
                    "createdAt": str(row["created_at"]),
                }
                for row in rows
            ]

    def set_ai_action_status(
        self, username: str, action_id: int, status: str, error_message: str | None = None
    ) -> None:
        with self._connect() as connection:
            _, board_id = self._board_for_user(connection, username)
            result = connection.execute(
                """
                UPDATE ai_actions
                SET
                    status = ?,
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND board_id = ?
                """,
                (status, error_message, action_id, board_id),
            )
            if result.rowcount == 0:
                raise NotFoundError("AI action not found.")
            connection.commit()
