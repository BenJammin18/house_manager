from datetime import timedelta

from sqlmodel import Session, select

from app.actions.trip_coverage import suggest_trip_coverage
from app.models.item import Domain, Item, Status
from app.utils.time import utc_naive_now


def _trip_item(due_in_days: int = 20) -> Item:
    return Item(
        domain=Domain.social,
        item_type="trip",
        title="Trip to Denver",
        due_at=utc_naive_now() + timedelta(days=due_in_days),
        metadata_json={"event_type": "travel"},
    )


def test_trip_with_open_pet_item_creates_coverage_suggestion(session: Session):
    session.add(Item(domain=Domain.pet, item_type="daily_walk", title="Walk the dog"))
    trip = _trip_item()
    session.add(trip)
    session.commit()
    session.refresh(trip)

    created = suggest_trip_coverage(session, trip)
    session.commit()

    assert created is True
    coverage_items = session.exec(
        select(Item).where(Item.item_type == "trip_coverage")
    ).all()
    assert len(coverage_items) == 1
    assert coverage_items[0].domain == Domain.pet
    assert coverage_items[0].metadata_json["trip_item_id"] == trip.id

    session.refresh(trip)
    assert trip.metadata_json["coverage_suggested"] is True


def test_trip_without_pet_or_baby_items_creates_nothing(session: Session):
    trip = _trip_item()
    session.add(trip)
    session.commit()
    session.refresh(trip)

    created = suggest_trip_coverage(session, trip)
    session.commit()

    assert created is False
    assert session.exec(select(Item).where(Item.item_type == "trip_coverage")).all() == []


def test_non_trip_social_item_does_nothing(session: Session):
    session.add(Item(domain=Domain.pet, item_type="daily_walk", title="Walk the dog"))
    dinner = Item(
        domain=Domain.social,
        item_type="dinner",
        title="Dinner with friends",
        due_at=utc_naive_now() + timedelta(days=3),
    )
    session.add(dinner)
    session.commit()
    session.refresh(dinner)

    created = suggest_trip_coverage(session, dinner)
    session.commit()

    assert created is False
    assert session.exec(select(Item).where(Item.item_type == "trip_coverage")).all() == []


def test_idempotent_only_suggests_once(session: Session):
    session.add(Item(domain=Domain.pet, item_type="daily_walk", title="Walk the dog"))
    trip = _trip_item()
    session.add(trip)
    session.commit()
    session.refresh(trip)

    assert suggest_trip_coverage(session, trip) is True
    session.commit()
    session.refresh(trip)

    assert suggest_trip_coverage(session, trip) is False
    session.commit()

    coverage_items = session.exec(select(Item).where(Item.item_type == "trip_coverage")).all()
    assert len(coverage_items) == 1
