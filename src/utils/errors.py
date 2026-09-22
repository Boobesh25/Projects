"""Centralized error classification and user-friendly status translator.

Converts raw technical exceptions (Google GenAI, LangChain, PostgreSQL, Qdrant, HTTPX)
into natural, lively, human-readable explanations with zero technical jargon.
"""

import re
from typing import TypedDict


class FriendlyError(TypedDict):
    category: str
    friendly_title: str
    friendly_message: str
    action_hint: str
    retry_suggested: bool


def classify_gemini_error(exc: Exception) -> FriendlyError:
    """Classify an exception and return structured non-technical explanations."""
    err_str = str(exc)

    # 1. Rate Limit / Quota Exhaustion (429 / RESOURCE_EXHAUSTED)
    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
        return {
            "category": "rate_limit",
            "friendly_title": "⏳ Quick Breather Needed",
            "friendly_message": (
                "You've reached the free-tier speed limit for Google AI queries. "
                "The system is cooling down briefly before accepting new queries."
            ),
            "action_hint": (
                "💡 **What to do**: Please wait about 30 seconds before asking your next question. "
                "If you have a Google Cloud or Google AI Studio billing project, adding your API key in the sidebar unlocks unlimited speed!"
            ),
            "retry_suggested": True,
        }

    # 2. Service High Demand / Unavailable (503 / 500 / UNAVAILABLE)
    if "503" in err_str or "UNAVAILABLE" in err_str or "high demand" in err_str.lower() or "overloaded" in err_str.lower():
        return {
            "category": "high_demand",
            "friendly_title": "⚡ High Demand on Google AI",
            "friendly_message": (
                "Google's AI service is experiencing temporary peak traffic worldwide right now. "
                "We attempted to reconnect automatically."
            ),
            "action_hint": (
                "💡 **What to do**: Spikes in traffic usually clear in a few seconds. "
                "Please give it a quick moment and tap ask again."
            ),
            "retry_suggested": True,
        }

    # 3. Invalid or Expired API Key (400 / 401 / 403 / API_KEY_INVALID)
    if "API_KEY_INVALID" in err_str or "401" in err_str or ("403" in err_str and "key" in err_str.lower()) or "api key is missing" in err_str.lower():
        return {
            "category": "auth_error",
            "friendly_title": "🔑 API Key Needs Attention",
            "friendly_message": (
                "We couldn't connect with the provided Google Gemini API key. "
                "The key might be expired, mistyped, or disabled."
            ),
            "action_hint": (
                "💡 **What to do**: Check the **🔑 Gemini API Key** section in the sidebar. "
                "You can generate a fresh free key in seconds at [Google AI Studio](https://aistudio.google.com/apikey)."
            ),
            "retry_suggested": False,
        }

    # 4. Model Version Deprecation / Not Found (404 / NOT_FOUND)
    if "404" in err_str or "NOT_FOUND" in err_str or "no longer available" in err_str.lower():
        return {
            "category": "model_error",
            "friendly_title": "🔄 Model Endpoint Upgrading",
            "friendly_message": (
                "The requested AI model version is currently transitioning to the latest release."
            ),
            "action_hint": "💡 **What to do**: The system automatically adapts to active endpoints. Please try again in a moment.",
            "retry_suggested": True,
        }

    # 5. Network Timeout / Connection Drop
    if "timeout" in err_str.lower() or "connect" in err_str.lower() or "connection error" in err_str.lower():
        return {
            "category": "network_error",
            "friendly_title": "🌐 Network Connection Timeout",
            "friendly_message": (
                "The request to Google's AI servers timed out before completing."
            ),
            "action_hint": "💡 **What to do**: Please verify your internet connection and try sending your question again.",
            "retry_suggested": True,
        }

    # 6. Storage Quota Exceeded
    if "storage limit exceeded" in err_str.lower() or "quota exceeded" in err_str.lower():
        return {
            "category": "storage_quota",
            "friendly_title": "📁 Storage Limit Reached",
            "friendly_message": err_str,
            "action_hint": "💡 **What to do**: Delete older unused documents from the sidebar to free up storage space.",
            "retry_suggested": False,
        }

    # Default fallback (graceful and clear)
    return {
        "category": "general_error",
        "friendly_title": "⚠️ Temporary Hiccup",
        "friendly_message": (
            "We encountered an unexpected pause while processing your request."
        ),
        "action_hint": "💡 **What to do**: Please try sending your query again. If it continues, check your API key in the sidebar.",
        "retry_suggested": True,
    }


def format_friendly_error_markdown(exc: Exception) -> str:
    """Format an exception into a stylish, non-technical Markdown alert card."""
    info = classify_gemini_error(exc)
    return (
        f"### {info['friendly_title']}\n\n"
        f"{info['friendly_message']}\n\n"
        f"{info['action_hint']}"
    )


def get_retry_status_message(attempt: int, max_attempts: int, exc: Exception | None = None) -> str:
    """Generate lively, reassuring progress status strings during retry backoff."""
    if exc:
        err_str = str(exc)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            return f"⏳ *Free-tier rate limit cooling down — resuming momentarily (step {attempt}/{max_attempts})...*"
        if "503" in err_str or "UNAVAILABLE" in err_str:
            return f"✨ *Google AI is experiencing high demand — reconnecting for you (step {attempt}/{max_attempts})...*"
    return f"🔄 *Reconnecting with AI services (attempt {attempt}/{max_attempts})...*"
