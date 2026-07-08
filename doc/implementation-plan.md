# AI Receptionist Dashboard Implementation Plan

## Goal

Build the database-backed staff dashboard around the existing FastAPI/Vapi/Twilio AI receptionist without breaking the current phone reservation flow.

The implementation should be phased so each stage is testable and reversible. Do not start with the Flutter UI. First make MSSQL the reservation source of truth while preserving existing Vapi behavior, then add staff APIs, then add the dashboard.

## Architecture Summary

- FastAPI remains the backend.
- Existing `/vapi/reservations/...` endpoints keep their URLs and response shapes.
- MSSQL replaces Google Calendar as the reservation source of truth.
- SQLAlchemy is the Python database layer.
- Alembic manages schema migrations.
- Staff dashboard APIs live under `/api/staff/...`.
- WebSockets provide live multi-iPad updates.
- Flutter Web is served by nginx in Docker.
- Docker Compose runs backend, MSSQL, frontend/nginx, migration jobs, and optional ngrok.

## Phase 1: Backend Database Foundation

### Purpose

Introduce MSSQL without changing Vapi behavior yet.

### Work

- Add database configuration:
  - `DATABASE_URL`
  - `MSSQL_DB`
  - `MSSQL_USER`
  - `MSSQL_PASSWORD`
  - `MSSQL_SA_PASSWORD`
- Add SQLAlchemy engine/session management.
- Add Alembic setup.
- Add initial MSSQL models:
  - `customers`
  - `restaurant_resources`
  - `resource_members`
  - `reservations`
  - `reservation_resource_assignments`
  - `call_logs`
  - `manager_followups`
  - `audit_logs`
  - `settings`
  - `backup_runs`
- Seed fixed resources:
  - all tables
  - all rooms
  - `table_1_2`
  - `room_1_2`
- Keep test/in-memory storage available for unit tests.

### Key Design Decisions

- Use `rowversion` or explicit integer `version` for optimistic concurrency.
- Store money as integer Korean won.
- Store status as stable enum strings:
  - `confirmed`
  - `seated`
  - `completed`
  - `cancelled`
  - `no_show`
- Store source as:
  - `ai_call`
  - `staff_manual`
  - `walk_in`

### Verification

- Alembic upgrade from empty DB works.
- Resource seed creates only allowed combinations.
- Repository tests cover create, search, list overlap, update, cancel, row versioning.

## Phase 2: Replace Google Calendar Storage

### Purpose

Make MSSQL the source of truth while keeping Vapi contract unchanged.

### Work

- Create a database-backed reservation repository behind the current reservation storage boundary.
- Rename the current calendar-shaped storage boundary to a storage-neutral concept, such as `ReservationStore`.
- Point `ReservationService` to MSSQL storage.
- Keep `/vapi/reservations/...` unchanged.
- Remove Google Calendar runtime selection after parity is proven.
- Remove Google Calendar settings/dependencies only after all regression tests pass.

### Preserve

- Vapi bearer auth.
- Vapi wrapped tool-call request support.
- Idempotency-key behavior.
- Caller-safe error responses.
- Twilio SMS behavior for AI-created reservations, modifications, and cancellations.

### Verification

- Existing Vapi integration tests still pass.
- Create/search/modify/cancel work against MSSQL.
- Cancelled reservations remain stored but non-blocking.
- No backend path requires Google Calendar credentials after cutover.

## Phase 3: Staff Auth And Staff APIs

### Purpose

Add staff dashboard backend capability without building the UI yet.

### Work

Add staff auth:

- Shared password only.
- Password hash configured through `.env` as `STAFF_PASSWORD_HASH`.
- Session secret configured through `.env` as `SESSION_SECRET_KEY`.
- Vapi auth and staff auth must stay separate.

Add staff API routes:

- `POST /api/staff/auth/login`
- `GET /api/staff/floor`
- `GET /api/staff/reservations`
- `POST /api/staff/reservations`
- `GET /api/staff/reservations/{id}`
- `PATCH /api/staff/reservations/{id}`
- `POST /api/staff/reservations/{id}/cancel`
- `POST /api/staff/reservations/{id}/arrive`
- `POST /api/staff/reservations/{id}/complete`
- `POST /api/staff/reservations/{id}/no-show`
- `POST /api/staff/walk-ins`
- `GET /api/staff/customers`
- `GET /api/staff/customers/{id}`
- `GET /api/staff/follow-ups`
- `PATCH /api/staff/follow-ups/{id}`
- `GET /api/staff/call-logs`
- `GET /api/staff/reports`
- `POST /api/staff/demo/reset`
- `POST /api/staff/backups`

