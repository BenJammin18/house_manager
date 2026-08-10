from typing import Optional

from pydantic import BaseModel, ConfigDict


class PetMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    pet_name: Optional[str] = None
    vet_name: Optional[str] = None
    location: Optional[str] = None
    reminder_lead_minutes: Optional[int] = None
