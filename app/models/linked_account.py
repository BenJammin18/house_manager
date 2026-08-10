from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.utils.time import utc_naive_now


class LinkedAccount(SQLModel, table=True):
    __tablename__ = "linked_account"

    id: Optional[int] = Field(default=None, primary_key=True)
    member_id: Optional[int] = Field(default=None, foreign_key="household_member.id")
    plaid_item_id: str
    plaid_access_token_encrypted: str
    plaid_account_id: str
    sync_cursor: Optional[str] = None
    institution_name: Optional[str] = None
    account_name: Optional[str] = None
    account_type: Optional[str] = None
    account_mask: Optional[str] = None
    active: bool = True
    created_at: datetime = Field(default_factory=utc_naive_now)
