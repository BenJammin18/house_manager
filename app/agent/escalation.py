from typing import Any, Optional

from sqlmodel import Session, select

from app.agent.client import MODEL, get_client
from app.models.household_member import HouseholdMember
from app.models.item import Item
from app.models.nudge_log import NudgeLog

DECIDE_ESCALATION_TOOL = {
    "name": "decide_escalation_action",
    "description": (
        "Decide how to escalate a household task/bill/appointment that has been "
        "nudged twice already and is still open. Choose the option that's most "
        "likely to actually get it handled."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["renudge", "reassign", "mark_urgent"],
                "description": (
                    "renudge: text the current assignee again with a firmer tone. "
                    "reassign: hand it to the other household member instead. "
                    "mark_urgent: raise priority and text the current assignee."
                ),
            },
            "message": {
                "type": "string",
                "description": "The SMS text to send. Short, direct, no guilt-tripping.",
            },
            "suggested_assignee_name": {
                "type": "string",
                "description": "Household member name to reassign to. Required when action is reassign.",
            },
        },
        "required": ["action", "message"],
    },
}


def _system_prompt() -> str:
    return (
        "You are the escalation-judgment step of a household-management app. An item "
        "has already been nudged at two mechanical thresholds (due-soon and 24h-overdue) "
        "and is still not done. Decide whether to nudge the same person again, reassign "
        "it to the other household member, or mark it urgent. Keep the SMS message short "
        "(under 200 characters), direct, and free of guilt-tripping or passive aggression."
    )


def decide_escalation_action(
    item: Item, nudge_logs: list[NudgeLog], members: list[HouseholdMember]
) -> dict[str, Any]:
    members_by_id = {m.id: m for m in members}
    current_assignee = members_by_id.get(item.assignee_id) if item.assignee_id else None
    other_members = [m for m in members if m.id != item.assignee_id]

    context_lines = [
        f"Item: {item.title} (domain: {item.domain.value}, priority: {item.priority.value})",
        f"Due: {item.due_at.isoformat() if item.due_at else 'no specific time'}",
        f"Currently assigned to: {current_assignee.name if current_assignee else 'unassigned'}",
        f"Other household members: {', '.join(m.name for m in other_members) or 'none'}",
        f"Times nudged so far: {len(nudge_logs)}",
    ]

    client = get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=_system_prompt(),
        tools=[DECIDE_ESCALATION_TOOL],
        tool_choice={"type": "tool", "name": "decide_escalation_action"},
        messages=[{"role": "user", "content": "\n".join(context_lines)}],
    )
    tool_use = next(b for b in response.content if b.type == "tool_use")
    return tool_use.input


def resolve_assignee_by_name(name: Optional[str], members: list[HouseholdMember]) -> Optional[int]:
    if not name:
        return None
    needle = name.strip().lower()
    for member in members:
        if member.name.strip().lower() == needle:
            return member.id
    return None


def get_nudge_history(session: Session, item_id: int) -> list[NudgeLog]:
    return session.exec(
        select(NudgeLog).where(NudgeLog.item_id == item_id).order_by(NudgeLog.sent_at)
    ).all()
