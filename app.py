import os
import multiprocessing
import uvicorn
import structlog
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
        * 🎨 **Frontend**: Connect Streamlit by setting `API_BASE_URL` to this Space URL.
        """
    )

# Mount Gradio landing UI at /ui onto the FastAPI app
app = gr.mount_gradio_app(fastapi_app, ui_demo, path="/ui")

if __name__ == "__main__":
    # Prevent ZeroGPU spawned subprocesses from duplicate port bindings
    if multiprocessing.current_process().name == "MainProcess":
        # Port 7860 is the standard HF space application port (7861 is used internally by HF proxy)
        port = 7860
        logger.info("starting_fastapi_server", port=port)
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")






