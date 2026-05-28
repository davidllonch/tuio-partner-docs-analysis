"""
Root-level conftest.py — loaded by pytest BEFORE any test-package conftest.

Responsibilities:
1. Stub `weasyprint` so tests can run without the native GTK/Pango libraries
   (which are not available on Windows CI or without system packages).
2. Patch `create_async_engine` so that the `pool_size` and `max_overflow`
   kwargs used in app.database.get_engine() are silently dropped when the
   target URL is an in-memory SQLite connection (which does not support them).

Both patches must fire before any `app.*` module is imported, which is why
they live here rather than in tests/conftest.py.
"""

import sys
import types
from unittest.mock import patch
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# 1. Stub weasyprint (native C library not available in test environments)
# ---------------------------------------------------------------------------

_weasyprint_stub = types.ModuleType("weasyprint")


class _FakeHTML:
    """Minimal weasyprint.HTML stand-in that returns an empty PDF-like bytes."""

    def __init__(self, *args, **kwargs):
        pass

    def write_pdf(self):
        return b"%PDF-1.4 test-stub"


_weasyprint_stub.HTML = _FakeHTML
sys.modules.setdefault("weasyprint", _weasyprint_stub)

# ---------------------------------------------------------------------------
# 2. Patch create_async_engine to drop pool_size / max_overflow for SQLite
# ---------------------------------------------------------------------------

import sqlalchemy.ext.asyncio as _sqla_async

_real_create_async_engine = _sqla_async.create_async_engine


def _patched_create_async_engine(url, **kwargs):
    """
    Drop pool_size and max_overflow when using an in-memory SQLite URL.
    SQLite does not support these arguments; they are only valid for PostgreSQL.
    Also forces StaticPool so all connections in the same process share one
    in-memory database (required by aiosqlite in-memory mode).
    """
    url_str = str(url)
    if "sqlite" in url_str:
        kwargs.pop("pool_size", None)
        kwargs.pop("max_overflow", None)
        kwargs.pop("pool_pre_ping", None)
        kwargs.setdefault("connect_args", {})["check_same_thread"] = False
        kwargs["poolclass"] = StaticPool
    return _real_create_async_engine(url, **kwargs)


_sqla_async.create_async_engine = _patched_create_async_engine

# Also patch the name exported by the sqlalchemy.ext.asyncio package itself
# in case app code imported it directly (e.g. `from sqlalchemy.ext.asyncio import ...`)
import sqlalchemy.ext.asyncio
sqlalchemy.ext.asyncio.create_async_engine = _patched_create_async_engine
