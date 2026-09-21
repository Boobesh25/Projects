"""Entry point for the FastAPI backend server."""

# Load .env into os.environ BEFORE any imports (needed for LangSmith)
from dotenv import load_dotenv
load_dotenv()

# Configure structured logging with file handler
from src.config.logging import setup_logging
setup_logging()

import uvicorn
from src.config.settings import settings, configure_langsmith

# Ensure LangSmith tracing is explicitly configured
configure_langsmith(settings)

if __name__ == "__main__":
    uvicorn.run(
        "src.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )

