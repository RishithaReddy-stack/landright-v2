"""
LandRight Agent Router
----------------------
Groq answers questions directly from its own knowledge by default.
Tools are only invoked when the question requires user-specific data
(profile, deadlines, tasks) or a DB write (mark done, remember this).

Routing logic:
  1. Classify intent — does this need personal data or a DB write?
  2. No  → direct Groq answer (fast, no tool overhead)
  3. Yes → ReAct agent with the relevant tools

Tool inventory:
  search_docs       — Qdrant knowledge base (immigration docs)
  get_user_profile  — user's university, visa, graduation date
  calculate_deadlines — OPT/STEM/tax dates derived from profile
  get_pending_tasks — user's checklist from DB
  mark_task_done    — write task completion to DB
  get_user_memory   — stored facts about this user
  update_user_memory — store new facts about this user
"""
import logging
import re
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.llm import get_llm, get_tool_llm
from backend.mcp.tools import get_tools

logger = logging.getLogger(__name__)

# ── System prompts ────────────────────────────────────────────────────────────

# Used when Groq answers directly from its own knowledge
DIRECT_SYSTEM_PROMPT = """You are LandRight — a friendly AI advisor for international students in the US.
Answer the student's question from your own knowledge. Be warm, concise, and practical.
Never give legal advice — for visa decisions say "check with your DSO."."""

# Used when the agent needs to call tools
AGENT_SYSTEM_PROMPT = """You are LandRight — a friendly AI advisor for international students in the US.
You have tools to fetch this student's profile, calculate their deadlines, manage their checklist,
and remember facts they share with you.

CRITICAL: The student has already filled in their profile (graduation date, university, visa type, major).
NEVER ask the student for information that might be in their profile. Always call get_user_profile first
and use whatever is there. Only ask the student if the profile field is empty.

Tool usage:
- OPT / STEM / tax / visa deadline questions → call get_user_profile then calculate_deadlines
- Questions about their checklist or pending steps → call get_pending_tasks
- ANY question about uploaded documents, files, or specific documents the student mentions
  (IELTS, I-20, offer letter, lease, DSO letter, etc.) → call search_docs immediately.
  NEVER say "I don't have that document" — always search first.
- General process questions (how does OPT work, what is CPT) → answer from your own knowledge, no tool needed
- Student shares a fact ("I got my SSN", "I'm working at Google") → call update_user_memory

Be warm and concise. Never give legal advice — for visa decisions say "check with your DSO."."""

MAX_ITERATIONS = 5

# ── Intent classifier ─────────────────────────────────────────────────────────

_MY_PATTERN = re.compile(r"\bmy\b", re.IGNORECASE)

_ACTION_PATTERNS = re.compile(
    r"\b(mark (it|this|that|as) done|i (finished|completed|did|have done)|"
    r"remember (that|this)|don'?t forget|note that|save that|"
    r"i uploaded|did i upload|i have uploaded|"
    r"am i eligible|can i apply|do i qualify|"
    r"what (tasks|steps) (do i|have i|are left)|what('s| is) (next|left|pending)|"
    r"have i|did i already)\b",
    re.IGNORECASE,
)

def _needs_tools(message: str) -> bool:
    """
    Route to the agent (with tools) when:
    - Message contains "my" — almost always means personal data or uploaded docs
    - Message is an action (mark done, remember this, I uploaded, am I eligible)
    Groq answers everything else from its own knowledge.
    """
    return bool(_MY_PATTERN.search(message) or _ACTION_PATTERNS.search(message))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _groq_configured() -> bool:
    return bool(settings.groq_api_key)


def _build_messages(system_prompt: str, question: str, history: list[dict] | None) -> list:
    messages = [SystemMessage(content=system_prompt)]
    if history:
        for msg in history[-8:]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=question))
    return messages


async def _direct_answer(question: str, history: list[dict] | None) -> str:
    """Groq answers directly — no tools, no agent overhead."""
    llm = get_llm()
    messages = _build_messages(DIRECT_SYSTEM_PROMPT, question, history)
    response = await llm.ainvoke(messages)
    return response.content


