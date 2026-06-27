"""
Notifications API
-----------------
GET  /api/notifications          — fetch unread (or all) notifications
PUT  /api/notifications/{id}/read — mark one as read
PUT  /api/notifications/read-all  — mark all as read
POST /api/notifications/trigger   — manually run nightly check (dev/admin only)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db
from backend.core.deps import get_current_user, get_admin_user
from backend.models.user import User
from backend.models.notification import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def get_notifications(
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch notifications for the current user, newest first."""
    query = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    if unread_only:
        query = query.where(Notification.is_read == False)

    result = await db.execute(query)
    notifications = result.scalars().all()

    return [
        {
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "kind": n.kind,
            "is_read": n.is_read,
            "created_at": n.created_at,
        }
        for n in notifications
    ]


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(404, "Notification not found")

    notif.is_read = True
    await db.commit()
    return {"message": "Marked as read"}


@router.put("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )
    notifications = result.scalars().all()
    for n in notifications:
        n.is_read = True
    await db.commit()
    return {"message": f"Marked {len(notifications)} notifications as read"}


@router.post("/trigger")
async def trigger_check(
    current_user: User = Depends(get_admin_user),   # admin only
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger the nightly deadline check.
    Admin only — useful for testing without waiting for the scheduler.
    """
    from datetime import datetime, timedelta
    from backend.models.user import Profile
    from backend.services.notifications import check_user_deadlines, THRESHOLDS

    result = await db.execute(
        select(User, Profile)
        .join(Profile, Profile.user_id == User.id)
        .where(Profile.program_end_date.isnot(None))
    )
    rows = result.all()

    # Debug: show what each threshold computes for each user
    now = datetime.utcnow()
    debug = []
    for user, profile in rows:
        user_debug = {
            "user_id": user.id,
            "program_end_date": profile.program_end_date.isoformat() if profile.program_end_date else None,
            "thresholds": []
        }
        for t in THRESHOLDS:
            deadline = t["deadline_fn"](profile)
            days_remaining = (deadline - now).days if deadline else None
            user_debug["thresholds"].append({
                "key": t["key"],
                "deadline": deadline.isoformat() if deadline else None,
                "days_remaining": days_remaining,
                "days_before": t["days_before"],
                "would_trigger": days_remaining is not None and 0 <= days_remaining <= t["days_before"],
            })
        debug.append(user_debug)

    total = 0
    for user, profile in rows:
        total += await check_user_deadlines(db, user, profile)

    return {
        "message": f"Check complete — {total} notifications created for {len(rows)} users.",
        "debug": debug,
    }
