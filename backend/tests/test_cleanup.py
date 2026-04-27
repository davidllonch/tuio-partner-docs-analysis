"""
Integration tests for app.services.cleanup.cleanup_old_documents.

Strategy:
- Use the shared in-memory SQLite DB (db_session fixture from conftest).
- Use tmp_path (pytest built-in) for a real temporary filesystem directory.
- Patch app.database.AsyncSessionLocal so cleanup_old_documents uses our
  test session instead of the production database.

GDPR scenarios covered:
1. Document older than 90 days  → file deleted, DB record removed
2. Document newer than 90 days  → file untouched, DB record kept
3. Document path outside base   → file NOT deleted, DB record kept
4. File missing from disk       → DB record still deleted (no crash)
5. Old submission with no docs  → PII fields anonymised
6. Old submission WITH docs     → NOT anonymised (docs still present)
"""

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio

from sqlalchemy import select

from app.models.submission import Document, Submission
from app.services.cleanup import cleanup_old_documents


# ---------------------------------------------------------------------------
# Patch helper: replace AsyncSessionLocal with a factory that returns
# the test session wrapped in a context manager.
# ---------------------------------------------------------------------------


def _make_session_factory(session):
    """
    Return a callable that behaves like async_sessionmaker() when used as:

        async with AsyncSessionLocal() as sess:
            ...

    We must NOT close the test session between calls, so the context manager
    is a no-op on __aexit__.
    """
    @asynccontextmanager
    async def _factory():
        yield session

    class _Callable:
        def __call__(self):
            return _factory()

    return _Callable()


# ---------------------------------------------------------------------------
# Fixture: a real temp directory to act as DOCUMENTS_BASE_PATH
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
def docs_base(tmp_path):
    """Return path string for the documents base directory."""
    return str(tmp_path)


def _write_file(path: str, content: bytes = b"fake file") -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def _create_submission_record(
    session,
    provider_name: str = "Acme S.L.",
    days_old: int = 0,
    partner_info: str | None = None,
    contract_data: str | None = None,
    ai_response: str | None = None,
) -> Submission:
    created_at = datetime.now(timezone.utc) - timedelta(days=days_old)
    sub = Submission(
        id=uuid.uuid4(),
        created_at=created_at,
        provider_name=provider_name,
        provider_type="correduria_seguros",
        entity_type="PJ",
        country="ES",
        status="complete",
        partner_info=partner_info,
        contract_data=contract_data,
        ai_response=ai_response,
    )
    session.add(sub)
    await session.flush()
    return sub


async def _create_document_record(
    session,
    submission_id: uuid.UUID,
    file_path: str,
    days_old: int = 0,
) -> Document:
    uploaded_at = datetime.now(timezone.utc) - timedelta(days=days_old)
    doc = Document(
        id=uuid.uuid4(),
        submission_id=submission_id,
        original_filename="test.pdf",
        user_label="Escrituras",
        file_path=file_path,
        mime_type="application/pdf",
        size_bytes=100,
        uploaded_at=uploaded_at,
    )
    session.add(doc)
    await session.flush()
    return doc


