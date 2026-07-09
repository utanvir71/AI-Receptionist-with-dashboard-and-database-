# ABCD Steakhouse Dashboard Frontend

Flutter Web staff dashboard for the AI receptionist reservation system.

## Commands

```bash
flutter pub get
flutter test
flutter analyze
flutter build web --release
```

Run against a local backend:

```bash
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000
```

When served through the project Docker Compose stack, nginx serves the built Flutter app and proxies `/api`, `/vapi`, `/health`, and `/api/staff/ws` to the FastAPI backend.
