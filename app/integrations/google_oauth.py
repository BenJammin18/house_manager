import requests
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app.config import settings
from app.integrations.crypto import decrypt_token

# One combined consent grant covers both Calendar and Gmail so the user only
# authorizes once per Google account. gmail.modify (not the broader
# mail.google.com scope) allows Trash + labels only — no send-as, no
# permanent delete.
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

TOKEN_URI = "https://oauth2.googleapis.com/token"
USERINFO_URI = "https://www.googleapis.com/oauth2/v2/userinfo"


def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": TOKEN_URI,
            "redirect_uris": [settings.google_redirect_uri],
        }
    }


def build_auth_url(state: str) -> str:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state)
    flow.redirect_uri = settings.google_redirect_uri
    auth_url, _ = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    return auth_url


def exchange_code(code: str) -> tuple[Credentials, str]:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = settings.google_redirect_uri
    flow.fetch_token(code=code)
    creds = flow.credentials

    userinfo = requests.get(
        USERINFO_URI, headers={"Authorization": f"Bearer {creds.token}"}, timeout=10
    )
    userinfo.raise_for_status()
    email = userinfo.json()["email"]
    return creds, email


def credentials_from_encrypted_token(encrypted_refresh_token: str) -> Credentials:
    creds = Credentials(
        token=None,
        refresh_token=decrypt_token(encrypted_refresh_token),
        token_uri=TOKEN_URI,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=SCOPES,
    )
    creds.refresh(GoogleAuthRequest())
    return creds
