from datetime import timedelta

from sqlmodel import Session, select

from app.integrations.google_calendar import create_event
from app.models.calendar_account import CalendarAccount
from app.models.item import Item

DEFAULT_EVENT_DURATION = timedelta(hours=1)


def _account_for_item(session: Session, item: Item) -> CalendarAccount | None:
    if item.assignee_id:
        account = session.exec(
            select(CalendarAccount).where(
                CalendarAccount.member_id == item.assignee_id, CalendarAccount.active
            )
        ).first()
        if account:
            return account
    return session.exec(select(CalendarAccount).where(CalendarAccount.active)).first()


def sync_item_to_calendar(session: Session, item: Item) -> bool:
    """Tier A action: create a calendar event for an item with a specific due time.

    Idempotent — skips items that already have a google_event_id, have no specific
    due time, or have no linked calendar account to use. Returns True if an event
    was created.
    """
    if item.due_at is None or item.due_date_only:
        return False
    if item.metadata_json.get("google_event_id"):
        return False

    account = _account_for_item(session, item)
    if account is None:
        return False

    calendar_id = account.calendar_ids_json[0] if account.calendar_ids_json else "primary"
    event = create_event(
        account=account,
        calendar_id=calendar_id,
        title=item.title,
        start=item.due_at,
        end=item.due_at + DEFAULT_EVENT_DURATION,
        description=item.description,
    )

    item.metadata_json = {
        **item.metadata_json,
        "google_event_id": event["id"],
        "google_calendar_id": calendar_id,
    }
    session.add(item)
    return True
