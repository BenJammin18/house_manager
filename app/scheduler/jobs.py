import logging
from collections import defaultdict
from datetime import timedelta

from sqlmodel import Session, select

from app.actions.calendar_conflicts import detect_calendar_conflicts
from app.actions.email_triage import scan_inbox
from app.actions.finance import check_budget_pace, reconcile_bills
from app.actions.registry import TIER_A_ACTIONS
from app.agent.digest import generate_digest
from app.agent.escalation import decide_escalation_action, get_nudge_history, resolve_assignee_by_name
from app.db import engine
from app.integrations.crypto import decrypt_token
from app.integrations.plaid_client import sync_transactions as plaid_sync_transactions
from app.integrations.plaid_client import (
    transaction_amount_cents,
    transaction_category,
    transaction_posted_date,
)
from app.integrations.twilio_client import TwilioNotConfigured, send_sms
from app.models.email_account import EmailAccount
from app.models.household_member import HouseholdMember
from app.models.item import Item, Priority, Status
from app.models.linked_account import LinkedAccount
from app.models.nudge_log import NudgeLog
from app.models.transaction import Transaction
from app.utils.time import utc_naive_now

logger = logging.getLogger(__name__)

DUE_SOON_WINDOW = timedelta(hours=2)
FIRM_NUDGE_AFTER = timedelta(hours=24)
LLM_ESCALATION_AFTER = timedelta(hours=72)


def _notify(session: Session, item: Item, level: int, message: str) -> None:
    members: list[HouseholdMember] = []
    if item.assignee_id:
        member = session.get(HouseholdMember, item.assignee_id)
        if member:
            members = [member]
    if not members:
        members = session.exec(select(HouseholdMember).where(HouseholdMember.is_active)).all()

    for member in members:
        status = "sent"
        sid = None
        if not member.phone_e164:
            status = "skipped_no_phone"
        else:
            try:
                sid = send_sms(member.phone_e164, message)
            except TwilioNotConfigured as exc:
                status = "skipped_not_configured"
                logger.info("Twilio not configured, skipping SMS: %s", exc)
            except Exception:
                status = "failed"
                logger.exception("Failed to send nudge SMS to %s", member.phone_e164)

        session.add(
            NudgeLog(
                item_id=item.id,
                member_id=member.id,
                channel="sms",
                escalation_level=level,
                message_text=message,
                twilio_sid=sid,
                status=status,
            )
        )


def _handle_llm_escalation(session: Session, item: Item, now) -> None:
    members = session.exec(select(HouseholdMember).where(HouseholdMember.is_active)).all()
    nudge_logs = get_nudge_history(session, item.id)
    try:
        decision = decide_escalation_action(item, nudge_logs, members)
    except Exception:
        logger.exception("LLM escalation decision failed for item %s", item.id)
        return

    action = decision.get("action")
    message = decision.get("message") or f"Still open: {item.title}"

    if action == "reassign":
        new_assignee_id = resolve_assignee_by_name(decision.get("suggested_assignee_name"), members)
        if new_assignee_id:
            item.assignee_id = new_assignee_id
    elif action == "mark_urgent":
        item.priority = Priority.urgent

    item.escalation_level = 3
    item.last_nudged_at = now
    item.nudge_count += 1
    item.updated_at = now
    session.add(item)
    _notify(session, item, 3, message)


def evaluate_due_items() -> None:
    """Runs the deterministic escalation state machine (levels 0->1->2) and
    fires eligible Tier A actions (currently: calendar sync)."""
    now = utc_naive_now()
    with Session(engine) as session:
        items = session.exec(
            select(Item).where(Item.status.in_([Status.pending, Status.in_progress]))
        ).all()

        for item in items:
            for action in TIER_A_ACTIONS.values():
                try:
                    action(session, item)
                except Exception:
                    logger.exception("Tier A action failed for item %s", item.id)

            if item.due_at is None:
                continue

            due_soon_or_overdue = now >= item.due_at - DUE_SOON_WINDOW
            still_overdue = now >= item.due_at + FIRM_NUDGE_AFTER
            very_overdue = now >= item.due_at + LLM_ESCALATION_AFTER

            if item.escalation_level == 0 and due_soon_or_overdue:
                item.escalation_level = 1
                item.last_nudged_at = now
                item.nudge_count += 1
                item.updated_at = now
                session.add(item)
                if item.priority in (Priority.high, Priority.urgent):
                    _notify(session, item, 1, f"Reminder: {item.title} is due soon.")
            elif item.escalation_level == 1 and still_overdue:
                item.escalation_level = 2
                item.last_nudged_at = now
                item.nudge_count += 1
                item.updated_at = now
                session.add(item)
                _notify(session, item, 2, f"Still open: {item.title} is overdue.")
            elif item.escalation_level == 2 and very_overdue:
                _handle_llm_escalation(session, item, now)

        session.commit()


