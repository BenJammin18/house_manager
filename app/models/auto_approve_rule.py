from datetime import datetime
from typing import Any, Optional

from app.utils.time import utc_naive_now

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.item import Domain


class AutoApproveRule(SQLModel, table=True):
    __tablename__ = "auto_approve_rule"

    id: Optional[int] = Field(default=None, primary_key=True)
    domain: Domain
    item_type: str
    condition_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    active: bool = True
    created_at: datetime = Field(default_factory=utc_naive_now)
