from sqlmodel import Session, select

from app.models.auto_approve_rule import AutoApproveRule
from app.models.item import Domain


def matches_auto_approve_rule(rule: AutoApproveRule, item_type: str, payload: dict) -> bool:
    if rule.item_type and rule.item_type != item_type:
        return False

    condition = rule.condition_json
    max_amount_cents = condition.get("max_amount_cents")
    if max_amount_cents is not None:
        amount_cents = payload.get("amount_cents")
        if amount_cents is None or amount_cents > max_amount_cents:
            return False

    vendor = condition.get("vendor")
    if vendor is not None:
        payee = (payload.get("payee") or payload.get("vendor") or "").strip().lower()
        if payee != vendor.strip().lower():
            return False

    return True


def is_auto_approved(session: Session, domain: Domain, item_type: str, payload: dict) -> bool:
    rules = session.exec(
        select(AutoApproveRule).where(
            AutoApproveRule.domain == domain, AutoApproveRule.active
        )
    ).all()
    return any(matches_auto_approve_rule(rule, item_type, payload) for rule in rules)
