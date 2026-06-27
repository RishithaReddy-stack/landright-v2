import time
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.user import User
from backend.models.conversation import Conversation, Message
from backend.models.trace import LLMTrace
from backend.agents.graph import ask
from backend.services.summarize import maybe_summarize, build_history_with_summary

router = APIRouter(prefix="/chat", tags=["chat"])
limiter = Limiter(key_func=get_remote_address)


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None  # None = start new conversation


class ChatResponse(BaseModel):
    answer: str
    conversation_id: int
    trace_id: Optional[int] = None


@router.post("", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # ── Resolve conversation ──────────────────────────────────────
    if body.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == body.conversation_id,
                Conversation.user_id == current_user.id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(404, "Conversation not found")
    else:
        conversation = Conversation(user_id=current_user.id)
        db.add(conversation)
        await db.flush()

    # ── Load history (with summarization if conversation is long) ─────
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
    )
    raw_history = [
        {"role": m.role, "content": m.content}
        for m in history_result.scalars().all()
    ]
    history = build_history_with_summary(raw_history, conversation.summary)

    # ── Save user message ─────────────────────────────────────────
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=body.message,
    )
    db.add(user_msg)
    await db.flush()

    # ── Run agent ─────────────────────────────────────────────────
    start = time.time()
    try:
        answer = await ask(
            question=body.message,
            db=db,
            user_id=current_user.id,
            history=history,
        )
        success = True
        error = None
    except Exception as e:
        import traceback; traceback.print_exc()
        answer = "I ran into a hiccup on my end — could you try sending that again? If it keeps happening, try rephrasing your question."
        success = False
        error = str(e)

    latency_ms = int((time.time() - start) * 1000)

    # ── Save assistant message ────────────────────────────────────
    ai_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
    )
    db.add(ai_msg)

    # ── Log trace ─────────────────────────────────────────────────
    trace = LLMTrace(
        user_id=current_user.id,
        conversation_id=conversation.id,
        tool_name=None,
        input=body.message,
        output=answer,
        latency_ms=latency_ms,
        success=success,
        error=error,
    )
    db.add(trace)
    await db.commit()
    await db.refresh(trace)   # get auto-assigned trace.id

    # ── Summarize if conversation is getting long (best-effort) ───────
    await maybe_summarize(db, conversation.id)

    return ChatResponse(answer=answer, conversation_id=conversation.id, trace_id=trace.id)


@router.get("/conversations")
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all conversations for the current user."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
    )
    convos = result.scalars().all()
    return [{"id": c.id, "created_at": c.created_at, "summary": c.summary} for c in convos]


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Load full message history for a conversation."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Conversation not found")

    msgs = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return [
        {"role": m.role, "content": m.content, "created_at": m.created_at}
        for m in msgs.scalars().all()
    ]
