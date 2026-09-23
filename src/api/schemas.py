"""Pydantic schemas for API request/response models."""

from pydantic import BaseModel, Field


class ConnectRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)


class GoogleAuthRequest(BaseModel):
    """Google OAuth login request — frontend sends the Google ID token."""
    id_token: str = Field(..., min_length=1)


class GoogleAuthResponse(BaseModel):
    """Response after successful Google login."""
    user_id: str
    email: str
    display_name: str
    avatar_url: str = ""
    existing_user: bool
    token: str
    history: list[dict] = []
    message: str
    has_api_key: bool = False
    masked_key: str = ""
    is_super_admin: bool = False


class ApiKeyUpdateRequest(BaseModel):
    """Request to save/update user's Google Gemini API key."""
    api_key: str = Field(..., min_length=1, max_length=256)


class ApiKeyStatusResponse(BaseModel):
    """Safe response for user API key status (never exposes raw key)."""
    user_id: str
    has_api_key: bool
    masked_key: str = ""
    message: str = ""


class StorageUsageResponse(BaseModel):
    """User storage usage and quota status."""
    user_id: str
    used_bytes: int
    used_mb: float
    quota_mb: int
    is_unlimited: bool
    is_super_admin: bool = False


class ConnectResponse(BaseModel):
    user_id: str
    existing_user: bool
    history: list[dict]
    message: str
    token: str = ""


class HealthResponse(BaseModel):
    status: str
    active_connections: int
    model: str


class FileUploadResponse(BaseModel):
    filename: str
    chunks_stored: int
    message: str
    is_shared: bool = False


class DocumentListResponse(BaseModel):
    user_id: str
    documents: list[str] = []
    shared_documents: list[str] = []
    storage_used_bytes: int = 0
    storage_used_mb: float = 0.0
    storage_quota_mb: int = 0
    is_super_admin: bool = False


class DocumentDeleteResponse(BaseModel):
    filename: str
    deleted: bool
    message: str


class ChatRequest(BaseModel):
    """Synchronous chat request."""
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    session_id: str | None = None
    include_shared: bool = True
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = ""



class ChatResponse(BaseModel):
    """Synchronous chat response."""
    answer: str
    session_id: str
    session_title: str | None = None
    trace: str = ""


class WSIncoming(BaseModel):
    """WebSocket message from client."""
    type: str  # "message" | "logout"
    content: str = ""


class WSOutgoing(BaseModel):
    """WebSocket message to client."""
    type: str  # "status" | "response" | "agent_update" | "error"
    content: str
    agent_name: str | None = None
