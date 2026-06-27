from langchain_groq import ChatGroq
from backend.core.config import settings

# Current recommended models as of June 2026 (per Groq deprecation page)
# openai/gpt-oss-120b replaces llama-3.3-70b-versatile
# qwen/qwen3.6-27b is the alternative

_CHAT_MODEL = "openai/gpt-oss-120b"
_TOOL_MODEL = "openai/gpt-oss-120b"   # same model — gpt-oss-120b handles tool calling well


def get_llm():
    """Direct (no-tool) answers — conversational responses."""
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=_CHAT_MODEL,
        temperature=0.3,
        max_tokens=1024,
    )


def get_tool_llm():
    """Agent with tools — use same model, it handles function calling reliably."""
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=_TOOL_MODEL,
        temperature=0,
        max_tokens=1024,
    )
