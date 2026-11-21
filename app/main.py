
from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes.chat import router as chat_router
from app.api.routes.store import router as store_router
from app.services.chat_service import chat_service
from app.services.database import database
from app.services.rate_limiter import ChatRateLimiter


logger = logging.getLogger(__name__)
chat_rate_limiter = ChatRateLimiter(max_requests=10, window_seconds=60)


def chat_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.initialize()
    if os.getenv("SUPPORTGPT_LOAD_MODEL", "").lower() in {"1", "true", "yes"}:
        try:
            chat_service.load_model()
        except Exception as exc:
            logger.error(
                "SupportGPT model initialization failed (%s); continuing in demo mode.",
                type(exc).__name__,
            )

    yield


app = FastAPI(
    title="SupportGPT API",
    description="NovaMart demo store with a SQLite-backed SupportGPT assistant.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def limit_chat_requests(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/api/chat":
        client_ip = chat_client_ip(request)
        retry_after = chat_rate_limiter.retry_after(client_ip)
        if retry_after is not None:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many chat requests. Please wait before trying again."},
                headers={"Retry-After": str(retry_after)},
            )
    return await call_next(request)


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