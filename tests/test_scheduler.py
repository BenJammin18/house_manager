from datetime import timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.models.household_member import HouseholdMember
from app.models.item import Domain, Item, Priority, Status
from app.scheduler import jobs as scheduler_jobs
from app.utils.time import utc_naive_now


@pytest.fixture(name="scheduler_engine")
def scheduler_engine_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(autouse=True)
def _patch_engine_and_sms(monkeypatch, scheduler_engine):
    monkeypatch.setattr(scheduler_jobs, "engine", scheduler_engine)
    sent = []
    monkeypatch.setattr(scheduler_jobs, "send_sms", lambda to, body: sent.append((to, body)) or "SMfake")
    return sent


def test_level_0_to_1_sends_sms_for_high_priority(scheduler_engine, _patch_engine_and_sms):
    now = utc_naive_now()
    with Session(scheduler_engine) as session:
        member = HouseholdMember(name="Ben", phone_e164="+15551234567")
        session.add(member)
        session.commit()
        session.refresh(member)

        item = Item(
            domain=Domain.bill,
            item_type="water_bill",
            title="Pay water bill",
            priority=Priority.high,
            assignee_id=member.id,
            due_at=now - timedelta(minutes=5),
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        item_id = item.id

    scheduler_jobs.evaluate_due_items()

    with Session(scheduler_engine) as session:
        item = session.get(Item, item_id)
        assert item.escalation_level == 1
        assert item.nudge_count == 1

    assert len(_patch_engine_and_sms) == 1
    assert _patch_engine_and_sms[0][0] == "+15551234567"


def test_level_0_to_1_skips_sms_for_normal_priority(scheduler_engine, _patch_engine_and_sms):
    now = utc_naive_now()
    with Session(scheduler_engine) as session:
        member = HouseholdMember(name="Ben", phone_e164="+15551234567")
        session.add(member)
        session.commit()
        session.refresh(member)

        item = Item(
            domain=Domain.chore,
            item_type="trash",
            title="Take out trash",
            priority=Priority.normal,
            assignee_id=member.id,
            due_at=now - timedelta(minutes=5),
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        item_id = item.id

    scheduler_jobs.evaluate_due_items()

    with Session(scheduler_engine) as session:
        item = session.get(Item, item_id)
        assert item.escalation_level == 1

    assert len(_patch_engine_and_sms) == 0


def test_level_1_to_2_always_sends_sms(scheduler_engine, _patch_engine_and_sms):
    now = utc_naive_now()
    with Session(scheduler_engine) as session:
        member = HouseholdMember(name="Ben", phone_e164="+15551234567")
        session.add(member)
        session.commit()
        session.refresh(member)

        item = Item(
            domain=Domain.chore,
            item_type="trash",
            title="Take out trash",
            priority=Priority.normal,
            assignee_id=member.id,
            due_at=now - timedelta(days=2),
            escalation_level=1,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        item_id = item.id

    scheduler_jobs.evaluate_due_items()

    with Session(scheduler_engine) as session:
        item = session.get(Item, item_id)
        assert item.escalation_level == 2

    assert len(_patch_engine_and_sms) == 1


def test_items_not_yet_due_are_untouched(scheduler_engine, _patch_engine_and_sms):
    now = utc_naive_now()
    with Session(scheduler_engine) as session:
        item = Item(
            domain=Domain.social,
            item_type="dinner",
            title="Dinner with friends",
            due_at=now + timedelta(days=3),
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        item_id = item.id

    scheduler_jobs.evaluate_due_items()

    with Session(scheduler_engine) as session:
        item = session.get(Item, item_id)
        assert item.escalation_level == 0
        assert item.status == Status.pending

    assert len(_patch_engine_and_sms) == 0
