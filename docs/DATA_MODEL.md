# Data Model Proposal (Part 5)

This document proposes the SQLite schema and persisted JSON shape for the MVP Kanban app.

Goals:
- Keep MVP implementation simple.
- Support one board per user now.
- Avoid schema dead-ends for future multi-user support.

## SQL Schema (Proposed)

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE boards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL UNIQUE,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE columns (
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

CREATE TABLE cards (
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

-- Optional now, useful later for persistent chat history.
CREATE TABLE chat_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  board_id INTEGER NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE
);

-- Optional now, useful later if we move auth sessions from memory to DB.
CREATE TABLE auth_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  session_token TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

## Why This Shape

- `users` is future-proof for multiple accounts.
- `boards.user_id` is `UNIQUE`, enforcing one board per user in MVP.
- `columns.position` and `cards.position` give deterministic ordering.
- Stable keys (`column_key`, `card_key`) map cleanly to frontend IDs.
- Chat/session tables are optional and can be introduced later without reworking core board tables.

## Persisted Kanban JSON (App I/O Contract)

This is the board payload returned by backend APIs and consumed by frontend board state.

```json
{
  "columns": [
    { "id": "col-backlog", "title": "Backlog", "cardIds": ["card-1", "card-2"] },
    { "id": "col-doing", "title": "Doing", "cardIds": ["card-3"] },
    { "id": "col-review", "title": "Review", "cardIds": [] },
    { "id": "col-done", "title": "Done", "cardIds": ["card-4"] },
    { "id": "col-notes", "title": "Notes", "cardIds": [] }
  ],
  "cards": {
    "card-1": { "id": "card-1", "title": "Draft spec", "details": "Prepare MVP scope notes." },
    "card-2": { "id": "card-2", "title": "Define schema", "details": "Map board model to SQLite." },
    "card-3": { "id": "card-3", "title": "Auth smoke test", "details": "Verify login and logout." },
    "card-4": { "id": "card-4", "title": "Part 4 complete", "details": "Ready for data layer work." }
  }
}
```

Notes:
- `columns[*].id` maps to `columns.column_key`.
- `cards[*].id` maps to `cards.card_key`.
- `cardIds` order is derived from `cards.position` within each column.

## Mapping Rules (SQL <-> JSON)

- Load:
  - Read all columns for the board by `position ASC`.
  - For each column, read cards in that column by `position ASC`.
  - Build `columns[]` and `cards{}` map.
- Save:
  - Treat board update as a full-board replacement for MVP simplicity.
  - In one transaction:
    - update column titles/positions,
    - upsert cards,
    - set each card's `column_id` and `position`,
    - delete cards missing from payload.

This keeps behavior deterministic and easy to test.

## Migration Approach

For MVP the schema is bootstrapped in code via `CREATE TABLE IF NOT EXISTS` inside `BoardRepository.initialize()` (see `backend/app/board_repository.py`). There is no migration runner and no `schema_migrations` table; any future schema change requires either an explicit `ALTER TABLE` step added to `initialize()` or wiping the local DB file.

If/when persistence becomes load-bearing, the recommended evolution is plain SQL files under `backend/migrations/` (e.g. `0001_init.sql`, `0002_add_chat.sql`) plus a `schema_migrations(version TEXT PRIMARY KEY, applied_at TEXT)` table that records applied versions. Not implemented today.

## Seed Strategy

- Ensure `users.username = 'user'` exists on first run.
- Ensure that user has exactly one board row.
- If no columns/cards exist for that board, seed initial 5-column board and starter cards.

## Documentation Consistency Checklist

- `boards.user_id UNIQUE` matches MVP "one board per user".
- Ordered board behavior is represented in SQL (`position`) and JSON (`cardIds` order).
- Frontend IDs (`col-*`, `card-*`) have direct key columns in SQL.
- DB model supports future multi-user and persistent chat/session without changing board contract.
