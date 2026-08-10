from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlmodel import Session, select

from app.agent.client import MODEL, get_client
from app.models.transaction import Transaction
from app.utils.time import utc_naive_now

LOOKBACK_DAYS = 60

# Claude only groups raw Plaid category labels into household-facing buckets —
# it never computes the dollar amounts. LLMs are not reliable at arithmetic;
# a live test produced a $2.1M/month proposal from a $6,310 observed total.
# The actual monthly figure is always prorated deterministically in code from
# the totals we already computed, so a bad grouping can look odd but can
# never produce a wildly wrong number.
GROUP_CATEGORIES_TOOL = {
    "name": "group_spend_categories",
    "description": (
        "Group raw transaction category labels into a handful of sensible "
        "household-facing budget buckets (e.g. Groceries, Dining, Transportation, "
        "Pet Care, Utilities), so the household has a starting point to review."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "groups": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Short household-facing bucket name, e.g. Groceries.",
                        },
                        "raw_categories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Which of the raw category labels from the input belong in this bucket.",
                        },
                    },
                    "required": ["name", "raw_categories"],
                },
            }
        },
        "required": ["groups"],
    },
}


def _system_prompt() -> str:
    return (
        "You group raw Plaid transaction category labels into a handful of sensible "
        "household-facing budget buckets. Every raw category listed in the input must "
        "appear in exactly one group. Don't compute or mention dollar amounts — only "
        "decide the groupings and bucket names."
    )


def propose_budget_categories(session: Session) -> list[dict[str, Any]]:
    since = utc_naive_now().date() - timedelta(days=LOOKBACK_DAYS)
    transactions = session.exec(
        select(Transaction).where(Transaction.posted_at >= since, Transaction.amount_cents > 0)
    ).all()

    if not transactions:
        return []

    totals: dict[str, int] = defaultdict(int)
    counts: dict[str, int] = defaultdict(int)
    for txn in transactions:
        category = txn.category or "Uncategorized"
        totals[category] += txn.amount_cents
        counts[category] += 1

    lines = [
        f"- {category}: ${total_cents / 100:.2f} total across {counts[category]} transactions"
        for category, total_cents in sorted(totals.items(), key=lambda kv: -kv[1])
    ]
    summary = f"Raw categories seen over the last {LOOKBACK_DAYS} days:\n" + "\n".join(lines)

    client = get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_system_prompt(),
        tools=[GROUP_CATEGORIES_TOOL],
        tool_choice={"type": "tool", "name": "group_spend_categories"},
        messages=[{"role": "user", "content": summary}],
    )
    tool_use = next(b for b in response.content if b.type == "tool_use")
    groups = tool_use.input.get("groups", [])

    # Match case/whitespace-insensitively — Claude echoing "Food_and_drink"
    # instead of "FOOD_AND_DRINK" shouldn't silently drop that category's
    # spend from every group.
    totals_by_normalized = {raw.strip().lower(): (raw, total) for raw, total in totals.items()}

    proposals = []
    for group in groups:
        group_total_cents = 0
        for raw in group.get("raw_categories", []):
            match = totals_by_normalized.get(raw.strip().lower())
            if match:
                group_total_cents += match[1]
        if group_total_cents <= 0:
            continue
        monthly_amount_cents = round(group_total_cents * 30 / LOOKBACK_DAYS)
        proposals.append({"name": group["name"], "monthly_amount_cents": monthly_amount_cents})

    return proposals
