from datetime import timedelta
from typing import Callable, Optional

from sqlmodel import Session, select
from sqlalchemy import or_

from app.actions.rules import is_auto_approved
from app.integrations.twilio_client import TwilioNotConfigured, send_sms
from app.models.action_request import ActionRequest, ActionStatus, ActionType
from app.models.household_member import HouseholdMember
from app.models.item import Domain, Item, Status
from app.utils.time import utc_naive_now

PROPOSAL_EXPIRY = timedelta(hours=24)

# Which Tier C action a domain's items map to, for the generic "propose via
# text" UI trigger. Domains with no natural mapping (e.g. social, bill —
# bill has its own bill_pay flow) are simply absent.
DOMAIN_TIER_C_ACTION: dict[Domain, ActionType] = {
    Domain.pet: ActionType.book_appointment,
    Domain.baby: ActionType.book_appointment,
    Domain.chore: ActionType.order_supply,
    Domain.maintenance: ActionType.order_supply,
    Domain.prescription: ActionType.order_supply,
}


def build_tier_c_payload(action_type: ActionType, item: Item) -> dict:
    if action_type == ActionType.book_appointment:
        provider = (
            item.metadata_json.get("vendor_name")
            or item.metadata_json.get("vet_name")
            or item.metadata_json.get("pharmacy")
            or item.metadata_json.get("prescribing_provider")
        )
        return {"provider": provider, "vendor_phone": item.metadata_json.get("vendor_phone")}
    if action_type == ActionType.order_supply:
        return {"vendor": item.metadata_json.get("vendor_name") or item.metadata_json.get("pharmacy")}
    return {}


def _mark_item_confirmed(session: Session, action_request: ActionRequest) -> None:
    """Shared honest v1 behavior for actions with no real execution backend
    (no bank rail, no ordering API, no booking API): 'executing' means
    confirming a human already did the real-world thing, not doing it for
    them. Marks the underlying item done."""
    if action_request.item_id is None:
        return
    item = session.get(Item, action_request.item_id)
    if item is None:
        return
    item.status = Status.done
    item.completed_at = utc_naive_now()
    item.completed_by_id = action_request.member_id
    item.updated_at = utc_naive_now()
    item.metadata_json = {**item.metadata_json, "confirmed_via_action_request": action_request.id}
    session.add(item)


# Tier B: gated by auto_approve_rule, otherwise asks. Tier C: no execution
# backend exists at all (no ordering/booking API) — always asks, never
# auto-approved, regardless of any matching rule.
TIER_C_ACTIONS = {ActionType.order_supply, ActionType.book_appointment}

EXECUTORS: dict[ActionType, Callable[[Session, ActionRequest], None]] = {
    ActionType.bill_pay: _mark_item_confirmed,
    ActionType.order_supply: _mark_item_confirmed,
    ActionType.book_appointment: _mark_item_confirmed,
}


def _proposal_message(action_type: ActionType, item: Item, payload: dict) -> str:
    if action_type == ActionType.bill_pay:
        amount = payload.get("amount_cents")
        amount_str = f"${amount / 100:.2f}" if amount is not None else "an unknown amount"
        return f"Mark '{item.title}' as paid ({amount_str})? Reply YES to confirm or NO to skip."
    if action_type == ActionType.order_supply:
        vendor = payload.get("vendor")
        vendor_str = f" from {vendor}" if vendor else ""
        return (
            f"Order/restock '{item.title}'{vendor_str}? "
            "Reply YES once you've ordered it, or NO to skip."
        )
    if action_type == ActionType.book_appointment:
        provider = payload.get("provider")
        provider_str = f" with {provider}" if provider else ""
        phone = payload.get("vendor_phone")
        phone_str = f" ({phone})" if phone else ""
        return (
            f"Call to book '{item.title}'{provider_str}{phone_str}? "
            "Reply YES once you've called and booked it, or NO to skip."
        )
    return f"Confirm action for '{item.title}'? Reply YES to confirm or NO to skip."


def propose_action(
    session: Session,
    item: Item,
    action_type: ActionType,
    payload: dict,
    member: Optional[HouseholdMember] = None,
) -> ActionRequest:
    """Creates an ActionRequest. If an active auto_approve_rule matches, executes
    immediately with no SMS ask (Tier B, gated). Otherwise texts the target member
    a yes/no proposal and leaves it pending for the inbound webhook to resolve."""
    target_member = member
    if target_member is None and item.assignee_id:
        target_member = session.get(HouseholdMember, item.assignee_id)

    action_request = ActionRequest(
        item_id=item.id,
        member_id=target_member.id if target_member else None,
        action_type=action_type,
        payload_json=payload,
        channel="sms",
        expires_at=utc_naive_now() + PROPOSAL_EXPIRY,
    )

    if action_type not in TIER_C_ACTIONS and is_auto_approved(
        session, item.domain, item.item_type, payload
    ):
        action_request.status = ActionStatus.approved
        action_request.responded_at = utc_naive_now()
        session.add(action_request)
        session.flush()
        _execute(session, action_request)
        session.add(action_request)
        return action_request

    session.add(action_request)
    session.flush()

    if target_member:
        recipients = [target_member] if target_member.phone_e164 else []
    else:
        # No specific assignee — an unassigned action_request can be resolved
        # by a reply from any household member (see
        # find_pending_action_request_for_phone), so notify everyone rather
        # than silently texting no one.
        recipients = session.exec(select(HouseholdMember).where(HouseholdMember.is_active)).all()

    message = _proposal_message(action_type, item, payload)
    for recipient in recipients:
        if not recipient.phone_e164:
            continue
        try:
            send_sms(recipient.phone_e164, message)
        except TwilioNotConfigured:
            break

    return action_request


def _execute(session: Session, action_request: ActionRequest) -> None:
    executor = EXECUTORS.get(action_request.action_type)
    if executor is None:
        action_request.status = ActionStatus.failed
        return
    try:
        executor(session, action_request)
        action_request.status = ActionStatus.executed
    except Exception:
        action_request.status = ActionStatus.failed


def resolve_response(session: Session, action_request: ActionRequest, approved: bool) -> ActionRequest:
    if action_request.status != ActionStatus.pending:
        return action_request

    action_request.responded_at = utc_naive_now()
    if approved:
        action_request.status = ActionStatus.approved
        session.add(action_request)
        _execute(session, action_request)
    else:
        action_request.status = ActionStatus.denied

    session.add(action_request)
    return action_request


def find_pending_action_request_for_phone(session: Session, phone_e164: str) -> Optional[ActionRequest]:
    member = session.exec(
        select(HouseholdMember).where(HouseholdMember.phone_e164 == phone_e164)
    ).first()
    if member is None:
        return None

    now = utc_naive_now()
    pending = session.exec(
        select(ActionRequest)
        .where(
            or_(ActionRequest.member_id == member.id, ActionRequest.member_id.is_(None)),
            ActionRequest.status == ActionStatus.pending,
        )
        .order_by(ActionRequest.requested_at.desc())
    ).all()
    return next((ar for ar in pending if ar.expires_at is None or ar.expires_at >= now), None)
