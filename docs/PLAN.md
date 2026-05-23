# Project Plan (Approval-Gated)

This plan is split into 10 parts. Each part has clear deliverables, tests, and success criteria.

Rules for execution:
- Keep implementation simple and MVP-focused.
- Use explicit approval gates before moving to the next part.
- Use test-first thinking for each change.
- Prefer incremental commits after a logically complete step.

Fixed decisions for this project:
- Frontend tests: Vitest + React Testing Library, plus Playwright for end-to-end flows.
- Backend tests: pytest + FastAPI TestClient.
- MVP auth flow: simple server-side session/cookie, credentials `user` / `password`.
- AI model: OpenRouter `openai/gpt-oss-120b` only (no fallback).
- Structured Outputs schema: propose and get sign-off before implementation.

Implemented decisions through Part 10 + hardening:
- Backend persists board data in SQLite via `backend/app/board_repository.py`; schema is initialized in code (migration files are proposed in `docs/DATA_MODEL.md` but not yet implemented).
- Frontend board state is API-backed (`GET /api/board`, `PUT /api/board`) with inline loading/save error messaging.
- Start scripts pass project `.env` into container runtime so OpenRouter key is available in Docker (`--env-file`).
- Current start/stop scripts recreate containers; persistence is guaranteed for a stable DB file path, but not across container recreation without a Docker volume mount.
- Playwright e2e runs against Next dev server and mocks backend auth/board routes for deterministic frontend flow testing.
- AI smoke route is `GET /api/ai/smoke` (authenticated), sends prompt `2+2`, and maps OpenRouter failures to explicit HTTP statuses (`500` missing key, `502` upstream error, `504` timeout).
- `POST /api/ai/chat` is implemented with strict validation plus normalization/retry hardening for real-world model output variants.
- Summary prompts (`summarize` / `summary` / `recap`) use deterministic server-side board summary generation for complete responses.
- Sidebar AI chat supports Enter-to-send (Shift+Enter keeps newline) and auto-applies returned board updates.

---

## Part 1: Plan + Frontend Documentation

### Deliverables checklist
- [x] Expand this `docs/PLAN.md` into a detailed execution checklist with tests and success criteria.
- [x] Create `frontend/AGENTS.md` to document the existing frontend architecture and testing setup.
- [x] User reviews and approves this plan and frontend documentation.

### Tests
- [x] Documentation sanity check: verify paths and commands in docs map to real files/scripts.
- [ ] Optional: run markdown lint if introduced in repo later.

### Success criteria
- [x] Plan covers Parts 1-10 with actionable steps and explicit validation.
- [x] `frontend/AGENTS.md` helps a new engineer navigate and safely modify the frontend.
- [x] User approval received before Part 2 starts.

---

## Part 2: Scaffolding (Docker + FastAPI + Scripts)

### Deliverables checklist
- [x] Create backend app scaffold in `backend/` with FastAPI entrypoint.
- [x] Add Dockerfile and supporting container config to run backend and serve static content.
- [x] Add start/stop scripts in `scripts/` for macOS, Linux, and Windows.
- [x] Add a `GET /api/health` (or equivalent) endpoint returning JSON.
- [x] Serve a simple static `hello world` page from FastAPI at `/` to prove full stack runs.

### Tests
- [x] Backend unit test for health endpoint with `pytest` + `TestClient`.
- [x] Script smoke tests: start script boots app; stop script terminates process cleanly.
- [x] Manual container test: build image and confirm `/` and `/api/health` both work locally.

### Success criteria
- [x] `docker build` and container run succeed from a clean clone.
- [x] Visiting `/` returns static hello world content.
- [x] `/api/health` returns expected JSON response.
- [ ] User approval received before Part 3.

---

## Part 3: Integrate Existing Frontend Build

### Deliverables checklist
- [x] Configure frontend production build and static export path for backend serving.
- [x] Wire backend static serving so `/` renders current Kanban UI instead of hello world.
- [x] Preserve asset paths and routing needed by the MVP.
- [x] Keep backend API endpoint(s) accessible in same runtime.

### Tests
- [x] Frontend unit tests (`npm run test:unit`) pass.
- [x] Frontend e2e tests (`npm run test:e2e`) pass in local environment.
- [x] Integration smoke test in container: board renders at `/`, health API still works.

### Success criteria
- [x] Demo Kanban board is visible at `/` from backend-served app.
- [x] No regression in existing drag/drop, rename, add/remove behavior.
- [ ] User approval received before Part 4.

---

## Part 4: Fake Sign-In Experience (MVP Auth)

### Deliverables checklist
- [x] Add login page/flow that gates access to board.
- [x] Accept only `user` / `password` in MVP.
- [x] Implement simple server-side session/cookie auth.
- [x] Add logout action that clears session and returns user to login.
- [x] Protect board route(s) and API route(s) as needed for authenticated user.

