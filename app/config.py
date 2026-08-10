from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HOUSE_MANAGER_", env_file=".env")

    database_url: str = "sqlite:///./house_manager.db"
    timezone: str = "America/New_York"

    anthropic_api_key: Optional[str] = None

    # Twilio: either account_sid + auth_token, or account_sid + api_key_sid/secret.
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_api_key_sid: Optional[str] = None
    twilio_api_key_secret: Optional[str] = None
    twilio_from_number: Optional[str] = None

    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://localhost:8000/oauth/google/callback"

    # Fernet key for encrypting OAuth/API tokens at rest. Generate with
    # `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
    encryption_key: Optional[str] = None

    plaid_client_id: Optional[str] = None
    plaid_secret: Optional[str] = None
    plaid_env: str = "sandbox"


settings = Settings()
