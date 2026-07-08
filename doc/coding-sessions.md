# Coding Session Phases

Use this file to split the implementation across context windows. Each new context window should complete exactly one phase unless the user explicitly asks otherwise.

## Session Status Tracker

Allowed status values:

- `done`
- `next session`
- `in queue`

Current status:

| Phase | Status | Notes |
| --- | --- | --- |
| Phase 1: MSSQL Backend Foundation And Vapi Storage Migration | `next session` | Start here in the next coding context window. |
| Phase 2: Staff APIs, Walk-Ins, Reports, And Live Updates | `in queue` | Start only after Phase 1 is done and verified. |
| Phase 3: Flutter Web Dashboard, Docker Compose, And Demo Readiness | `in queue` | Start only after Phase 2 is done and verified. |

After finishing any phase, update this status tracker before ending the session:

- Change the completed phase status to `done`.
- Change the next phase status from `in queue` to `next session`.
- Add a short note with the completion commit, test commands, and test result.
- Do not mark a phase `done` while tests or lint are failing.

## Prompt For A New Coding Session

Use this prompt when starting a fresh context window:

```text
Read every file in the doc folder first:
- doc/project-plan.md
- doc/implementation-plan.md
- doc/coding-sessions.md

Then start the phase marked `next session` in doc/coding-sessions.md.
Use a non-main branch.
After coding, run the required tests and Ruff.
If tests fail, fix and rerun until they pass.
Before ending, update doc/coding-sessions.md status tracker, summarize changed files and test results, commit, and push.
```

At the start of each context window:

1. Read `doc/project-plan.md`.
2. Read `doc/implementation-plan.md`.
3. Read this file.
4. Check the current git branch and working tree status.
5. Continue only the phase requested by the user.

All new implementation work should happen on a non-main branch. Do not commit secrets, `.env`, credential JSON files, virtual environments, cache files, or generated outputs.

## Required Verification After Every Phase

After coding for any phase:

1. Run the relevant tests for the changed area.
2. Run the full backend test suite when backend behavior changed.
3. Run Ruff after backend Python changes.
4. Run frontend tests/analyzers after Flutter work exists.
5. If any test, lint, or analyzer result is bad, fix the problem and run verification again.
6. Repeat until the verification result is good.

Current backend verification commands:

```bash
cd backend
.venv/bin/pytest -q
.venv/bin/ruff check .
```

If the virtualenv does not exist in a fresh environment, create it and install requirements before testing:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
.venv/bin/ruff check .
```

After every phase, report:

- branch name
- files changed
- summary of what changed
- test commands run
- test results
- any remaining risks or follow-up work

Do not claim a phase is complete if tests or lint are failing. Fix failures first, then test again.

## Phase 1: MSSQL Backend Foundation And Vapi Storage Migration

Goal: make MSSQL the main reservation source of truth while preserving the existing Vapi AI receptionist API behavior.

Scope:

- Add SQLAlchemy database setup.
- Add Alembic migrations.
- Add MSSQL configuration through environment variables.
- Add database models for:
  - customers
  - restaurant resources
  - resource members
  - reservations
  - reservation resource assignments
  - call logs
  - manager follow-ups
  - audit logs
  - settings
  - backup runs
- Seed the fixed restaurant tables, rooms, and allowed combinations.
- Implement database-backed reservation storage behind the existing reservation service boundary.
- Keep the existing `/vapi/reservations/...` URLs and request/response shapes unchanged.
- Replace Google Calendar runtime storage with MSSQL.
- Keep Twilio SMS behavior unchanged for the AI phone flow.
- Keep in-memory storage available for tests where useful.

Out of scope for Phase 1:

- Flutter frontend.
- Staff dashboard UI.
- Full reports UI.
- Docker Compose production polish, except minimal database setup if needed for tests.

Required verification:

- Existing Vapi integration tests pass.
- Existing reservation rule tests pass.
- New MSSQL repository tests pass.
- Alembic upgrade test or migration smoke test passes.
- Ruff passes.

Expected phase summary:

- Explain how MSSQL replaced Google Calendar.
- List any Google Calendar code left in place and why.
- Confirm Vapi contract compatibility.
- Confirm no real Twilio SMS was sent during tests.

## Phase 2: Staff APIs, Walk-Ins, Reports, And Live Updates

Goal: add staff-facing backend APIs and live update infrastructure without building the Flutter UI yet.

Scope:

- Add staff shared-password auth.
- Add staff routes under `/api/staff/...`.
- Add reservation list/detail/create/edit/cancel/arrive/complete/no-show APIs.
- Add walk-in creation and completion APIs.
- Enforce walk-in 100-minute free-window check.
- Add customer profile APIs.
- Add manager follow-up APIs.
- Add call log storage route or Vapi webhook if needed.
- Add report APIs for daily, weekly, monthly, and yearly metrics.
- Add demo reset API.
- Add manual backup API.
- Add audit logging for staff mutations.
- Add optimistic concurrency checks.
- Add WebSocket endpoint for live multi-iPad updates.

Out of scope for Phase 2:

- Flutter UI implementation.
- Final visual design.
- Cloudflare/domain setup.

Required verification:

- Staff API auth tests pass.
- Staff reservation lifecycle tests pass.
- Walk-in tests pass.
- SMS decision tests pass with fake Twilio.
- Report aggregation tests pass.
- WebSocket tests pass.
- Existing Vapi tests still pass.
- Ruff passes.

Expected phase summary:

- List every staff route added.
- Explain SMS behavior for staff actions.
- Explain WebSocket event payloads.
- Confirm stale edit conflict handling works.
- Confirm no real Twilio SMS was sent during tests.

## Phase 3: Flutter Web Dashboard, Docker Compose, And Demo Readiness

Goal: build the responsive Flutter Web dashboard and make the full system runnable through Docker Compose/ngrok.

Scope:

- Create Flutter Web frontend.
- Build top-level navigation:
  - Floor
  - Reservations
  - Customers
  - Follow-ups
  - Reports
  - Settings
- Build Floor tab:
  - reservation side panel
  - floor map
  - date/time selector
  - table/room status
  - combined resource visuals
  - walk-in flow
  - reservation detail popup
- Build Reservations tab:
  - searchable list
  - day calendar
  - week calendar
  - drag changes with conflict checks
- Build Customers, Follow-ups, Reports, and Settings screens for V1.
- Add frontend API client and WebSocket client.
- Add loading, empty, disconnected, conflict, and SMS confirmation states.
- Add Dockerfiles.
- Add root `docker-compose.yml`.
- Add nginx frontend serving and proxying for `/api` and `/vapi`.
- Add optional ngrok profile for demo access.
- Add `.env.example` without secrets.
- Update README/runbook for local and Ubuntu server usage.

Required verification:

- Backend full test suite passes.
- Ruff passes.
- Flutter analyzer/test commands pass once frontend exists.
- Docker Compose build succeeds.
- Docker Compose smoke test succeeds:
  - `/health`
  - staff login
  - floor state
  - create reservation
  - seat/complete with bill
  - report includes revenue
  - Vapi search still works

Expected phase summary:

- Give local run commands.
- Give Ubuntu server run commands.
- Give ngrok demo instructions.
- List frontend screens implemented.
- List test results.
- List any demo limitations.
