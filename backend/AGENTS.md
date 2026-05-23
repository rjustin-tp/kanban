# Backend Agent Guide

This backend is a FastAPI service for the Project Management MVP.

## Current scope (Part 8 AI connectivity smoke)

- Builds frontend static export during Docker build and serves it at `/`.
- Exposes a health API at `/api/health`.
- Implements MVP session auth endpoints:
  - `POST /api/auth/login`
  - `GET /api/auth/session`
  - `POST /api/auth/logout`
- Persists Kanban board state in SQLite and exposes board endpoints:
  - `GET /api/board`
  - `PUT /api/board`
- Adds OpenRouter connectivity smoke endpoint:
  - `GET /api/ai/smoke` (authenticated, sends prompt `2+2`)
- Includes pytest coverage for backend endpoint behavior.
- Is containerized with Docker and started through scripts in `scripts/`.

## Backend layout

- `backend/app/main.py`: FastAPI app setup and routes.
- `backend/app/board_repository.py`: DB initialization, seed data, board load/save logic.
- `backend/app/ai_service.py`: OpenRouter client, request/response parsing, and error handling.
- `backend/app/static/`: fallback static content for local backend runs (Docker replaces with frontend export).
- `backend/tests/test_main.py`: backend endpoint tests.
- `backend/tests/test_auth.py`: auth endpoint tests for login/session/logout behavior.
- `backend/tests/test_ai_service.py`: OpenRouter client unit tests (mocked HTTP + failure paths).
- `backend/tests/test_ai_api.py`: smoke endpoint auth and error mapping tests.
- `backend/tests/test_board_api.py`: board API auth, read/update, and invalid payload tests.
- `backend/tests/test_board_repository.py`: repository behavior and persistence tests.
- `backend/pyproject.toml`: Python project metadata and dependencies.

## Expected runtime

- The Docker container runs:
  - `uv run --project /app/backend uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Python dependencies are installed in-container using `uv`.

## Test command

- From `backend/`: `uv run --project . --extra dev python -m pytest`