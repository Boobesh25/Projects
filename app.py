import os
import time
import asyncio
import structlog
import gradio as gr
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import router
from src.database import init_db

logger = structlog.get_logger(__name__)

# Satisfy Hugging Face ZeroGPU runtime check if running on ZeroGPU hardware
try:
    import spaces
    @spaces.GPU
    def _gpu_worker():
        return True
    _gpu_worker()
    logger.info("zero_gpu_runtime_initialized")
except Exception as e:
    logger.debug("zero_gpu_not_active", error=str(e))

# Create Gradio landing page
with gr.Blocks(title="GenAI RAG Backend API") as demo:
    gr.Markdown(
        """
        # ⚡ GenAI RAG Chatbot Backend API is Live!
        
        * 📖 **Interactive Swagger Docs**: [/docs](/docs)
        * 🩺 **Health Check Endpoint**: [/health](/health)
        * 🎨 **Frontend**: Connect Streamlit by setting `API_BASE_URL` to this Space URL.
        """
    )

# Include all FastAPI routes directly into Gradio's underlying ASGI app
demo.app.include_router(router)
demo.app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    logger.info("launching_gradio_server", port=port)

    # Initialize database tables on startup
    try:
        logger.info("initializing database tables")
        asyncio.run(init_db())
        logger.info("database ready")
    except Exception as e:
        logger.error("database_init_failed", error=str(e))

    # Launch Gradio server
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        show_error=True,
        ssr_mode=False,
    )

    # Unconditional keep-alive loop so the container process never terminates
    while True:
        time.sleep(3600)



