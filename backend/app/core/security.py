"""Vapi tool authentication helpers."""

from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings


def verify_vapi_authorization(authorization: str | None, *, expected_secret: str) -> None:
    """Validate a Vapi custom-tool bearer token."""
    if not expected_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vapi tool secret is not configured",
        )

    scheme, _, token = (authorization or "").partition(" ")
    if scheme != "Bearer" or not token or not compare_digest(token, expected_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid Vapi tool authorization",
        )


def require_vapi_authorization(
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    """FastAPI dependency for Vapi custom-tool endpoints."""
    verify_vapi_authorization(authorization, expected_secret=settings.vapi_tool_secret)
