import pytest
from sqlmodel import Session, select

from app.models.asset import Asset
from app.models.item import Domain, Item
from app.models.vendor import Vendor

pytestmark = pytest.mark.live_api


def test_capture_recognizes_registered_asset(client, session: Session):
    vendor = Vendor(name="Joe's HVAC", phone="+15551112222")
    session.add(vendor)
    session.commit()
    session.refresh(vendor)

    session.add(Asset(name="Upstairs AC unit", vendor_id=vendor.id))
    session.commit()

    response = client.post("/api/capture", data={"text": "the AC is blowing warm air upstairs"})
    assert response.status_code == 200
    assert "Couldn't quite parse" not in response.text

    item = session.exec(select(Item).order_by(Item.id.desc())).first()
    assert item is not None
    assert item.domain == Domain.maintenance
    assert item.metadata_json.get("vendor_name") == "Joe's HVAC"
    assert item.metadata_json.get("vendor_phone") == "+15551112222"
