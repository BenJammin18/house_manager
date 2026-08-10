import pytest
from sqlmodel import Session, select

from app.models.item import Domain, Item

pytestmark = pytest.mark.live_api

CASES = [
    ("Fluffy has a vet checkup next Tuesday at 3pm", Domain.pet),
    ("pay the water bill by the 15th, it's $62.40", Domain.bill),
    ("take out the trash every Tuesday night", Domain.chore),
    ("clean the gutters sometime this fall", Domain.maintenance),
    ("dinner with the Johnsons this Friday at 7pm", Domain.social),
    ("refill Mia's amoxicillin at CVS", Domain.prescription),
    ("baby's 6 month checkup with Dr. Lee next Wednesday at 10am", Domain.baby),
]


@pytest.mark.parametrize("text,expected_domain", CASES)
def test_capture_extracts_expected_domain(client, session: Session, text: str, expected_domain: Domain):
    response = client.post("/api/capture", data={"text": text})
    assert response.status_code == 200
    assert "Couldn't quite parse" not in response.text

    item = session.exec(select(Item).order_by(Item.id.desc())).first()
    assert item is not None
    assert item.domain == expected_domain
    assert item.title
