from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.agent.client import MODEL, get_client
from app.config import settings

CREATE_OR_UPDATE_ITEM_TOOL = {
    "name": "create_or_update_item",
    "description": (
        "Create a household task/event item from a natural-language description. "
        "Covers chores, home maintenance, pet care, baby care, bills, social/family "
        "scheduling, and prescriptions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "enum": ["chore", "maintenance", "pet", "baby", "bill", "social", "prescription"],
            },
            "item_type": {
                "type": "string",
                "description": "Short snake_case subtype, e.g. vet_appt, water_bill, trash_day.",
            },
            "title": {"type": "string", "description": "Short human-readable title."},
            "description": {"type": "string", "description": "Optional extra detail."},
            "due_at_iso": {
                "type": "string",
                "description": (
                    "ISO 8601 datetime (with timezone offset) if a specific date/time is "
                    "known or can be inferred from today's date. Omit if there is no due date."
                ),
            },
            "due_date_only": {
                "type": "boolean",
                "description": "True if only a date matters (e.g. 'by the 15th'), not a specific time.",
            },
            "recurrence_rule": {
                "type": "string",
                "description": "RFC5545 RRULE if this recurs, e.g. FREQ=WEEKLY;BYDAY=TU. Omit for one-off items.",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "normal", "high", "urgent"],
            },
            "assignee_name": {
                "type": "string",
                "description": "Household member's name if one is mentioned or clearly implied, else omit.",
            },
            "asset_name": {
                "type": "string",
                "description": (
                    "If this is about a registered home asset/appliance (e.g. 'AC', 'dishwasher'), "
                    "the matching asset name from the provided list. Omit if none match or none apply."
                ),
            },
            "metadata": {
                "type": "object",
                "description": (
                    "Domain-specific extra fields, e.g. amount_cents/payee for a bill, "
                    "pet_name/vet_name for a pet item, medication_name/pharmacy for a prescription."
                ),
            },
            "needs_clarification": {
                "type": "string",
                "description": (
                    "Set this instead of guessing if the input is too ambiguous to extract "
                    "confidently (e.g. no domain or title can be determined). Explain what's unclear."
                ),
            },
        },
        "required": ["domain", "item_type", "title"],
    },
}


def _system_prompt(member_names: list[str], asset_names: list[str]) -> str:
    now = datetime.now(ZoneInfo(settings.timezone))
    return (
        "You extract a single household task/event from free text into a structured item "
        "for a family household-management app. "
        f"Today's date/time is {now.isoformat()} ({settings.timezone}). "
        f"Household members: {', '.join(member_names) or 'none configured'}. "
        f"Registered home assets/appliances: {', '.join(asset_names) or 'none configured'}. "
        "Resolve relative dates ('next Tuesday', 'by the 15th') against today's date. "
        "If the text clearly refers to one of the registered assets (even loosely, e.g. "
        "'AC' matching 'Upstairs AC unit'), set asset_name to that exact registered name "
        "and use domain 'maintenance'. "
        "If the text is too ambiguous to extract confidently, use needs_clarification "
        "instead of guessing."
    )


def capture_item(text: str, member_names: list[str], asset_names: list[str] | None = None) -> dict[str, Any]:
    client = get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_system_prompt(member_names, asset_names or []),
        tools=[CREATE_OR_UPDATE_ITEM_TOOL],
        tool_choice={"type": "tool", "name": "create_or_update_item"},
        messages=[{"role": "user", "content": text}],
    )
    tool_use = next(b for b in response.content if b.type == "tool_use")
    return tool_use.input


def resolve_assignee_id(
    assignee_name: Optional[str], members: list[tuple[int, str]]
) -> Optional[int]:
    if not assignee_name:
        return None
    needle = assignee_name.strip().lower()
    for member_id, name in members:
        if name.strip().lower() == needle:
            return member_id
    for member_id, name in members:
        if needle in name.strip().lower() or name.strip().lower() in needle:
            return member_id
    return None


def resolve_asset_id(asset_name: Optional[str], assets: list[tuple[int, str]]) -> Optional[int]:
    if not asset_name:
        return None
    needle = asset_name.strip().lower()
    for asset_id, name in assets:
        if name.strip().lower() == needle:
            return asset_id
    for asset_id, name in assets:
        if needle in name.strip().lower() or name.strip().lower() in needle:
            return asset_id
    return None
