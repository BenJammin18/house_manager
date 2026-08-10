from functools import lru_cache

from googleapiclient.discovery import build

from app.integrations.google_oauth import credentials_from_encrypted_token
from app.models.email_account import EmailAccount

IMPORTANT_LABEL_NAME = "house_manager/important"


def _service(account: EmailAccount):
    creds = credentials_from_encrypted_token(account.oauth_refresh_token_encrypted)
    return build("gmail", "v1", credentials=creds)


def list_recent_message_ids(account: EmailAccount, max_results: int = 20) -> list[str]:
    service = _service(account)
    result = (
        service.users()
        .messages()
        .list(userId="me", labelIds=["INBOX"], maxResults=max_results)
        .execute()
    )
    return [m["id"] for m in result.get("messages", [])]


def get_message_summary(account: EmailAccount, message_id: str) -> dict:
    service = _service(account)
    message = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "Subject"],
        )
        .execute()
    )
    headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}
    return {
        "id": message_id,
        "subject": headers.get("Subject", ""),
        "sender": headers.get("From", ""),
        "snippet": message.get("snippet", ""),
    }


def trash_message(account: EmailAccount, message_id: str) -> None:
    service = _service(account)
    service.users().messages().trash(userId="me", id=message_id).execute()


def _get_or_create_important_label_id(service) -> str:
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"] == IMPORTANT_LABEL_NAME:
            return label["id"]
    created = (
        service.users()
        .labels()
        .create(
            userId="me",
            body={
                "name": IMPORTANT_LABEL_NAME,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )
        .execute()
    )
    return created["id"]


def label_important(account: EmailAccount, message_id: str) -> None:
    service = _service(account)
    label_id = _get_or_create_important_label_id(service)
    service.users().messages().modify(
        userId="me", id=message_id, body={"addLabelIds": [label_id]}
    ).execute()
