"""
Entry point for Hugging Face Spaces (Gradio SDK) and Cloud deployments.
Mounts FastAPI backend to provide 100% Free Hosting with 16GB RAM on Hugging Face Spaces.
"""

import os
import uvicorn
from src.api.app import app as fastapi_app

try:
    import gradio as gr

    with gr.Blocks(title="GenAI RAG Backend API") as demo:
        gr.Markdown(
            """
            # ⚡ GenAI RAG Chatbot Backend API is Live!
            
            - **Swagger API Documentation**: [`/docs`](/docs)
            - **Health Endpoint**: [`/health`](/health)
            - **Frontend**: Connect your Streamlit app by setting `API_BASE_URL` to this Space's URL.
            """
        )

    # Mount Gradio landing page onto FastAPI at /ui so root API endpoints stay clean
    app = gr.mount_gradio_app(fastapi_app, demo, path="/ui")
except ImportError:
    app = fastapi_app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
