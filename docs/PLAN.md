# Project plan

This document is the execution checklist for the MVP. Work proceeds phase by phase, and each phase is complete only when its validation and success criteria are met.

## Part 1: Plan and baseline

### Checklist
- [x] Review [AGENTS.md](C:/Repos/pm/AGENTS.md) constraints and architecture decisions.
- [x] Expand this project plan with implementation checklists, validation, and success criteria.
- [x] Create [frontend/AGENTS.md](C:/Repos/pm/frontend/AGENTS.md) describing the existing frontend baseline.
- [x] Collect user decisions for testing depth, schema artifact location, AI update policy, and MVP scope boundaries.
- [x] Obtain explicit user approval before implementation execution.

### Validation
- Plan and constraints are documented and internally consistent.
- Baseline frontend behavior and test tooling are documented.

### Success criteria
- Approved plan exists with clear phase gates and no unresolved scope ambiguity.

## Part 2: Scaffolding

### Checklist
- [x] Create [backend/](C:/Repos/pm/backend/) FastAPI project structure.
- [x] Add Dockerfile and local run configuration for full-stack containerized startup.
- [x] Create cross-platform scripts in [scripts/](C:/Repos/pm/scripts/) for start/stop (Windows, macOS, Linux).
- [x] Serve sample static HTML at `/` and expose at least one sample API endpoint.

### Validation
- Container builds successfully.
- App starts from scripts on the host platform.
- `GET /` and sample API endpoint both respond.

### Success criteria
- Local Dockerized baseline runtime is reproducible with one documented command path.

## Part 3: Integrate frontend static build

### Checklist
- [x] Build NextJS frontend assets from [frontend/](C:/Repos/pm/frontend/).
- [x] Configure FastAPI to serve built frontend at `/`.
- [x] Keep the existing Kanban demo behavior unchanged.

### Validation
- Frontend build command succeeds.
- Served `/` page renders Kanban board with five columns.

### Success criteria
- App root displays the current Kanban demo through the backend host.

## Part 4: Fake user sign-in

### Checklist
- [x] Add login screen shown before board access.
- [x] Implement fixed credential check (`user` / `password`).
- [x] Add logout behavior returning user to login state.

### Validation
- Incorrect credentials are rejected with clear error.
- Correct credentials grant access to board.
- Logout removes board access and returns to login.

### Success criteria
- Board is gated behind MVP authentication flow.

## Part 5: Database modeling

### Checklist
- [x] Define board/user schema and save JSON at [docs/database-schema.json](C:/Repos/pm/docs/database-schema.json).
- [x] Document persistence strategy in [docs/](C:/Repos/pm/docs/).
- [x] Obtain user sign-off before persistence API implementation.

### Validation
- Schema covers users, board ownership, columns, cards, and ordering.
- Documentation explains migration path to multi-user support.

### Success criteria
- Approved schema supports MVP behavior and future expansion.

## Part 6: Backend Kanban APIs

### Checklist
- [x] Implement backend routes for reading and mutating a signed-in user's board.
- [x] Add SQLite initialization that creates DB/tables automatically when missing.
- [x] Implement backend-level validation for payload shape and required fields.

### Validation
- Unit tests cover create/edit/delete/move/rename operations.
- Restarting app preserves saved board state.

### Success criteria
- Backend is the source of truth for board data persistence.

## Part 7: Frontend + backend integration

### Checklist
- [x] Replace frontend-only local board state with backend API calls.
- [x] Wire rename, add, delete, and drag/drop move operations through API.
- [x] Ensure UI refreshes from persisted backend state.

### Validation
- Integration tests verify state survives browser refresh.
- Interaction parity with existing UX is preserved.
- Drag-and-drop reliability regressions are covered (same-column reorder and drop-target highlighting).

### Success criteria
- Kanban board is fully persistent and API-backed.

## Part 8: AI connectivity

### Checklist
- [x] Add backend OpenRouter client integration using `.env` key.
- [x] Use model `openai/gpt-oss-120b` for requests.
- [x] Add a simple backend connectivity check prompt (`2+2`).

### Validation
- Request reaches OpenRouter and returns a valid response.
- Missing/invalid API key surfaces explicit error.

### Success criteria
- Backend can reliably call OpenRouter in local runtime.

## Part 9: Structured AI orchestration

### Checklist
- [x] Send board JSON, user message, and recent conversation history to AI.
- [x] Enforce structured output contract with reply plus optional board mutation payload.
- [x] Add confirmation flow before applying AI-requested board mutations.

### Validation
- Contract tests cover valid response, malformed response, and no-update response.
- Mutation requests are not applied without explicit user confirmation.

### Success criteria
- AI responses are deterministic and safe to process.

## Part 10: Sidebar AI UI

### Checklist
- [ ] Add sidebar chat UI using project color scheme.
- [ ] Implement chat send/receive and conversation rendering.
- [ ] Support mutation confirmation UX and automatic board refresh after apply.

### Validation
- End-to-end flow: user prompt -> AI response -> optional confirmation -> board update.
- UI remains usable with repeated interactions.

### Success criteria
- User can chat with AI and apply AI-suggested board updates from the sidebar.