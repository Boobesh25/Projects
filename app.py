import os
import structlog
import uvicorn
import gradio as gr
from src.api.app import app as fastapi_app

logger = structlog.get_logger(__name__)

# Create Gradio landing page
with gr.Blocks(title="GenAI RAG Backend API") as ui_demo:
    gr.Markdown(
        """
        # ⚡ GenAI RAG Chatbot Backend API is Live!
        
        * 📖 **Interactive Swagger Docs**: [/docs](/docs)
        * 🩺 **Health Check Endpoint**: [/health](/health)
        * 🎨 **Connect Streamlit UI**: Point `API_BASE_URL` to this Space URL.
        """
    )

# Mount Gradio onto FastAPI so all FastAPI routes (/health, /docs, /chat, /upload) work at root
app = gr.mount_gradio_app(fastapi_app, ui_demo, path="/ui")
demo = app  # Hugging Face imports 'demo' or 'app'

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    logger.info("starting_server", port=port)
    uvicorn.run(app, host="0.0.0.0", port=port)

