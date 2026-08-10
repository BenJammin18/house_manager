import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import Response
from sqlmodel import Session
from twilio.twiml.messaging_response import MessagingResponse

from app.actions.proposal import find_pending_action_request_for_phone, resolve_response
from app.db import get_session
from app.integrations.twilio_client import validate_webhook_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks")

APPROVE_WORDS = {"yes", "y", "confirm", "ok", "okay", "approve"}
DENY_WORDS = {"no", "n", "deny", "cancel", "skip", "stop"}


def _reply(message: str) -> Response:
    twiml = MessagingResponse()
    twiml.message(message)
    return Response(content=str(twiml), media_type="application/xml")


@router.post("/sms")
async def sms_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    session: Session = Depends(get_session),
) -> Response:
    form = await request.form()
    signature = request.headers.get("X-Twilio-Signature", "")
    if not validate_webhook_signature(str(request.url), dict(form), signature):
        logger.warning("Rejected unverified Twilio webhook request from %s", From)
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    action_request = find_pending_action_request_for_phone(session, From)
    if action_request is None:
        return _reply("No pending confirmation found for this number.")

    word = Body.strip().lower()
    if word in APPROVE_WORDS:
        resolve_response(session, action_request, approved=True)
        session.commit()
        return _reply("Got it — confirmed.")
    if word in DENY_WORDS:
        resolve_response(session, action_request, approved=False)
        session.commit()
        return _reply("OK — skipped.")

    return _reply("Reply YES to confirm or NO to skip.")
