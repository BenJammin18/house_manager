from datetime import datetime
from typing import Optional

from app.utils.time import utc_naive_now

from sqlmodel import Field, SQLModel


class HouseholdMember(SQLModel, table=True):
    __tablename__ = "household_member"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone_e164: Optional[str] = None
    email: Optional[str] = None
    color: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_naive_now)
