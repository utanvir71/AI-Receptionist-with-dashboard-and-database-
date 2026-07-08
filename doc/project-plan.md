# AI Receptionist Dashboard And Database Project Plan

## Project Goal

Build a staff-facing restaurant reservation dashboard and database layer for the existing ABCD Steakhouse AI phone receptionist backend.

The current backend already handles the AI phone receptionist flow through Vapi, FastAPI, Twilio SMS, reservation rules, table allocation, modification, cancellation, and manager escalation. This project will keep that working behavior, add an MSSQL database as the main source of truth, and build a responsive Flutter Web dashboard for staff.

## Existing Backend To Preserve

- FastAPI backend remains the main API server.
- Vapi custom tool endpoints should keep their current URLs and request/response shapes:
  - `/vapi/reservations/check-availability`
  - `/vapi/reservations/create`
  - `/vapi/reservations/search`
  - `/vapi/reservations/modify`
  - `/vapi/reservations/cancel`
  - `/vapi/reservations/manager-followup`
- Twilio SMS confirmation, modification, and cancellation behavior stays in place.
- AI phone receptionist behavior stays English-only for V1.
- Existing reservation business rules should be reused instead of rewritten from scratch.

## Major Backend Change

MSSQL becomes the main reservation source of truth.

Google Calendar will be removed from the new version. The existing Vapi endpoints should continue working, but internally they should read and write reservations from MSSQL instead of Google Calendar.

The backend should add database-backed storage for:

- Reservations
- Customers
- Restaurant resources, tables, rooms, and combined resources
- Call logs
- Manager follow-ups
- Staff audit history
- Settings
- Reports and revenue fields
- Demo seed data

Recommended backend implementation choices:

- Use SQLAlchemy for the FastAPI database layer.
- Use Alembic migrations for MSSQL schema changes.
- Keep Vapi request and response contracts stable while swapping the storage backend from Google Calendar to MSSQL.
- Add a Vapi webhook or backend endpoint for storing call logs if the current Vapi tool flow does not already send transcript or summary data to the backend.

## Deployment Direction

- The system will run on an Ubuntu server.
- Backend, MSSQL, Flutter Web frontend, and optional ngrok should run with Docker Compose.
- Flutter Web should be built into static files and served by a separate nginx container.
- The iPad will open the responsive Flutter Web app in the browser.
- For now, public/demo access will use ngrok.
- Later, the public access path can move to a domain with Cloudflare.

## Authentication

- Staff login uses one shared password only.
- No individual staff accounts for V1.
- No automatic sign-out is needed.
- Audit history should still be recorded as generic `staff` actions.
- The shared staff password should be configured through environment variables as a hashed value, not stored as a plain-text database value.

## Frontend Direction

Build a responsive Flutter Web application for iPad browser use.

The main dashboard should show:

- Reservation list in a side panel.
- Floor map in the main area.
- Each table or room icon shows the current reservation if occupied.
- If empty, each table or room icon can show the next upcoming reservation.
- The reservation side panel can collapse to give the floor map more space.
- Staff can click a table or room to see:
  - current reservation
  - upcoming reservations
  - capacity
  - quick action buttons

Reservation creation and editing should open as a pop-up panel over the floor map, not a separate full screen.

Staff dashboard API routes should use a separate prefix such as `/api/staff/...`, while Vapi keeps `/vapi/reservations/...` unchanged.

Top-level dashboard navigation should include:

- `Floor`
- `Reservations`
- `Customers`
- `Follow-ups`
- `Reports`
- `Settings`

The `Floor` tab is the operational default view. The reservation side panel defaults to today's reservations grouped into:

- `Upcoming`
- `Seated`
- `Completed`
- `Cancelled`
- `No-show`

Staff can use a date picker to switch the side panel and floor map to another date. The floor map should also have a time selector for checking availability at a specific time. For today, the selector defaults to the current date and current time. For future dates, it can default to the selected date and a valid reservation time.

The `Reservations` tab should be separate from the today-focused side panel. It should include:

- searchable table/list view for past and future reservations
- calendar-style day view
- calendar-style week view

Staff can drag reservations in the day/week calendar view to change date/time or table/room assignment. The backend must run conflict checks before saving. If only the table/room changes, save after conflict check without SMS. If date/time changes, show confirmation because SMS will send automatically.

## Floor Map And Resource Rules

Known resources:

- Table 1: max 3
- Table 2: max 3
- Table 1 + Table 2: max 8
- Table 3: max 4
- Table 4: max 4
- Table 5: max 3
- Table 6: max 3
- Table 7: max 6
- Table 10: max 6
- Table 11: max 6
- Table 12: max 6
- Table 13: max 3
- Table 14: max 3
- Table 15: max 4
- Table 16: max 4
- Room 1: max 6
- Room 2: max 6
- Room 1 + Room 2: max 12
- Room 3: max 6
- Room 4: max 5
- Room 5: max 6

Only these combinations are allowed:

- Table 1 + Table 2
- Room 1 + Room 2

When combined resources are assigned, the floor map should visually merge the icons into one larger resource until the reservation ends.

If staff drags a reservation onto Table 1 and the party is too large for Table 1 alone, the UI should automatically offer the combined Table 1 + Table 2 option.

## Reservation Rules

- Restaurant hours: 11:00 to 21:00.
- Valid reservation start windows:
  - 11:00 to 14:30
  - 17:00 to 19:30
