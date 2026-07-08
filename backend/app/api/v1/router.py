"""Top-level API router for Vapi tool endpoints."""

from fastapi import APIRouter

from app.api.v1 import vapi_tools


api_router = APIRouter()
api_router.include_router(vapi_tools.router, prefix="/reservations", tags=["vapi-tools"])
