import os
import structlog
import gradio as gr
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import router
from src.database import init_db

logger = structlog.get_logger(__name__)

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

@demo.app.on_event("startup")
async def startup_event():
    logger.info("initializing database")
    try:
        await init_db()
        logger.info("database ready")
    except Exception as e:
        logger.error("database_init_failed", error=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    logger.info("launching_gradio_server", port=port)
    try:
        demo.launch(
            server_name="0.0.0.0",
            server_port=port,
            show_error=True,
            ssr_mode=False,
        )
    except TypeError:
        try:
            demo.launch(
                server_name="0.0.0.0",
                server_port=port,
                show_error=True,
                ssr=False,
            )
        except TypeError:
            demo.launch(
                server_name="0.0.0.0",
                server_port=port,
                show_error=True,
            )


