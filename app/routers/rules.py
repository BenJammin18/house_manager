from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.models.auto_approve_rule import AutoApproveRule
from app.models.item import Domain

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _render_rules(request: Request, session: Session) -> HTMLResponse:
    rules = session.exec(select(AutoApproveRule).order_by(AutoApproveRule.id.desc())).all()
    return templates.TemplateResponse(request, "partials/rules_list.html", {"rules": rules})


@router.get("/rules", response_class=HTMLResponse)
def list_rules(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return _render_rules(request, session)


@router.post("/rules", response_class=HTMLResponse)
def create_rule(
    request: Request,
    domain: Domain = Form(...),
    item_type: str = Form(""),
    max_amount_cents: str = Form(""),
    vendor: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    condition: dict = {}
    if max_amount_cents:
        condition["max_amount_cents"] = int(float(max_amount_cents) * 100)
    if vendor:
        condition["vendor"] = vendor

    rule = AutoApproveRule(domain=domain, item_type=item_type, condition_json=condition)
    session.add(rule)
    session.commit()
    return _render_rules(request, session)


@router.post("/rules/{rule_id}/toggle", response_class=HTMLResponse)
def toggle_rule(
    request: Request, rule_id: int, session: Session = Depends(get_session)
) -> HTMLResponse:
    rule = session.get(AutoApproveRule, rule_id)
    if rule is not None:
        rule.active = not rule.active
        session.add(rule)
        session.commit()
    return _render_rules(request, session)
