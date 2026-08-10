from datetime import timedelta

from sqlmodel import Session, select

from app.models.item import CreatedBy, Domain, Item, Priority, Status
from app.utils.time import utc_naive_now

TRIP_KEYWORDS = ("trip", "vacation", "travel")
COVERAGE_LEAD_TIME = timedelta(days=7)


def _is_trip(item: Item) -> bool:
    if item.domain != Domain.social:
        return False
    haystack = f"{item.item_type} {item.metadata_json.get('event_type', '')}".lower()
    return any(keyword in haystack for keyword in TRIP_KEYWORDS)


def suggest_trip_coverage(session: Session, item: Item) -> bool:
    """Tier A action: when a social item is tagged as a trip and the household
    has open pet/baby items, proactively create a coverage-arrangement item
    (e.g. book a dog walker or sitter) with enough lead time before the trip.
    Idempotent — only fires once per trip item."""
    if not _is_trip(item) or item.due_at is None:
        return False
    if item.metadata_json.get("coverage_suggested"):
        return False

    now = utc_naive_now()
    care_domains = []
    for domain in (Domain.pet, Domain.baby):
        has_open_items = session.exec(
            select(Item.id)
            .where(Item.domain == domain, Item.status.in_([Status.pending, Status.in_progress]))
            .limit(1)
        ).first()
        if has_open_items:
            care_domains.append(domain)

    if not care_domains:
        item.metadata_json = {**item.metadata_json, "coverage_suggested": True}
        session.add(item)
        return False

    coverage_due = item.due_at - COVERAGE_LEAD_TIME
    if coverage_due < now:
        coverage_due = now + timedelta(days=1)

    for domain in care_domains:
        session.add(
            Item(
                domain=domain,
                item_type="trip_coverage",
                title=f"Arrange {domain.value} coverage for trip: {item.title}",
                description=f"You have '{item.title}' coming up on {item.due_at.strftime('%b %d')}.",
                priority=Priority.high,
                due_at=coverage_due,
                metadata_json={"trip_item_id": item.id},
                created_by=CreatedBy.agent,
            )
        )

    item.metadata_json = {**item.metadata_json, "coverage_suggested": True}
    session.add(item)
    return True
