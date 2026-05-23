# Backend Agent Guide

This backend is a FastAPI service for the Project Management MVP.

## Current scope (Part 2 scaffold)

- Serves a static hello world page at `/`.
- Exposes a health API at `/api/health`.
- Includes pytest coverage for the scaffold endpoints.
- Is containerized with Docker and started through scripts in `scripts/`.

## Backend layout

- `backend/app/main.py`: FastAPI app setup and routes.
- `backend/app/static/index.html`: static hello world page with client-side health call.
- `backend/tests/test_main.py`: scaffold endpoint tests.
- `backend/pyproject.toml`: Python project metadata and dependencies.

## Expected runtime

- The Docker container runs:
  - `uv run --project /app/backend uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Python dependencies are installed in-container using `uv`.

## Test command

- From `backend/`: `uv run --project . --extra dev pytest`