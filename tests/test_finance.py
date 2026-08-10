from datetime import timedelta

from sqlmodel import Session, select

from app.actions.finance import check_budget_pace, reconcile_bills
from app.models.budget_category import BudgetCategory
from app.models.household_member import HouseholdMember
from app.models.item import Domain, Item, Status
from app.models.linked_account import LinkedAccount
from app.models.transaction import Transaction
from app.utils.time import utc_naive_now


def _make_linked_account(session: Session) -> LinkedAccount:
    account = LinkedAccount(
        plaid_item_id="item-1",
        plaid_access_token_encrypted="encrypted",
        plaid_account_id="acct-1",
        institution_name="City Water Co Bank",
        account_name="Checking",
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def test_reconcile_bills_matches_payee_and_amount(session: Session):
    account = _make_linked_account(session)
    bill = Item(
        domain=Domain.bill,
        item_type="water_bill",
        title="Pay water bill",
        metadata_json={"amount_cents": 6240, "payee": "City Water"},
    )
    session.add(bill)
    session.add(
        Transaction(
            linked_account_id=account.id,
            plaid_transaction_id="txn-1",
            amount_cents=6240,
            merchant_name="CITY WATER UTILITY",
            posted_at=utc_naive_now().date(),
        )
    )
    session.commit()
    session.refresh(bill)

    matched = reconcile_bills(session)
    session.commit()

    assert matched == 1
    session.refresh(bill)
    assert bill.status == Status.done
    assert bill.metadata_json["matched_transaction_id"] is not None


def test_reconcile_bills_no_match_when_amount_differs(session: Session):
    account = _make_linked_account(session)
    bill = Item(
        domain=Domain.bill,
        item_type="water_bill",
        title="Pay water bill",
        metadata_json={"amount_cents": 6240, "payee": "City Water"},
    )
    session.add(bill)
    session.add(
        Transaction(
            linked_account_id=account.id,
            plaid_transaction_id="txn-1",
            amount_cents=9999,
            merchant_name="CITY WATER UTILITY",
            posted_at=utc_naive_now().date(),
        )
    )
    session.commit()
    session.refresh(bill)

    matched = reconcile_bills(session)
    session.commit()

    assert matched == 0
    session.refresh(bill)
    assert bill.status != Status.done


def test_budget_pace_alert_created_when_overspending(session: Session):
    account = _make_linked_account(session)
    session.add(BudgetCategory(name="Dining", monthly_amount_cents=10000))
    session.commit()

    today = utc_naive_now().date()
    # Spend the whole month's budget on day 1 of the month -> way over pace.
    session.add(
        Transaction(
            linked_account_id=account.id,
            plaid_transaction_id="txn-dining-1",
            amount_cents=15000,
            merchant_name="Some Restaurant",
            category="Dining",
            posted_at=today.replace(day=1),
        )
    )
    session.commit()

    created = check_budget_pace(session)
    session.commit()

    assert created == 1
    alerts = session.exec(select(Item).where(Item.item_type == "budget_pace_alert")).all()
    assert len(alerts) == 1
    assert alerts[0].domain == Domain.finance
    assert alerts[0].metadata_json["spent_cents"] == 15000


def test_budget_pace_alert_not_duplicated_same_month(session: Session):
    account = _make_linked_account(session)
    session.add(BudgetCategory(name="Dining", monthly_amount_cents=10000))
    session.commit()

    today = utc_naive_now().date()
    session.add(
        Transaction(
            linked_account_id=account.id,
            plaid_transaction_id="txn-dining-1",
            amount_cents=15000,
            merchant_name="Some Restaurant",
            category="Dining",
            posted_at=today.replace(day=1),
        )
    )
    session.commit()

    assert check_budget_pace(session) == 1
    session.commit()
    assert check_budget_pace(session) == 0


def test_budget_pace_no_alert_when_within_budget(session: Session):
    account = _make_linked_account(session)
    session.add(BudgetCategory(name="Dining", monthly_amount_cents=100000))
    session.commit()

    today = utc_naive_now().date()
    session.add(
        Transaction(
            linked_account_id=account.id,
            plaid_transaction_id="txn-dining-1",
            amount_cents=2000,
            merchant_name="Some Restaurant",
            category="Dining",
            posted_at=today.replace(day=1),
        )
    )
    session.commit()

    assert check_budget_pace(session) == 0
