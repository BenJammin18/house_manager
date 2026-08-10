from datetime import datetime
from enum import Enum
from typing import Any, Optional

from app.utils.time import utc_naive_now

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class ActionType(str, Enum):
    calendar_create = "calendar_create"
    bill_pay = "bill_pay"
    order_supply = "order_supply"
    book_appointment = "book_appointment"
    send_message = "send_message"


class ActionStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    denied = "denied"
    expired = "expired"
    executed = "executed"
    failed = "failed"


class ActionRequest(SQLModel, table=True):
    __tablename__ = "action_request"

    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: Optional[int] = Field(default=None, foreign_key="item.id")
    member_id: Optional[int] = Field(default=None, foreign_key="household_member.id")
    action_type: ActionType
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    channel: str = "sms"
    status: ActionStatus = ActionStatus.pending

    requested_at: datetime = Field(default_factory=utc_naive_now)
    responded_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
