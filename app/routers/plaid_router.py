import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.db import get_session
from app.integrations.crypto import encrypt_token
from app.integrations.plaid_client import create_link_token, exchange_public_token
from app.models.household_member import HouseholdMember
from app.models.linked_account import LinkedAccount

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plaid")
templates = Jinja2Templates(directory="app/templates")


@router.get("/link", response_class=HTMLResponse)
def plaid_link_page(
    request: Request, member_id: int = Query(...), session: Session = Depends(get_session)
) -> HTMLResponse:
    member = session.get(HouseholdMember, member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Household member not found")
    link_token = create_link_token(member_id)
    return templates.TemplateResponse(
        request,
        "plaid_link.html",
        {"link_token": link_token, "member_id": member_id, "member_name": member.name},
    )


@router.post("/exchange")
def plaid_exchange(
    member_id: int = Body(...),
    public_token: str = Body(...),
    institution_name: str = Body(""),
    accounts: list[dict] = Body(default_factory=list),
    session: Session = Depends(get_session),
) -> dict:
    access_token, item_id = exchange_public_token(public_token)
    encrypted_token = encrypt_token(access_token)

    for account in accounts:
        session.add(
            LinkedAccount(
                member_id=member_id,
                plaid_item_id=item_id,
                plaid_access_token_encrypted=encrypted_token,
                plaid_account_id=account.get("id", ""),
                institution_name=institution_name or None,
                account_name=account.get("name"),
                account_type=account.get("subtype") or account.get("type"),
                account_mask=account.get("mask"),
            )
        )
    session.commit()
    return {"status": "linked", "accounts": len(accounts)}
