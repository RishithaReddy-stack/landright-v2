# Import all models here so Alembic can discover them
from backend.models.user import User, Profile
from backend.models.conversation import Conversation, Message
from backend.models.memory import UserMemory
from backend.models.task import Task
from backend.models.trace import LLMTrace
from backend.models.notification import Notification

__all__ = [
    "User", "Profile",
    "Conversation", "Message",
    "UserMemory",
    "Task",
    "LLMTrace",
    "Notification",
]
