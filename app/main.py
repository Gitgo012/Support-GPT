
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from app.api.routes.chat import router as chat_router
from app.api.routes.store import router as store_router
from app.services.chat_service import chat_service
from app.services.database import database
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.initialize()
    if os.getenv("SUPPORTGPT_LOAD_MODEL", "").lower() in {"1", "true", "yes"}:
        chat_service.load_model()

    yield


app = FastAPI(
    title="SupportGPT API",
    description="NovaMart demo store with a SQLite-backed SupportGPT assistant.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)

templates = Jinja2Templates(directory="app/templates")

app.include_router(
    chat_router,
    prefix="/api",
    tags=["Chat"],
)
app.include_router(
    store_router,
    prefix="/api",
    tags=["Store"],
)


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
    )