from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.agent.budget import propose_budget_categories
from app.db import get_session
from app.models.budget_category import BudgetCategory, BudgetCreatedBy

router = APIRouter(prefix="/budgets")
templates = Jinja2Templates(directory="app/templates")


def _render_budgets(request: Request, session: Session) -> HTMLResponse:
    categories = session.exec(select(BudgetCategory).order_by(BudgetCategory.id.desc())).all()
    return templates.TemplateResponse(request, "partials/budgets_list.html", {"categories": categories})


@router.get("", response_class=HTMLResponse)
def list_budgets(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return _render_budgets(request, session)


@router.post("", response_class=HTMLResponse)
def create_budget(
    request: Request,
    name: str = Form(...),
    monthly_amount: str = Form(...),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    category = BudgetCategory(
        name=name,
        monthly_amount_cents=int(float(monthly_amount) * 100),
        created_by=BudgetCreatedBy.user,
    )
    session.add(category)
    session.commit()
    return _render_budgets(request, session)


@router.post("/{category_id}/toggle", response_class=HTMLResponse)
def toggle_budget(
    request: Request, category_id: int, session: Session = Depends(get_session)
) -> HTMLResponse:
    category = session.get(BudgetCategory, category_id)
    if category is not None:
        category.active = not category.active
        session.add(category)
        session.commit()
    return _render_budgets(request, session)


@router.post("/propose", response_class=HTMLResponse)
def propose_budgets(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    proposals = propose_budget_categories(session)
    for proposal in proposals:
        session.add(
            BudgetCategory(
                name=proposal["name"],
                monthly_amount_cents=proposal["monthly_amount_cents"],
                created_by=BudgetCreatedBy.agent,
                active=False,
            )
        )
    session.commit()
    return _render_budgets(request, session)
