from sqlmodel import Session, select

from app.actions import proposal as proposal_module
from app.agent.capture_tool import resolve_asset_id
from app.models.action_request import ActionRequest
from app.models.asset import Asset
from app.models.household_member import HouseholdMember
from app.models.item import Domain, Item
from app.models.vendor import Vendor


def test_create_vendor(client, session: Session):
    response = client.post(
        "/vendors",
        data={"name": "Joe's HVAC", "service_type": "HVAC", "phone": "+15551112222", "email": ""},
    )
    assert response.status_code == 200
    vendor = session.exec(select(Vendor).where(Vendor.name == "Joe's HVAC")).one()
    assert vendor.service_type == "HVAC"
    assert vendor.phone == "+15551112222"


def test_request_service_creates_item_and_texts_all_members(monkeypatch, client, session: Session):
    sent = []
    monkeypatch.setattr(proposal_module, "send_sms", lambda to, body: sent.append((to, body)) or "SMfake")

    for member in session.exec(select(HouseholdMember)).all():
        member.phone_e164 = f"+1555000{member.id:04d}"
        session.add(member)
    session.commit()

    vendor = Vendor(name="Green Lawn Co", service_type="Lawn Care", phone="+15559990000")
    session.add(vendor)
    session.commit()
    session.refresh(vendor)

    response = client.post(f"/vendors/{vendor.id}/request-service", data={"description": "mow the lawn"})
    assert response.status_code == 200

    item = session.exec(select(Item).where(Item.title == "mow the lawn")).one()
    assert item.domain == Domain.maintenance
    assert item.metadata_json["vendor_name"] == "Green Lawn Co"

    action_request = session.exec(select(ActionRequest).where(ActionRequest.item_id == item.id)).one()
    assert action_request.member_id is None  # unassigned -> notify everyone

    # Texted every member with a phone (2 seeded members).
    assert len(sent) == 2
    assert all("Green Lawn Co" in body for _, body in sent)
    assert all("+15559990000" in body for _, body in sent)


def test_create_asset_links_vendor(client, session: Session):
    vendor = Vendor(name="Joe's HVAC", phone="+15551112222")
    session.add(vendor)
    session.commit()
    session.refresh(vendor)

    response = client.post(
        "/assets",
        data={
            "name": "Upstairs AC unit",
            "category": "HVAC System",
            "location": "Attic",
            "vendor_id": str(vendor.id),
        },
    )
    assert response.status_code == 200
    asset = session.exec(select(Asset).where(Asset.name == "Upstairs AC unit")).one()
    assert asset.vendor_id == vendor.id


def test_report_issue_uses_linked_vendor(monkeypatch, client, session: Session):
    monkeypatch.setattr(proposal_module, "send_sms", lambda to, body: "SMfake")

    vendor = Vendor(name="Joe's HVAC", phone="+15551112222")
    session.add(vendor)
    session.commit()
    session.refresh(vendor)

    asset = Asset(name="Upstairs AC unit", vendor_id=vendor.id)
    session.add(asset)
    session.commit()
    session.refresh(asset)

    response = client.post(f"/assets/{asset.id}/report-issue", data={"description": "AC blowing warm air"})
    assert response.status_code == 200

    item = session.exec(select(Item).where(Item.title == "AC blowing warm air")).one()
    assert item.domain == Domain.maintenance
    assert item.metadata_json["asset_id"] == asset.id
    assert item.metadata_json["vendor_name"] == "Joe's HVAC"
    assert item.metadata_json["vendor_phone"] == "+15551112222"

    action_request = session.exec(select(ActionRequest).where(ActionRequest.item_id == item.id)).one()
    assert action_request.payload_json["provider"] == "Joe's HVAC"


def test_report_issue_without_vendor_does_not_crash(monkeypatch, client, session: Session):
    monkeypatch.setattr(proposal_module, "send_sms", lambda to, body: "SMfake")

    asset = Asset(name="Old dishwasher")
    session.add(asset)
    session.commit()
    session.refresh(asset)

    response = client.post(f"/assets/{asset.id}/report-issue", data={"description": ""})
    assert response.status_code == 200

    item = session.exec(select(Item).where(Item.title == "Old dishwasher needs service")).one()
    assert item.metadata_json["vendor_name"] is None


def test_resolve_asset_id_matches_loosely():
    assets = [(1, "Upstairs AC unit"), (2, "Dishwasher")]
    assert resolve_asset_id("AC", assets) == 1
    assert resolve_asset_id("dishwasher", assets) == 2
    assert resolve_asset_id("microwave", assets) is None
    assert resolve_asset_id(None, assets) is None
