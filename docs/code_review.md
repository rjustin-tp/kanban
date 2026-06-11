# Code Review: Kanban MVP

Repository-wide review of the FastAPI + Next.js Kanban MVP at `51597c0` (Parts 1-10 complete). Scope: correctness, architecture, security, performance, tests, infra. Each issue lists a concrete file:line reference and an action item.

The MVP framing matters: the project is explicitly small, local-only, single-user, single-worker, no persistence guarantees beyond a stable DB path. Issues that would be hard "must fix" in production are sometimes downgraded here. Where a hardening item is borderline-MVP vs. borderline-real, it is called out.

## Status

- **Critical:** 1/1 fixed.
- **Important:** 11/11 fixed (#10 partially — backend guard landed, no in-UI confirmation step yet).
- **Minor:** 0/15 fixed — outstanding work.

Verification after fixes: backend pytest 41/41, frontend vitest 18/18, eslint clean, Playwright e2e 6/6.

---

## Strengths

- **Domain logic isolated and tested.** `frontend/src/lib/kanban.ts` keeps board semantics pure, with focused unit tests. `backend/app/ai_chat.py` keeps the operation model, application, and integrity validation independent of FastAPI.
- **Operation model is well-typed.** Pydantic discriminated union on `type`, `extra="forbid"`, and explicit length constraints (`MessageText`, `AssistantText`) catch malformed AI output at the boundary.
- **Error mapping for OpenRouter is explicit and consistent.** Config / timeout / request failures map to `500` / `504` / `502` and the same mapping is reused in both `/api/ai/smoke` and `/api/ai/chat`.
- **Summary path short-circuits the model.** Deterministic local summary keeps a known-flaky behavior (long board summaries) reliable. Good tradeoff.
- **Tests exercise real behavior.** Backend tests use TestClient with a real SQLite DB in `tmp_path`, not mocked repositories. AI tests stub the AI client only, not the parsing pipeline. Playwright e2e drives a real DnD interaction. This is the right shape.
- **Operation normalizer recovers from common AI shape variants** (`renameColumn` → `update_column`, `cardTitle` → `cardId`, `action`/`type` polymorphism), with explicit tests for each variant.
- **Docker build is layered correctly.** Frontend stage caches `npm ci` independently; backend stage caches `uv sync` against `pyproject.toml` before copying source.

---

## Issues

### Critical (must fix)

#### 1. Column rename writes to backend on every keystroke
- File: `frontend/src/components/KanbanBoard.tsx:100-111`
- The `<input>` in `KanbanColumn` (`frontend/src/components/KanbanColumn.tsx:42-47`) is controlled, and `onChange` calls `handleRenameColumn` → `setBoard` → `persistBoard` on every character. Typing "Queue" issues 5 sequential `PUT /api/board` calls.
- Why it matters: each PUT does a full `DELETE FROM cards; DELETE FROM columns; INSERT...` cycle in SQLite (`backend/app/board_repository.py:135-167`). Bursts of writes can land out of order under any network jitter, and responses can race with concurrent AI mutations. The Playwright test at `frontend/tests/kanban.spec.ts:235-257` already encodes this expectation, which makes the bug load-bearing in tests.
- Action: debounce `persistBoard` for column renames (250-400ms), or persist on `onBlur` and dirty-check. Keep local state in sync immediately; only the network call should be deferred.
- **Status: FIXED.** `handleRenameColumn` now stages the next board state immediately and schedules `persistBoard` 400ms later via a `useRef` timer; subsequent keystrokes clear the prior timer. New unit test in `KanbanBoard.test.tsx` ("debounces column rename into a single save") asserts that typing "Queue" produces exactly one PUT.

---

### Important (should fix)

#### 2. AI system prompt does not describe the operation schema
- File: `backend/app/ai_service.py:88-94`
- System prompt is: `"You are an assistant for a kanban app. Respond only with JSON object matching this shape: {assistantMessage: string, operations?: array}."` The model is never told what an operation looks like.
- Result: the model emits inconsistent shapes, which the codebase patches with ~140 lines of normalization in `backend/app/ai_chat.py:138-312` (camelCase aliases, `cardTitle` → `cardId` resolution, `action` → `type` translation, "end" position handling). Six dedicated tests exist to cover these AI quirks (`backend/tests/test_ai_api.py:232-503`).
- Action: rewrite the system prompt to enumerate the eight operation types with their exact required/optional fields, ideally with one example per type. Then delete the dead normalization paths (alias map and `_action_to_operation` can likely go). This is the single highest-leverage change in the codebase.
- **Status: FIXED (prompt half).** New `STRUCTURED_CHAT_SYSTEM_PROMPT` in `ai_service.py` enumerates all 8 operation types with their required/optional fields and forbids extra keys. The normalizer was intentionally kept as a defensive belt-and-braces — removing it is left as follow-up once real-OpenRouter traffic confirms the new prompt's output (low risk, but the existing alias tests would need to be retired alongside).

#### 3. AI retry loop re-sends the identical prompt on parse failure
- File: `backend/app/main.py:212-229`
- `AI_PARSE_ATTEMPTS = 4` (line 33). On `ValidationError`/`ValueError`, the loop re-calls `prompt_structured_chat` with the same `payload.message` and `conversation`. The model has no signal that its prior output was rejected, so retries usually fail the same way.
- Why it matters: at the default 20s timeout (`ai_service.py:28`), a single bad prompt can block the request for up to ~80s and bill OpenRouter 4× for the same failure. The frontend (`KanbanBoard.tsx:154-195`) has no client-side timeout or cancellation.
- Action: either (a) append the validation error as an assistant correction note before retrying, or (b) reduce `AI_PARSE_ATTEMPTS` to 1-2 once issue #2 is fixed. (b) is simplest if the schema fix lands first.
- **Status: FIXED.** `AI_PARSE_ATTEMPTS` reduced from 4 to 2 (one retry max). Existing `test_ai_chat_retries_once_for_invalid_structured_response` continues to pass at the new budget.

#### 4. In-memory session and chat state break under multiple workers
- File: `backend/app/main.py:34-35`
- `sessions: dict[str, str]` and `chat_histories: dict[str, list[...]]` are module globals. Two `uvicorn --workers 2` processes will not share them; logins on one worker will fail auth on the other.
- Why it matters: the Dockerfile uses single-worker uvicorn (`Dockerfile:31`), so the MVP works. But there is no comment or check enforcing this, and a future operator scaling out will find out the hard way.
- Action: add a comment at the top of `main.py` stating "single-worker only" with the reason, OR move sessions/history to SQLite (the proposed `auth_sessions` and `chat_messages` tables in `docs/DATA_MODEL.md:59-76` exist exactly for this).
- **Status: FIXED (documentation).** Added a comment above the `sessions` / `chat_histories` declarations spelling out the single-worker requirement and what breaks if violated. Moving to SQLite remains future work.

#### 5. SQLite has no migration mechanism, despite a documented one
- File: `backend/app/board_repository.py:71-120`
- Schema is bootstrapped with `CREATE TABLE IF NOT EXISTS`. `docs/DATA_MODEL.md:130-148` proposes a real migration system with `schema_migrations` and `0001_init.sql` files. The proposal was never implemented.
- Why it matters: any future schema change (adding a column, e.g.) requires manually dropping the DB. The docs lie about how schemas evolve.
- Action: either implement the `backend/migrations/` directory with the documented runner, or update `docs/DATA_MODEL.md` to match reality ("schema is bootstrapped in-code via `IF NOT EXISTS`; production-style migrations are out of scope for MVP"). Pick one — do not leave the gap.
- **Status: FIXED (docs).** `docs/DATA_MODEL.md` migration section rewritten to describe the in-code bootstrap actually used, with the file-based migration approach reframed as future work.

#### 6. Client-supplied chat history overrides server history without contract
- File: `backend/app/main.py:188-195`; `frontend/src/components/KanbanBoard.tsx:160-174`
- When `payload.conversation` is provided, the backend uses it verbatim as the history (then truncates). The frontend sends `priorConversation = chatMessages` on every chat request, so client state always wins.
- Why it matters: open two tabs, send "delete all cards" in tab A, then send "summarize" in tab B — tab B sends its own (different) history and silently desyncs the server's view. The history-in-memory model and the client-pushes-history model are doing the same job from opposite directions.
- Action: pick one. Simplest: stop sending `conversation` from the frontend (`KanbanBoard.tsx:171-174`) and let the server own truncation against the in-memory store. The endpoint contract in `docs/PLAN.md:221-227` already says "if omitted, server uses stored in-memory history" — make the frontend match.
- **Status: FIXED.** Frontend chat payload is now `{ message }` only; backend's existing in-memory history path takes over. New unit test "does not send conversation field in chat requests" locks this in.

#### 7. Validation logic duplicated between repository and AI layer
- Files: `backend/app/board_repository.py:305-343` (`_validate_board_data`) and `backend/app/ai_chat.py:430-468` (`_validate_board_integrity`)
- Both check the same invariants (unique column ids, no duplicate card refs, cards map matches column refs, each card has title+details). About 30 nearly-identical lines.
- Action: extract a single `validate_board_payload` function (e.g. into a new `backend/app/board_validation.py`) and call it from both places. Then the contract has one source of truth.
- **Status: FIXED.** `validate_board_payload` now lives at module level in `board_repository.py`; `ai_chat.py` imports it and `_validate_board_integrity` is gone. Both paths exercise the same validator.

#### 8. Replace-board insertion logic duplicated within the repository
- File: `backend/app/board_repository.py:129-172` (`replace_board_data`) and `218-257` (`replace_board_data_for_board_id`)
- The DELETE-then-INSERT body is repeated twice with one difference: the first opens its own connection, the second reuses an existing one.
- Action: extract the insertion body into a single private method that takes a connection. Then `replace_board_data` becomes `with self._connect()` + call. ~40 lines deleted.
- **Status: FIXED.** Both paths now call `_write_board_rows(connection, board_id, board_data)`. `replace_board_data_for_board_id` is gone; `replace_board_data` shrank to ~6 lines.

#### 9. `_is_summary_request` matches substrings, not words
- File: `backend/app/main.py:45-47`
- `"summary" in normalized` triggers on phrases like `"Don't give me a summary, just move card-1"` or `"Recap me later but for now delete card-2"`. The user's instruction is silently swallowed and replaced with a column dump.
- Action: match whole words (`re.search(r"\b(summarize|summary|recap)\b", normalized)`) or drop the shortcut entirely. If the goal is "summaries are deterministic," guard it more carefully.
- **Status: FIXED.** `_is_summary_request` now uses a module-level `SUMMARY_KEYWORD_PATTERN` regex with `\b…\b`. New test `test_ai_chat_summary_keyword_requires_word_boundary` confirms a payload like `"Move the analysummary-card to Done"` reaches the AI client, not the local summary path.

#### 10. Operations auto-apply without user confirmation
- File: `backend/app/main.py:242-245`, `frontend/src/components/KanbanBoard.tsx:183-185`
- If the AI returns operations and they validate, they are written to SQLite immediately and the frontend overwrites local board state. The user has no preview, no undo.
- Why it matters: a single mis-parsed `delete_column` (which cascades to all child cards, per `ai_chat.py:374-380`) is irreversible. Combined with #2 (loose prompt), the surface for AI to do something destructive is real.
- Action: for MVP, the minimum is a per-operation log in the UI so the user sees what changed. Better: surface a "proposed changes — Apply / Discard" panel in the chat sidebar before mutating. At least add a backend-side guard rejecting batches that delete more than N cards in one request.
- **Status: PARTIALLY FIXED (backend guard).** Added `MAX_DELETIONS_PER_BATCH = 5` and `_count_deletions` in `main.py`; batches that propose more than 5 `delete_card` + `delete_column` ops return `400` and the board is not mutated. New test `test_ai_chat_rejects_oversized_deletion_batch` covers this. The richer "preview / apply" UX is left as follow-up.

#### 11. Session cookie missing `secure` flag
- File: `backend/app/main.py:125-131`
- `set_cookie` sets `httponly=True, samesite="lax"` but not `secure=True`. Fine over localhost HTTP; not fine if anyone ever runs this behind HTTPS without flipping it.
- Action: read `secure` from an env var (`PM_COOKIE_SECURE`, default `False`) so a production-ish deployment can enable it without code change.
- **Status: FIXED.** `set_cookie` now reads `secure=os.getenv("PM_COOKIE_SECURE") == "1"`. Two tests cover both paths: cookie has `Secure` when the env var is set, doesn't when it isn't.

#### 12. OpenRouter response parsing crashes on empty `choices`
- Files: `backend/app/ai_service.py:64-68` and `130-134`
- `response_data.get("choices", [{}])[0]` defends against missing `choices`, but if the API returns `{"choices": []}` (which happens on certain provider errors), `[0]` raises `IndexError` and surfaces as a 500 instead of the mapped 502.
- Action: check `len(choices)` explicitly, raise `OpenRouterRequestError("OpenRouter response had no choices.")`.
- **Status: FIXED.** Both methods now call a shared `_extract_assistant_content` that rejects empty/non-list `choices` with `OpenRouterRequestError("OpenRouter response had no choices.")`. Two new tests cover the empty-`choices` path for both `prompt_text` and `prompt_structured_chat`.

---

### Minor (nice to have)

#### 13. `board_repo` and `ai_client` initialized at module import
- File: `backend/app/main.py:74-76`
- This works, but every test has to do `main_module.board_repo = BoardRepository(tmp_path / "kanban.db"); main_module.board_repo.initialize()` and remember to restore it (see `test_ai_api.py:113-503`, repeated 9 times).
- Action: use FastAPI `Depends()` for both, with module-level singletons as the default. Tests can override via `app.dependency_overrides`.

#### 14. `KanbanBoard.tsx` has too many responsibilities (343 lines)
- File: `frontend/src/components/KanbanBoard.tsx`
- Holds board state, chat state, drag/drop wiring, persistence, AI request flow, and the entire layout. Refactor opportunity, not a bug.
- Action: extract `useBoard()` (state + load + persist) and `useAiChat()` (messages, send, error). The component becomes layout-only.

#### 15. `Math.random` + `Date.now` for client id generation
- File: `frontend/src/lib/kanban.ts:164-168`
- Works, collision-unlikely. `crypto.randomUUID()` is broadly available in modern browsers and Node 19+.
- Action: `return ${prefix}-${crypto.randomUUID()}` (one line).

#### 16. `handleAddCard` substitutes a hard-coded placeholder for empty details
- File: `frontend/src/components/KanbanBoard.tsx:120`
- `details: details || "No details yet."` leaks an MVP-y string into stored data forever. If a user explicitly clears it later, that string still re-appears on the next add.
- Action: store an empty string; if the UI wants placeholder copy, render it in `KanbanCard.tsx` when `details === ""`.

#### 17. Card drag handle covers the Remove button
- File: `frontend/src/components/KanbanCard.tsx:29-31, 42-49`
- `{...listeners}` on the article means dragging starts anywhere, including on the Remove button. The 6px `activationConstraint` (`KanbanBoard.tsx:33-37`) mostly hides this, but a tap on Remove can occasionally drag instead.
- Action: attach `listeners` only to a header/handle element, not the article. Or stop click propagation on the Remove button.

#### 18. Dockerfile runs as root, no HEALTHCHECK
- File: `Dockerfile`
- Container runs as root; FastAPI health endpoint exists but Docker doesn't know about it.
- Action: add `RUN adduser --system --no-create-home pm && USER pm` (after `uv sync`); add `HEALTHCHECK CMD curl -fsS http://localhost:8000/api/health || exit 1`.

#### 19. SQLite file is not persisted across container recreations
- Files: `scripts/start-mac.sh:19`, `scripts/start-linux.sh:19`, `scripts/start-windows.ps1:19`
- `docker run` does not mount `backend/data/`. Every `./scripts/start-mac.sh` rebuilds the image and recreates the container — the next start has a fresh, seeded DB.
- The user is aware (CLAUDE.md notes this), but it makes the "persistence" claim brittle. Easy fix.
- Action: add `-v "${ROOT_DIR}/backend/data:/app/backend/data"` to the `docker run` line in all three start scripts, and document the path.

#### 20. `start-mac.sh` and `start-linux.sh` are byte-identical
- Files: `scripts/start-mac.sh`, `scripts/start-linux.sh`
- Same for stop scripts.
- Action: keep both as platform-specific entry points (documentation value) but consider symlinking, or just leave as-is. Minor.

#### 21. No CI configured
- No `.github/workflows/`, no pre-commit hooks. The tests exist but nothing runs them on push.
- Action: add a single workflow file running `cd backend && uv run ... pytest` and `cd frontend && npm ci && npm run lint && npm run test:unit`. Playwright can be optional.

#### 22. No backend linter/type-checker configured
- File: `backend/pyproject.toml`
- Only `pytest` in dev deps.
- Action: add `ruff` and `mypy` (or `pyright`) under `[project.optional-dependencies].dev`. The code is well-typed; type checking is low-cost.

#### 23. `initialData` is rendered before the API responds
- File: `frontend/src/components/KanbanBoard.tsx:24`; `frontend/src/lib/kanban.ts:18-72`
- `useState(() => initialData)` shows the static seed for one paint before the `GET /api/board` response replaces it. Briefly inconsistent.
- Action: initialize with `null`, render the loading state until the fetch resolves, then set. Drop `initialData` (used only by tests; tests should provide their own fixture).

#### 24. `replace_board_data` does a full board rewrite on every save
- File: `backend/app/board_repository.py:135-167`
- DELETE-then-INSERT all rows even for a single card move. Documented as intentional in `docs/DATA_MODEL.md:121-128` for simplicity.
- Action: leave as-is for MVP; mention in the doc that this trades write efficiency for code simplicity. Issue #1 compounds this — if rename is debounced, the cost drops sharply.

#### 25. Chat sidebar uses a fixed minimum height
- File: `frontend/src/components/KanbanBoard.tsx:277`
- `min-h-[520px]` will push layout on small viewports.
- Action: make the height responsive (`min-h-[320px] md:min-h-[520px]`).

#### 26. No rate limit / no concurrency guard on `POST /api/ai/chat`
- File: `backend/app/main.py:183-256`
- A user holding the Enter key can fire many in-flight AI requests. The frontend gates with `isSendingChat` (`KanbanBoard.tsx:156`), but the backend trusts the client.
- Action: lightweight guard — per-user mutex around the chat handler, or a `time.monotonic()` cooldown stored in `chat_histories`.

#### 27. `chat_histories` is not size-bounded per user
- File: `backend/app/main.py:35`
- It's capped at `CHAT_HISTORY_LIMIT = 12` per user, but never expired across sessions. For MVP single user, immaterial.
- Action: skip for MVP. Note for future.

---

## Recommendations

1. **Land the prompt fix first (#2).** It pulls the rug out from under issues #3 and removes ~140 lines of normalization. Most of the AI test suite (`test_ai_api.py:232-503`) becomes redundant once the model emits the documented shape. Verify with a one-off integration test against real OpenRouter before deleting the normalizer.
2. **Pick a stance on history ownership (#6).** This is small but the current dual-source model is the kind of thing that bites later. Recommend: server owns history; frontend drops the `conversation` field from its request payload.
3. **Run all changes through the existing test suite.** Coverage is strong where it counts — board logic, AI parse, auth round-trip. Add a debounce test for column rename (#1) when fixing.
4. **Consider an UI confirmation step for AI mutations (#10).** This is the most user-impacting hardening item and doesn't require backend changes — render the `operations[]` returned alongside the assistant message, with an "Undo" that re-PUTs the prior board.

---

## Assessment

**Ship-readiness: yes (Critical + Important resolved)**

The MVP is functionally complete and the tests prove the documented behavior. The original critical issue (#1, save-on-keystroke) is fixed and locked in by a new test. All 12 important issues are addressed; #10 keeps the richer UI confirmation step as follow-up but lands the backend deletion-batch guard now. The minor issues (#13-#27) remain as planned hardening work — none are blocking.

Verification after fixes: backend pytest 41/41, frontend vitest 18/18, eslint clean, Playwright e2e 6/6.
