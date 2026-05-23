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
- [ ] User approval received before Part 8.

---

## Part 8: AI Connectivity (OpenRouter Smoke)

### Deliverables checklist
- [ ] Add backend OpenRouter client integration using `OPENROUTER_API_KEY`.
- [ ] Add internal service method to send a simple prompt and return text response.
- [ ] Add a backend test route or test utility for controlled connectivity verification.
- [ ] Implement the required smoke test prompt: `2+2`.

### Tests
- [ ] Unit tests for request construction and response parsing (mocked HTTP).
- [ ] Connectivity smoke test (manual or integration-guarded) verifies successful AI call.
- [ ] Error handling tests for missing key / non-200 responses / timeout behavior.

### Success criteria
- [ ] Backend can successfully call OpenRouter and parse response content.
- [ ] `2+2` test proves round-trip connectivity in local environment.
- [ ] User approval received before Part 9.

---

## Part 9: Structured Outputs for Chat + Optional Board Update

### Deliverables checklist
- [ ] Propose exact Structured Outputs schema and get sign-off first.
- [ ] Extend AI request payload to include:
  - current board JSON,
  - user message,
  - conversation history.
- [ ] Parse validated structured response containing:
  - assistant reply text,
  - optional board update payload.
- [ ] Safely apply board update payload when present.
- [ ] Persist resulting board changes.

### Tests
- [ ] Contract tests validating schema parsing and rejection of malformed output.
- [ ] Backend tests for "reply only" vs "reply + board update" paths.
- [ ] Tests for conversation history handling and token-safe truncation strategy (if needed).

### Success criteria
- [ ] AI response contract is explicit, validated, and stable.
- [ ] Optional board updates are applied deterministically and persisted.
- [ ] User approval received before Part 10.

---

## Part 10: Sidebar AI Chat UX + Live Board Refresh

### Deliverables checklist
- [ ] Add sidebar chat UI integrated into the board page.
- [ ] Render conversation history and pending/error states.
- [ ] Send chat messages to backend AI endpoint using structured contract.
- [ ] Apply backend-returned board updates to UI automatically.
- [ ] Keep styling aligned with project color system and current visual language.

### Tests
- [ ] Frontend component tests for chat input, message list, loading/error states.
- [ ] Integration tests ensuring AI response updates chat transcript and board state.
- [ ] Playwright e2e for full flow: login -> ask AI -> board updates -> refresh persists.

### Success criteria
- [ ] Chat feels integrated and responsive within Kanban layout.
- [ ] Board refresh/update behavior is automatic when AI returns changes.
- [ ] End-to-end tests prove the full MVP journey works reliably.

---

## Approval Workflow

- [ ] Approval checkpoint after every part before starting the next one.
- [ ] Mandatory explicit sign-off at Part 1 and Part 5.
- [ ] If scope changes mid-part, update this plan before continuing implementation.