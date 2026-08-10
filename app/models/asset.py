from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.utils.time import utc_naive_now


class Asset(SQLModel, table=True):
    __tablename__ = "asset"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str  # e.g. "Upstairs AC unit", "Dishwasher"
    category: Optional[str] = None  # freeform, e.g. "Appliance", "HVAC System"
    location: Optional[str] = None  # e.g. "Kitchen", "Attic"
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendor.id")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_naive_now)
