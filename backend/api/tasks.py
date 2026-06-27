from fastapi import APIRouter, Depends
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.user import User
from backend.models.task import Task

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
async def get_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Task)
        .where(Task.user_id == current_user.id)
        .order_by(Task.stage, Task.id)
    )
    tasks = result.scalars().all()
    return [
        {
            "id": t.id,
            "stage": t.stage,
            "title": t.title,
            "is_complete": t.is_complete,
            "completed_at": t.completed_at,
        }
        for t in tasks
    ]


@router.put("/{task_id}/complete")
async def complete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        from fastapi import HTTPException
        raise HTTPException(404, "Task not found")
    task.is_complete = True
    task.completed_at = datetime.utcnow()
    await db.commit()
    return {"message": f"✓ {task.title}"}
