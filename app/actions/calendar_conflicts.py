import logging
from datetime import datetime, timedelta
from itertools import combinations
from typing import Optional

from sqlmodel import Session, select

from app.integrations.google_calendar import list_events
from app.models.calendar_account import CalendarAccount
from app.models.item import CreatedBy, Domain, Item, Status
from app.utils.time import to_utc_naive, utc_naive_now

logger = logging.getLogger(__name__)

LOOKAHEAD = timedelta(days=14)


def _parse_event_time(value: dict) -> Optional[datetime]:
    raw = value.get("dateTime") or value.get("date")
    if not raw:
        return None
    return to_utc_naive(datetime.fromisoformat(raw))


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def detect_calendar_conflicts(session: Session) -> int:
    """Reads events from every linked calendar_account (each spouse's personal
    calendar + the shared family one) and flags overlaps across *different*
    calendars. v1 heuristic: any overlap is flagged, no attempt to infer
    whether attendance is actually required."""
    now = utc_naive_now()
    time_max = now + LOOKAHEAD

    accounts = session.exec(select(CalendarAccount).where(CalendarAccount.active)).all()

    # (calendar_label, event_id, title, start, end)
    all_events: list[tuple[str, str, str, datetime, datetime]] = []
    for account in accounts:
        for calendar_id in account.calendar_ids_json or ["primary"]:
            calendar_label = f"{account.google_account_email}:{calendar_id}"
            try:
                events = list_events(account, calendar_id, now, time_max)
            except Exception:
                logger.exception("Failed to list events for %s", calendar_label)
                continue
            for event in events:
                start = _parse_event_time(event.get("start", {}))
                end = _parse_event_time(event.get("end", {}))
                if start is None or end is None:
                    continue
                all_events.append(
                    (calendar_label, event.get("id", ""), event.get("summary", "(no title)"), start, end)
                )

    already_flagged = _existing_flagged_pairs(session)
    created = 0

    for (label_a, id_a, title_a, start_a, end_a), (label_b, id_b, title_b, start_b, end_b) in combinations(
        all_events, 2
    ):
        if label_a == label_b:
            continue
        if not _overlaps(start_a, end_a, start_b, end_b):
            continue

        pair_key = frozenset((id_a, id_b))
        if pair_key in already_flagged:
            continue

        session.add(
            Item(
                domain=Domain.social,
                item_type="calendar_conflict",
                title=f"Calendar conflict: '{title_a}' overlaps '{title_b}'",
                description=f"{label_a}: {title_a} ({start_a}–{end_a})\n{label_b}: {title_b} ({start_b}–{end_b})",
                due_at=min(start_a, start_b),
                metadata_json={"event_ids": [id_a, id_b]},
                created_by=CreatedBy.agent,
            )
        )
        already_flagged.add(pair_key)
        created += 1

    return created


def _existing_flagged_pairs(session: Session) -> set[frozenset]:
    items = session.exec(
        select(Item).where(
            Item.domain == Domain.social,
            Item.item_type == "calendar_conflict",
            Item.status.in_([Status.pending, Status.in_progress]),
        )
    ).all()
    pairs = set()
    for item in items:
        event_ids = item.metadata_json.get("event_ids")
        if event_ids and len(event_ids) == 2:
            pairs.add(frozenset(event_ids))
    return pairs