def _upsert_transaction(session: Session, linked_account_id: int, txn) -> None:
    existing = session.exec(
        select(Transaction).where(Transaction.plaid_transaction_id == txn.transaction_id)
    ).first()
    amount_cents = transaction_amount_cents(txn.amount)
    category = transaction_category(txn)
    posted_at = transaction_posted_date(txn)
    merchant_name = txn.merchant_name or txn.name

    if existing:
        existing.amount_cents = amount_cents
        existing.merchant_name = merchant_name
        existing.category = category
        existing.posted_at = posted_at
        existing.pending = txn.pending
        session.add(existing)
    else:
        session.add(
            Transaction(
                linked_account_id=linked_account_id,
                plaid_transaction_id=txn.transaction_id,
                amount_cents=amount_cents,
                merchant_name=merchant_name,
                category=category,
                posted_at=posted_at,
                pending=txn.pending,
            )
        )


def sync_transactions_job() -> None:
    """Pulls new/updated transactions for every linked bank item, then runs
    bill reconciliation and budget-pace-alert checks against the fresh data."""
    with Session(engine) as session:
        accounts = session.exec(select(LinkedAccount).where(LinkedAccount.active)).all()
        by_item: dict[str, list[LinkedAccount]] = defaultdict(list)
        for account in accounts:
            by_item[account.plaid_item_id].append(account)

        for item_id, item_accounts in by_item.items():
            access_token = decrypt_token(item_accounts[0].plaid_access_token_encrypted)
            account_by_plaid_id = {a.plaid_account_id: a for a in item_accounts}
            cursor = item_accounts[0].sync_cursor
            has_more = True

            while has_more:
                try:
                    result = plaid_sync_transactions(access_token, cursor)
                except Exception:
                    logger.exception("Plaid transaction sync failed for item %s", item_id)
                    break

                for txn in [*result["added"], *result["modified"]]:
                    linked_account = account_by_plaid_id.get(txn.account_id)
                    if linked_account is not None:
                        _upsert_transaction(session, linked_account.id, txn)

                for removed in result["removed"]:
                    existing = session.exec(
                        select(Transaction).where(
                            Transaction.plaid_transaction_id == removed.transaction_id
                        )
                    ).first()
                    if existing:
                        session.delete(existing)

                cursor = result["next_cursor"]
                has_more = result["has_more"]

            for account in item_accounts:
                account.sync_cursor = cursor
                session.add(account)

        session.commit()

        reconcile_bills(session)
        check_budget_pace(session)
        session.commit()


def scan_inbox_job() -> None:
    with Session(engine) as session:
        accounts = session.exec(select(EmailAccount).where(EmailAccount.active)).all()
        for account in accounts:
            try:
                scan_inbox(session, account)
            except Exception:
                logger.exception("Inbox scan failed for email_account %s", account.id)


def detect_calendar_conflicts_job() -> None:
    with Session(engine) as session:
        try:
            created = detect_calendar_conflicts(session)
            session.commit()
            if created:
                logger.info("Detected %d new calendar conflict(s)", created)
        except Exception:
            logger.exception("Calendar conflict detection failed")


def send_daily_digest() -> None:
    with Session(engine) as session:
        digest_text = generate_digest(session)
        members = session.exec(select(HouseholdMember).where(HouseholdMember.is_active)).all()
        for member in members:
            if not member.phone_e164:
                continue
            try:
                send_sms(member.phone_e164, digest_text)
            except TwilioNotConfigured:
                logger.info("Twilio not configured, skipping digest SMS")
                break
            except Exception:
                logger.exception("Failed to send digest SMS to %s", member.phone_e164)
