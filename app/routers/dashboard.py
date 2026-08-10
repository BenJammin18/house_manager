from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.models.asset import Asset
from app.models.auto_approve_rule import AutoApproveRule
from app.models.budget_category import BudgetCategory
from app.models.calendar_account import CalendarAccount
from app.models.email_account import EmailAccount
from app.models.household_member import HouseholdMember
from app.models.item import Domain, Item, Priority, Status
from app.models.linked_account import LinkedAccount
from app.models.vendor import Vendor

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    items = session.exec(
        select(Item)
        .where(Item.status.in_([Status.pending, Status.in_progress]))
        .order_by(Item.domain, Item.due_at)
    ).all()
    members = session.exec(select(HouseholdMember)).all()
    members_by_id = {m.id: m for m in members}
    linked_member_ids = {
        a.member_id
        for a in session.exec(select(CalendarAccount).where(CalendarAccount.active)).all()
    }
    email_linked_member_ids = {
        a.member_id for a in session.exec(select(EmailAccount).where(EmailAccount.active)).all()
    }
    rules = session.exec(select(AutoApproveRule).order_by(AutoApproveRule.id.desc())).all()
    linked_accounts = session.exec(
        select(LinkedAccount).where(LinkedAccount.active).order_by(LinkedAccount.id)
    ).all()
    categories = session.exec(select(BudgetCategory).order_by(BudgetCategory.id.desc())).all()
    vendors = session.exec(select(Vendor).order_by(Vendor.name)).all()
    assets = session.exec(select(Asset).order_by(Asset.name)).all()
    vendors_by_id = {v.id: v for v in vendors}

    grouped: dict[str, list[Item]] = {}
    for item in items:
        grouped.setdefault(item.domain.value, []).append(item)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "grouped": grouped,
            "members": members_by_id,
            "all_members": members,
            "linked_member_ids": linked_member_ids,
            "email_linked_member_ids": email_linked_member_ids,
            "rules": rules,
            "linked_accounts": linked_accounts,
            "categories": categories,
            "vendors": vendors,
            "assets": assets,
            "vendors_by_id": vendors_by_id,
            "domains": list(Domain),
            "priorities": list(Priority),
        },
    )
