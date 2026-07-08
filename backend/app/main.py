"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api.staff.router import router as staff_router
from app.api.v1.router import api_router


app = FastAPI(title="ABCD Steakhouse AI Receptionist API", version="0.1.0")
app.include_router(api_router, prefix="/vapi")
app.include_router(staff_router, prefix="/api/staff", tags=["staff"])


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Return a simple health signal for local and deployment checks."""
    return {"status": "ok"}
