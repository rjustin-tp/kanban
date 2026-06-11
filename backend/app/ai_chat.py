from __future__ import annotations

import copy
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.board_repository import validate_board_payload

MessageText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
AssistantText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: MessageText

    model_config = ConfigDict(extra="forbid")


class ChatRequest(BaseModel):
    message: MessageText
    conversation: list[ChatMessage] | None = None

    model_config = ConfigDict(extra="forbid")


class CreateCardOperation(BaseModel):
    type: Literal["create_card"]
    columnId: str
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    details: str = ""
    cardId: str | None = None
    index: int | None = None

    model_config = ConfigDict(extra="forbid")


class UpdateCardOperation(BaseModel):
    type: Literal["update_card"]
    cardId: str
    title: str | None = None
    details: str | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_has_change(self) -> "UpdateCardOperation":
        if self.title is None and self.details is None:
            raise ValueError("update_card must include title and/or details.")
        return self


class DeleteCardOperation(BaseModel):
    type: Literal["delete_card"]
    cardId: str

    model_config = ConfigDict(extra="forbid")


class MoveCardOperation(BaseModel):
    type: Literal["move_card"]
    cardId: str
    toColumnId: str
    toIndex: int | None = None

    model_config = ConfigDict(extra="forbid")


class CreateColumnOperation(BaseModel):
    type: Literal["create_column"]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    columnId: str | None = None
    index: int | None = None

    model_config = ConfigDict(extra="forbid")


class UpdateColumnOperation(BaseModel):
    type: Literal["update_column"]
    columnId: str
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]

    model_config = ConfigDict(extra="forbid")


class DeleteColumnOperation(BaseModel):
    type: Literal["delete_column"]
    columnId: str

    model_config = ConfigDict(extra="forbid")


class MoveColumnOperation(BaseModel):
    type: Literal["move_column"]
    columnId: str
    toIndex: int

    model_config = ConfigDict(extra="forbid")


Operation = Annotated[
    CreateCardOperation
    | UpdateCardOperation
    | DeleteCardOperation
    | MoveCardOperation
    | CreateColumnOperation
    | UpdateColumnOperation
    | DeleteColumnOperation
    | MoveColumnOperation,
    Field(discriminator="type"),
]


class StructuredAIResponse(BaseModel):
    assistantMessage: AssistantText
    operations: list[Operation] = Field(default_factory=list, max_length=50)

    model_config = ConfigDict(extra="forbid")


def apply_operations_to_board(
    board: dict[str, Any], operations: list[Operation]
) -> tuple[dict[str, Any], bool]:
    if not operations:
        return board, False

    working_board = copy.deepcopy(board)
    for operation in operations:
        _apply_single_operation(working_board, operation)

    validate_board_payload(working_board)
    return working_board, True


def normalize_structured_response(raw: dict[str, Any], board: dict[str, Any] | None = None) -> dict[str, Any]:
    operations = raw.get("operations")
    if operations is None:
        normalized = dict(raw)
        normalized["operations"] = []
        return normalized
    if not isinstance(operations, list):
        return raw

    normalized_operations: list[Any] = []
    for operation in operations:
        if not isinstance(operation, dict):
            normalized_operations.append(operation)
            continue
        normalized_operation = _normalize_operation(operation, board)
        if isinstance(normalized_operation, dict) and normalized_operation.get("type") == "noop":
            continue
        normalized_operations.append(normalized_operation)

    normalized = dict(raw)
    normalized["operations"] = normalized_operations
    return normalized


def _apply_single_operation(board: dict[str, Any], operation: Operation) -> None:
    if isinstance(operation, CreateCardOperation):
        _create_card(board, operation)
        return
    if isinstance(operation, UpdateCardOperation):
        _update_card(board, operation)
        return
    if isinstance(operation, DeleteCardOperation):
        _delete_card(board, operation)
        return
    if isinstance(operation, MoveCardOperation):
        _move_card(board, operation)
        return
    if isinstance(operation, CreateColumnOperation):
        _create_column(board, operation)
        return
    if isinstance(operation, UpdateColumnOperation):
        _update_column(board, operation)
        return
    if isinstance(operation, DeleteColumnOperation):
        _delete_column(board, operation)
        return
    if isinstance(operation, MoveColumnOperation):
        _move_column(board, operation)
        return

    raise ValueError("Unsupported operation type.")


