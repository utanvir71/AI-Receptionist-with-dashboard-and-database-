# Development Sessions Roadmap

Status: working tracker. Update this file after each session.

## Working Rules

- Keep each session small enough to finish and test locally.
- Ask the user before any external setup is required, such as Vapi UI changes, Google credentials, Twilio credentials, ngrok setup, or manager contact values.
- Do not mix unrelated work in one session.
- Prefer tests first for backend behavior.
- Verify locally at the end of each completed session.
- Do not run `git add`, create commits, push branches, create pull requests, or use GitHub
  unless the user explicitly asks.
- After verification, report the local status and wait for the user to decide the next git step.

## Session 0: Project Scaffold

Status: done.

Goal: create the repo structure and planning docs.

Completed:

- FastAPI package skeleton.
- `docs/` planning files.
- project-local restaurant KB.
- Vapi prompt draft.
- Vapi tool migration notes.
- `.gitignore`.
- local `.env`.
- GitHub repository initialized and pushed.

Commit:

- `118031d chore: scaffold ai receptionist backend`
- `e4b987b chore: stop tracking env example`

## Session 1: Core Business Rules

Status: done.

Goal: implement the local, dependency-free reservation rules.

Scope:

- Seoul timezone parsing.
- Reservation start-window validation.
- Past-date validation.
- 100-minute reservation duration helper.
- Restaurant resources:
  - regular tables
  - Table 1 + Table 2 combination
  - private rooms
  - Room 1 + Room 2 combination
- Window-side resource rules.
- Private-room minimum-spend mapping.
- Conflict overlap detection.
- Resource allocation priority:
  - smallest suitable resource first
  - same capacity prefers window-side
  - private rooms only when requested
  - regular 9-12 guests ask private room, otherwise impossible

Files likely touched:

- `app/utils/time.py`
- `app/models/resources.py`
- `app/services/resource_allocator.py`
- `tests/unit/test_time_rules.py`
- `tests/unit/test_resource_allocator.py`

No user action required unless a business rule is unclear.

Exit criteria:

- Unit tests pass.
- No Google Calendar, Twilio, or Vapi network calls.
- Do not stage, commit, or push unless the user explicitly asks.

Completed:

- Added `requirements.txt` and installed dependencies into the local `.venv`.
- Implemented Seoul timezone normalization.
- Implemented reservation start-window validation.
- Implemented fixed 100-minute reservation duration.
- Implemented regular table and private-room resource definitions.
- Implemented private-room minimum-spend mapping.
- Implemented overlap conflict detection.
- Implemented resource allocation priority.
- Added unit tests for time rules and resource allocation.

## Session 2: API Schemas And Vapi Auth

Status: done.

Goal: define the stable Vapi-facing request and response contracts.

Scope:

- Pydantic schemas for:
  - `check_availability`
  - `create_reservation`
  - `search_reservation`
  - `modify_reservation`
  - `cancel_reservation`
  - `manager_followup`
- Shared response status values.
- Bearer-token auth for Vapi tool calls.
- FastAPI route stubs using schemas and auth.
- Test auth success/failure.
- Test request validation.

Files likely touched:

- `app/schemas/reservations.py`
- `app/core/security.py`
- `app/api/v1/vapi_tools.py`
- `tests/unit/test_security.py`
- `tests/integration/test_vapi_routes.py`

User action required:

- None during coding.
- Later, user will set `VAPI_TOOL_SECRET` in `.env` and Vapi headers.

Exit criteria:

- Route validation tests pass.
- Auth tests pass.
- Do not stage, commit, or push unless the user explicitly asks.

Completed:

- Added strict Pydantic request and response schemas for Vapi tools.
- Added stable Vapi-facing status values.
- Added E.164 phone validation.
- Added bearer-token authorization helper for Vapi tool calls.
- Added FastAPI route stubs for all planned Vapi reservation endpoints.
- Added unit tests for schemas and authorization.
- Added integration tests for authenticated route validation.

## Session 3: In-Memory Reservation Service

Status: done.

Goal: connect schemas, time rules, and allocator into a service that works without Google Calendar.

