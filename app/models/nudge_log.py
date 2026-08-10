from datetime import datetime
from typing import Optional

from app.utils.time import utc_naive_now

from sqlmodel import Field, SQLModel


class NudgeLog(SQLModel, table=True):
    __tablename__ = "nudge_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="item.id")
    member_id: Optional[int] = Field(default=None, foreign_key="household_member.id")
    channel: str
    escalation_level: int
    message_text: str
    sent_at: datetime = Field(default_factory=utc_naive_now)
    twilio_sid: Optional[str] = None
    status: str = "sent"
