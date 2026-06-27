"""
Admin / Eval Dashboard API
--------------------------
All endpoints require admin role.

GET  /api/admin/metrics          — aggregate stats
GET  /api/admin/traces           — paginated trace log
POST /api/admin/traces/{id}/feedback  — thumbs up/down from chat UI
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case

from backend.core.database import get_db
from backend.core.deps import get_current_user, get_admin_user
from backend.models.user import User
from backend.models.trace import LLMTrace
from backend.models.conversation import Conversation

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Metrics ───────────────────────────────────────────────────────────────────

@router.get("/metrics")
async def get_metrics(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate stats for the eval dashboard."""

    # Total traces + success rate
    totals = await db.execute(
        select(
            func.count(LLMTrace.id).label("total"),
            func.sum(case((LLMTrace.success == True, 1), else_=0)).label("succeeded"),
            func.avg(LLMTrace.latency_ms).label("avg_latency_ms"),
        )
    )
    row = totals.one()

    # Feedback counts
    feedback = await db.execute(
        select(
            func.sum(case((LLMTrace.feedback == 1,  1), else_=0)).label("thumbs_up"),
            func.sum(case((LLMTrace.feedback == -1, 1), else_=0)).label("thumbs_down"),
        )
    )
    fb = feedback.one()

    # Total users + conversations
    user_count  = (await db.execute(select(func.count(User.id)))).scalar()
    conv_count  = (await db.execute(select(func.count(Conversation.id)))).scalar()

    total    = row.total or 0
    succeeded = int(row.succeeded or 0)

    return {
        "total_traces":      total,
        "success_rate":      round(succeeded / total * 100, 1) if total else 0,
        "avg_latency_ms":    round(float(row.avg_latency_ms or 0), 0),
        "thumbs_up":         int(fb.thumbs_up or 0),
        "thumbs_down":       int(fb.thumbs_down or 0),
        "total_users":       user_count,
        "total_conversations": conv_count,
    }


# ── Traces ────────────────────────────────────────────────────────────────────

@router.get("/traces")
async def get_traces(
    limit:  int = 50,
    offset: int = 0,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Paginated trace log, newest first."""
    result = await db.execute(
        select(LLMTrace)
        .order_by(LLMTrace.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    traces = result.scalars().all()
    return [
        {
            "id":              t.id,
            "user_id":         t.user_id,
            "conversation_id": t.conversation_id,
            "tool_name":       t.tool_name,
            "input":           (t.input or "")[:200],   # truncate for list view
            "output":          (t.output or "")[:200],
            "latency_ms":      t.latency_ms,
            "success":         t.success,
            "error":           t.error,
            "feedback":        t.feedback,
            "created_at":      t.created_at,
        }
        for t in traces
    ]


# ── Feedback (called from chat UI, any logged-in user) ────────────────────────

class FeedbackRequest(BaseModel):
    value: int   # 1 or -1


@router.post("/traces/{trace_id}/feedback")
async def submit_feedback(
    trace_id: int,
    body: FeedbackRequest,
    current_user: User = Depends(get_current_user),   # any user, not admin-only
    db: AsyncSession = Depends(get_db),
):
    if body.value not in (1, -1):
        raise HTTPException(400, "feedback value must be 1 (up) or -1 (down)")

    result = await db.execute(
        select(LLMTrace).where(
            LLMTrace.id == trace_id,
            LLMTrace.user_id == current_user.id,   # can only rate own traces
        )
    )
    trace = result.scalar_one_or_none()
    if not trace:
        raise HTTPException(404, "Trace not found")

    trace.feedback = body.value
    await db.commit()
    return {"message": "Feedback recorded"}