# ---------------------------------------------------------------------------
# Test 1: old document — file deleted and DB record removed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_old_document_is_deleted_from_disk_and_db(db_session, docs_base):
    sub = await _create_submission_record(db_session, days_old=91)
    sub_dir = os.path.join(docs_base, str(sub.id))
    file_path = os.path.join(sub_dir, "old_doc.pdf")
    _write_file(file_path)

    doc = await _create_document_record(
        db_session, sub.id, file_path, days_old=91
    )
    await db_session.commit()

    doc_id = doc.id

    with patch("app.database.AsyncSessionLocal", _make_session_factory(db_session)):
        await cleanup_old_documents(docs_base, "sqlite://")

    # File must be gone from disk
    assert not os.path.exists(file_path)

    # DB record must be removed
    result = await db_session.execute(select(Document).where(Document.id == doc_id))
    assert result.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# Test 2: recent document — file and DB record untouched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recent_document_is_not_deleted(db_session, docs_base):
    sub = await _create_submission_record(db_session, days_old=5)
    sub_dir = os.path.join(docs_base, str(sub.id))
    file_path = os.path.join(sub_dir, "recent.pdf")
    _write_file(file_path)

    doc = await _create_document_record(
        db_session, sub.id, file_path, days_old=5
    )
    await db_session.commit()

    doc_id = doc.id

    with patch("app.database.AsyncSessionLocal", _make_session_factory(db_session)):
        await cleanup_old_documents(docs_base, "sqlite://")

    # File must still be on disk
    assert os.path.exists(file_path)

    # DB record must still exist
    result = await db_session.execute(select(Document).where(Document.id == doc_id))
    assert result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Test 3: path outside base dir — file NOT deleted, error logged, record kept
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_document_with_path_outside_base_not_deleted(db_session, tmp_path):
    # Use two entirely separate sibling directories so one is NOT inside the other
    base_dir = tmp_path / "base_docs"
    base_dir.mkdir()
    outside_dir = tmp_path / "outside_docs"
    outside_dir.mkdir()

    sub = await _create_submission_record(db_session, days_old=91)

    outside_path = str(outside_dir / "secret.pdf")
    _write_file(outside_path)

    doc = await _create_document_record(
        db_session, sub.id, outside_path, days_old=91
    )
    await db_session.commit()

    doc_id = doc.id

    with patch("app.database.AsyncSessionLocal", _make_session_factory(db_session)):
        await cleanup_old_documents(str(base_dir), "sqlite://")

    # File must NOT be deleted — it is outside the base directory
    assert os.path.exists(outside_path)

    # DB record must NOT be removed (the cleanup skips the record on path error)
    result = await db_session.execute(select(Document).where(Document.id == doc_id))
    assert result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Test 4: file already missing from disk — DB record is still deleted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_file_on_disk_db_record_still_deleted(db_session, docs_base):
    sub = await _create_submission_record(db_session, days_old=91)
    sub_dir = os.path.join(docs_base, str(sub.id))
    # Deliberately do NOT create the file on disk
    ghost_path = os.path.join(sub_dir, "ghost.pdf")
    # Ensure the dir exists so realpath resolves within base
    os.makedirs(sub_dir, exist_ok=True)

    doc = await _create_document_record(
        db_session, sub.id, ghost_path, days_old=91
    )
    await db_session.commit()

    doc_id = doc.id

    with patch("app.database.AsyncSessionLocal", _make_session_factory(db_session)):
        await cleanup_old_documents(docs_base, "sqlite://")

    # DB record must be removed even though the file was never on disk
    result = await db_session.execute(select(Document).where(Document.id == doc_id))
    assert result.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# Test 5: old submission with no remaining documents → PII anonymised
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_old_submission_without_docs_is_anonymised(db_session, docs_base):
    sub = await _create_submission_record(
        db_session,
        provider_name="Juan García López",
        days_old=91,
        partner_info='{"nif": "12345678A"}',
        contract_data='{"commission": 10}',
        ai_response="## Informe KYC ...",
    )
    await db_session.commit()

    sub_id = sub.id

    with patch("app.database.AsyncSessionLocal", _make_session_factory(db_session)):
        await cleanup_old_documents(docs_base, "sqlite://")

    result = await db_session.execute(select(Submission).where(Submission.id == sub_id))
    updated = result.scalar_one()

    assert updated.partner_info is None
    assert updated.contract_data is None
    assert updated.ai_response is None
    assert updated.provider_name == "Anonymised"


# ---------------------------------------------------------------------------
# Test 6: old submission WITH remaining documents → NOT anonymised
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_old_submission_with_remaining_docs_is_not_anonymised(
    db_session, docs_base
):
    sub = await _create_submission_record(
        db_session,
        provider_name="María Fernández",
        days_old=91,
        partner_info='{"nif": "87654321B"}',
    )
    sub_dir = os.path.join(docs_base, str(sub.id))
    file_path = os.path.join(sub_dir, "recent_doc.pdf")
    _write_file(file_path)

    # This document is recent (5 days old) so it is not cleaned up
    await _create_document_record(db_session, sub.id, file_path, days_old=5)
    await db_session.commit()

    sub_id = sub.id

    with patch("app.database.AsyncSessionLocal", _make_session_factory(db_session)):
        await cleanup_old_documents(docs_base, "sqlite://")

    result = await db_session.execute(select(Submission).where(Submission.id == sub_id))
    updated = result.scalar_one()

    # PII must NOT be wiped because the submission still has a document
    assert updated.partner_info == '{"nif": "87654321B"}'
    assert updated.provider_name == "María Fernández"
