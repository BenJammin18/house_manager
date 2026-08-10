from datetime import datetime
from enum import Enum
from typing import Any, Optional

from app.utils.time import utc_naive_now

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Domain(str, Enum):
    chore = "chore"
    maintenance = "maintenance"
    pet = "pet"
    baby = "baby"
    bill = "bill"
    finance = "finance"
    social = "social"
    prescription = "prescription"


class Status(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    skipped = "skipped"
    cancelled = "cancelled"


class Priority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class CreatedBy(str, Enum):
    user = "user"
    agent = "agent"


class Item(SQLModel, table=True):
    __tablename__ = "item"

    id: Optional[int] = Field(default=None, primary_key=True)
    domain: Domain
    item_type: str
    title: str
    description: Optional[str] = None
    status: Status = Status.pending
    priority: Priority = Priority.normal
    assignee_id: Optional[int] = Field(default=None, foreign_key="household_member.id")
    created_by: CreatedBy = CreatedBy.user

    due_at: Optional[datetime] = None
    due_date_only: bool = False
    recurrence_rule: Optional[str] = None
    next_occurrence_at: Optional[datetime] = None

    completed_at: Optional[datetime] = None
    completed_by_id: Optional[int] = Field(default=None, foreign_key="household_member.id")

    last_nudged_at: Optional[datetime] = None
    nudge_count: int = 0
    escalation_level: int = 0

    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=utc_naive_now)
    updated_at: datetime = Field(default_factory=utc_naive_now)
