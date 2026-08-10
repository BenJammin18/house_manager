from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.utils.time import utc_naive_now


class Vendor(SQLModel, table=True):
    __tablename__ = "vendor"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    service_type: Optional[str] = None  # freeform, e.g. "HVAC", "Lawn Care", "Pest Control"
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_naive_now)
