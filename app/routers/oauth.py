from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.integrations.crypto import encrypt_token
from app.integrations.google_oauth import build_auth_url, exchange_code
from app.models.calendar_account import CalendarAccount
from app.models.email_account import EmailAccount
from app.models.household_member import HouseholdMember

router = APIRouter(prefix="/oauth/google")


@router.get("/login")
def google_login(member_id: int = Query(...), session: Session = Depends(get_session)):
    member = session.get(HouseholdMember, member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Household member not found")
    auth_url = build_auth_url(state=str(member_id))
    return RedirectResponse(auth_url)


@router.get("/callback")
def google_callback(code: str, state: str, session: Session = Depends(get_session)):
    member_id = int(state)
    creds, email = exchange_code(code)
    if not creds.refresh_token:
        raise HTTPException(
            status_code=400,
            detail=(
                "Google did not return a refresh token. Revoke house_manager's access at "
                "myaccount.google.com/permissions and try linking again."
            ),
        )
    encrypted_token = encrypt_token(creds.refresh_token)

    calendar_account = session.exec(
        select(CalendarAccount).where(
            CalendarAccount.member_id == member_id,
            CalendarAccount.google_account_email == email,
        )
    ).first()
    if calendar_account:
        calendar_account.oauth_refresh_token_encrypted = encrypted_token
        calendar_account.active = True
        session.add(calendar_account)
    else:
        session.add(
            CalendarAccount(
                member_id=member_id,
                google_account_email=email,
                calendar_ids_json=["primary"],
                oauth_refresh_token_encrypted=encrypted_token,
            )
        )

    # Same OAuth grant covers Gmail too (see app/integrations/google_oauth.py
    # SCOPES) — link both from one consent flow rather than asking twice.
    email_account = session.exec(
        select(EmailAccount).where(
            EmailAccount.member_id == member_id, EmailAccount.gmail_address == email
        )
    ).first()
    if email_account:
        email_account.oauth_refresh_token_encrypted = encrypted_token
        email_account.active = True
        session.add(email_account)
    else:
        session.add(
            EmailAccount(
                member_id=member_id,
                gmail_address=email,
                oauth_refresh_token_encrypted=encrypted_token,
            )
        )

    session.commit()

    return RedirectResponse("/")
