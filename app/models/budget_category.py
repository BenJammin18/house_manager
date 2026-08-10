from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel

from app.utils.time import utc_naive_now


class BudgetCreatedBy(str, Enum):
    user = "user"
    agent = "agent"


class BudgetCategory(SQLModel, table=True):
    __tablename__ = "budget_category"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    monthly_amount_cents: int
    created_by: BudgetCreatedBy = BudgetCreatedBy.user
    active: bool = True
    created_at: datetime = Field(default_factory=utc_naive_now)
