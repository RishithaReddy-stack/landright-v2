from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.api.auth import router as auth_router
from backend.api.profile import router as profile_router
from backend.api.chat import router as chat_router
from backend.api.tasks import router as tasks_router
from backend.api.documents import router as documents_router
from backend.api.notifications import router as notifications_router
from backend.services.scheduler import start_scheduler, stop_scheduler

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="LandRight API",
    description="AI Copilot for International Students",
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,          prefix="/api")
app.include_router(profile_router,       prefix="/api")
app.include_router(chat_router,          prefix="/api")
app.include_router(tasks_router,         prefix="/api")
app.include_router(documents_router,     prefix="/api")
app.include_router(notifications_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}
