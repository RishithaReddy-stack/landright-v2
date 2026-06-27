from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="student", nullable=False)  # student | admin
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("Profile", back_populates="user", uselist=False)
    conversations = relationship("Conversation", back_populates="user")
    memory = relationship("UserMemory", back_populates="user")
    tasks = relationship("Task", back_populates="user")
    traces = relationship("LLMTrace", back_populates="user")
    notifications = relationship("Notification", back_populates="user")


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    university = Column(String, nullable=True)
    visa_type = Column(String, nullable=True)       # F1, J1
    major = Column(String, nullable=True)
    program_end_date = Column(DateTime, nullable=True)  # source of truth for deadline calc
    current_stage = Column(String, default="pre_arrival")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profile")