### Tests
- [x] Backend auth tests: login success/failure, session creation, logout, protected route access.
- [x] Frontend unit/integration tests for login form validation and auth state transitions.
- [x] Playwright e2e for login -> board -> logout flow.

### Success criteria
- [x] Unauthenticated users cannot access board view.
- [x] Valid credentials grant access; invalid credentials do not.
- [x] Logout reliably clears session and blocks board access again.
- [x] User approval received before Part 5.

---

## Part 5: Database Modeling Proposal + Sign-Off

### Deliverables checklist
- [x] Propose SQLite schema for users, board, columns, cards, and optional chat/session entities.
- [x] Provide a JSON representation of persisted Kanban shape for app I/O.
- [x] Document schema decisions and migration approach in `docs/`.
- [x] Include rationale for future multi-user support while keeping MVP simple.
- [x] Present schema for user sign-off before implementing persistence APIs.

### Tests
- [ ] Validation test(s) for JSON shape (if schema validator introduced).
- [x] Documentation review checklist: consistency between SQL schema and JSON schema.

### Success criteria
- [x] Approved schema is unambiguous and implementation-ready.
- [x] Data model supports one board per user now and multiple users later.
- [x] User sign-off explicitly received before Part 6.

---

## Part 6: Backend Kanban API + Persistence

### Deliverables checklist
- [x] Implement DB initialization (create DB/tables if missing).
- [x] Add backend repository/service layer for board CRUD operations.
- [x] Add API routes for reading/updating Kanban data for authenticated user.
- [x] Ensure updates are transactional and preserve ordering semantics.
- [x] Seed initial board for first-time user if no saved data exists.

### Tests
- [x] Backend unit tests for repository/service methods.
- [x] Backend API tests for all routes with auth and error cases.
- [x] Persistence tests proving writes survive process restarts.

### Success criteria
- [x] API can fetch and update user board state reliably.
- [x] DB auto-creates on first run without manual setup.
- [x] Test suite covers happy path + key failure path behavior.
- [x] User approval received before Part 7.

---

## Part 7: Frontend + Backend Integration

### Deliverables checklist
- [x] Replace frontend in-memory board state bootstrap with backend fetch.
- [x] Persist board changes (rename/move/add/delete) through backend API.
- [x] Add loading and error states for API interactions.
- [x] Keep UI behavior and style consistent with existing experience.

### Tests
- [x] Frontend tests for API-backed state initialization and mutations.
- [x] Mocked integration tests for error handling and retry behavior (if added).
- [x] Playwright e2e for persistence across page reload.

### Success criteria
- [x] User interactions modify persisted board, not local-only memory.
- [x] Reload shows latest saved board state.
- [x] No regression in core board UX.
- [x] User approval received before Part 8.

---

## Part 8: AI Connectivity (OpenRouter Smoke)

### Deliverables checklist
- [x] Add backend OpenRouter client integration using `OPENROUTER_API_KEY`.
- [x] Add internal service method to send a simple prompt and return text response.
- [x] Add a backend test route or test utility for controlled connectivity verification.
- [x] Implement the required smoke test prompt: `2+2`.

### Tests
- [x] Unit tests for request construction and response parsing (mocked HTTP).
- [x] Connectivity smoke test (manual or integration-guarded) verifies successful AI call.
- [x] Error handling tests for missing key / non-200 responses / timeout behavior.

### Success criteria
- [x] Backend can successfully call OpenRouter and parse response content.
- [x] `2+2` test proves round-trip connectivity in local environment.
- [x] User approval received before Part 9.

---

## Part 9: Structured Outputs for Chat + Optional Board Update

### Proposed contract (for approval before implementation)

Decisions locked for MVP Part 9:
- Single endpoint: `POST /api/ai/chat` (authenticated).
- One response object containing:
  - assistant reply text (always required),
  - optional board operations (applied server-side, then persisted).
- AI may modify only board columns/cards through explicit operations (no full-board replacement from AI).
- Conversation history is in-memory per authenticated session.
- History truncation is deterministic: include most recent `N` messages only (default `N=12`, configurable in code constant).

#### Endpoint request contract (`POST /api/ai/chat`)

```json
{
  "message": "Move onboarding card to In Progress",
  "conversation": [
    { "role": "user", "content": "Can you reorganize my board?" },
    { "role": "assistant", "content": "Sure. What should change first?" }
  ]
}
```

Request validation rules:
- `message`: required, trimmed, non-empty string, max length 2000.
- `conversation`: optional array; if omitted, server uses stored in-memory history.
- each conversation item:
  - `role`: required enum `user | assistant` (no `system` from client),
  - `content`: required, trimmed, non-empty string, max length 2000.
