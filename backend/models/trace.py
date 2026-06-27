from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, SmallInteger
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.core.database import Base


class LLMTrace(Base):
    """
    Logs every agent tool call and LLM invocation.
    Used for monitoring, debugging, and the eval dashboard.
    """
    __tablename__ = "llm_traces"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    tool_name = Column(String, nullable=True)       # None = direct LLM call
    input = Column(Text, nullable=True)
    output = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)
    error = Column(Text, nullable=True)
    feedback = Column(SmallInteger, nullable=True)   # 1=thumbs up, -1=thumbs down, None=no feedback
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="traces")
    conversation = relationship("Conversation", back_populates="traces")
