from datetime import timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.models.household_member import HouseholdMember
from app.models.item import Domain, Item, Priority, Status
from app.models.nudge_log import NudgeLog
from app.scheduler import jobs as scheduler_jobs
from app.utils.time import utc_naive_now

pytestmark = pytest.mark.live_api


@pytest.fixture(name="scheduler_engine")
def scheduler_engine_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine


def test_level_2_to_3_escalates_via_llm_and_sends_sms(monkeypatch, scheduler_engine):
    monkeypatch.setattr(scheduler_jobs, "engine", scheduler_engine)
    sent = []
    monkeypatch.setattr(
        scheduler_jobs, "send_sms", lambda to, body: sent.append((to, body)) or "SMfake"
    )

    now = utc_naive_now()
    with Session(scheduler_engine) as session:
        ben = HouseholdMember(name="Ben", phone_e164="+15551234567")
        wife = HouseholdMember(name="Robin", phone_e164="+15557654321")
        session.add(ben)
        session.add(wife)
        session.commit()
        session.refresh(ben)
        session.refresh(wife)

        item = Item(
            domain=Domain.chore,
            item_type="gutters",
            title="Clean the gutters",
            priority=Priority.normal,
            assignee_id=ben.id,
            due_at=now - timedelta(days=4),
            escalation_level=2,
            nudge_count=2,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        item_id = item.id

        session.add(
            NudgeLog(
                item_id=item.id,
                member_id=ben.id,
                channel="sms",
                escalation_level=1,
                message_text="Reminder: Clean the gutters is due soon.",
                status="sent",
            )
        )
        session.add(
            NudgeLog(
                item_id=item.id,
                member_id=ben.id,
                channel="sms",
                escalation_level=2,
                message_text="Still open: Clean the gutters is overdue.",
                status="sent",
            )
        )
        session.commit()

    scheduler_jobs.evaluate_due_items()

    with Session(scheduler_engine) as session:
        item = session.get(Item, item_id)
        assert item.escalation_level == 3
        assert item.nudge_count == 3
        assert item.status == Status.pending

    assert len(sent) == 1
    to_number, message = sent[0]
    assert to_number in ("+15551234567", "+15557654321")
    assert len(message) > 0
