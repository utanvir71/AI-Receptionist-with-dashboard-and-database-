"""Top-level API router for Vapi endpoints."""

from fastapi import APIRouter

from app.api.v1 import call_logs, vapi_tools


api_router = APIRouter()
api_router.include_router(vapi_tools.router, prefix="/reservations", tags=["vapi-tools"])
api_router.include_router(call_logs.router, prefix="/call-logs", tags=["vapi-call-logs"])
