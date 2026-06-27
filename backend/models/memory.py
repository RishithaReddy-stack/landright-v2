from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.core.database import Base


class UserMemory(Base):
    """
    Durable facts about a user that persist across conversations.
    Examples:
        key="has_ssn"          value="false"
        key="has_drivers_license" value="true"
        key="on_cpt"           value="false"
        key="received_job_offer" value="true"
        key="preferred_city"   value="Fayetteville"
    """
    __tablename__ = "user_memory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key = Column(String, nullable=False)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="memory")
