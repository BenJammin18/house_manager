import logging
from datetime import datetime

from sqlmodel import Session, select

from app.agent.email_classify import classify_email
from app.integrations.gmail_client import (
    get_message_summary,
    label_important,
    list_recent_message_ids,
    trash_message,
)
from app.models.email_account import EmailAccount
from app.models.email_triage_log import EmailActionTaken, EmailClassification, EmailTriageLog
from app.models.item import CreatedBy, Domain, Item
from app.utils.time import to_utc_naive

logger = logging.getLogger(__name__)


def _triage_one_message(session: Session, email_account: EmailAccount, message_id: str) -> None:
    summary = get_message_summary(email_account, message_id)
    decision = classify_email(summary["subject"], summary["sender"], summary["snippet"])
    classification = EmailClassification(decision["classification"])
    action_taken = EmailActionTaken.none

    logger.info(
        "Email %s classified as %s: %s", message_id, classification.value, decision.get("reason")
    )

    if classification == EmailClassification.spam:
        trash_message(email_account, message_id)
        action_taken = EmailActionTaken.trashed
    elif classification == EmailClassification.important:
        label_important(email_account, message_id)
        action_taken = EmailActionTaken.flagged
    elif classification == EmailClassification.calendar_candidate:
        event = decision.get("extracted_event") or {}
        due_at_iso = event.get("due_at_iso")
        if due_at_iso:
            session.add(
                Item(
                    domain=Domain.social,
                    item_type="email_event",
                    title=event.get("title") or summary["subject"] or "Event from email",
                    description=event.get("description"),
                    due_at=to_utc_naive(datetime.fromisoformat(due_at_iso)),
                    assignee_id=email_account.member_id,
                    created_by=CreatedBy.agent,
                )
            )
            action_taken = EmailActionTaken.calendar_event_created

    session.add(
        EmailTriageLog(
            email_account_id=email_account.id,
            gmail_message_id=message_id,
            classification=classification,
            action_taken=action_taken,
        )
    )
    session.commit()


def scan_inbox(session: Session, email_account: EmailAccount) -> int:
    """Scans the most recent inbox messages, skipping anything already
    triaged (idempotency via email_triage_log). Only processes new messages
    going forward from when an account is linked — no mailbox backfill."""
    message_ids = list_recent_message_ids(email_account)
    if not message_ids:
        return 0

    already_seen = set(
        session.exec(
            select(EmailTriageLog.gmail_message_id).where(
                EmailTriageLog.email_account_id == email_account.id,
                EmailTriageLog.gmail_message_id.in_(message_ids),
            )
        ).all()
    )

    triaged = 0
    for message_id in message_ids:
        if message_id in already_seen:
            continue
        try:
            _triage_one_message(session, email_account, message_id)
            triaged += 1
        except Exception:
            logger.exception("Failed to triage message %s", message_id)

    return triaged
