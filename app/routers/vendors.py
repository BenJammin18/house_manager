from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.actions.proposal import propose_action
from app.db import get_session
from app.models.action_request import ActionType
from app.models.item import CreatedBy, Domain, Item, Priority
from app.models.vendor import Vendor

router = APIRouter(prefix="/vendors")
templates = Jinja2Templates(directory="app/templates")


def _render_vendors(request: Request, session: Session) -> HTMLResponse:
    vendors = session.exec(select(Vendor).order_by(Vendor.name)).all()
    return templates.TemplateResponse(request, "partials/vendors_list.html", {"vendors": vendors})


@router.get("", response_class=HTMLResponse)
def list_vendors(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return _render_vendors(request, session)


@router.post("", response_class=HTMLResponse)
def create_vendor(
    request: Request,
    name: str = Form(...),
    service_type: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    session.add(
        Vendor(
            name=name,
            service_type=service_type or None,
            phone=phone or None,
            email=email or None,
            notes=notes or None,
        )
    )
    session.commit()
    return _render_vendors(request, session)


@router.post("/{vendor_id}/request-service", response_class=HTMLResponse)
def request_service(
    request: Request,
    vendor_id: int,
    description: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    vendor = session.get(Vendor, vendor_id)
    if vendor is not None:
        item = Item(
            domain=Domain.maintenance,
            item_type="vendor_service",
            title=description or f"Schedule service with {vendor.name}",
            priority=Priority.normal,
            metadata_json={
                "vendor_id": vendor.id,
                "vendor_name": vendor.name,
                "vendor_phone": vendor.phone,
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
            {"provider": vendor.name, "vendor_phone": vendor.phone},
        )
        session.commit()
    return _render_vendors(request, session)
