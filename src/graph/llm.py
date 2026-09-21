"""LLM client using Google's native Gemini SDK via LangChain."""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage
from src.config.settings import settings
from src.graph.usage_tracker import UsageTrackingCallback


def get_llm(
    temperature: float = 0.2,
    user_id: str = "",
    node_name: str = "unknown",
    api_key: str = "",
) -> ChatGoogleGenerativeAI:
    """Get the Gemini LLM client with usage tracking callback using the provided API key."""
    effective_key = (api_key or settings.gemini_api_key).strip()
    if not effective_key:
        raise ValueError("Google Gemini API key is missing. Please configure your API key.")

    callbacks = []
    if user_id:
        callbacks.append(UsageTrackingCallback(user_id=user_id, node_name=node_name))

    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=effective_key,
        temperature=temperature,
        max_output_tokens=8192,
        callbacks=callbacks,
    )


def extract_text_content(response: BaseMessage) -> str:
    """Safely extract text from LLM response (handles list, dict, or string content)."""
    content = response.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                if part.get("type") == "text" and "text" in part:
                    parts.append(part["text"])
        return " ".join(parts).strip()
    return str(content).strip()


def get_usage_from_response(response: BaseMessage) -> dict:
    """Extract token usage from an AIMessage response's usage_metadata."""
    usage = getattr(response, "usage_metadata", None)
    if usage:
        if isinstance(usage, dict):
            return {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            }
        # LangChain may wrap it as an object with attributes
        if hasattr(usage, "input_tokens"):
            return {
                "input_tokens": getattr(usage, "input_tokens", 0),
                "output_tokens": getattr(usage, "output_tokens", 0),
            }
    return {"input_tokens": 0, "output_tokens": 0}
