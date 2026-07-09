# ABCD Steakhouse AI Receptionist Dashboard

This repository contains the FastAPI/Vapi backend, MSSQL database layer, and Flutter Web staff dashboard for the ABCD Steakhouse AI receptionist demo.

## Local Development

Backend tests and lint:

```bash
cd backend
.venv/bin/pytest -q
.venv/bin/ruff check .
```

Frontend tests, analyzer, and web build:

```bash
cd frontend
flutter test
flutter analyze
flutter build web --release
```

Run the Flutter dashboard against an already running backend:

```bash
cd frontend
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000
```

For the Docker/nginx path, use the Compose stack below and open the frontend service instead.

## Docker Compose Demo

Create a local environment file:

```bash
cp .env.example .env
```

Edit `.env` before a real deployment. The checked-in example uses a local demo staff password of `change-me-staff-password`; replace `STAFF_PASSWORD_HASH`, `SESSION_SECRET_KEY`, `MSSQL_SA_PASSWORD`, and `VAPI_TOOL_SECRET`.

Build and start the full stack:

```bash
docker compose up --build
```

Open the dashboard:

```text
http://localhost:8080
```

The frontend nginx container is the public entrypoint:

- `/` serves Flutter Web.
- `/api/staff/...` proxies to FastAPI staff APIs.
- `/api/staff/ws` proxies WebSocket live updates.
- `/vapi/reservations/...` preserves Vapi tool routes.
- `/health` proxies the FastAPI health check.

Apple Silicon local runs use the amd64 SQL Server image through Docker emulation. If the `mssql` container exits with code `139`, increase Docker Desktop memory or run the Compose stack on an amd64 Ubuntu host before judging the demo stack itself.

Run migrations only:

```bash
docker compose run --rm migrate
```

Stop the stack:

```bash
docker compose down
```

Remove demo database and backup volumes:

```bash
docker compose down -v
```

## Ubuntu Server

Install Docker Engine and the Docker Compose plugin, then copy this repository to the server.

```bash
cp .env.example .env
nano .env
docker compose up -d --build
docker compose ps
curl http://localhost:8080/health
```

Keep MSSQL private to the Docker network. The Compose file only publishes nginx on `FRONTEND_PORT`; it does not publish MSSQL directly.

## Ngrok Demo

Set an ngrok authtoken in `.env`:

```env
NGROK_AUTHTOKEN=...
```

Start the public tunnel profile:

```bash
docker compose --profile ngrok up -d --build
docker compose logs -f ngrok
```

Use the ngrok HTTPS URL for staff demo access and Vapi tool URLs. Vapi tool URLs keep the same paths, for example:

```text
https://example.ngrok-free.app/vapi/reservations/check-availability
```

## Demo Limitations

- The Flutter dashboard is English-only and formatted for Korea time/date/currency conventions.
- Staff auth is one shared password, backed by `STAFF_PASSWORD_HASH`.
- SMS is only sent when real Twilio credentials are configured.
- Manual backup metadata is available through the staff API; real backup storage should be copied off-server for production safety.
- Cloudflare/domain setup is intentionally outside this V1 demo stack.