### Business Rules

- New staff reservation sends confirmation SMS automatically.
- Staff cancellation sends cancellation SMS after confirmation warning.
- Staff date/time change sends modification SMS after confirmation warning.
- Table/room-only changes do not send SMS.
- Party-size-only changes do not send SMS.
- Internal note changes do not send SMS.
- Completion requires `final_bill_krw`.
- Private-room completion warns if final bill is below minimum spend.
- Mutating staff actions write audit logs as actor `staff`.

### Verification

- Unauthenticated staff requests return `401`.
- Vapi bearer token cannot access staff routes.
- Staff password hash is never exposed.
- SMS fake notifier records exactly the intended SMS events.
- Stale version update returns conflict: `record changed, reload before saving`.

## Phase 4: Floor State And Walk-Ins

### Purpose

Support the operational floor map and fast walk-in seating.

### Work

- Add floor-state query for selected date/time.
- Return resource status:
  - empty
  - current seated/occupied reservation
  - next reservation
  - conflict warning if applicable
- Support combined resources:
  - Table 1 + Table 2
  - Room 1 + Room 2
- Add walk-in creation:
  - tap empty table/room
  - `Seat Walk-in`
  - enter party size
  - require full 100-minute free window before next reservation
  - create as `seated`
  - no name/phone/SMS required
- Walk-ins can complete before 100 minutes and release immediately.
- Reservations still protect planned future bookings; early completion does not remove the original planned booking window for reservation planning.

### Verification

- Walk-in blocked when less than 100 minutes free before next reservation.
- Walk-in creation does not send SMS.
- Walk-in completion requires final bill amount.
- Walk-ins appear in reports as `walk_in`.
- Anonymous walk-ins do not create customer profiles.

## Phase 5: WebSockets And Concurrency

### Purpose

Make multiple iPads stay in sync.

### Work

- Add authenticated WebSocket endpoint, likely `/api/staff/ws`.
- Broadcast after committed changes:
  - reservation create/update/cancel
  - arrival/seated
  - completion
  - no-show
  - walk-in create/complete
  - manager follow-up update
  - demo reset
- Event payload should include:
  - `type`
  - `entity`
  - `id`
  - `version`
  - `occurred_at`
  - selected date if useful
- On reconnect, frontend should reload visible state through REST.

### Verification

- Two connected clients receive the same event.
- No event is broadcast after rollback.
- Stale update fails without overwriting.

## Phase 6: Manager Follow-Ups, Call Logs, Reports

### Purpose

Add operational history and reporting.

### Work

Manager follow-ups:

- Separate records from call logs.
- Statuses:
  - `open`
  - `resolved`
  - `cancelled`

Call logs:

- Save call time.
- Save customer phone.
- Save transcript or summary.
- Save action taken.
- Add Vapi webhook/backend route if transcript/summary is not currently posted to the backend.

Reports:

- Daily, weekly, monthly, yearly.
- Metrics:
  - bookings
  - completed visits
  - cancellations
  - no-shows
  - party sizes
  - source mix
  - table/room usage
  - revenue
- Charts:
  - bookings by day
  - revenue by day
  - no-show rate
  - table/room usage
  - AI/staff/walk-in source mix

### Verification

- Reports aggregate integer KRW correctly.
- Private-room minimum warning is recorded/returned at completion.
- Call logs do not require manager-follow-up flag.

## Phase 7: Flutter Web Dashboard

### Purpose

Build the actual staff-facing iPad/browser UI.

### Global UX

- English UI.
- Korea formatting:
  - `Asia/Seoul`
  - 24-hour time
  - `YYYY-MM-DD`
  - `010-1234-5678` when possible
  - `₩45,000`
- Top navigation:
  - `Floor`
  - `Reservations`
  - `Customers`
  - `Follow-ups`
  - `Reports`
  - `Settings`
- Show connection status in top bar.
- Show disconnected banner when offline.

### Floor Tab

- Default screen after login.
- Left collapsible reservation panel.
- Main floor map canvas.
- Date selector and time selector.
- Today's reservations grouped by:
  - `Upcoming`
  - `Seated`
  - `Completed`
  - `Cancelled`
  - `No-show`
