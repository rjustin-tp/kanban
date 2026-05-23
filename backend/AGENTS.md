# Backend Agent Guide

This backend is a FastAPI service for the Project Management MVP.

## Current scope (Part 4 auth-gated board)

- Builds frontend static export during Docker build and serves it at `/`.
- Exposes a health API at `/api/health`.
- Implements MVP session auth endpoints:
  - `POST /api/auth/login`
  - `GET /api/auth/session`
  - `POST /api/auth/logout`
- Includes pytest coverage for backend endpoint behavior.
- Is containerized with Docker and started through scripts in `scripts/`.

## Backend layout

- `backend/app/main.py`: FastAPI app setup and routes.
- `backend/app/static/`: fallback static content for local backend runs (Docker replaces with frontend export).
- `backend/tests/test_main.py`: backend endpoint tests.
- `backend/tests/test_auth.py`: auth endpoint tests for login/session/logout behavior.
- `backend/pyproject.toml`: Python project metadata and dependencies.

## Expected runtime

- The Docker container runs:
  - `uv run --project /app/backend uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Python dependencies are installed in-container using `uv`.

## Test command

- From `backend/`: `uv run --project . --extra dev python -m pytest`