Scope:

- Reservation service interface.
- In-memory calendar/repository fake for tests.
- Create reservation behavior.
- Check availability behavior.
- Search by phone and reservation date/time.
- Modify reservation behavior.
- Cancel reservation behavior.
- Cancelled bookings are non-blocking.
- Nearby fallback option generation within plus/minus 2 hours.
- Loop policy represented in responses, not conversation state.

Files likely touched:

- `app/services/reservation_service.py`
- `app/services/calendar_service.py`
- `tests/unit/test_reservation_service.py`

User action required:

- None.

Exit criteria:

- Full local reservation flow works in tests without external services.
- Do not stage, commit, or push unless the user explicitly asks.

Completed:

- Added the reservation calendar storage boundary.
- Added an in-memory calendar fake for local tests.
- Added reservation create, check availability, search, modify, and cancel service behavior.
- Kept cancelled records in storage while making them non-blocking for future availability.
- Added nearby fallback options within plus/minus 2 hours.
- Added loop-policy response metadata for unavailable times.
- Added explicit `cancelled` and `private_room_required` Vapi status values.
- Added unit coverage for the full local reservation flow.

## Session 4: Google Calendar Integration

Status: done.

Goal: make Google Calendar the V1 source of truth.

Scope:

- Google Calendar client wrapper.
- Event create/update/search/cancel.
- `extendedProperties.private` metadata.
- Human-readable event description.
- Event title format: `{party_size} guests - {customer_name}`.
- Ignore cancelled events during availability.
- Test with mocked Google Calendar client.

Files likely touched:

- `app/services/calendar_service.py`
- `app/services/reservation_service.py`
- `tests/unit/test_calendar_service.py`
- `tests/integration/test_google_calendar_contract.py`

User action required before live testing:

- Create or choose test Google Calendar named `ABCD Steakhouse Demo Reservations`.
- Provide Google Calendar ID in `.env`.
- Provide Google authentication method.

Important Google Calendar auth decision:

- Preferred: Google service account shared into the calendar, so the backend can create events without repeated user login.
- Alternative: OAuth refresh token stored in `.env`, but service account is cleaner for this restaurant backend.

Exit criteria:

- Mocked tests pass.
- Optional live test calendar smoke test passes after user provides credentials.
- Do not stage, commit, or push unless the user explicitly asks.

Completed:

- Added a Google Calendar-backed reservation storage implementation behind the existing calendar boundary.
- Added Google Calendar event create, update/search, and cancellation-as-status behavior.
- Stored machine-readable reservation metadata in `extendedProperties.private`.
- Added human-readable event title and description formatting for staff.
- Ignored cancelled reservation events for availability checks.
- Added mocked Google Calendar tests for event body structure, metadata parsing, search, and cancelled-event handling.
- Added settings-based Google Calendar client construction for service-account credentials.
- Passed a live test-calendar smoke test after local credentials were configured.

## Session 5: Notifications

Status: done.

Goal: add SMS and manager email boundaries.

Scope:

- Notification service interface.
- Twilio SMS implementation.
- Short English SMS templates:
  - confirmation
  - modification
  - cancellation
- Manager failed-transfer email implementation.
- SMS failure logs only for V1.
- Reservation remains confirmed if SMS fails after calendar success.
- Tests using fakes/mocks.

Files likely touched:

- `app/services/notification_service.py`
- `app/services/reservation_service.py`
- `tests/unit/test_notification_service.py`
- `tests/unit/test_reservation_notifications.py`

User action required before live testing:

- Twilio account SID.
- Twilio auth token.
- Twilio sender number.
- Manager email SMTP details.

Exit criteria:

- Mocked notification tests pass.
- Optional live SMS/email smoke tests pass after user provides credentials.
- Do not stage, commit, or push unless the user explicitly asks.

Completed:

