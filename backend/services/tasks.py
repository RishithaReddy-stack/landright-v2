"""
Task seeding — populates default tasks when a user sets their current stage.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.task import Task

STAGE_TASKS: dict[str, list[str]] = {
    "pre_arrival": [
        "Get an eSIM before you land",
        "Secure housing (on-campus or verified off-campus)",
        "Review your lease for red flags before signing",
        "Set up utilities in your name",
        "Download your I-94 from cbp.dhs.gov",
    ],
    "day_0": [
        "Report to the international student office",
        "Get your SEVIS record activated",
        "Collect your student ID",
        "Get your DSO's contact info",
        "Understand your on-campus work restrictions",
    ],
    "week_1": [
        "Open a bank account (no SSN required)",
        "Get a state ID at the DMV",
        "Confirm health insurance coverage in student portal",
        "Set up renters insurance if applicable",
        "Get a local SIM / long-term phone plan",
    ],
    "month_1": [
        "Apply for a secured credit card",
        "Opt out of overdraft protection on your bank account",
        "Set up autopay on your credit card",
        "Understand your credit utilization limit (keep under 30%)",
    ],
    "ongoing": [
        "Check SSN eligibility (need work authorization first)",
        "File Form 8843 by April 15 (required every year even with no income)",
        "Research OPT/CPT timeline with your DSO",
        "Apply for OPT 90 days before graduation",
    ],
}


async def seed_tasks_for_stage(db: AsyncSession, user_id: int, stage: str) -> None:
    """
    Inserts default tasks for a stage if not already seeded.
    Safe to call multiple times — checks for existing tasks first.
    """
    titles = STAGE_TASKS.get(stage, [])
    if not titles:
        return

    existing = await db.execute(
        select(Task).where(Task.user_id == user_id, Task.stage == stage)
    )
    if existing.scalars().first():
        return  # already seeded

    for title in titles:
        db.add(Task(user_id=user_id, stage=stage, title=title))
    await db.commit()
