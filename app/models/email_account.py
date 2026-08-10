from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.utils.time import utc_naive_now


class EmailAccount(SQLModel, table=True):
    __tablename__ = "email_account"

    id: Optional[int] = Field(default=None, primary_key=True)
    member_id: int = Field(foreign_key="household_member.id")
    gmail_address: str
    oauth_refresh_token_encrypted: str
    active: bool = True
    created_at: datetime = Field(default_factory=utc_naive_now)
