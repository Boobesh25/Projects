"""
Authentication Service
======================
Handles:
- Google OAuth ID token verification (matching Rag_Reranker pattern)
- JWT session creation & verification
- Dev / Sandbox user creation
"""

import os
import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-career-analyser-jwt-key-2026")
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "72"))
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

security = HTTPBearer(auto_error=False)

def create_access_token(user_id: str, email: str, display_name: str) -> str:
    """Creates signed JWT token for session."""
    payload = {
        "sub": user_id,
        "email": email,
        "name": display_name,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_access_token(token: str) -> Dict[str, Any]:
    """Decodes and validates JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authorization token.")

async def verify_google_id_token(id_token: str) -> Dict[str, Any]:
    """
    Verifies Google ID Token via Google's public certs.
    Returns: {"google_id": ..., "email": ..., "name": ..., "picture": ...}
    """
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests

    try:
        idinfo = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID or None
        )
        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise HTTPException(status_code=401, detail="Invalid token issuer.")

        return {
            "google_id": idinfo["sub"],
            "email": idinfo.get("email", ""),
            "name": idinfo.get("name", idinfo.get("email", "").split("@")[0]),
            "picture": idinfo.get("picture", "")
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Google token verification failed: {str(e)}")

async def get_current_user_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """FastAPI route dependency extracting authenticated user."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization bearer token.")
    return verify_access_token(credentials.credentials)

