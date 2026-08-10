from datetime import date
from functools import lru_cache
from typing import Any, Optional

import certifi
import plaid
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest

from app.config import settings

_ENV_HOSTS = {
    "sandbox": plaid.Environment.Sandbox,
    "production": plaid.Environment.Production,
}


@lru_cache
def get_client() -> plaid_api.PlaidApi:
    configuration = plaid.Configuration(
        host=_ENV_HOSTS.get(settings.plaid_env, plaid.Environment.Sandbox),
        api_key={
            "clientId": settings.plaid_client_id,
            "secret": settings.plaid_secret,
        },
        # This machine's default OpenSSL trust store doesn't resolve certs
        # correctly (a local Python/Homebrew issue, not a Plaid one) — point
        # explicitly at certifi's bundle so this doesn't depend on the
        # SSL_CERT_FILE env var being set wherever the app happens to run.
        ssl_ca_cert=certifi.where(),
    )
    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


def create_link_token(member_id: int) -> str:
    request = LinkTokenCreateRequest(
        client_name="house_manager",
        language="en",
        country_codes=[CountryCode("US")],
        user=LinkTokenCreateRequestUser(client_user_id=str(member_id)),
        products=[Products("transactions")],
    )
    response = get_client().link_token_create(request)
    return response.link_token


def exchange_public_token(public_token: str) -> tuple[str, str]:
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = get_client().item_public_token_exchange(request)
    return response.access_token, response.item_id


def sync_transactions(access_token: str, cursor: Optional[str]) -> dict[str, Any]:
    request = TransactionsSyncRequest(access_token=access_token)
    if cursor:
        request.cursor = cursor
    response = get_client().transactions_sync(request)
    return {
        "added": response.added,
        "modified": response.modified,
        "removed": response.removed,
        "next_cursor": response.next_cursor,
        "has_more": response.has_more,
    }


def transaction_amount_cents(plaid_amount: float) -> int:
    """Plaid amounts are dollars, positive = money leaving the account (spend).
    That sign convention is exactly what we want for budget tracking."""
    return round(plaid_amount * 100)


def transaction_posted_date(txn) -> date:
    return txn.date


def transaction_category(txn) -> Optional[str]:
    personal_finance_category = getattr(txn, "personal_finance_category", None)
    if personal_finance_category and personal_finance_category.get("primary"):
        return personal_finance_category["primary"]
    category = getattr(txn, "category", None)
    if category:
        return category[0]
    return None
