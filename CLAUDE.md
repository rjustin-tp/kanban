# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project context

MVP project management web app: a single Kanban board per user with an AI sidebar that can create / edit / move cards. NextJS frontend, FastAPI backend (Python 3.12, uv), SQLite persistence, OpenRouter (`openai/gpt-oss-120b`) for AI, all bundled into one Docker container. MVP auth is hardcoded `user` / `password`. See `AGENTS.md` for business requirements and `docs/PLAN.md` for the part-by-part execution plan (Parts 1–10 are complete).

There are per-folder `AGENTS.md` files (`backend/AGENTS.md`, `frontend/AGENTS.md`) with deeper layout notes — read the one for the area you're touching.

## Commands

### Running the app (Docker — production-like)
- Start: `./scripts/start-mac.sh` (or `start-linux.sh` / `start-windows.ps1`). Builds the image, runs container `pm-mvp-app` on port 8000, passes the root `.env` via `--env-file`.
- Stop: `./scripts/stop-mac.sh` (or platform equivalent).
- App at `http://127.0.0.1:8000`. Frontend is statically exported and served by FastAPI at `/`; APIs are under `/api/*`.

### Frontend (`frontend/`)
- Dev server: `npm run dev` (Next dev — does not hit the backend; e2e tests mock backend routes).
- Build: `npm run build` (static export; Docker copies `frontend/out` → `backend/app/static`).
- Lint: `npm run lint`
- Unit/integration tests (Vitest + RTL): `npm run test:unit`
- Run a single unit test: `npx vitest run src/components/KanbanBoard.test.tsx`
- E2E (Playwright, against Next dev with mocked backend): `npm run test:e2e`
- Run a single e2e test: `npx playwright test tests/kanban.spec.ts`
- All tests: `npm run test:all`

### Backend (`backend/`)
- All Python is managed by `uv`. Run from `backend/`:
- Tests: `uv run --project . --extra dev python -m pytest`
- Run a single test: `uv run --project . --extra dev python -m pytest tests/test_ai_api.py::test_name`
- Local server (without Docker): `uv run --project . uvicorn app.main:app --reload`

## Architecture

### Repo layout (only the parts you can't infer from `ls`)
- `backend/app/static/` is empty in dev but is the directory the FastAPI `StaticFiles` mount serves at `/`. The Docker build replaces it with the Next static export.
- `backend/data/kanban.db` is the default SQLite file. Override with env var `KANBAN_DB_PATH`. The DB is **not** mounted as a Docker volume by the start scripts, so container recreation loses data unless the path is mounted externally.
- `docs/PLAN.md` tracks delivered scope; `docs/DATA_MODEL.md` proposes the SQL schema (note: `boards.user_id UNIQUE` enforces "one board per user" — load-bearing for MVP).

### Backend (FastAPI, single `app/main.py`)
- App is composed at import time: `BoardRepository(_resolve_db_path()).initialize()` creates the SQLite schema and seeds a `user` row + starter board on first run.
- Auth is in-memory: `sessions: dict[str, str]` keyed by a cookie token (`pm_session`). `chat_histories: dict[str, list[...]]` is also in-process. Restarting the backend drops both.
- All `/api/*` routes except `/api/health` and `/api/auth/login` require `require_authenticated_user`.
- `/api/board` returns/replaces the full board JSON shape documented in `docs/DATA_MODEL.md` (`{ columns: [{id,title,cardIds[]}], cards: { id: {id,title,details} } }`).
- AI flow:
  - `app/ai_service.py` is the OpenRouter HTTP client. It raises `OpenRouterConfigError` / `OpenRouterTimeoutError` / `OpenRouterRequestError`, which `main.py` maps to HTTP `500` / `504` / `502`.
  - `app/ai_chat.py` defines the structured response contract (`StructuredAIResponse`, operation union: `create_card`, `update_card`, `delete_card`, `move_card`, `create_column`, `update_column`, `delete_column`, `move_column`) and `apply_operations_to_board`, which validates and applies operations sequentially in one batch — partial application is forbidden.
  - `POST /api/ai/chat` re-tries parsing up to `AI_PARSE_ATTEMPTS` (4) times against `normalize_structured_response` before failing with `502`.
  - Summary prompts (message contains `summarize` / `summary` / `recap`) are short-circuited to a deterministic server-side board summary — they never hit the model. Keep this behavior when adding AI features.
  - Conversation history is truncated to the last `CHAT_HISTORY_LIMIT` (12) messages after each turn.

### Frontend (Next.js 16 app router, React 19, Tailwind v4)
- Single page (`src/app/page.tsx` → `AuthGate`). `AuthGate` polls `/api/auth/session` on mount, then renders the login form or the board.
- `src/components/KanbanBoard.tsx` is the state owner: loads from `GET /api/board`, persists every mutation via `PUT /api/board`. Drag/drop, rename, add, delete all funnel through the same save path.
- `src/lib/kanban.ts` holds the domain model (`Card`, `Column`, `BoardData`) and pure `moveCard` logic — change board semantics there with a test in `src/lib/kanban.test.ts` first.
- Drag/drop uses `@dnd-kit`; rendering uses Tailwind v4 with design tokens declared as CSS variables in `src/app/globals.css` (`--accent-yellow`, `--primary-blue`, `--secondary-purple`, `--navy-dark`, `--gray-text`).
- Playwright tests mock `/api/*` routes (they run against `next dev`, not the real backend) — keep `data-testid` attributes stable when refactoring components.

## Working rules (from `AGENTS.md`)

- Keep it simple. No over-engineering, no speculative defensive code, no extra features beyond the MVP scope.
- When something breaks, find the root cause with evidence before patching. Don't guess.
- Use the latest idiomatic API for the library version pinned in `package.json` / `pyproject.toml`.
- No emojis anywhere — code, docs, commits, or UI.
- Match the project color tokens above for any UI work.
