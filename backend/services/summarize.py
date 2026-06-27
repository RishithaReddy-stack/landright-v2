"""
Conversation Summarization
--------------------------
When a conversation exceeds MESSAGE_THRESHOLD, condense older messages
into a summary stored on the Conversation record.

The agent then receives: [summary as SystemMessage] + [last RECENT_KEEP messages]
instead of the full history — preventing context overflow on long conversations.

In dev mode (no AWS), summarization is skipped gracefully.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.conversation import Conversation, Message
from backend.core.config import settings

MESSAGE_THRESHOLD = 20   # summarize when conversation exceeds this many messages
RECENT_KEEP = 6          # always keep the last N messages verbatim


async def maybe_summarize(db: AsyncSession, conversation_id: int) -> None:
    """
    Check if conversation is long enough to summarize.
    If so, summarize older messages and store on Conversation.summary.
    No-op in dev mode (AWS not configured).
    """
    if not settings.aws_access_key_id or not settings.aws_secret_access_key:
        return  # skip in dev

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()

    if len(messages) < MESSAGE_THRESHOLD:
        return  # not long enough yet

    # Messages to summarize = all except the last RECENT_KEEP
    to_summarize = messages[:-RECENT_KEEP]

    # Format for the LLM
    history_text = "\n".join(
        f"{m.role.upper()}: {m.content}" for m in to_summarize
    )

    prompt = (
        "Summarize the following conversation between an AI advisor and an international student. "
        "Focus on: decisions made, facts the student shared, tasks completed, and open questions. "
        "Be concise — 3-5 sentences max.\n\n"
        f"{history_text}"
    )

    try:
        import boto3
        from langchain_aws import ChatBedrock

        client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        llm = ChatBedrock(
            client=client,
            model_id=settings.bedrock_model_id,
            model_kwargs={"temperature": 0.0, "max_tokens": 256},
        )
        from langchain.schema import HumanMessage
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        summary_text = response.content
    except Exception:
        return  # summarization is best-effort; never break the chat

    # Persist summary on the Conversation row
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = conv_result.scalar_one_or_none()
    if conversation:
        conversation.summary = summary_text
        await db.commit()


def build_history_with_summary(
    messages: list,
    summary: str | None,
) -> list[dict]:
    """
    Build the history list passed to the agent:
    - If a summary exists, prepend it and only include the last RECENT_KEEP messages
    - Otherwise return all messages as-is
    """
    if not summary:
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    recent = messages[-RECENT_KEEP:] if len(messages) > RECENT_KEEP else messages
    history = [
        {
            "role": "system",
            "content": f"[Summary of earlier conversation]\n{summary}",
        }
    ]
    history += [{"role": m["role"], "content": m["content"]} for m in recent]
    return history
