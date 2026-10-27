import sqlite3
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


class BoardStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

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
            raise ValueError("Board not found for user.")
        return int(row["user_id"]), int(row["board_id"])

    def get_board(self, username: str) -> dict:
        with self._connect() as connection:
            self.ensure_user_board(username)
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
            self.ensure_user_board(username)
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
                raise ValueError("Column not found.")
            connection.commit()

    def add_card(
        self, username: str, column_key: str, title: str, details: str
    ) -> int:
        with self._connect() as connection:
            self.ensure_user_board(username)
            _, board_id = self._board_for_user(connection, username)
            column = connection.execute(
                "SELECT id FROM columns WHERE board_id = ? AND key = ?",
                (board_id, column_key),
            ).fetchone()
            if not column:
                raise ValueError("Column not found.")

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
            self.ensure_user_board(username)
            _, board_id = self._board_for_user(connection, username)
            card = connection.execute(
                "SELECT id FROM cards WHERE id = ? AND board_id = ?",
                (card_id, board_id),
            ).fetchone()
            if not card:
                raise ValueError("Card not found.")

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
            self.ensure_user_board(username)
            _, board_id = self._board_for_user(connection, username)
            card = connection.execute(
                "SELECT id, column_id, position FROM cards WHERE id = ? AND board_id = ?",
                (card_id, board_id),
            ).fetchone()
            if not card:
                raise ValueError("Card not found.")

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
            self.ensure_user_board(username)
            _, board_id = self._board_for_user(connection, username)

            card = connection.execute(
                "SELECT id, column_id, position FROM cards WHERE id = ? AND board_id = ?",
                (card_id, board_id),
            ).fetchone()
            if not card:
                raise ValueError("Card not found.")

            target_column = connection.execute(
                "SELECT id FROM columns WHERE board_id = ? AND key = ?",
                (board_id, target_column_key),
            ).fetchone()
            if not target_column:
                raise ValueError("Target column not found.")

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

                connection.execute(
                    """
                    UPDATE cards
                    SET position = position + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE column_id = ? AND position >= ? AND id != ?
                    """,
                    (destination_column_id, bounded_target, card_id),
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
