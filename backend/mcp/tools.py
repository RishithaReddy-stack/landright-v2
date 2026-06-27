"""
MCP Tool Registry
-----------------
Tools are created via get_tools(db, user_id) so each agent invocation
gets tools with the correct DB session and user context baked in.

Adding a new tool tomorrow:
1. Define the function here with @tool
2. Add it to the returned list in get_tools()
The agent picks it up automatically — no other changes needed.
"""
import json
from datetime import datetime
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.qdrant import search, format_results
from backend.models.user import Profile
from backend.models.task import Task
from backend.models.memory import UserMemory
from backend.services.deadline import calculate_all


def get_tools(db: AsyncSession, user_id: int) -> list:
    """
    Factory: returns a list of LangChain tools bound to this request's
    DB session and user_id. Call once per chat request.
    """

    @tool
    async def search_docs(query: str) -> str:
        """
        Search documents the student has uploaded (I-20, offer letters, DSO instructions,
        university guides, lease agreements, etc.) for relevant information.
        Use this when the student asks about something that might be in their uploaded files.
        """
        results = search(query, user_id=user_id, limit=4)
        return format_results(results)

    @tool
    async def get_user_profile() -> str:
        """
        Get the current student's profile: university, visa type, major,
        program end date, and current stage. Use this before answering any
        question that depends on the student's specific situation.
        """
        result = await db.execute(
            select(Profile).where(Profile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return "Profile not set up yet."
        return json.dumps({
            "university": profile.university,
            "visa_type": profile.visa_type,
            "major": profile.major,
            "program_end_date": profile.program_end_date.isoformat() if profile.program_end_date else None,
            "current_stage": profile.current_stage,
        })

    @tool
    async def calculate_deadlines() -> str:
        """
        Calculate all important deadlines for this student: OPT application
        window, STEM extension eligibility, tax deadline, SSN eligibility.
        Derives everything from the student's program end date and major —
        never uses stored values.
        """
        result = await db.execute(
            select(Profile).where(Profile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        if not profile or not profile.program_end_date:
            return "Program end date not set. Ask the student to update their profile first."
        deadlines = calculate_all(
            program_end_date=profile.program_end_date,
            visa_type=profile.visa_type,
            major=profile.major,
        )
        return json.dumps(deadlines, indent=2)

    @tool
    async def get_pending_tasks() -> str:
        """
        Get the student's incomplete tasks for their current stage.
        Use this when the student asks what they still need to do.
        """
        result = await db.execute(
            select(Profile).where(Profile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        stage = profile.current_stage if profile else "pre_arrival"

        tasks_result = await db.execute(
            select(Task).where(
                Task.user_id == user_id,
                Task.stage == stage,
                Task.is_complete == False,
            )
        )
        tasks = tasks_result.scalars().all()
        if not tasks:
            return f"No pending tasks for stage: {stage}. You're all caught up!"
        return json.dumps([{"id": t.id, "title": t.title} for t in tasks])

    @tool
    async def mark_task_done(task_id: int) -> str:
        """
        Mark a specific task as complete. Use this when the student confirms
        they've completed a task from their checklist.
        task_id: the ID of the task to mark complete (get IDs from get_pending_tasks).
        """
        result = await db.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return f"Task {task_id} not found."
        task.is_complete = True
        task.completed_at = datetime.utcnow()
        await db.commit()
        return f"✓ Marked as done: {task.title}"

    @tool
    async def get_user_memory() -> str:
        """
        Retrieve durable facts remembered about this student across conversations:
        whether they have an SSN, a driver's license, are on CPT, have a job offer, etc.
        Check this before asking the student something they may have already told you.
        """
        result = await db.execute(
            select(UserMemory).where(UserMemory.user_id == user_id)
        )
        memories = result.scalars().all()
        if not memories:
            return "No facts remembered yet."
        return json.dumps({m.key: m.value for m in memories})

    @tool
    async def update_user_memory(key: str, value: str) -> str:
        """
        Store or update a durable fact about this student.
        Use this when the student tells you something important that should be
        remembered across conversations.

        Examples:
          key="has_ssn", value="true"
          key="job_offer_company", value="Google"
          key="preferred_contact", value="email"
          key="on_cpt", value="true"
          key="bank", value="Chase"
        """
        result = await db.execute(
            select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.key == key,
            )
        )
        memory = result.scalar_one_or_none()
        if memory:
            memory.value = value
            memory.updated_at = datetime.utcnow()
        else:
            db.add(UserMemory(user_id=user_id, key=key, value=value))
        await db.commit()
        return f"Remembered: {key} = {value}"

    return [
        search_docs,
        get_user_profile,
        calculate_deadlines,
        get_pending_tasks,
        mark_task_done,
        get_user_memory,
        update_user_memory,
    ]
