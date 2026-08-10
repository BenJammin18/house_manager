import pytest

from app.agent.email_classify import classify_email

pytestmark = pytest.mark.live_api

CASES = [
    (
        "CONGRATULATIONS!!! You've won a $1000 gift card, click here NOW",
        "prizes@totally-legit-deals.ru",
        "Claim your free prize before it expires! Limited time offer, act now!!!",
        "spam",
    ),
    (
        "Your child's school picture day results are ready",
        "photos@schoolphotocompany.com",
        "View and order your child's school photos from picture day.",
        "normal",
    ),
    (
        "Reservation Confirmed: Dinner for 2 at Luigi's",
        "reservations@opentable.com",
        "Your table is booked for Friday, September 4th at 7:00 PM.",
        "calendar_candidate",
    ),
]


@pytest.mark.parametrize("subject,sender,snippet,expected", CASES)
def test_classify_email_matches_expected_category(subject, sender, snippet, expected):
    result = classify_email(subject, sender, snippet)
    assert result["classification"] == expected
    if expected == "calendar_candidate":
        assert result.get("extracted_event", {}).get("due_at_iso")
