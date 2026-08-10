from datetime import timedelta
from calendar import monthrange

from sqlmodel import Session, select

from app.models.budget_category import BudgetCategory
from app.models.item import CreatedBy, Domain, Item, Priority, Status
from app.models.transaction import Transaction
from app.utils.time import utc_naive_now

RECONCILE_LOOKBACK = timedelta(days=45)
AMOUNT_TOLERANCE_CENTS = 100
OVER_PACE_THRESHOLD = 1.15


def _texts_match(a: str, b: str) -> bool:
    a, b = a.strip().lower(), b.strip().lower()
    return bool(a) and bool(b) and (a in b or b in a)


def reconcile_bills(session: Session) -> int:
    """Tier A action: cross-references open bill items against real transactions
    and auto-marks a bill done when a matching payment is found. Reversible by
    editing the item — this doesn't pay anything, it just notices a payment
    already happened."""
    since = utc_naive_now().date() - RECONCILE_LOOKBACK
    bills = session.exec(
        select(Item).where(
            Item.domain == Domain.bill, Item.status.in_([Status.pending, Status.in_progress])
        )
    ).all()

    matched = 0
    for bill in bills:
        payee = bill.metadata_json.get("payee")
        amount_cents = bill.metadata_json.get("amount_cents")
        if not payee or amount_cents is None:
            continue

        candidates = session.exec(
            select(Transaction).where(
                Transaction.posted_at >= since,
                Transaction.amount_cents >= amount_cents - AMOUNT_TOLERANCE_CENTS,
                Transaction.amount_cents <= amount_cents + AMOUNT_TOLERANCE_CENTS,
            )
        ).all()

        match = next(
            (t for t in candidates if t.merchant_name and _texts_match(payee, t.merchant_name)),
            None,
        )
        if match is None:
            continue

        bill.status = Status.done
        bill.completed_at = utc_naive_now()
        bill.updated_at = utc_naive_now()
        bill.metadata_json = {**bill.metadata_json, "matched_transaction_id": match.id}
        session.add(bill)
        matched += 1

    return matched


def check_budget_pace(session: Session) -> int:
    """Creates a finance-domain item when month-to-date spend in a budget
    category materially outpaces the prorated monthly budget. Flows through
    the existing digest/nudge pipeline — no new notification path needed."""
    today = utc_naive_now().date()
    month_start = today.replace(day=1)
    days_in_month = monthrange(today.year, today.month)[1]
    day_of_month = today.day
    month_key = today.strftime("%Y-%m")

    categories = session.exec(select(BudgetCategory).where(BudgetCategory.active)).all()
    created = 0

    for category in categories:
        transactions = session.exec(
            select(Transaction).where(
                Transaction.posted_at >= month_start, Transaction.amount_cents > 0
            )
        ).all()
        spend_cents = sum(
            t.amount_cents
            for t in transactions
            if t.category and _texts_match(category.name, t.category)
        )

        prorated_cents = category.monthly_amount_cents * day_of_month / days_in_month
        if prorated_cents <= 0 or spend_cents <= prorated_cents * OVER_PACE_THRESHOLD:
            continue

        already_alerted = session.exec(
            select(Item.id).where(
                Item.domain == Domain.finance,
                Item.item_type == "budget_pace_alert",
                Item.status.in_([Status.pending, Status.in_progress]),
            )
        ).all()
        duplicate = False
        for item_id in already_alerted:
            item = session.get(Item, item_id)
            if item and item.metadata_json.get("budget_category_id") == category.id and item.metadata_json.get("month") == month_key:
                duplicate = True
                break
        if duplicate:
            continue

        pace_ratio = spend_cents / category.monthly_amount_cents if category.monthly_amount_cents else 0
        session.add(
            Item(
                domain=Domain.finance,
                item_type="budget_pace_alert",
                title=f"{category.name} budget: ${spend_cents / 100:.2f} of ${category.monthly_amount_cents / 100:.2f} spent, {day_of_month}/{days_in_month} days into the month",
                priority=Priority.high if pace_ratio >= 1.5 else Priority.normal,
                metadata_json={
                    "budget_category_id": category.id,
                    "spent_cents": spend_cents,
                    "budget_cents": category.monthly_amount_cents,
                    "month": month_key,
                },
                created_by=CreatedBy.agent,
            )
        )
        created += 1

    return created