- Added reservation notification interfaces and no-op defaults for missing live credentials.
- Added Twilio SMS notification implementation for confirmation, modification, and cancellation.
- Added short English SMS templates matching the V1 plan.
- Added SMTP manager follow-up email implementation.
- Wired reservation create, modify, and cancel flows to send notifications after calendar success.
- Kept reservations confirmed/cancelled when SMS sending fails, logging warning-only failures for V1.
- Added mocked unit tests for notification services and reservation notification behavior.
- Live Twilio SMS and SMTP smoke tests were not run because live credentials were not provided.

## Session 6: Full Vapi Tool Endpoints

Status: done.

Goal: expose production-ready endpoints for Vapi custom tools.

Scope:

- Wire routes to reservation service.
- Caller-safe response bodies.
- Error handling.
- Idempotency for duplicate Vapi tool calls.
- Health endpoint.
- Integration tests using FastAPI test client.

Files likely touched:

- `app/api/v1/vapi_tools.py`
- `app/services/reservation_service.py`
- `app/utils/idempotency.py`
- `tests/integration/test_vapi_routes.py`

User action required:

- None during coding.

Exit criteria:

- FastAPI route tests pass.
- Local server starts.
- Do not stage, commit, or push unless the user explicitly asks.

Completed:

- Wired Vapi reservation routes to the reservation service.
- Kept caller-safe response bodies from the existing `VapiToolResponse` envelope.
- Added caller-safe error handling for unexpected service failures.
- Added an in-process idempotency cache keyed by Vapi `Idempotency-Key` headers.
- Kept `/health` available for local and deployment checks.
- Added FastAPI integration tests for route wiring, shared reservation state, duplicate idempotent calls, safe errors, and health.

## Session 7: Local Run With ngrok

Status: planned.

Goal: connect local FastAPI to Vapi through ngrok and test real tool calls.

Scope:

- Start FastAPI locally.
- Start ngrok.
- Update Vapi tool URLs to ngrok endpoints.
- Add `Authorization` header in Vapi tools.
- Test:
  - `check_availability`
  - `create_reservation`
  - unavailable fallback
  - modification
  - cancellation

User action required:

- Run or approve ngrok.
- Copy ngrok HTTPS URL into Vapi tools.
- Add Vapi header secret.
- Possibly provide `.env` values.

Exit criteria:

- Real Vapi tool calls reach local FastAPI.
- Test reservation can be created in test Google Calendar.
- Do not stage, commit, or push unless the user explicitly asks.

## Session 8: Vapi Prompt And Tool Cleanup

Status: planned.

Goal: align Vapi assistant setup with the backend.

Scope:

- Update Vapi prompt from `docs/vapi-receptionist-prompt.md`.
- Keep:
  - `abcd-steakhouse-knowledge`
  - `end-call`
- Replace old Make.com `create_restaurant_reservation`.
- Create final Vapi tools:
  - `check_availability`
  - `create_reservation`
  - `search_reservation`
  - `modify_reservation`
  - `cancel_reservation`
  - optional `manager_followup`
- Confirm old pending-request language is removed.

User action required:

- Make Vapi UI changes or let Codex guide step by step.

Exit criteria:

- Vapi tools match backend routes and schemas.
- Prompt matches tool names.
- Test call flow works.

## Session 9: Production Hardening

Status: planned.

Goal: make local backend safer and easier to deploy later.

Scope:

- Structured logging.
- Request IDs.
- Clean error codes.
- Rate limit plan or implementation.
- Better startup config validation.
- Deployment notes.
- Operational runbook.

Files likely touched:

- `app/core/logging.py`
- `app/core/config.py`
- `README.md`
- `docs/operations.md`

User action required:

- Decide deployment target later.

Exit criteria:

- Production-readiness docs and safety checks are in place.
- Do not stage, commit, or push unless the user explicitly asks.

## Session 10: Future Database And CRM Preparation

Status: later.

Goal: prepare for database/CRM without changing V1 behavior.

Scope:

- Database schema design.
- Reservation audit model.
- Notification attempts table.
- Restaurant settings model.
- Menu/events settings model.
- CRM integration placeholder design.

User action required:

- Decide database provider and CRM direction.

Exit criteria:

- Future architecture doc is ready.
- No V1 behavior broken.
