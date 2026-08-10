from sqlmodel import Session, select

from app.actions import email_triage as email_triage_module
from app.actions.email_triage import scan_inbox
from app.models.email_account import EmailAccount
from app.models.email_triage_log import EmailActionTaken, EmailTriageLog
from app.models.item import Domain, Item


def _make_email_account(session: Session) -> EmailAccount:
    account = EmailAccount(
        member_id=1, gmail_address="ben@example.com", oauth_refresh_token_encrypted="enc"
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def test_spam_message_gets_trashed(monkeypatch, session: Session):
    account = _make_email_account(session)
    monkeypatch.setattr(email_triage_module, "list_recent_message_ids", lambda a: ["msg-1"])
    monkeypatch.setattr(
        email_triage_module,
        "get_message_summary",
        lambda a, mid: {"id": mid, "subject": "You won!!!", "sender": "spam@x.com", "snippet": "click now"},
    )
    trashed = []
    monkeypatch.setattr(email_triage_module, "trash_message", lambda a, mid: trashed.append(mid))
    monkeypatch.setattr(
        email_triage_module,
        "classify_email",
        lambda subject, sender, snippet: {"classification": "spam", "reason": "obvious spam"},
    )

    triaged = scan_inbox(session, account)

    assert triaged == 1
    assert trashed == ["msg-1"]
    log = session.exec(select(EmailTriageLog)).one()
    assert log.action_taken == EmailActionTaken.trashed


def test_important_message_gets_labeled(monkeypatch, session: Session):
    account = _make_email_account(session)
    monkeypatch.setattr(email_triage_module, "list_recent_message_ids", lambda a: ["msg-2"])
    monkeypatch.setattr(
        email_triage_module,
        "get_message_summary",
        lambda a, mid: {"id": mid, "subject": "Medical results", "sender": "clinic@x.com", "snippet": "..."},
    )
    labeled = []
    monkeypatch.setattr(email_triage_module, "label_important", lambda a, mid: labeled.append(mid))
    monkeypatch.setattr(
        email_triage_module,
        "classify_email",
        lambda subject, sender, snippet: {"classification": "important", "reason": "medical"},
    )

    scan_inbox(session, account)

    assert labeled == ["msg-2"]
    log = session.exec(select(EmailTriageLog)).one()
    assert log.action_taken == EmailActionTaken.flagged


def test_calendar_candidate_creates_item(monkeypatch, session: Session):
    account = _make_email_account(session)
    monkeypatch.setattr(email_triage_module, "list_recent_message_ids", lambda a: ["msg-3"])
    monkeypatch.setattr(
        email_triage_module,
        "get_message_summary",
        lambda a, mid: {"id": mid, "subject": "Reservation confirmed", "sender": "opentable@x.com", "snippet": "..."},
    )
    monkeypatch.setattr(
        email_triage_module,
        "classify_email",
        lambda subject, sender, snippet: {
            "classification": "calendar_candidate",
            "reason": "dinner reservation",
            "extracted_event": {
                "title": "Dinner reservation",
                "due_at_iso": "2026-09-01T19:00:00-04:00",
                "description": "Table for 2",
            },
        },
    )

    scan_inbox(session, account)

    log = session.exec(select(EmailTriageLog)).one()
    assert log.action_taken == EmailActionTaken.calendar_event_created

    item = session.exec(select(Item).where(Item.domain == Domain.social)).one()
    assert item.title == "Dinner reservation"
    assert item.assignee_id == account.member_id


def test_normal_message_takes_no_action(monkeypatch, session: Session):
    account = _make_email_account(session)
    monkeypatch.setattr(email_triage_module, "list_recent_message_ids", lambda a: ["msg-4"])
    monkeypatch.setattr(
        email_triage_module,
        "get_message_summary",
        lambda a, mid: {"id": mid, "subject": "Newsletter", "sender": "news@x.com", "snippet": "..."},
    )
    monkeypatch.setattr(
        email_triage_module,
        "classify_email",
        lambda subject, sender, snippet: {"classification": "normal", "reason": "not actionable"},
    )

    scan_inbox(session, account)

    log = session.exec(select(EmailTriageLog)).one()
    assert log.action_taken == EmailActionTaken.none


def test_already_triaged_messages_are_skipped(monkeypatch, session: Session):
    account = _make_email_account(session)
    session.add(
        EmailTriageLog(
            email_account_id=account.id,
            gmail_message_id="msg-5",
            classification="normal",
            action_taken="none",
        )
    )
    session.commit()

    monkeypatch.setattr(email_triage_module, "list_recent_message_ids", lambda a: ["msg-5"])

    def fail_if_called(*args, **kwargs):
        raise AssertionError("should not classify an already-triaged message")

    monkeypatch.setattr(email_triage_module, "classify_email", fail_if_called)

    triaged = scan_inbox(session, account)
    assert triaged == 0
