from sqlmodel import Session, select

from app.actions import calendar_conflicts as calendar_conflicts_module
from app.actions.calendar_conflicts import detect_calendar_conflicts
from app.models.calendar_account import CalendarAccount
from app.models.item import Domain, Item

EVENTS_BY_CALENDAR = {}


def _make_calendar_account(session: Session, member_id: int, email: str, calendar_ids: list[str]) -> CalendarAccount:
    account = CalendarAccount(
        member_id=member_id,
        google_account_email=email,
        calendar_ids_json=calendar_ids,
        oauth_refresh_token_encrypted="enc",
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def _fake_list_events(account, calendar_id, time_min, time_max):
    return EVENTS_BY_CALENDAR.get((account.google_account_email, calendar_id), [])


def test_overlapping_events_on_different_calendars_flagged(monkeypatch, session: Session):
    EVENTS_BY_CALENDAR.clear()
    monkeypatch.setattr(calendar_conflicts_module, "list_events", _fake_list_events)

    _make_calendar_account(session, 1, "ben@x.com", ["primary"])
    _make_calendar_account(session, 2, "wife@x.com", ["primary"])

    EVENTS_BY_CALENDAR[("ben@x.com", "primary")] = [
        {
            "id": "evt-ben-1",
            "summary": "Client call",
            "start": {"dateTime": "2026-08-15T14:00:00-04:00"},
            "end": {"dateTime": "2026-08-15T15:00:00-04:00"},
        }
    ]
    EVENTS_BY_CALENDAR[("wife@x.com", "primary")] = [
        {
            "id": "evt-wife-1",
            "summary": "Parent-teacher conference",
            "start": {"dateTime": "2026-08-15T14:30:00-04:00"},
            "end": {"dateTime": "2026-08-15T15:30:00-04:00"},
        }
    ]

    created = detect_calendar_conflicts(session)
    session.commit()

    assert created == 1
    conflicts = session.exec(select(Item).where(Item.item_type == "calendar_conflict")).all()
    assert len(conflicts) == 1
    assert conflicts[0].domain == Domain.social


def test_non_overlapping_events_not_flagged(monkeypatch, session: Session):
    EVENTS_BY_CALENDAR.clear()
    monkeypatch.setattr(calendar_conflicts_module, "list_events", _fake_list_events)

    _make_calendar_account(session, 1, "ben@x.com", ["primary"])
    _make_calendar_account(session, 2, "wife@x.com", ["primary"])

    EVENTS_BY_CALENDAR[("ben@x.com", "primary")] = [
        {
            "id": "evt-ben-1",
            "summary": "Client call",
            "start": {"dateTime": "2026-08-15T14:00:00-04:00"},
            "end": {"dateTime": "2026-08-15T15:00:00-04:00"},
        }
    ]
    EVENTS_BY_CALENDAR[("wife@x.com", "primary")] = [
        {
            "id": "evt-wife-1",
            "summary": "Parent-teacher conference",
            "start": {"dateTime": "2026-08-15T16:00:00-04:00"},
            "end": {"dateTime": "2026-08-15T17:00:00-04:00"},
        }
    ]

    created = detect_calendar_conflicts(session)
    session.commit()

    assert created == 0


def test_overlap_within_same_calendar_not_flagged(monkeypatch, session: Session):
    EVENTS_BY_CALENDAR.clear()
    monkeypatch.setattr(calendar_conflicts_module, "list_events", _fake_list_events)

    _make_calendar_account(session, 1, "ben@x.com", ["primary"])

    EVENTS_BY_CALENDAR[("ben@x.com", "primary")] = [
        {
            "id": "evt-1",
            "summary": "Event A",
            "start": {"dateTime": "2026-08-15T14:00:00-04:00"},
            "end": {"dateTime": "2026-08-15T15:00:00-04:00"},
        },
        {
            "id": "evt-2",
            "summary": "Event B",
            "start": {"dateTime": "2026-08-15T14:30:00-04:00"},
            "end": {"dateTime": "2026-08-15T15:30:00-04:00"},
        },
    ]

    created = detect_calendar_conflicts(session)
    session.commit()

    assert created == 0


def test_conflict_not_duplicated_on_rerun(monkeypatch, session: Session):
    EVENTS_BY_CALENDAR.clear()
    monkeypatch.setattr(calendar_conflicts_module, "list_events", _fake_list_events)

    _make_calendar_account(session, 1, "ben@x.com", ["primary"])
    _make_calendar_account(session, 2, "wife@x.com", ["primary"])

    EVENTS_BY_CALENDAR[("ben@x.com", "primary")] = [
        {
            "id": "evt-ben-1",
            "summary": "Client call",
            "start": {"dateTime": "2026-08-15T14:00:00-04:00"},
            "end": {"dateTime": "2026-08-15T15:00:00-04:00"},
        }
    ]
    EVENTS_BY_CALENDAR[("wife@x.com", "primary")] = [
        {
            "id": "evt-wife-1",
            "summary": "Parent-teacher conference",
            "start": {"dateTime": "2026-08-15T14:30:00-04:00"},
            "end": {"dateTime": "2026-08-15T15:30:00-04:00"},
        }
    ]

    assert detect_calendar_conflicts(session) == 1
    session.commit()
    assert detect_calendar_conflicts(session) == 0