async def _grounded_answer(
    question: str,
    history: list[dict] | None,
    db: AsyncSession,
    user_id: int,
) -> str:
    """
    Fallback when the ReAct agent fails on tool calling.
    Manually runs the most relevant tools and injects their output as
    context into a direct Groq call — so the user still gets a useful answer.
    """
    from backend.db.qdrant import search, format_results
    import asyncio, json

    context_parts = []

    # Always try a doc search for the question
    try:
        results = await asyncio.to_thread(search, question, user_id, 4)
        if results:
            context_parts.append(f"Relevant content from user's uploaded documents:\n{format_results(results)}")
    except Exception as ex:
        logger.warning(f"Grounded fallback: doc search failed: {ex}")

    # Also pull the user profile for personalised answers
    try:
        from backend.mcp.tools import get_tools
        tools = get_tools(db, user_id)
        tool_map = {t.name: t for t in tools}
        profile_raw = await tool_map["get_user_profile"].ainvoke({})
        context_parts.append(f"Student profile:\n{profile_raw}")
    except Exception as ex:
        logger.warning(f"Grounded fallback: profile fetch failed: {ex}")

    llm = get_llm()
    context_block = "\n\n".join(context_parts)
    grounded_prompt = (
        "You are LandRight, a friendly AI advisor for international students in the US.\n"
        "Use the context below to answer the student's question accurately. "
        "If the answer is in their uploaded documents, quote from them. "
        "Be warm and concise. Never give legal advice.\n\n"
        f"Context:\n{context_block}" if context_block else
        "You are LandRight, a friendly AI advisor for international students in the US. "
        "Answer the student's question warmly and concisely."
    )
    messages = _build_messages(grounded_prompt, question, history)
    response = await llm.ainvoke(messages)
    return response.content


async def _agent_answer(
    question: str,
    history: list[dict] | None,
    db: AsyncSession,
    user_id: int,
) -> str:
    """ReAct agent with tools — uses the tool-use fine-tuned model to avoid malformed calls."""
    llm = get_tool_llm()   # fine-tuned for function calling — avoids <function=...> format errors
    tools = get_tools(db, user_id)
    agent = create_react_agent(llm, tools)
    messages = _build_messages(AGENT_SYSTEM_PROMPT, question, history)

    try:
        result = await agent.ainvoke(
            {"messages": messages},
            config={"recursion_limit": MAX_ITERATIONS * 2},
        )
        final = result["messages"][-1]
        return final.content

    except Exception as e:
        error_str = str(e).lower()
        if any(k in error_str for k in ["tool_use_failed", "bad_request", "badrequest", "400", "recursion"]):
            logger.warning(f"Agent tool-call failed, falling back to grounded answer: {e}")
            return await _grounded_answer(question, history, db, user_id)
        raise


async def _mock_ask(question: str, db: AsyncSession, user_id: int) -> str:
    """Dev-mode fallback when Groq is not configured."""
    tools = get_tools(db, user_id)
    tool_map = {t.name: t for t in tools}
    profile_raw = await tool_map["get_user_profile"].ainvoke({})
    deadlines_raw = await tool_map["calculate_deadlines"].ainvoke({})
    tasks_raw = await tool_map["get_pending_tasks"].ainvoke({})
    return (
        f"[DEV MODE — Groq not configured]\n\n"
        f"**Profile:**\n{profile_raw}\n\n"
        f"**Deadlines:**\n{deadlines_raw}\n\n"
        f"**Pending tasks:**\n{tasks_raw}\n\n"
        f"Your question was: *{question}*\n\n"
        f"Set GROQ_API_KEY in your .env to get real AI responses."
    )


# ── Main entry point ──────────────────────────────────────────────────────────

async def ask(
    question: str,
    db: AsyncSession,
    user_id: int,
    history: list[dict] | None = None,
) -> str:
    """
    Route the question and return a response.

    - Personal data / DB write needed → ReAct agent with tools
    - Everything else → direct Groq answer (faster, no tool overhead)
    """
    if not _groq_configured():
        return await _mock_ask(question, db, user_id)

    if _needs_tools(question):
        logger.info(f"[router] tool route — '{question[:60]}'")
        return await _agent_answer(question, history, db, user_id)

    logger.info(f"[router] direct route — '{question[:60]}'")
    return await _direct_answer(question, history)
