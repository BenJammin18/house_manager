from typing import Optional

from pydantic import BaseModel, ConfigDict


class SocialMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    attendees: Optional[list[str]] = None
    location: Optional[str] = None
    event_type: Optional[str] = None
