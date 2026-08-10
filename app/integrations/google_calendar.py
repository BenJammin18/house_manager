from datetime import datetime, timezone
from typing import Optional

from googleapiclient.discovery import build

from app.integrations.google_oauth import credentials_from_encrypted_token
from app.models.calendar_account import CalendarAccount


def _credentials_for_account(account: CalendarAccount):
    return credentials_from_encrypted_token(account.oauth_refresh_token_encrypted)


def _rfc3339(dt: datetime) -> str:
    """Item due_at values are stored as naive UTC (SQLite drops tzinfo on
    round-trip). Google Calendar's dateTime field requires an explicit
    RFC3339 offset — a naive isoformat() (no 'Z'/offset) is silently wrong
    input Google would reject. Always attach UTC explicitly before sending."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def create_event(
    account: CalendarAccount,
    calendar_id: str,
    title: str,
    start: datetime,
    end: datetime,
    description: Optional[str] = None,
) -> dict:
    creds = _credentials_for_account(account)
    service = build("calendar", "v3", credentials=creds)
    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": _rfc3339(start)},
        "end": {"dateTime": _rfc3339(end)},
    }
    return service.events().insert(calendarId=calendar_id, body=body).execute()


def move_event(
    account: CalendarAccount,
    calendar_id: str,
    event_id: str,
    start: datetime,
    end: datetime,
) -> dict:
    creds = _credentials_for_account(account)
    service = build("calendar", "v3", credentials=creds)
    body = {"start": {"dateTime": _rfc3339(start)}, "end": {"dateTime": _rfc3339(end)}}
    return service.events().patch(calendarId=calendar_id, eventId=event_id, body=body).execute()


def list_events(account: CalendarAccount, calendar_id: str, time_min: datetime, time_max: datetime) -> list[dict]:
    creds = _credentials_for_account(account)
    service = build("calendar", "v3", credentials=creds)
    result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=_rfc3339(time_min),
            timeMax=_rfc3339(time_max),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return result.get("items", [])
