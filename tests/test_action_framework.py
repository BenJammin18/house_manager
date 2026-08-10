from sqlmodel import Session, select

from app.actions import proposal as proposal_module
from app.actions.proposal import propose_action, resolve_response
from app.models.action_request import ActionRequest, ActionStatus, ActionType
from app.models.auto_approve_rule import AutoApproveRule
from app.models.household_member import HouseholdMember
from app.models.item import Domain, Item, Status


def _make_bill_item(session: Session, assignee_id: int, amount_cents: int = 6240) -> Item:
    item = Item(
        domain=Domain.bill,
        item_type="water_bill",
        title="Pay water bill",
        assignee_id=assignee_id,
        metadata_json={"amount_cents": amount_cents, "payee": "City Water"},
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def test_auto_approve_rule_bypasses_sms_and_executes(monkeypatch, session: Session):
    sent = []
    monkeypatch.setattr(proposal_module, "send_sms", lambda to, body: sent.append((to, body)))

    member = session.exec(select(HouseholdMember).where(HouseholdMember.name == "Ben")).one()
    member.phone_e164 = "+15551234567"
    session.add(member)
    session.add(AutoApproveRule(domain=Domain.bill, item_type="", condition_json={"max_amount_cents": 10000}))
    session.commit()

    item = _make_bill_item(session, member.id, amount_cents=6240)
    action_request = propose_action(
        session, item, ActionType.bill_pay, {"amount_cents": 6240, "payee": "City Water"}
    )
    session.commit()

    assert action_request.status == ActionStatus.executed
    assert sent == []

    session.refresh(item)
    assert item.status == Status.done


def test_propose_without_rule_texts_and_stays_pending(monkeypatch, session: Session):
    sent = []
    monkeypatch.setattr(proposal_module, "send_sms", lambda to, body: sent.append((to, body)) or "SMfake")

    member = session.exec(select(HouseholdMember).where(HouseholdMember.name == "Ben")).one()
    member.phone_e164 = "+15551234567"
    session.add(member)
    session.commit()

    item = _make_bill_item(session, member.id)
    action_request = propose_action(
        session, item, ActionType.bill_pay, {"amount_cents": 6240, "payee": "City Water"}
    )
    session.commit()

    assert action_request.status == ActionStatus.pending
    assert len(sent) == 1
    assert sent[0][0] == "+15551234567"

    session.refresh(item)
    assert item.status != Status.done


def test_resolve_response_approved_executes(monkeypatch, session: Session):
    monkeypatch.setattr(proposal_module, "send_sms", lambda to, body: "SMfake")

    member = session.exec(select(HouseholdMember).where(HouseholdMember.name == "Ben")).one()
    member.phone_e164 = "+15551234567"
    session.add(member)
    session.commit()

    item = _make_bill_item(session, member.id)
    action_request = propose_action(
        session, item, ActionType.bill_pay, {"amount_cents": 6240, "payee": "City Water"}
    )
    session.commit()

    resolve_response(session, action_request, approved=True)
    session.commit()

    assert action_request.status == ActionStatus.executed
    session.refresh(item)
    assert item.status == Status.done
    assert item.completed_by_id == member.id


def test_resolve_response_denied_does_not_execute(monkeypatch, session: Session):
    monkeypatch.setattr(proposal_module, "send_sms", lambda to, body: "SMfake")

    member = session.exec(select(HouseholdMember).where(HouseholdMember.name == "Ben")).one()
    member.phone_e164 = "+15551234567"
    session.add(member)
    session.commit()

    item = _make_bill_item(session, member.id)
    action_request = propose_action(
        session, item, ActionType.bill_pay, {"amount_cents": 6240, "payee": "City Water"}
    )
    session.commit()

    resolve_response(session, action_request, approved=False)
    session.commit()

    assert action_request.status == ActionStatus.denied
    session.refresh(item)
    assert item.status != Status.done


def test_webhook_approves_pending_request(monkeypatch, client, session: Session):
    from app.routers import webhooks as webhooks_module

    monkeypatch.setattr(webhooks_module, "validate_webhook_signature", lambda url, params, sig: True)
    monkeypatch.setattr(proposal_module, "send_sms", lambda to, body: "SMfake")

    member = session.exec(select(HouseholdMember).where(HouseholdMember.name == "Ben")).one()
    member.phone_e164 = "+15551234567"
    session.add(member)
    session.commit()

    item = _make_bill_item(session, member.id)
    propose_action(session, item, ActionType.bill_pay, {"amount_cents": 6240, "payee": "City Water"})
    session.commit()

    response = client.post(
        "/webhooks/sms",
        data={"From": "+15551234567", "Body": "YES"},
        headers={"X-Twilio-Signature": "fake"},
    )
    assert response.status_code == 200
    assert "confirmed" in response.text.lower()

    session.refresh(item)
    assert item.status == Status.done

    action_request = session.exec(select(ActionRequest)).one()
    assert action_request.status == ActionStatus.executed


def test_webhook_rejects_unverified_request(monkeypatch, client, session: Session):
    from app.routers import webhooks as webhooks_module

    monkeypatch.setattr(webhooks_module, "validate_webhook_signature", lambda url, params, sig: False)

    response = client.post(
        "/webhooks/sms",
        data={"From": "+15551234567", "Body": "YES"},
    )
    assert response.status_code == 403
