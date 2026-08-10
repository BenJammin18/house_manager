from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.agent.capture_tool import capture_item, resolve_assignee_id, resolve_asset_id
from app.db import get_session
from app.models.asset import Asset
from app.models.household_member import HouseholdMember
from app.models.item import CreatedBy, Domain, Item, Priority, Status
from app.models.vendor import Vendor
from app.schemas.metadata import validate_metadata
from app.utils.time import to_utc_naive

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.post("/api/capture", response_class=HTMLResponse)
def capture(
    request: Request,
    text: str = Form(...),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    members = session.exec(select(HouseholdMember)).all()
    member_pairs = [(m.id, m.name) for m in members]
    assets = session.exec(select(Asset)).all()
    asset_pairs = [(a.id, a.name) for a in assets]

    extracted = capture_item(text, [name for _, name in member_pairs], [name for _, name in asset_pairs])

    if extracted.get("needs_clarification"):
        return templates.TemplateResponse(
            request,
            "partials/capture_result.html",
            {"error": extracted["needs_clarification"], "item": None},
        )
    return _create_and_render(request, session, extracted, member_pairs, members, assets)


def _create_and_render(
    request: Request,
    session: Session,
    extracted: dict,
    member_pairs: list[tuple[int, str]],
    members: list[HouseholdMember],
    assets: list[Asset],
) -> HTMLResponse:

    domain = Domain(extracted["domain"])
    metadata = validate_metadata(domain, extracted.get("metadata") or {})

    asset_id = resolve_asset_id(extracted.get("asset_name"), [(a.id, a.name) for a in assets])
    if asset_id is not None:
        asset = next(a for a in assets if a.id == asset_id)
        vendor = session.get(Vendor, asset.vendor_id) if asset.vendor_id else None
        metadata = {
            **metadata,
            "asset_id": asset.id,
            "vendor_id": vendor.id if vendor else None,
            "vendor_name": vendor.name if vendor else None,
            "vendor_phone": vendor.phone if vendor else None,
        }

    due_at = (
        to_utc_naive(datetime.fromisoformat(extracted["due_at_iso"]))
        if extracted.get("due_at_iso")
        else None
    )

    item = Item(
        domain=domain,
        item_type=extracted["item_type"],
        title=extracted["title"],
        description=extracted.get("description"),
        priority=Priority(extracted["priority"]) if extracted.get("priority") else Priority.normal,
        assignee_id=resolve_assignee_id(extracted.get("assignee_name"), member_pairs),
        due_at=due_at,
        due_date_only=bool(extracted.get("due_date_only", False)),
        recurrence_rule=extracted.get("recurrence_rule"),
        metadata_json=metadata,
        created_by=CreatedBy.agent,
        status=Status.pending,
    )
    session.add(item)
    session.commit()
    session.refresh(item)

    members_by_id = {m.id: m for m in members}
    return templates.TemplateResponse(
        request,
        "partials/capture_result.html",
        {
            "error": None,
            "item": item,
            "assignee": members_by_id.get(item.assignee_id) if item.assignee_id else None,
        },
        headers={"HX-Trigger": "item-captured"},
    )
