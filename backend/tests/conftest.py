"""
Shared pytest fixtures for the KYC/KYB backend test suite.

Strategy
--------
- Uses SQLite (in-memory) instead of PostgreSQL so tests run without a
  running database server. SQLAlchemy's async engine supports SQLite via
  aiosqlite.
- The real UUID primary-key columns use PostgreSQL's native UUID type.
  SQLite does not have that type, so we override it with a VARCHAR
  equivalent by setting the 'native_enum' and dialect rendering flags.
- Each test gets a fresh, isolated database (function-scoped fixture).
- No external services (Anthropic, SMTP, slowapi rate-limiter) are called.
  Those are patched where needed.

Dependencies needed in addition to the main requirements.txt:
    pip install pytest pytest-asyncio httpx aiosqlite
"""

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Patch the database module BEFORE importing app code so every module that
# does `from app.database import Base` picks up our overridden metadata.
# ---------------------------------------------------------------------------

from app.database import Base
from app.models import analyst as _analyst_module  # noqa: F401 — registers the model
from app.models import submission as _submission_module  # noqa: F401
from app.models import analysis as _analysis_module  # noqa: F401
from app.models import audit as _audit_module  # noqa: F401

# ---------------------------------------------------------------------------
# SQLite-compatible async engine (in-memory, no file, no server required)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _make_engine():
    """
    Create an in-memory SQLite async engine.

    StaticPool ensures the same in-memory DB is shared across every
    connection in the same process (required for SQLite in-memory mode).
    check_same_thread=False is required for SQLite + asyncio.
    """
    return create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )


# ---------------------------------------------------------------------------
# Fake settings — prevent pydantic-settings from reading a missing .env file
# ---------------------------------------------------------------------------

from app.config import Settings


def make_test_settings() -> Settings:
    """Return a Settings instance with safe dummy values for testing."""
    return Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        JWT_SECRET_KEY="test-secret-key-that-is-long-enough",
        JWT_ALGORITHM="HS256",
        JWT_EXPIRE_HOURS=1,
        ANTHROPIC_API_KEY="sk-ant-test",
        OPENAI_API_KEY="sk-openai-test",
        SMTP_HOST="localhost",
        SMTP_PORT=25,
        SMTP_USER="test@example.com",
        SMTP_PASSWORD="password",
        REPORT_EMAIL_RECIPIENT="compliance@example.com",
        EMAIL_FROM_ADDRESS="noreply@example.com",
        DOCUMENTS_BASE_PATH="/tmp/kyc_test_docs",
        CORS_ORIGINS="http://localhost:5173",
    )


# ---------------------------------------------------------------------------
# pytest-asyncio configuration
# ---------------------------------------------------------------------------

pytest_plugins = ("pytest_asyncio",)


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def db_engine():
    """Create tables and yield the engine; drop tables after the test."""
    engine = _make_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh AsyncSession for each test."""
    factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    async with factory() as session:
        yield session


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Yield an HTTPX AsyncClient that talks directly to the FastAPI app
    (no network — pure in-process).

    Overrides:
    - get_db  -> our in-memory SQLite session
    - get_settings -> dummy Settings with the same JWT secret used to mint tokens
    - slowapi rate limiter -> disabled (returns None key so limits never fire)
    """
    from app.main import app
    from app.database import get_db
    from app.config import get_settings

    test_settings = make_test_settings()

    # Override the APScheduler startup so it doesn't try to connect to Postgres
    import app.services.cleanup as _cleanup
    _cleanup.create_cleanup_scheduler = lambda **_kwargs: _FakeScheduler()

    async def override_get_db():
        yield db_session

    def override_get_settings():
        return test_settings

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper: create an analyst directly in the DB (bypasses HTTP)
# ---------------------------------------------------------------------------


from app.auth.jwt import hash_password
from app.models.analyst import Analyst


async def create_analyst_in_db(
    session: AsyncSession,
    email: str = "analyst@example.com",
    password: str = "securepass123",
    full_name: str = "Test Analyst",
    is_active: bool = True,
) -> Analyst:
    analyst = Analyst(
        id=uuid.uuid4(),
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        created_at=datetime.now(timezone.utc),
        is_active=is_active,
    )
    session.add(analyst)
    await session.commit()
    await session.refresh(analyst)
    return analyst


# ---------------------------------------------------------------------------
# Helper: mint a JWT for a given analyst (bypasses HTTP login)
# ---------------------------------------------------------------------------


from app.auth.jwt import create_access_token


def make_token_for(analyst: Analyst, settings=None) -> str:
    if settings is None:
        settings = make_test_settings()
    return create_access_token(
        data={"sub": str(analyst.id)},
        secret=settings.JWT_SECRET_KEY,
        expire_hours=settings.JWT_EXPIRE_HOURS,
        algorithm=settings.JWT_ALGORITHM,
    )


# ---------------------------------------------------------------------------
# Fake APScheduler stub so the lifespan hook does not crash on startup
# ---------------------------------------------------------------------------


class _FakeScheduler:
    running = False

    def start(self):
        self.running = True

    def shutdown(self, wait=True):
        self.running = False
