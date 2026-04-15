import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.routers import auth as auth_router
from app.routers import submissions as submissions_router
from app.routers import analysts as analysts_router
from app.routers import invitations as invitations_router
from app.routers import declaration_templates as declaration_templates_router
from app.services.cleanup import create_cleanup_scheduler

# Configure structured logging for the entire application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Rate limiter — controls how many requests a single IP can make per hour.
# Think of it like a doorman who checks how many times someone has already
# come in tonight before letting them through again.
limiter = Limiter(key_func=get_remote_address, default_limits=[])

# Store the scheduler at module level so we can stop it cleanly on shutdown
_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown logic.
    FastAPI calls this automatically when the server starts and stops.
    """
    global _scheduler
    settings = get_settings()

    logger.info("Starting KYC/KYB Partner Documentation API v1.0.0")

    # Start the nightly document cleanup scheduler.
    _scheduler = create_cleanup_scheduler(
        documents_base_path=settings.DOCUMENTS_BASE_PATH,
        database_url=settings.DATABASE_URL,
    )
    _scheduler.start()
    logger.info("APScheduler started — document cleanup runs nightly at 02:00 UTC")

    yield  # The server is now running and handling requests

    # Graceful shutdown — wait for in-progress jobs to finish
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")

    logger.info("Application shutdown complete")


# Create the FastAPI application instance
app = FastAPI(
    title="KYC/KYB Partner Documentation API",
    version="1.0.0",
    description=(
        "Backend API for KYC/KYB compliance document analysis. "
        "Partners submit documents via the public endpoint; "
        "analysts review results through the protected endpoints."
    ),
    lifespan=lifespan,
)

# Attach the rate limiter to the app so slowapi middleware can find it
app.state.limiter = limiter

# Register the error handler that returns HTTP 429 when rate limit is exceeded
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS Middleware ──────────────────────────────────────────────────────────
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Register API routers ─────────────────────────────────────────────────────
app.include_router(auth_router.router, prefix="/api")
app.include_router(submissions_router.router, prefix="/api")
app.include_router(analysts_router.router, prefix="/api")
app.include_router(invitations_router.router, prefix="/api")
app.include_router(declaration_templates_router.router, prefix="/api")


# ── Health check (public, no auth required) ──────────────────────────────────
@app.get("/api/health", tags=["health"])
async def health_check():
    """
    Simple health check endpoint.
    Used by Docker, load balancers, and monitoring tools to verify the server is alive.
    """
    return {"status": "ok", "version": "1.0.0"}
