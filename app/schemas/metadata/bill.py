from typing import Optional

from pydantic import BaseModel, ConfigDict


class BillMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    amount_cents: Optional[int] = None
    payee: Optional[str] = None
    account_last4: Optional[str] = None
    autopay: Optional[bool] = None
    bill_url: Optional[str] = None
