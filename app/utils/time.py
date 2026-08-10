from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.config import settings


def utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_utc_naive(dt: datetime) -> datetime:
    """Normalize any datetime to naive UTC, since SQLite drops tzinfo on
    round-trip. A naive input is assumed to be wall-clock time in the
    household's configured timezone (e.g. from a browser datetime-local
    input); an aware input is converted directly."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(settings.timezone))
    return dt.astimezone(timezone.utc).replace(tzinfo=None)
