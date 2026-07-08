import pytest
from fastapi import HTTPException

from app.core.security import verify_vapi_authorization


def test_verify_vapi_authorization_accepts_matching_bearer_token() -> None:
    verify_vapi_authorization("Bearer test-secret", expected_secret="test-secret")


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        "test-secret",
        "Bearer wrong-secret",
        "Basic test-secret",
    ],
)
def test_verify_vapi_authorization_rejects_missing_or_invalid_token(
    authorization: str | None,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        verify_vapi_authorization(authorization, expected_secret="test-secret")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid Vapi tool authorization"


def test_verify_vapi_authorization_rejects_unconfigured_secret() -> None:
    with pytest.raises(HTTPException) as exc_info:
        verify_vapi_authorization("Bearer test-secret", expected_secret="")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Vapi tool secret is not configured"
