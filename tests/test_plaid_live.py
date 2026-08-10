import pytest

pytestmark = pytest.mark.live_api


def test_create_link_token_succeeds():
    from app.integrations.plaid_client import create_link_token

    token = create_link_token(member_id=1)
    assert token.startswith("link-")
