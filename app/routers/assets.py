from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.actions.proposal import propose_action
from app.db import get_session
from app.models.action_request import ActionType
from app.models.asset import Asset
from app.models.item import CreatedBy, Domain, Item, Priority
from app.models.vendor import Vendor

router = APIRouter(prefix="/assets")
templates = Jinja2Templates(directory="app/templates")


def _render_assets(request: Request, session: Session) -> HTMLResponse:
    assets = session.exec(select(Asset).order_by(Asset.name)).all()
    vendors_by_id = {v.id: v for v in session.exec(select(Vendor)).all()}
    return templates.TemplateResponse(
        request, "partials/assets_list.html", {"assets": assets, "vendors_by_id": vendors_by_id}
    )


@router.get("", response_class=HTMLResponse)
def list_assets(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return _render_assets(request, session)


@router.post("", response_class=HTMLResponse)
def create_asset(
    request: Request,
    name: str = Form(...),
    category: str = Form(""),
    location: str = Form(""),
    vendor_id: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    session.add(
        Asset(
            name=name,
            category=category or None,
            location=location or None,
            vendor_id=int(vendor_id) if vendor_id else None,
        )
    )
    session.commit()
    return _render_assets(request, session)


@router.post("/{asset_id}/report-issue", response_class=HTMLResponse)
def report_issue(
    request: Request,
    asset_id: int,
    description: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    asset = session.get(Asset, asset_id)
    if asset is not None:
        vendor = session.get(Vendor, asset.vendor_id) if asset.vendor_id else None
        item = Item(
            domain=Domain.maintenance,
            item_type="repair",
            title=description or f"{asset.name} needs service",
            priority=Priority.high,
            metadata_json={
                "asset_id": asset.id,
                "vendor_id": vendor.id if vendor else None,
                "vendor_name": vendor.name if vendor else None,
                "vendor_phone": vendor.phone if vendor else None,
            },
            created_by=CreatedBy.user,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        propose_action(
            session,
            item,
            ActionType.book_appointment,
            {
                "provider": vendor.name if vendor else None,
                "vendor_phone": vendor.phone if vendor else None,
            },
        )
        session.commit()
    return _render_assets(request, session)