def _normalize_operation(operation: dict[str, Any], board: dict[str, Any] | None = None) -> dict[str, Any]:
    raw_type = operation.get("type")
    if not isinstance(raw_type, str):
        action = operation.get("action")
        if isinstance(action, str):
            operation = _action_to_operation(operation)
            raw_type = operation.get("type")
    if not isinstance(raw_type, str):
        return operation

    normalized_type = _normalize_operation_type(raw_type)
    normalized = dict(operation)
    normalized["type"] = normalized_type

    if normalized_type == "update_column":
        if "title" not in normalized and "newTitle" in normalized:
            normalized["title"] = normalized["newTitle"]
        normalized.pop("newTitle", None)

    if normalized_type == "update_card":
        if "title" not in normalized and "newTitle" in normalized:
            normalized["title"] = normalized["newTitle"]
        if "details" not in normalized and "newDetails" in normalized:
            normalized["details"] = normalized["newDetails"]
        normalized.pop("newTitle", None)
        normalized.pop("newDetails", None)

    if normalized_type == "move_card":
        if "cardId" not in normalized and isinstance(normalized.get("cardTitle"), str):
            resolved_card = _resolve_card_id_from_title(board, normalized["cardTitle"])
            if resolved_card is not None:
                normalized["cardId"] = resolved_card
        if "toColumnId" not in normalized and isinstance(normalized.get("toColumn"), str):
            resolved_column = _resolve_column_id(board, normalized["toColumn"])
            if resolved_column is not None:
                normalized["toColumnId"] = resolved_column
        if "toIndex" not in normalized and normalized.get("position") == "end":
            normalized["toIndex"] = None
        normalized.pop("fromColumnId", None)
        normalized.pop("cardTitle", None)
        normalized.pop("toColumn", None)
        normalized.pop("position", None)

    return normalized


def _normalize_operation_type(value: str) -> str:
    aliases = {
        "renameColumn": "update_column",
        "updateColumn": "update_column",
        "createColumn": "create_column",
        "deleteColumn": "delete_column",
        "moveColumn": "move_column",
        "renameCard": "update_card",
        "updateCard": "update_card",
        "createCard": "create_card",
        "deleteCard": "delete_card",
        "moveCard": "move_card",
    }
    if value in aliases:
        return aliases[value]
    if "_" in value:
        return value
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def _resolve_column_id(board: dict[str, Any] | None, candidate: str) -> str | None:
    if board is None:
        return None
    columns = board.get("columns")
    if not isinstance(columns, list):
        return None
    normalized_candidate = candidate.strip().lower()
    for column in columns:
        if not isinstance(column, dict):
            continue
        column_id = column.get("id")
        title = column.get("title")
        if isinstance(column_id, str) and column_id == candidate:
            return column_id
        if isinstance(column_id, str) and column_id.lower() == normalized_candidate:
            return column_id
        if isinstance(title, str) and title.strip().lower() == normalized_candidate:
            return str(column_id) if isinstance(column_id, str) else None
    return None


def _resolve_card_id_from_title(board: dict[str, Any] | None, card_title: str) -> str | None:
    if board is None:
        return None
    cards = board.get("cards")
    if not isinstance(cards, dict):
        return None
    normalized_title = card_title.strip().lower()
    matching_ids = [
        key
        for key, card in cards.items()
        if isinstance(key, str)
        and isinstance(card, dict)
        and isinstance(card.get("title"), str)
        and card["title"].strip().lower() == normalized_title
    ]
    if len(matching_ids) == 1:
        return matching_ids[0]
    return None


def _action_to_operation(operation: dict[str, Any]) -> dict[str, Any]:
    action = operation.get("action")
    if action == "addCardToColumn":
        return {
            "type": "move_card",
            "cardId": operation.get("cardId"),
            "toColumnId": operation.get("columnId"),
            "position": operation.get("position"),
        }
    if action == "removeCardFromColumn":
        # Drop standalone remove actions; paired add action carries target location.
        return {
            "type": "noop",
        }
    return operation


