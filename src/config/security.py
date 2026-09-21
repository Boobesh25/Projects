"""Security utilities: Fernet AES encryption for API keys at rest and key validation."""

import base64
import hashlib
import structlog
from cryptography.fernet import Fernet
from google import genai
from google.genai.errors import ClientError, APIError

from src.config.settings import settings

logger = structlog.get_logger(__name__)


def _get_fernet() -> Fernet:
    """Derive a consistent 32-byte URL-safe base64 key from JWT_SECRET."""
    secret = settings.jwt_secret or "default-secret-key-change-in-production"
    raw_key = hashlib.sha256(secret.encode("utf-8")).digest()
    b64_key = base64.urlsafe_b64encode(raw_key)
    return Fernet(b64_key)


def encrypt_api_key(api_key: str) -> str:
    """Encrypt a plain text API key into an authenticated Fernet ciphertext string."""
    if not api_key:
        return ""
    f = _get_fernet()
    return f.encrypt(api_key.strip().encode("utf-8")).decode("utf-8")


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt a Fernet ciphertext string back into the original plain text API key."""
    if not encrypted_key:
        return ""
    f = _get_fernet()
    try:
        return f.decrypt(encrypted_key.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error("api_key_decryption_failed", error=str(e))
        return ""


def mask_api_key(api_key: str) -> str:
    """Return a masked representation of an API key (e.g. AIza...3xYz)."""
    if not api_key:
        return ""
    clean = api_key.strip()
    if len(clean) <= 8:
        return "****"
    return f"{clean[:4]}...{clean[-4:]}"


def validate_gemini_api_key(api_key: str) -> tuple[bool, str]:
    """
    Validate a Google Gemini API key by making a lightweight probe call.
    Returns (is_valid: bool, error_message: str).
    """
    if not api_key or not api_key.strip():
        return False, "API key cannot be empty."

    key = api_key.strip()
    try:
        client = genai.Client(api_key=key)
        # Probe using embedding or model info (minimal token usage)
        client.models.embed_content(
            model=settings.embedding_model,
            contents=["healthcheck"],
            config={"output_dimensionality": 128},
        )
        return True, ""
    except (ClientError, APIError) as e:
        logger.warning("gemini_key_validation_failed", error=str(e))
        msg = str(e)
        if "API_KEY_INVALID" in msg or "400" in msg or "403" in msg:
            return False, "Invalid Google Gemini API key. Please check the key in Google AI Studio."
        return False, f"Google API error: {msg}"
    except Exception as e:
        logger.error("gemini_key_validation_error", error=str(e))
        return False, f"Could not validate key: {str(e)}"
