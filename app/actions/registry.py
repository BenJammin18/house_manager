from app.actions.calendar import sync_item_to_calendar
from app.actions.trip_coverage import suggest_trip_coverage

# Tier A actions: safe to run automatically, no per-instance approval needed.
TIER_A_ACTIONS = {
    "calendar_create": sync_item_to_calendar,
    "trip_coverage": suggest_trip_coverage,
}
