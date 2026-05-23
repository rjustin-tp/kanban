from app.board_repository import BoardRepository


def test_repository_seeds_initial_board_for_new_user(tmp_path) -> None:
    repo = BoardRepository(tmp_path / "kanban.db")
    repo.initialize()

    board = repo.get_board_data("user")

    assert len(board["columns"]) == 5
    assert board["columns"][0]["id"] == "col-backlog"
    assert "card-1" in board["cards"]


def test_repository_persists_board_updates_across_reloads(tmp_path) -> None:
    db_path = tmp_path / "kanban.db"
    repo = BoardRepository(db_path)
    repo.initialize()

    board = repo.get_board_data("user")
    board["columns"][0]["title"] = "Queue"
    board["columns"][0]["cardIds"] = ["card-2"]
    board["columns"][4]["cardIds"].append("card-1")

    updated = repo.replace_board_data("user", board)
    assert updated["columns"][0]["title"] == "Queue"

    repo_after_restart = BoardRepository(db_path)
    repo_after_restart.initialize()
    reloaded = repo_after_restart.get_board_data("user")
    assert reloaded["columns"][0]["title"] == "Queue"
    assert "card-1" in reloaded["columns"][4]["cardIds"]


def test_repository_rejects_invalid_board_payload(tmp_path) -> None:
    repo = BoardRepository(tmp_path / "kanban.db")
    repo.initialize()
    board = repo.get_board_data("user")

    board["columns"][0]["cardIds"].append("missing-card")

    try:
        repo.replace_board_data("user", board)
    except ValueError as error:
        assert "All card ids must exist in cards map." in str(error)
        return

    raise AssertionError("Expected ValueError for invalid board payload.")
