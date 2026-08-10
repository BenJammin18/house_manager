from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import (
    assets,
    budgets,
    capture,
    dashboard,
    items,
    oauth,
    plaid_router,
    rules,
    vendors,
    webhooks,
)
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="house_manager", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(dashboard.router)
app.include_router(items.router)
app.include_router(capture.router)
app.include_router(oauth.router)
app.include_router(rules.router)
app.include_router(budgets.router)
app.include_router(plaid_router.router)
app.include_router(vendors.router)
app.include_router(assets.router)
app.include_router(webhooks.router)
