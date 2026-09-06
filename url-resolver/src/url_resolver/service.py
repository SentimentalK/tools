"""
FastAPI HTTP microservice for the Content Resolver capability.
Provides /healthz, /readyz, and /v1/resolve with fail-closed token authentication.
"""

import os
import secrets
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from .models import (
    InvalidUrlError,
    ResolutionOutcome,
    ResolveUrlInputV1,
    ResolverInternalError,
    ResolverValidationError,
    UnsupportedProtocolError,
)
from .resolver import resolve_url

app = FastAPI(
    title="Content Resolver Service",
    description="Lightweight URL metadata resolution service for Tools monorepo.",
    version="0.2.0",
)


def get_configured_token() -> Optional[str]:
    """Retrieve internal token from environment."""
    token = os.environ.get("TOOLS_INTERNAL_TOKEN", "").strip()
    return token if token else None


def verify_auth_token(authorization: Optional[str] = Header(None)) -> None:
    """Verifies Bearer token against TOOLS_INTERNAL_TOKEN."""
    configured = get_configured_token()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "auth_not_configured", "message": "Server authentication token is not configured."},
        )

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Missing Authorization header."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid Authorization scheme, expected 'Bearer <token>'."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    if not secrets.compare_digest(token, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid authentication token."},
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/healthz", summary="Liveness probe")
def healthz():
    """Returns 200 if the service process is alive."""
    return {"status": "ok"}


@app.get("/readyz", summary="Readiness probe")
def readyz(response: Response):
    """
    Returns 200 if the service is configured and ready to accept traffic.
    Fails closed (503) if TOOLS_INTERNAL_TOKEN is missing or invalid.
    """
    token = get_configured_token()
    if not token:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "error": "TOOLS_INTERNAL_TOKEN is not configured"}
    return {"status": "ready"}


@app.post(
    "/v1/resolve",
    response_model=ResolutionOutcome,
    summary="Resolve URL metadata",
)
def resolve_endpoint(
    req: ResolveUrlInputV1,
    authorization: Optional[str] = Header(None),
):
    """
    Resolve public metadata for the provided URL.
    Returns structured ResolutionOutcome (status='resolved' | 'unavailable').
    """
    verify_auth_token(authorization)

    try:
        outcome = resolve_url(req.url)
        return outcome
    except ResolverValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_url", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "internal_error", "message": str(e)},
        )
