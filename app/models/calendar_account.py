from datetime import datetime
from typing import Any, Optional

from app.utils.time import utc_naive_now

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class CalendarAccount(SQLModel, table=True):
    __tablename__ = "calendar_account"

    id: Optional[int] = Field(default=None, primary_key=True)
    member_id: int = Field(foreign_key="household_member.id")
    google_account_email: str
    calendar_ids_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    oauth_refresh_token_encrypted: str
    active: bool = True
    created_at: datetime = Field(default_factory=utc_naive_now)
