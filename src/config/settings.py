"""Application settings loaded from environment variables."""

import os
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Central configuration for the application."""

    # Google Gemini
    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.5-flash-lite", env="GEMINI_MODEL")
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/",
        env="GEMINI_BASE_URL",
    )

    # PostgreSQL
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/genai_chat",
        env="DATABASE_URL",
    )

    # Server
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")

    # Auth
    jwt_secret: str = Field(default="change-me-in-production-use-a-random-string", env="JWT_SECRET")
    jwt_expiry_hours: int = Field(default=24, env="JWT_EXPIRY_HOURS")

    # Google OAuth & URLs
    google_client_id: str = Field(default="", env="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", env="GOOGLE_CLIENT_SECRET")
    frontend_url: str = Field(default="https://projects-bu8jtjbtyqe7otklpukvoq.streamlit.app", env="FRONTEND_URL")
    api_browser_url: str = Field(default="", env="API_BROWSER_URL")

    # Agent settings
    max_context_messages: int = Field(default=25, env="MAX_CONTEXT_MESSAGES")
    daily_message_limit: int = Field(default=50, env="DAILY_MESSAGE_LIMIT")

    # Qdrant
    qdrant_host: str = Field(default="localhost", env="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, env="QDRANT_PORT")
    qdrant_url: str = Field(default="", env="QDRANT_URL")
    qdrant_api_key: str = Field(default="", env="QDRANT_API_KEY")

    # Redis (cache)
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")

    # Embedding
    embedding_model: str = Field(default="models/gemini-embedding-001", env="EMBEDDING_MODEL")

    # LangSmith / Tracing (Optional)
    langchain_tracing_v2: bool = Field(default=False, env="LANGCHAIN_TRACING_V2")
    langchain_api_key: str = Field(default="", env="LANGCHAIN_API_KEY")
    langchain_project: str = Field(default="genai_project", env="LANGCHAIN_PROJECT")
    langsmith_endpoint: str = Field(default="https://api.smith.langchain.com", env="LANGSMITH_ENDPOINT")

    # Super Admin & Multi-User Storage Quotas
    admin_emails: str = Field(default="boobesh2509@gmail.com", env="ADMIN_EMAILS")
    user_storage_quota_mb: int = Field(default=0, env="USER_STORAGE_QUOTA_MB")  # 0 = Unlimited (local default)
    shared_user_id: str = "__shared__"

    @field_validator("langchain_tracing_v2", mode="before")
    @classmethod
    def parse_tracing_flag(cls, v):
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "t", "yes", "on")
        return bool(v)

    def is_super_admin(self, email: str | None) -> bool:
        """Check if an email belongs to a designated Super Admin."""
        if not email:
            return False
        configured_admins = [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]
        return email.strip().lower() in configured_admins

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"



def configure_langsmith(s: Settings) -> None:
    """
    Ensure LangSmith tracing is safely configured:
    - If langchain_api_key is empty or langchain_tracing_v2 is False,
      explicitly disable tracing (LANGCHAIN_TRACING_V2=false) to prevent
      LangChain from attempting connections or emitting missing-key warnings.
    - If a valid key and tracing are enabled, propagate to os.environ.
    """
    if s.langchain_tracing_v2 and s.langchain_api_key.strip():
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = s.langchain_api_key.strip()
        os.environ["LANGCHAIN_PROJECT"] = s.langchain_project
        os.environ["LANGSMITH_ENDPOINT"] = s.langsmith_endpoint
    else:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        if "LANGCHAIN_API_KEY" in os.environ and not os.environ["LANGCHAIN_API_KEY"].strip():
            os.environ.pop("LANGCHAIN_API_KEY", None)
        if "LANGSMITH_API_KEY" in os.environ and not os.environ["LANGSMITH_API_KEY"].strip():
            os.environ.pop("LANGSMITH_API_KEY", None)


settings = Settings()
configure_langsmith(settings)