- server enforces final history window size by keeping only last `N` messages after appending current user message.

#### AI structured output schema (OpenRouter response format)

Top-level object:
```json
{
  "assistantMessage": "I moved the onboarding card to In Progress.",
  "operations": [
    {
      "type": "move_card",
      "cardId": "card-onboarding",
      "toColumnId": "col-in-progress",
      "toIndex": 0
    }
  ]
}
```

Validation rules:
- `assistantMessage`: required, non-empty string, max length 4000.
- `operations`: optional array, default `[]`, max 50 operations per request.
- unknown keys are rejected by schema parser.
- invalid payload fails closed (no board mutation), returns `502` with a stable error detail.

Operation union (`operations[]`):
- `create_card`
  - required: `type`, `columnId`, `title`
  - optional: `details`, `cardId`, `index`
  - rules: title non-empty; if `cardId` omitted server creates deterministic id.
- `update_card`
  - required: `type`, `cardId`
  - optional (at least one required): `title`, `details`
- `delete_card`
  - required: `type`, `cardId`
- `move_card`
  - required: `type`, `cardId`, `toColumnId`, `toIndex`
- `create_column`
  - required: `type`, `title`
  - optional: `columnId`, `index`
- `update_column`
  - required: `type`, `columnId`, `title`
- `delete_column`
  - required: `type`, `columnId`
  - rules: deleting a column also deletes cards currently inside it (simple MVP behavior).
- `move_column`
  - required: `type`, `columnId`, `toIndex`

Server-side safety rules for operation application:
- apply operations sequentially in listed order within a single transaction.
- if any operation fails validation or refers to missing ids, reject entire operation batch (no partial writes).
- normalize indices to valid bounds (`<0` -> `0`, `>len` -> append).
- after apply, run board integrity validation:
  - every `cardId` in columns exists in `cards`,
  - every card appears in exactly one column,
  - no duplicate column ids or card ids.
- persist resulting full board via existing board repository write path.

#### Endpoint response contract (`POST /api/ai/chat`)

Success:
```json
{
  "assistantMessage": "I moved the onboarding card to In Progress.",
  "appliedOperations": true,
  "board": {
    "columns": [],
    "cards": {}
  }
}
```

Response validation rules:
- `assistantMessage`: required string.
- `appliedOperations`: required boolean (`true` only when at least one valid operation was applied).
- `board`: required full canonical board payload after any applied operations.

Error mapping:
- `401`: unauthenticated.
- `400`: invalid request body from client.
- `502`: upstream AI/schema contract failure (including malformed structured output).
- `504`: AI timeout.
- `500`: server config/runtime error (e.g., missing API key).

Sign-off needed before coding:
- [x] Approve `POST /api/ai/chat` request/response contract above.
- [x] Approve operation-based board mutation model (no full-board replacement from AI).
- [x] Approve in-memory conversation history + last-`N` truncation.

### Deliverables checklist
- [x] Propose exact Structured Outputs schema and get sign-off first.
- [x] Extend AI request payload to include:
  - current board JSON,
  - user message,
  - conversation history.
- [x] Parse validated structured response containing:
  - assistant reply text,
  - optional board update payload.
- [x] Safely apply board update payload when present.
- [x] Persist resulting board changes.

### Tests
- [x] Contract tests validating schema parsing and rejection of malformed output.
- [x] Backend tests for "reply only" vs "reply + board update" paths.
- [x] Tests for conversation history handling and token-safe truncation strategy (if needed).

### Success criteria
- [x] AI response contract is explicit, validated, and stable.
- [x] Optional board updates are applied deterministically and persisted.
- [x] User approval received before Part 10.

---

## Part 10: Sidebar AI Chat UX + Live Board Refresh

### Deliverables checklist
- [x] Add sidebar chat UI integrated into the board page.
- [x] Render conversation history and pending/error states.
- [x] Send chat messages to backend AI endpoint using structured contract.
- [x] Apply backend-returned board updates to UI automatically.
- [x] Keep styling aligned with project color system and current visual language.

### Tests
- [x] Frontend component tests for chat input, message list, loading/error states.
- [x] Integration tests ensuring AI response updates chat transcript and board state.
- [x] Playwright e2e for full flow: login -> ask AI -> board updates -> refresh persists.

### Success criteria
- [x] Chat feels integrated and responsive within Kanban layout.
- [x] Board refresh/update behavior is automatic when AI returns changes.
- [x] End-to-end tests prove the full MVP journey works reliably.
- [x] User approval received for Part 10.

---

## Approval Workflow

- [ ] Approval checkpoint after every part before starting the next one.
- [ ] Mandatory explicit sign-off at Part 1 and Part 5.
- [ ] If scope changes mid-part, update this plan before continuing implementation.