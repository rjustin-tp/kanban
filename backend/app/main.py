import secrets
from collections.abc import Mapping
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.board_repository import BoardRepository

app = FastAPI(title="Project Management MVP Backend")

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "kanban.db"
SESSION_COOKIE_NAME = "pm_session"
VALID_USERNAME = "user"
VALID_PASSWORD = "password"
sessions: dict[str, str] = {}


def _resolve_db_path() -> Path:
    configured_path = os.getenv("KANBAN_DB_PATH")
    if configured_path:
        return Path(configured_path)
    return DEFAULT_DB_PATH


board_repo = BoardRepository(_resolve_db_path())
board_repo.initialize()


class LoginRequest(BaseModel):
    username: str
    password: str


class CardPayload(BaseModel):
    id: str
    title: str
    details: str


class ColumnPayload(BaseModel):
    id: str
    title: str
    cardIds: list[str] = Field(default_factory=list)


class BoardPayload(BaseModel):
    columns: list[ColumnPayload]
    cards: dict[str, CardPayload]


def require_authenticated_user(request: Request) -> str:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    username = sessions.get(session_id)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return username


@app.get("/api/health")
def get_health() -> dict[str, str]:
    return {"status": "ok", "service": "pm-backend"}


@app.post("/api/auth/login")
def login(payload: LoginRequest, response: Response) -> dict[str, Any]:
    if payload.username != VALID_USERNAME or payload.password != VALID_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = payload.username
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return {"ok": True, "user": payload.username}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        sessions.pop(session_id, None)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/session")
def get_session(request: Request) -> dict[str, Any]:
    username = require_authenticated_user(request)
    return {"authenticated": True, "user": username}


@app.get("/api/board")
def get_board(request: Request) -> dict[str, Any]:
    username = require_authenticated_user(request)
    return board_repo.get_board_data(username)


@app.put("/api/board")
def put_board(request: Request, payload: BoardPayload) -> dict[str, Any]:
    username = require_authenticated_user(request)
    try:
        return board_repo.replace_board_data(username, payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
