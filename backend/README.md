# ABCD Steakhouse AI Receptionist

FastAPI backend for a production-oriented AI phone receptionist for ABCD
Steakhouse Gangnam. Vapi handles the phone conversation; this service handles
reservation rules, availability, confirmed bookings, Google Calendar sync,
Twilio SMS notifications, and manager follow-up boundaries.

## What This Backend Does

- Validates reservation dates, times, party sizes, and seating preferences.
- Allocates internal restaurant resources without revealing table or room IDs to callers.
- Creates, modifies, searches, and cancels reservations through Vapi tool endpoints.
- Uses Google Calendar as the V1 reservation source of truth.
- Sends customer SMS confirmations, updates, and cancellations through Twilio.
- Keeps cancelled reservations as non-blocking calendar records.
- Returns caller-safe status messages for Vapi conversation handling.

## Architecture

```text
Caller
  -> Vapi assistant
  -> Vapi custom tool HTTP request
  -> ngrok during local development
  -> FastAPI backend
  -> Reservation service
  -> Resource allocator
  -> Google Calendar
  -> Twilio SMS
```

Key backend layers:

- `app/api/v1/`: Vapi-facing HTTP routes.
- `app/schemas/`: strict request and response contracts.
- `app/services/`: reservation orchestration, calendar storage, notifications, resource allocation.
- `app/models/`: restaurant resource definitions and seating rules.
- `app/utils/`: time handling and small shared utilities.
- `tests/`: unit and integration coverage for reservation behavior and Vapi routes.

## Current Status

Implemented:

- Core reservation business rules.
- Vapi bearer-token authorization.
- Vapi custom tool endpoints.
- Vapi wrapped tool-call request and response support.
- In-memory reservation service for tests.
- Google Calendar-backed reservation storage.
- Twilio SMS notification boundary.
- Local ngrok/Vapi smoke-test workflow.

Planned:

- Production hardening, structured logging, request IDs, rate limiting, startup validation, and deployment runbook.
- Future database/CRM preparation after V1 behavior is stable.

See [docs/development-sessions.md](docs/development-sessions.md) for the implementation roadmap.

## Requirements

- Python 3.11+
- ngrok for local Vapi testing
- Google service account with access to the reservation calendar
- Twilio account for live SMS
- Vapi assistant with custom tools configured

## Local Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a local environment file:

```bash
cp .env.example .env
```

Fill `.env` with local credentials. Do not commit `.env`.

Important settings:

```env
VAPI_TOOL_SECRET=
GOOGLE_CALENDAR_ID=
GOOGLE_APPLICATION_CREDENTIALS=
GOOGLE_SERVICE_ACCOUNT_JSON=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
MANAGER_EMAIL=
SMTP_HOST=
SMTP_PORT=
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
```

Use either `GOOGLE_APPLICATION_CREDENTIALS` or `GOOGLE_SERVICE_ACCOUNT_JSON`.
The service account must be shared into the target Google Calendar.

## Run Locally

Start FastAPI:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, expose the backend with ngrok:

```bash
ngrok http 8000
```

Use the ngrok HTTPS URL in Vapi tool server settings. Example:

```text
https://example.ngrok-free.dev/vapi/reservations/check-availability
```

Keep both FastAPI and ngrok running while testing Vapi calls.

## Vapi Tool Endpoints

Configure these Vapi custom tools:

| Tool | Method | Path |
| --- | --- | --- |
| `check_availability` | `POST` | `/vapi/reservations/check-availability` |
| `create_reservation` | `POST` | `/vapi/reservations/create` |
| `search_reservation` | `POST` | `/vapi/reservations/search` |
| `modify_reservation` | `POST` | `/vapi/reservations/modify` |
| `cancel_reservation` | `POST` | `/vapi/reservations/cancel` |
| `manager_followup` | `POST` | `/vapi/reservations/manager-followup` |

Each Vapi backend tool must include these HTTP headers:

```text
Authorization: Bearer <VAPI_TOOL_SECRET>
ngrok-skip-browser-warning: true
```

`ngrok-skip-browser-warning` is only needed for local ngrok testing.

Keep the knowledge-base tool and `end-call` tool attached to the assistant. Remove or avoid the old Make.com `create_restaurant_reservation` tool for the final flow.

## Health Check

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Test A Tool Locally

```bash
curl -X POST http://127.0.0.1:8000/vapi/reservations/check-availability \
  -H "Authorization: Bearer $VAPI_TOOL_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "party_size": 4,
    "reservation_start": "2026-07-01T18:30:00+09:00",
    "seating_preference": "no_preference"
  }'
```

Expected status for an available slot:

```json
{
  "status": "available",
  "message": "That time is available."
}
```

## Tests And Lint

Run the test suite:

```bash
pytest -q
```

Run lint:

```bash
ruff check .
```

If `pytest` or `ruff` are not on your shell path, use the virtualenv binaries:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
```

## Important Business Rules

- Restaurant hours are 11:00 to 21:00.
- Valid reservation starts are 11:00 to 14:30 and 17:00 to 19:30.
- Every reservation blocks 100 minutes.
- Exact-minute reservation starts are allowed inside valid windows.
- Private rooms require a steak order and minimum spend.
- Regular 9-12 guest bookings require private-room handling.
- Parties over 12 require manager escalation.
- Cancelled reservations remain in Google Calendar but no longer block availability.

See [docs/ai-receptionist-v1-plan.md](docs/ai-receptionist-v1-plan.md) for the full business spec.

## Documentation

- [V1 plan](docs/ai-receptionist-v1-plan.md)
- [Development sessions](docs/development-sessions.md)
- [Vapi prompt](docs/vapi-receptionist-prompt.md)
- [Vapi tool migration](docs/vapi-tool-migration.md)
- [Restaurant knowledge base](docs/kb/abcd-steakhouse-kb.md)

## Git And Secret Safety

The repository ignores local secrets, service-account files, virtual environments,
caches, logs, and local scratch files. Never commit:

- `.env`
- files under `secrets/`
- Google service-account JSON
- Twilio credentials
- Vapi secrets

Use test calendars and test phone numbers during development whenever possible.