def _create_card(board: dict[str, Any], operation: CreateCardOperation) -> None:
    column = _get_column(board, operation.columnId)
    card_id = operation.cardId or _generate_id("card", operation.title, set(board["cards"].keys()))
    if card_id in board["cards"]:
        raise ValueError("Card id already exists.")
    board["cards"][card_id] = {
        "id": card_id,
        "title": operation.title,
        "details": operation.details,
    }
    insert_index = _clamp_index(operation.index, len(column["cardIds"]))
    column["cardIds"].insert(insert_index, card_id)


def _update_card(board: dict[str, Any], operation: UpdateCardOperation) -> None:
    card = board["cards"].get(operation.cardId)
    if card is None:
        raise ValueError("Card not found.")
    if operation.title is not None:
        card["title"] = operation.title.strip()
    if operation.details is not None:
        card["details"] = operation.details


def _delete_card(board: dict[str, Any], operation: DeleteCardOperation) -> None:
    if operation.cardId not in board["cards"]:
        raise ValueError("Card not found.")
    for column in board["columns"]:
        if operation.cardId in column["cardIds"]:
            column["cardIds"].remove(operation.cardId)
            break
    del board["cards"][operation.cardId]


def _move_card(board: dict[str, Any], operation: MoveCardOperation) -> None:
    if operation.cardId not in board["cards"]:
        raise ValueError("Card not found.")
    target_column = _get_column(board, operation.toColumnId)
    source_column = _find_column_for_card(board, operation.cardId)
    source_column["cardIds"].remove(operation.cardId)
    insert_index = _clamp_index(operation.toIndex, len(target_column["cardIds"]))
    target_column["cardIds"].insert(insert_index, operation.cardId)


def _create_column(board: dict[str, Any], operation: CreateColumnOperation) -> None:
    used_ids = {column["id"] for column in board["columns"]}
    column_id = operation.columnId or _generate_id("col", operation.title, used_ids)
    if column_id in used_ids:
        raise ValueError("Column id already exists.")
    new_column = {"id": column_id, "title": operation.title, "cardIds": []}
    insert_index = _clamp_index(operation.index, len(board["columns"]))
    board["columns"].insert(insert_index, new_column)


def _update_column(board: dict[str, Any], operation: UpdateColumnOperation) -> None:
    column = _get_column(board, operation.columnId)
    column["title"] = operation.title


def _delete_column(board: dict[str, Any], operation: DeleteColumnOperation) -> None:
    index = next((i for i, column in enumerate(board["columns"]) if column["id"] == operation.columnId), -1)
    if index < 0:
        raise ValueError("Column not found.")
    column = board["columns"].pop(index)
    for card_id in column["cardIds"]:
        board["cards"].pop(card_id, None)


def _move_column(board: dict[str, Any], operation: MoveColumnOperation) -> None:
    index = next((i for i, column in enumerate(board["columns"]) if column["id"] == operation.columnId), -1)
    if index < 0:
        raise ValueError("Column not found.")
    column = board["columns"].pop(index)
    insert_index = _clamp_index(operation.toIndex, len(board["columns"]))
    board["columns"].insert(insert_index, column)


def _get_column(board: dict[str, Any], column_id: str) -> dict[str, Any]:
    for column in board["columns"]:
        if column["id"] == column_id:
            return column
    raise ValueError("Column not found.")


def _find_column_for_card(board: dict[str, Any], card_id: str) -> dict[str, Any]:
    for column in board["columns"]:
        if card_id in column["cardIds"]:
            return column
    raise ValueError("Card is not assigned to a column.")


def _clamp_index(index: int | None, upper_bound: int) -> int:
    if index is None:
        return upper_bound
    if index < 0:
        return 0
    if index > upper_bound:
        return upper_bound
    return index


def _generate_id(prefix: str, label: str, existing_ids: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "item"
    candidate = f"{prefix}-{base}"
    if candidate not in existing_ids:
        return candidate

    suffix = 2
    while True:
        numbered = f"{candidate}-{suffix}"
        if numbered not in existing_ids:
            return numbered
        suffix += 1


