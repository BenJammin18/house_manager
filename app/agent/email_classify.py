from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.agent.client import MODEL, get_client
from app.config import settings

CLASSIFY_EMAIL_TOOL = {
    "name": "classify_email",
    "description": "Classify one inbox email for a household-management app and decide what, if anything, to do with it.",
    "input_schema": {
        "type": "object",
        "properties": {
            "classification": {
                "type": "string",
                "enum": ["spam", "important", "normal", "calendar_candidate"],
                "description": (
                    "spam: junk/promotional/phishing, safe to move to Trash. "
                    "important: needs a human's attention soon (bill notice, school notice, "
                    "medical result, time-sensitive request) but isn't itself a calendar event. "
                    "calendar_candidate: describes a specific scheduled event/appointment/reservation "
                    "with an extractable date and time. "
                    "normal: everything else — no action needed."
                ),
            },
            "reason": {"type": "string", "description": "One short sentence explaining the classification."},
            "extracted_event": {
                "type": "object",
                "description": "Required when classification is calendar_candidate, omitted otherwise.",
                "properties": {
                    "title": {"type": "string"},
                    "due_at_iso": {
                        "type": "string",
                        "description": "ISO 8601 datetime with timezone offset for the event.",
                    },
                    "description": {"type": "string"},
                },
            },
        },
        "required": ["classification", "reason"],
    },
}


def _system_prompt() -> str:
    now = datetime.now(ZoneInfo(settings.timezone))
    return (
        "You triage one inbox email for a family household-management app. "
        f"Today's date/time is {now.isoformat()} ({settings.timezone}). "
        "Be conservative about 'spam' — only classify it as spam if you're confident "
        "it's junk, promotional, or phishing; when in doubt, classify as 'normal' rather "
        "than risking a real email being moved to Trash. Only use 'calendar_candidate' "
        "when there's a specific, extractable date/time for a real event."
    )


def classify_email(subject: str, sender: str, snippet: str) -> dict[str, Any]:
    client = get_client()
    content = f"From: {sender}\nSubject: {subject}\nSnippet: {snippet}"
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=_system_prompt(),
        tools=[CLASSIFY_EMAIL_TOOL],
        tool_choice={"type": "tool", "name": "classify_email"},
        messages=[{"role": "user", "content": content}],
    )
    tool_use = next(b for b in response.content if b.type == "tool_use")
    return tool_use.input
