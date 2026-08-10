from sqlmodel import Session, select

from app.actions import proposal as proposal_module
from app.actions.proposal import propose_action
from app.models.action_request import ActionStatus, ActionType
from app.models.auto_approve_rule import AutoApproveRule
from app.models.household_member import HouseholdMember
from app.models.item import Domain, Item, Status


def test_tier_c_never_auto_approved_even_with_matching_rule(monkeypatch, session: Session):
    sent = []
    monkeypatch.setattr(proposal_module, "send_sms", lambda to, body: sent.append((to, body)))

    member = session.exec(select(HouseholdMember).where(HouseholdMember.name == "Ben")).one()
    member.phone_e164 = "+15551234567"
    session.add(member)
    # A rule that would auto-approve everything in this domain, if it applied.
    session.add(AutoApproveRule(domain=Domain.pet, item_type="", condition_json={}))
    session.commit()

    item = Item(
        domain=Domain.pet,
        item_type="vet_appt",
        title="Fluffy checkup",
        assignee_id=member.id,
        metadata_json={"vet_name": "Dr. Lee"},
    )
    session.add(item)
    session.commit()
    session.refresh(item)

    action_request = propose_action(
        session, item, ActionType.book_appointment, {"provider": "Dr. Lee"}
    )
    session.commit()

    assert action_request.status == ActionStatus.pending
    assert len(sent) == 1
    assert "Dr. Lee" in sent[0][1]


def test_order_supply_execute_marks_item_done(monkeypatch, session: Session):
    monkeypatch.setattr(proposal_module, "send_sms", lambda to, body: "SMfake")

    member = session.exec(select(HouseholdMember).where(HouseholdMember.name == "Ben")).one()
    member.phone_e164 = "+15551234567"
    session.add(member)
    session.commit()

    item = Item(
        domain=Domain.prescription,
        item_type="refill",
        title="Refill amoxicillin",
        assignee_id=member.id,
        metadata_json={"pharmacy": "CVS"},
    )
    session.add(item)
    session.commit()
    session.refresh(item)

    action_request = propose_action(
        session, item, ActionType.order_supply, {"vendor": "CVS"}
    )
    session.commit()
    assert action_request.status == ActionStatus.pending

    from app.actions.proposal import resolve_response

    resolve_response(session, action_request, approved=True)
    session.commit()

    assert action_request.status == ActionStatus.executed
    session.refresh(item)
    assert item.status == Status.done