- Reservation duration: 100 minutes.
- Reservations block the table or room for the full original 100-minute period.
- Late arrival does not shorten or move the 100-minute reservation block.
- Early completion does not change future reservation availability. The original planned end time still protects scheduled bookings.
- Staff may seat a walk-in after early completion only if the table has a full 100-minute free window before the next reservation.
- Staff may extend a reservation only if no later booking conflict exists.
- Cancelled reservations are non-blocking.
- AI-created reservations and staff-created reservations both use the same reservation rules and both have source values.
- Staff-created reservations send confirmation SMS automatically.
- Staff cancellation sends cancellation SMS automatically after a confirmation warning.
- Staff date/time changes send modification SMS automatically after a confirmation warning.
- Table/room-only changes, party-size-only changes, and internal note changes do not send SMS.

Reservation sources:

- `ai_call`
- `staff_manual`
- `walk_in`

Dashboard reservation statuses:

- `confirmed`
- `seated`
- `completed`
- `cancelled`
- `no_show`

When staff taps `Arrived`, the reservation becomes `seated` and the actual seated time is saved. When staff marks a reservation `completed`, the app must require a final bill amount in Korean won. Staff can edit the final bill amount later, and that edit should create an audit history entry.

## Status And No-Show Rules

Staff can manually mark a reservation as no-show before the 100-minute reservation block ends.

Automatic no-show should happen only after the reservation block is finished. The system should not automatically mark no-show while the original 100-minute reservation time is still active.

Actual seating and departure times can be saved as automatic audit fields.

## Walk-Ins

Staff can create a walk-in seating record without name, phone number, or SMS.

Fast walk-in creation should work from the floor map:

1. Staff taps an empty table or room.
2. Staff presses `Seat Walk-in`.
3. Staff enters party size.
4. The system checks that the table or room has a full 100-minute free window before the next reservation.
5. If the table or room does not have a full 100-minute free window, the system blocks the walk-in.
6. If available, the walk-in is created as `seated` immediately using the current time.

Walk-ins:

- require party size and assigned table/room
- use the same `seated` and `completed` statuses as reservations
- require final bill amount when completed
- are included in reports with source `walk_in`
- do not appear in customer profiles unless customer details are later added
- require the same private-room minimum spending rule when seated in a private room
- use the normal 100-minute planned duration for availability checks
- can be completed before 100 minutes
- release the table immediately when completed

## Conflicts And Concurrency

- The app should support multiple iPads using it at the same time.
- Changes should update everywhere live using WebSockets.
- If two staff members edit the same reservation at the same time, the second person should receive a conflict warning instead of silently overwriting changes.
- Conflict warning wording should follow the pattern: record changed, reload before saving.
- If internet is disconnected, the app should show an internet disconnected message. Offline editing/sync is not required.
- Dashboard alerts are needed for table conflicts.
- Upcoming reservations do not need general dashboard alerts.

## Staff Search And Customer Profiles

Staff should be able to search reservations by:

- customer name
- phone number
- date

Customer profiles should show:

- total visits
- upcoming bookings
- cancellations
- no-shows
- preferences
- allergies
- staff notes

Phone numbers should be stored and displayed in Korean format when possible, such as `010-1234-5678`, while still accepting international numbers from Twilio.

## Manager Follow-Ups

Manager follow-ups should be separate records only when needed, such as:

- party size over 12
- failed AI handling
- other manager-required cases

Manager follow-ups should appear on a dedicated screen.

Follow-up statuses:

- `open`
- `resolved`
- `cancelled`

Call logs should save:

- call time
- customer phone number
- transcript or summary
- action taken

Call logs should not need a manager-follow-up flag. Manager follow-up status belongs in the separate manager follow-up records.

If Vapi does not already send call transcript or summary data to the current backend, add a dedicated Vapi webhook/backend route for call log storage.

## Reports

Reports should be viewable inside the application. CSV export is not required for V1.

Report time ranges:

- daily
- weekly
- monthly
- yearly

Reports should include reservation metrics:

- bookings
- completed visits
- cancellations
- no-shows
- party sizes
- table and room usage

Reports should also include revenue. For V1, keep revenue simple:

- Staff must type the final bill amount when marking a reservation completed.
- Currency is Korean won.
- No tax or tip breakdown is needed.
- POS/payment import can be added later if needed.

Reports should include simple charts in V1, such as:

- bookings by day
- revenue by day
- no-show rate
- table and room usage

Audit logs should be stored in the database for backend/history purposes. They do not need to be visible in the V1 application.

For private-room reservations or walk-ins, the app should warn staff at completion if the final bill is below the required private-room minimum spend.

## Settings

Keep settings simple for V1.

Editable settings should include:

- restaurant hours
- 100-minute reservation duration
- table and room capacities

Twilio credentials and other secret settings should be configured through `.env`, not edited in the UI.

Physical table layout is mostly fixed, but the UI must support the known combined resources:

- Table 1 + Table 2
- Room 1 + Room 2

## Backups

For the portfolio version, a manual `Back Up Database` button is enough.

Automatic daily backups are not required for V1.

The manual backup should create an MSSQL `.bak` file in a Docker volume or backups folder.

## Demo Data

The portfolio/demo should use fictional data only.

The database should include a seed/demo mode that creates fictional:

- customers
- reservations
- tables and rooms
- reports
- revenue examples

Demo mode should include a `Reset Demo Data` button that clears fictional data and recreates a fresh sample restaurant day.

`Reset Demo Data` should be protected by the normal shared staff password/session. No extra typed confirmation such as `RESET` is required for V1.

## Localization And Formatting

The application UI should be English.

Formatting should use South Korea conventions:

- Timezone: `Asia/Seoul`
- 24-hour time
- Dates like `2026-07-07`
- Currency like `KRW` / `₩45,000`

SMS messages remain English.

## Open Questions To Continue

- Which staff actions should be quick buttons on a table or reservation.
- How much of the existing Google Calendar code should be deleted versus left unused during migration.
- Exact MSSQL schema design.
- Exact Flutter component layout for floor map, list panel, reservation forms, reports, and settings.
