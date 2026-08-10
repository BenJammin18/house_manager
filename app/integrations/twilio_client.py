from functools import lru_cache

from twilio.request_validator import RequestValidator
from twilio.rest import Client

from app.config import settings


class TwilioNotConfigured(RuntimeError):
    pass


@lru_cache
def _client() -> Client:
    if not settings.twilio_account_sid:
        raise TwilioNotConfigured("HOUSE_MANAGER_TWILIO_ACCOUNT_SID is not set")
    if settings.twilio_api_key_sid and settings.twilio_api_key_secret:
        return Client(
            settings.twilio_api_key_sid,
            settings.twilio_api_key_secret,
            settings.twilio_account_sid,
        )
    if settings.twilio_auth_token:
        return Client(settings.twilio_account_sid, settings.twilio_auth_token)
    raise TwilioNotConfigured(
        "Set either HOUSE_MANAGER_TWILIO_AUTH_TOKEN or "
        "HOUSE_MANAGER_TWILIO_API_KEY_SID/SECRET"
    )


def send_sms(to: str, body: str) -> str:
    if not settings.twilio_from_number:
        raise TwilioNotConfigured("HOUSE_MANAGER_TWILIO_FROM_NUMBER is not set")
    message = _client().messages.create(to=to, from_=settings.twilio_from_number, body=body)
    return message.sid


def validate_webhook_signature(url: str, params: dict, signature: str) -> bool:
    """Verifies an inbound webhook actually came from Twilio. Requires the
    account's Auth Token (distinct from an API Key secret) — fails closed
    (returns False) if it isn't configured, since this endpoint can trigger
    real actions."""
    if not settings.twilio_auth_token:
        return False
    validator = RequestValidator(settings.twilio_auth_token)
    return validator.validate(url, params, signature)
