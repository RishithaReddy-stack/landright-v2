from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id:           Mapped[int]      = mapped_column(Integer, primary_key=True, index=True)
    user_id:      Mapped[int]      = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title:        Mapped[str]      = mapped_column(String(200), nullable=False)
    body:         Mapped[str]      = mapped_column(Text, nullable=False)
    kind:         Mapped[str]      = mapped_column(String(50), nullable=False)   # "urgent" | "warning" | "info"
    is_read:      Mapped[bool]     = mapped_column(Boolean, default=False, nullable=False)
    email_sent:   Mapped[bool]     = mapped_column(Boolean, default=False, nullable=False)
    created_at:   Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="notifications")
