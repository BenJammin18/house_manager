from typing import Optional

from pydantic import BaseModel, ConfigDict


class ChoreMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    location: Optional[str] = None
    estimated_minutes: Optional[int] = None
    supplies_needed: Optional[list[str]] = None
