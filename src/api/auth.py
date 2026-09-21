"""JWT-based authentication + Google OAuth verification."""

import jwt
import httpx
import structlog
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Depends, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.config.settings import settings

logger = structlog.get_logger(__name__)
security = HTTPBearer(auto_error=False)


def create_token(user_id: str, email: str = "") -> str:
    """Create a JWT token for an authenticated user."""
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_token(token: str) -> str:
    """Verify a JWT token and return the user_id. Raises on invalid."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no user_id")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Please login again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")


async def verify_google_token(id_token: str) -> dict:
    """
    Verify a Google ID token by decoding it and verifying with Google's certs.
    Returns: {"google_id": ..., "email": ..., "name": ..., "picture": ..., "email_verified": bool}
    """
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests

    try:
        # Verify the token with Google's public certificates
        idinfo = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            settings.google_client_id,
        )

        # Check issuer
        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise HTTPException(status_code=401, detail="Invalid token issuer.")

        return {
            "google_id": idinfo["sub"],
            "email": idinfo.get("email", ""),
            "name": idinfo.get("name", idinfo.get("email", "").split("@")[0]),
            "picture": idinfo.get("picture", ""),
            "email_verified": idinfo.get("email_verified", False),
        }

    except ValueError as e:
        logger.warning("google_token_verification_failed", error=str(e))
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {e}")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """FastAPI dependency: extract and verify user from Bearer token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization header.")
    return verify_token(credentials.credentials)


def verify_ws_token(token: str) -> str:
    """Verify token for WebSocket connections (passed as query param)."""
    try:
        return verify_token(token)
    except HTTPException:
        return ""
