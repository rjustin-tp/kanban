from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_BOARD = {
    "columns": [
        {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-1", "card-2"]},
        {"id": "col-discovery", "title": "Discovery", "cardIds": ["card-3"]},
        {"id": "col-progress", "title": "In Progress", "cardIds": ["card-4", "card-5"]},
        {"id": "col-review", "title": "Review", "cardIds": ["card-6"]},
        {"id": "col-done", "title": "Done", "cardIds": ["card-7", "card-8"]},
    ],
    "cards": {
        "card-1": {
            "id": "card-1",
            "title": "Align roadmap themes",
            "details": "Draft quarterly themes with impact statements and metrics.",
        },
        "card-2": {
            "id": "card-2",
            "title": "Gather customer signals",
            "details": "Review support tags, sales notes, and churn feedback.",
        },
        "card-3": {
            "id": "card-3",
            "title": "Prototype analytics view",
            "details": "Sketch initial dashboard layout and key drill-downs.",
        },
        "card-4": {
            "id": "card-4",
            "title": "Refine status language",
            "details": "Standardize column labels and tone across the board.",
        },
        "card-5": {
            "id": "card-5",
            "title": "Design card layout",
            "details": "Add hierarchy and spacing for scanning dense lists.",
        },
        "card-6": {
            "id": "card-6",
            "title": "QA micro-interactions",
            "details": "Verify hover, focus, and loading states.",
        },
        "card-7": {
            "id": "card-7",
            "title": "Ship marketing page",
            "details": "Final copy approved and asset pack delivered.",
        },
        "card-8": {
            "id": "card-8",
            "title": "Close onboarding sprint",
            "details": "Document release notes and share internally.",
        },
    },
}


class BoardRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
                    column_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
                    UNIQUE (board_id, column_key),
                    UNIQUE (board_id, position)
                );

                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    board_id INTEGER NOT NULL,
                    card_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    details TEXT NOT NULL,
                    column_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
                    FOREIGN KEY (column_id) REFERENCES columns(id) ON DELETE CASCADE,
                    UNIQUE (board_id, card_key),
                    UNIQUE (column_id, position)
                );
                """
            )

    def get_board_data(self, username: str) -> dict[str, Any]:
        with self._connect() as connection:
            user_id = self._ensure_user(connection, username)
            board_id = self._ensure_board(connection, user_id)
            self._seed_board_if_missing(connection, board_id)
            return self._read_board(connection, board_id)

    def replace_board_data(self, username: str, board_data: dict[str, Any]) -> dict[str, Any]:
        self._validate_board_data(board_data)
        with self._connect() as connection:
            user_id = self._ensure_user(connection, username)
            board_id = self._ensure_board(connection, user_id)

            connection.execute("DELETE FROM cards WHERE board_id = ?", (board_id,))
            connection.execute("DELETE FROM columns WHERE board_id = ?", (board_id,))

            column_key_to_id: dict[str, int] = {}
            for column_position, column in enumerate(board_data["columns"]):
                cursor = connection.execute(
                    """
                    INSERT INTO columns (board_id, column_key, title, position)
                    VALUES (?, ?, ?, ?)
                    """,
                    (board_id, column["id"], column["title"], column_position),
                )
                column_key_to_id[column["id"]] = int(cursor.lastrowid)

            cards_by_id = board_data["cards"]
            for column in board_data["columns"]:
                column_id = column_key_to_id[column["id"]]
                for card_position, card_id in enumerate(column["cardIds"]):
                    card = cards_by_id[card_id]
                    connection.execute(
                        """
                        INSERT INTO cards (board_id, card_key, title, details, column_id, position)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            board_id,
                            card["id"],
                            card["title"],
                            card["details"],
                            column_id,
                            card_position,
                        ),
                    )

            connection.execute(
                "UPDATE boards SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (board_id,)
            )
            return self._read_board(connection, board_id)

    def _ensure_user(self, connection: sqlite3.Connection, username: str) -> int:
        connection.execute(
            """
            INSERT INTO users (username, password_hash)
            VALUES (?, ?)
            ON CONFLICT(username) DO NOTHING
            """,
            (username, "mvp-managed-by-auth-layer"),
        )
        row = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None:
            raise ValueError("Unable to resolve user.")
        return int(row["id"])

    def _ensure_board(self, connection: sqlite3.Connection, user_id: int) -> int:
        connection.execute(
            """
            INSERT INTO boards (user_id, name)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id, "My Board"),
        )
        row = connection.execute(
            "SELECT id FROM boards WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Unable to resolve board.")
        return int(row["id"])

    def _seed_board_if_missing(self, connection: sqlite3.Connection, board_id: int) -> None:
        row = connection.execute(
            "SELECT COUNT(*) AS total FROM columns WHERE board_id = ?",
            (board_id,),
        ).fetchone()
        if row is None or int(row["total"]) > 0:
            return

        self.replace_board_data_for_board_id(connection, board_id, DEFAULT_BOARD)

    def replace_board_data_for_board_id(
        self, connection: sqlite3.Connection, board_id: int, board_data: dict[str, Any]
    ) -> None:
        connection.execute("DELETE FROM cards WHERE board_id = ?", (board_id,))
        connection.execute("DELETE FROM columns WHERE board_id = ?", (board_id,))

        column_key_to_id: dict[str, int] = {}
        for column_position, column in enumerate(board_data["columns"]):
            cursor = connection.execute(
                """
                INSERT INTO columns (board_id, column_key, title, position)
                VALUES (?, ?, ?, ?)
                """,
                (board_id, column["id"], column["title"], column_position),
            )
            column_key_to_id[column["id"]] = int(cursor.lastrowid)

        cards_by_id = board_data["cards"]
        for column in board_data["columns"]:
            column_id = column_key_to_id[column["id"]]
            for card_position, card_id in enumerate(column["cardIds"]):
                card = cards_by_id[card_id]
                connection.execute(
                    """
                    INSERT INTO cards (board_id, card_key, title, details, column_id, position)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        board_id,
                        card["id"],
                        card["title"],
                        card["details"],
                        column_id,
                        card_position,
                    ),
                )

        connection.execute(
            "UPDATE boards SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (board_id,)
        )

    def _read_board(self, connection: sqlite3.Connection, board_id: int) -> dict[str, Any]:
        columns_rows = connection.execute(
            """
            SELECT id, column_key, title
            FROM columns
            WHERE board_id = ?
            ORDER BY position ASC
            """,
            (board_id,),
        ).fetchall()

        cards_rows = connection.execute(
            """
            SELECT card_key, title, details, column_id
            FROM cards
            WHERE board_id = ?
            ORDER BY column_id ASC, position ASC
            """,
            (board_id,),
        ).fetchall()

        cards_by_column: dict[int, list[str]] = {}
        cards_map: dict[str, dict[str, str]] = {}
        for row in cards_rows:
            card_id = str(row["card_key"])
            cards_map[card_id] = {
                "id": card_id,
                "title": str(row["title"]),
                "details": str(row["details"]),
            }
            column_id = int(row["column_id"])
            cards_by_column.setdefault(column_id, []).append(card_id)

        columns: list[dict[str, Any]] = []
        for row in columns_rows:
            column_id = int(row["id"])
            columns.append(
                {
                    "id": str(row["column_key"]),
                    "title": str(row["title"]),
                    "cardIds": cards_by_column.get(column_id, []),
                }
            )

        return {"columns": columns, "cards": cards_map}

    def _validate_board_data(self, board_data: dict[str, Any]) -> None:
        columns = board_data.get("columns")
        cards = board_data.get("cards")
        if not isinstance(columns, list) or not isinstance(cards, dict):
            raise ValueError("Board payload must include columns and cards.")

        column_ids: set[str] = set()
        seen_card_ids: set[str] = set()
        for column in columns:
            column_id = column.get("id")
            if not isinstance(column_id, str) or not column_id:
                raise ValueError("Each column must have a non-empty id.")
            if column_id in column_ids:
                raise ValueError("Column ids must be unique.")
            column_ids.add(column_id)

            card_ids = column.get("cardIds")
            if not isinstance(card_ids, list):
                raise ValueError("Each column must have cardIds.")

            for card_id in card_ids:
                if not isinstance(card_id, str) or not card_id:
                    raise ValueError("Card ids must be non-empty strings.")
                if card_id in seen_card_ids:
                    raise ValueError("A card cannot appear in multiple positions.")
                seen_card_ids.add(card_id)
                if card_id not in cards:
                    raise ValueError("All card ids must exist in cards map.")

        if set(cards.keys()) != seen_card_ids:
            raise ValueError("Cards map must match card ids used by columns.")

        for key, card in cards.items():
            if card.get("id") != key:
                raise ValueError("Card key and card.id must match.")
            if not card.get("title"):
                raise ValueError("Cards must include title.")
            if "details" not in card:
                raise ValueError("Cards must include details.")