- Table/room icons show current or next reservation.
- Combined resources visually merge while assigned.
- Popup panels open over floor map.

Resource quick actions:

- `Seat Walk-in`
- `New Reservation`
- `Arrived`
- `Complete`
- `Move`
- `Cancel`
- `Mark No-show`
- `Edit Notes`

### Reservations Tab

- Search by name, phone, date.
- Filters by status/source/date range.
- Views:
  - list/table
  - day calendar
  - week calendar
- Calendar supports drag changes.
- Date/time drag shows SMS confirmation.
- Table-only drag saves after conflict check without SMS.

### Customers Tab

- Search-first layout.
- Customer profile shows:
  - total visits
  - upcoming bookings
  - cancellations
  - no-shows
  - preferences
  - allergies
  - staff notes
- Anonymous walk-ins excluded unless details are later added.

### Follow-Ups Tab

- Status tabs:
  - `Open`
  - `Resolved`
  - `Cancelled`
- Detail panel shows reason, notes, reservation context, and call summary if available.

### Reports Tab

- Time filters:
  - daily
  - weekly
  - monthly
  - yearly
- Charts and summary metrics.
- No CSV export in V1.

### Settings Tab

- Editable:
  - restaurant hours
  - reservation windows
  - reservation duration
  - table/room capacities
  - demo reset
  - backup
- Not editable:
  - Twilio credentials
  - database password
  - staff password plaintext

## Phase 8: Docker, Backup, Demo, Rollout

### Compose Services

- `backend`
- `mssql`
- `frontend`
- `migrate`
- optional `ngrok` profile

### Routing

Single public entrypoint:

- `/` -> Flutter Web via nginx
- `/api/staff/...` -> FastAPI staff API
- `/vapi/reservations/...` -> FastAPI Vapi API
- `/health` -> FastAPI health check

### Ports

- Public:
  - nginx `80`
  - later `443`
- Internal:
  - backend `8000`
  - MSSQL `1433`, not internet-exposed

### Backup

- Manual `Back Up Database` button.
- Create `.bak` file in mounted backup volume/folder.
- Track backup metadata in `backup_runs`.
- Backups must be copied off-server for real safety.

### Demo Reset

- Only available when demo mode is enabled.
- Protected by normal staff auth/session.
- No typed `RESET` confirmation needed.
- Must never clear non-demo production data.

## Recommended Execution Order

1. Database foundation and resource seed.
2. MSSQL repository behind existing reservation service.
3. Vapi storage swap and Google Calendar removal.
4. Staff auth and reservation APIs.
5. Walk-ins and floor-state APIs.
6. WebSockets and conflict handling.
7. Reports, follow-ups, call logs, demo reset, backups.
8. Flutter Web shell and navigation.
9. Floor tab.
10. Reservation create/edit/detail flows.
11. Reservations list/calendar views.
12. Customers, follow-ups, reports, settings.
13. Docker Compose/ngrok integration.
14. Full regression and demo smoke test.

## Testing Plan

Keep current tests as golden regression coverage where possible.

Required test groups:

- Existing Vapi contract tests.
- SQL repository tests.
- Alembic migration tests.
- Reservation business-rule tests.
- SMS decision tests using fake Twilio.
- Staff API auth tests.
- Staff reservation lifecycle tests.
- Walk-in availability tests.
- Combined resource conflict tests.
- WebSocket broadcast tests.
- Optimistic concurrency tests.
- Report aggregation tests.
- Demo reset safety tests.
- Docker Compose smoke test.

## Main Risks

- Breaking Vapi tool contracts while changing storage.
- Accidentally sending real Twilio SMS during tests or demos.
- Exposing MSSQL port publicly.
- Losing timezone consistency between MSSQL, FastAPI, and Flutter.
- Incorrect overlap logic for combined resources.
- Demo reset clearing real data.
- WebSocket events broadcasting before database commit.
- Staff table-only moves accidentally sending SMS.

## Decisions Still Needed Before Coding

- Final floor-map geometry.
- Final status color palette.
- Whether top navigation is icon+text or text-only.
- Whether table/room icons are schematic or closer to real floor shapes.
- Whether private-room minimum warning can be overridden or only acknowledged.
- Whether customer call logs appear in the Customers tab in V1.
