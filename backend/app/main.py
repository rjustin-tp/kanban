import re
import secrets
from collections.abc import Mapping
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from app.ai_service import (
    OpenRouterClient,
    OpenRouterConfigError,
    OpenRouterRequestError,
    OpenRouterTimeoutError,
)
from app.ai_chat import (
    ChatRequest,
    StructuredAIResponse,
    apply_operations_to_board,
    normalize_structured_response,
)
from app.board_repository import BoardRepository

app = FastAPI(title="Project Management MVP Backend")

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "kanban.db"
SESSION_COOKIE_NAME = "pm_session"
VALID_USERNAME = "user"
VALID_PASSWORD = "password"
CHAT_HISTORY_LIMIT = 12
AI_PARSE_ATTEMPTS = 2
MAX_DELETIONS_PER_BATCH = 5
SUMMARY_KEYWORD_PATTERN = re.compile(r"\b(summarize|summary|recap)\b")

# Single-worker only: sessions and chat_histories are in-process state. Running
# uvicorn with --workers > 1 will route requests to processes that do not share
# these dicts and auth will fail intermittently. Move to SQLite if scaling out.
sessions: dict[str, str] = {}
chat_histories: dict[str, list[dict[str, str]]] = {}


def _resolve_db_path() -> Path:
    configured_path = os.getenv("KANBAN_DB_PATH")
    if configured_path:
        return Path(configured_path)
    return DEFAULT_DB_PATH


def _is_summary_request(message: str) -> bool:
    return SUMMARY_KEYWORD_PATTERN.search(message.lower()) is not None


def _count_deletions(operations: list[Any]) -> int:
    return sum(
        1
        for operation in operations
        if getattr(operation, "type", None) in {"delete_card", "delete_column"}
    )


def _build_board_summary(board: dict[str, Any]) -> str:
    columns = board.get("columns", [])
    cards = board.get("cards", {})

    lines = ["Here is your full board summary:"]
    total_cards = 0
    for column in columns:
        title = str(column.get("title", "Untitled"))
        card_ids = [card_id for card_id in column.get("cardIds", []) if isinstance(card_id, str)]
        card_titles = [
            str(cards[card_id].get("title", card_id))
            for card_id in card_ids
            if isinstance(cards.get(card_id), Mapping)
        ]
        total_cards += len(card_titles)
        if card_titles:
            lines.append(f"- {title} ({len(card_titles)}): " + "; ".join(card_titles))
        else:
            lines.append(f"- {title} (0): No cards")

    lines.append(f"Total cards: {total_cards}")
    return "\n".join(lines)


board_repo = BoardRepository(_resolve_db_path())
board_repo.initialize()
ai_client = OpenRouterClient()


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
        secure=os.getenv("PM_COOKIE_SECURE") == "1",
        samesite="lax",
        path="/",
    )
    return {"ok": True, "user": payload.username}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        username = sessions.pop(session_id, None)
        if username:
            chat_histories.pop(username, None)
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


@app.get("/api/ai/smoke")
def get_ai_smoke(request: Request) -> dict[str, str]:
    require_authenticated_user(request)
    prompt = "2+2"
    try:
        response_text = ai_client.prompt_text(prompt)
    except OpenRouterConfigError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except OpenRouterTimeoutError as error:
        raise HTTPException(status_code=504, detail=str(error)) from error
    except OpenRouterRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return {"prompt": prompt, "response": response_text}


@app.post("/api/ai/chat")
def post_ai_chat(request: Request, payload: ChatRequest) -> dict[str, Any]:
    username = require_authenticated_user(request)
    board = board_repo.get_board_data(username)

    if payload.conversation is not None:
        conversation = [entry.model_dump() for entry in payload.conversation]
    else:
        conversation = chat_histories.get(username, [])

    conversation = (
        conversation + [{"role": "user", "content": payload.message}]
    )[-CHAT_HISTORY_LIMIT:]

    if _is_summary_request(payload.message):
        summary_text = _build_board_summary(board)
        chat_histories[username] = (
            conversation + [{"role": "assistant", "content": summary_text}]
        )[-CHAT_HISTORY_LIMIT:]
        return {
            "assistantMessage": summary_text,
            "appliedOperations": False,
            "board": board,
        }

    structured: StructuredAIResponse | None = None
    updated_board: dict[str, Any] = board
    applied_operations = False
    attempts = 0
    max_attempts = AI_PARSE_ATTEMPTS

    try:
        while attempts < max_attempts:
            attempts += 1
            ai_result = ai_client.prompt_structured_chat(board, payload.message, conversation)
            try:
                structured = StructuredAIResponse.model_validate(
                    normalize_structured_response(ai_result, board)
                )
                if _count_deletions(structured.operations) > MAX_DELETIONS_PER_BATCH:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "AI proposed too many deletions in one batch; "
                            f"limit is {MAX_DELETIONS_PER_BATCH}."
                        ),
                    )
                updated_board, applied_operations = apply_operations_to_board(
                    board, structured.operations
                )
                break
            except (ValidationError, ValueError):
                if attempts >= max_attempts:
                    raise
                continue
    except OpenRouterConfigError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except OpenRouterTimeoutError as error:
        raise HTTPException(status_code=504, detail=str(error)) from error
    except OpenRouterRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except (ValidationError, ValueError) as error:
        raise HTTPException(status_code=502, detail="Invalid structured AI response.") from error

    if structured is None:
        raise HTTPException(status_code=502, detail="Invalid structured AI response.")

    if applied_operations:
        persisted_board = board_repo.replace_board_data(username, updated_board)
    else:
        persisted_board = board

    chat_histories[username] = (
        conversation
        + [{"role": "assistant", "content": structured.assistantMessage}]
    )[-CHAT_HISTORY_LIMIT:]

    return {
        "assistantMessage": structured.assistantMessage,
        "appliedOperations": applied_operations,
        "board": persisted_board,
    }


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
