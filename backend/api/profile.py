from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.user import User, Profile
from backend.services.tasks import seed_tasks_for_stage

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileUpdate(BaseModel):
    university: Optional[str] = None
    visa_type: Optional[str] = None
    major: Optional[str] = None
    program_end_date: Optional[datetime] = None
    current_stage: Optional[str] = None


VALID_STAGES = {"pre_arrival", "day_0", "week_1", "month_1", "ongoing"}
VALID_VISA   = {"F1", "J1"}


@router.get("")
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {
        "university": profile.university,
        "visa_type": profile.visa_type,
        "major": profile.major,
        "program_end_date": profile.program_end_date,
        "current_stage": profile.current_stage,
        "updated_at": profile.updated_at,
    }


@router.put("")
async def update_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.visa_type and body.visa_type not in VALID_VISA:
        raise HTTPException(400, f"visa_type must be one of {VALID_VISA}")
    if body.current_stage and body.current_stage not in VALID_STAGES:
        raise HTTPException(400, f"current_stage must be one of {VALID_STAGES}")

    result = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Profile not found")

    previous_stage = profile.current_stage

    for field, value in body.model_dump(exclude_none=True).items():
        # Strip timezone — DB column is TIMESTAMP WITHOUT TIME ZONE
        if isinstance(value, datetime) and value.tzinfo is not None:
            value = value.replace(tzinfo=None)
        setattr(profile, field, value)

    await db.commit()

    # Seed tasks when stage is set or changed
    new_stage = body.current_stage or previous_stage
    if new_stage:
        await seed_tasks_for_stage(db, current_user.id, new_stage)

    return {"message": "Profile updated", "stage": new_stage}
