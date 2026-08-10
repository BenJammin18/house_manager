from typing import Optional

from pydantic import BaseModel, ConfigDict


class BabyMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    child_name: Optional[str] = None
    category: Optional[str] = None  # feeding|diaper|appointment|milestone
    provider: Optional[str] = None
