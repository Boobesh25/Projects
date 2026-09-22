import os
import uvicorn
import structlog
import gradio as gr
from src.api.app import app as fastapi_app

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
with gr.Blocks(title="GenAI RAG Backend API") as ui_demo:
    gr.Markdown(
        """
        # ⚡ GenAI RAG Chatbot Backend API is Live!
        
        * 📖 **Interactive Swagger Docs**: [/docs](/docs)
        * 🩺 **Health Check Endpoint**: [/health](/health)
        * 🎨 **Frontend**: Connect Streamlit by setting `API_BASE_URL` to this Space URL.
        """
    )

# Mount Gradio landing page onto FastAPI at /ui
app = gr.mount_gradio_app(fastapi_app, ui_demo, path="/ui")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    logger.info("starting_fastapi_server", port=port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")




