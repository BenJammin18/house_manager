from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.actions.proposal import DOMAIN_TIER_C_ACTION, build_tier_c_payload, propose_action
from app.db import get_session
from app.models.action_request import ActionType
from app.models.household_member import HouseholdMember
from app.models.item import CreatedBy, Domain, Item, Priority, Status
from app.utils.time import to_utc_naive, utc_naive_now

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _render_item_list(request: Request, session: Session) -> HTMLResponse:
    items = session.exec(
        select(Item)
        .where(Item.status.in_([Status.pending, Status.in_progress]))
        .order_by(Item.domain, Item.due_at)
    ).all()
    members = {m.id: m for m in session.exec(select(HouseholdMember)).all()}

    grouped: dict[str, list[Item]] = {}
    for item in items:
        grouped.setdefault(item.domain.value, []).append(item)

    return templates.TemplateResponse(
        request,
        "partials/item_list.html",
        {"grouped": grouped, "members": members},
    )


@router.get("/items", response_class=HTMLResponse)
def list_items(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return _render_item_list(request, session)


@router.post("/items", response_class=HTMLResponse)
def create_item(
    request: Request,
    title: str = Form(...),
    domain: Domain = Form(...),
    item_type: str = Form(""),
    description: str = Form(""),
    priority: Priority = Form(Priority.normal),
    assignee_id: str = Form(""),
    due_at: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    parsed_due_at = to_utc_naive(datetime.fromisoformat(due_at)) if due_at else None
    item = Item(
        title=title,
        domain=domain,
        item_type=item_type or domain.value,
        description=description or None,
        priority=priority,
        assignee_id=int(assignee_id) if assignee_id else None,
        due_at=parsed_due_at,
        created_by=CreatedBy.user,
    )
    session.add(item)
    session.commit()
    return _render_item_list(request, session)


@router.post("/items/{item_id}/complete", response_class=HTMLResponse)
def complete_item(
    request: Request,
    item_id: int,
    completed_by_id: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    item = session.get(Item, item_id)
    if item is not None:
        item.status = Status.done
        item.completed_at = utc_naive_now()
        item.completed_by_id = int(completed_by_id) if completed_by_id else None
        item.updated_at = utc_naive_now()
        session.add(item)
        session.commit()
    return _render_item_list(request, session)


@router.post("/items/{item_id}/propose-payment", response_class=HTMLResponse)
def propose_payment(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    item = session.get(Item, item_id)
    if item is not None and item.domain == Domain.bill:
        payload = {
            "amount_cents": item.metadata_json.get("amount_cents"),
            "payee": item.metadata_json.get("payee"),
        }
        propose_action(session, item, ActionType.bill_pay, payload)
        session.commit()
    return _render_item_list(request, session)


@router.post("/items/{item_id}/propose-tier-c", response_class=HTMLResponse)
def propose_tier_c(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    item = session.get(Item, item_id)
    action_type = DOMAIN_TIER_C_ACTION.get(item.domain) if item is not None else None
    if item is not None and action_type is not None:
        payload = build_tier_c_payload(action_type, item)
        propose_action(session, item, action_type, payload)
        session.commit()
    return _render_item_list(request, session)


@router.post("/items/{item_id}/skip", response_class=HTMLResponse)
def skip_item(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    item = session.get(Item, item_id)
    if item is not None:
        item.status = Status.skipped
        item.updated_at = utc_naive_now()
        session.add(item)
        session.commit()
    return _render_item_list(request, session)
