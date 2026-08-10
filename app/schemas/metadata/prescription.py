from typing import Optional

from pydantic import BaseModel, ConfigDict


class PrescriptionMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    medication_name: Optional[str] = None
    pharmacy: Optional[str] = None
    refills_left: Optional[int] = None
    prescribing_provider: Optional[str] = None
