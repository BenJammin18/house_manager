from sqlmodel import Session, select

from app.agent.client import MODEL, get_client
from app.models.household_member import HouseholdMember
from app.models.item import Item, Status

DIGEST_SYSTEM_PROMPT = (
    "You write a short daily digest for a household-management app. Given a list of "
    "open household items (chores, bills, pet/baby care, social plans, prescriptions), "
    "write a concise, prioritized, plain-text summary grouped by domain — most urgent "
    "first. Keep it scannable on a phone screen or a text message: a few lines per "
    "domain at most, no headers beyond the domain name, no markdown formatting."
)


def _describe_item(item: Item, members_by_id: dict[int, HouseholdMember]) -> str:
    parts = [item.title]
    if item.due_at:
        parts.append(f"due {item.due_at.strftime('%b %d %I:%M %p')}")
    if item.assignee_id and item.assignee_id in members_by_id:
        parts.append(members_by_id[item.assignee_id].name)
    if item.escalation_level:
        parts.append(f"escalation level {item.escalation_level}")
    return f"- [{item.domain.value}] " + " · ".join(parts)


def generate_digest(session: Session) -> str:
    items = session.exec(
        select(Item)
        .where(Item.status.in_([Status.pending, Status.in_progress]))
        .order_by(Item.escalation_level.desc(), Item.due_at)
    ).all()
    members_by_id = {m.id: m for m in session.exec(select(HouseholdMember)).all()}

    if not items:
        return "Nothing open right now."

    item_lines = "\n".join(_describe_item(i, members_by_id) for i in items)

    client = get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=DIGEST_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": item_lines}],
    )
    return next(b.text for b in response.content if b.type == "text")
