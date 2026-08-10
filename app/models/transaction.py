from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.utils.time import utc_naive_now


class Transaction(SQLModel, table=True):
    __tablename__ = "transaction"

    id: Optional[int] = Field(default=None, primary_key=True)
    linked_account_id: int = Field(foreign_key="linked_account.id")
    plaid_transaction_id: str = Field(unique=True, index=True)
    amount_cents: int
    merchant_name: Optional[str] = None
    category: Optional[str] = None
    posted_at: date
    pending: bool = False
    created_at: datetime = Field(default_factory=utc_naive_now)
