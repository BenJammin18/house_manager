from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint

from app.utils.time import utc_naive_now


class EmailClassification(str, Enum):
    spam = "spam"
    important = "important"
    normal = "normal"
    calendar_candidate = "calendar_candidate"


class EmailActionTaken(str, Enum):
    trashed = "trashed"
    flagged = "flagged"
    calendar_event_created = "calendar_event_created"
    none = "none"


class EmailTriageLog(SQLModel, table=True):
    __tablename__ = "email_triage_log"
    __table_args__ = (UniqueConstraint("email_account_id", "gmail_message_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    email_account_id: int = Field(foreign_key="email_account.id")
    gmail_message_id: str
    classification: EmailClassification
    action_taken: EmailActionTaken
    created_at: datetime = Field(default_factory=utc_naive_now)
