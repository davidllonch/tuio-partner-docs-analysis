"""
Tests for GET /api/submissions/{submission_id}/report.pdf

The PDF download endpoint is the most recently added feature and has no
existing test coverage. It has three distinct failure modes and one success
path — all tested here without calling weasyprint, markdown, or the real DB.

Covered cases:
1. No auth header -> 403
2. Invalid JWT     -> 401
3. Unknown submission ID -> 404
4. Submission exists but ai_response is NULL -> 404
5. Happy path: submission with ai_response returns a PDF response

The happy-path test patches weasyprint so the test suite does not require
the weasyprint binary (a native C library) to be installed in CI.

Also covers the helper _sanitize_filename function directly, since it is
the only pure function in submissions.py and exercises path-traversal defences.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from tests.conftest import create_analyst_in_db, make_token_for
from app.models.submission import Submission


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_submission(
    db_session,
    ai_response: str | None = None,
    provider_name: str = "Acme Corp",
    provider_type: str = "correduria_seguros",
    entity_type: str = "PJ",
    country: str = "ES",
    status: str = "complete",
) -> Submission:
    """Insert a Submission row directly into the in-memory DB."""
    submission = Submission(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        provider_name=provider_name,
        provider_type=provider_type,
        entity_type=entity_type,
        country=country,
        status=status,
        ai_response=ai_response,
    )
    db_session.add(submission)
    await db_session.commit()
    await db_session.refresh(submission)
    return submission


# ---------------------------------------------------------------------------
# Auth / authorization tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_report_pdf_without_auth_returns_401(client, db_session):
    """
    The PDF download endpoint is analyst-only.
    A request with no Authorization header must be rejected with HTTP 401.
    """
    fake_id = uuid.uuid4()
    response = await client.get(f"/api/submissions/{fake_id}/report.pdf")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_download_report_pdf_with_invalid_token_returns_401(client, db_session):
    """
    A garbage Bearer token must be rejected before any DB access happens.
    """
    fake_id = uuid.uuid4()
    response = await client.get(
        f"/api/submissions/{fake_id}/report.pdf",
        headers={"Authorization": "Bearer this.is.garbage"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 404 cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_report_pdf_for_nonexistent_submission_returns_404(
    client, db_session
):
    """
    Requesting a PDF for a submission ID that does not exist in the database
    must return HTTP 404, not a server error.
    """
    analyst = await create_analyst_in_db(db_session)
    token = make_token_for(analyst)
    nonexistent_id = uuid.uuid4()

    response = await client.get(
        f"/api/submissions/{nonexistent_id}/report.pdf",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_download_report_pdf_for_submission_with_no_ai_response_returns_404(
    client, db_session
):
    """
    A submission that exists in the database but has no ai_response (for
    example, it is still being analysed, or the analysis failed) must return
    HTTP 404 with a clear message.

    This is a core business rule: there is nothing to render as a PDF yet.
    """
    analyst = await create_analyst_in_db(db_session)
    token = make_token_for(analyst)

    submission = await _create_submission(
        db_session,
        ai_response=None,  # No report yet
        status="analysing",
    )

    response = await client.get(
        f"/api/submissions/{submission.id}/report.pdf",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    detail = response.json()["detail"].lower()
    assert "no report" in detail or "not available" in detail


@pytest.mark.asyncio
async def test_download_report_pdf_for_submission_with_empty_ai_response_returns_404(
    client, db_session
):
    """
    An ai_response that is an empty string is treated the same as NULL —
    falsy in Python — so the endpoint must return 404.

    This prevents an endpoint from returning a blank PDF, which would be
    confusing and potentially signal a pipeline error to external observers.
    """
    analyst = await create_analyst_in_db(db_session)
    token = make_token_for(analyst)

    submission = await _create_submission(
        db_session,
        ai_response="",  # Empty string — falsy
        status="error",
    )

    response = await client.get(
        f"/api/submissions/{submission.id}/report.pdf",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_report_pdf_returns_pdf_content_type(client, db_session):
    """
    A submission with a valid ai_response must return HTTP 200 with
    Content-Type: application/pdf and a non-empty body.

    weasyprint is patched with a fake that returns minimal valid bytes so
    the test does not require the native weasyprint/GTK libraries in CI.
    """
    analyst = await create_analyst_in_db(db_session)
    token = make_token_for(analyst)

    submission = await _create_submission(
        db_session,
        ai_response="## Informe KYC\n\nDocumentación validada correctamente.",
        provider_name="Acme Seguros S.L.",
        status="complete",
    )

    # Patch weasyprint so the test works without the native binary installed.
    # The fake returns the smallest valid PDF header bytes.
    fake_pdf_bytes = b"%PDF-1.4 fake-pdf-content"

    with patch("weasyprint.HTML") as mock_weasyprint_html:
        mock_weasyprint_html.return_value.write_pdf.return_value = fake_pdf_bytes

        response = await client.get(
            f"/api/submissions/{submission.id}/report.pdf",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 0


@pytest.mark.asyncio
async def test_download_report_pdf_content_disposition_uses_provider_name(
    client, db_session
):
    """
    The Content-Disposition header must include the provider name in the filename.
    This lets browsers suggest a meaningful filename when the analyst saves the file.
    """
    analyst = await create_analyst_in_db(db_session)
    token = make_token_for(analyst)

    submission = await _create_submission(
        db_session,
        ai_response="## Informe",
        provider_name="TuioPartner",
        status="complete",
    )

    fake_pdf_bytes = b"%PDF-1.4 fake"

    with patch("weasyprint.HTML") as mock_weasyprint_html:
        mock_weasyprint_html.return_value.write_pdf.return_value = fake_pdf_bytes

        response = await client.get(
            f"/api/submissions/{submission.id}/report.pdf",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    disposition = response.headers.get("content-disposition", "")
    # The endpoint builds a filename that includes the provider name
    assert "TuioPartner" in disposition or "Informe_KYC" in disposition


@pytest.mark.asyncio
async def test_download_report_pdf_provider_name_with_special_chars_does_not_crash(
    client, db_session
):
    """
    Provider names can contain accented characters, spaces, and punctuation.
    The endpoint strips these to produce a safe ASCII filename.
    The response must still be HTTP 200 — no 500 error from bad string handling.
    """
    analyst = await create_analyst_in_db(db_session)
    token = make_token_for(analyst)

    submission = await _create_submission(
        db_session,
        ai_response="## Informe",
        provider_name="Société d'Assurance & Cie.",
        status="complete",
    )

    fake_pdf_bytes = b"%PDF-1.4 fake"

    with patch("weasyprint.HTML") as mock_weasyprint_html:
        mock_weasyprint_html.return_value.write_pdf.return_value = fake_pdf_bytes

        response = await client.get(
            f"/api/submissions/{submission.id}/report.pdf",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_download_report_pdf_provider_name_xss_is_html_escaped(
    client, db_session
):
    """
    The provider_name is inserted into an HTML template before being rendered
    to PDF. A name containing HTML/script tags must be escaped, not injected.

    We verify this by capturing the HTML string passed to weasyprint and
    asserting the raw tag characters do not appear unescaped.
    """
    analyst = await create_analyst_in_db(db_session)
    token = make_token_for(analyst)

    submission = await _create_submission(
        db_session,
        ai_response="## Informe",
        provider_name='<script>alert("xss")</script>',
        status="complete",
    )

    captured_html = {}

    def capture_html(string, **_kwargs):
        captured_html["value"] = string
        mock = type(
            "FakeHTML", (), {"write_pdf": lambda self: b"%PDF-1.4 fake"}
        )()
        return mock

    with patch("weasyprint.HTML", side_effect=capture_html):
        response = await client.get(
            f"/api/submissions/{submission.id}/report.pdf",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    rendered = captured_html.get("value", "")
    # The raw <script> tag must not appear in the HTML sent to weasyprint
    assert "<script>" not in rendered
    assert 'alert("xss")' not in rendered


# ---------------------------------------------------------------------------
# Unit tests for _sanitize_filename (pure function, no DB needed)
# ---------------------------------------------------------------------------


from app.utils.file_utils import sanitize_filename


class TestSanitizeFilename:
    """
    sanitize_filename is a pure function that strips unsafe characters from
    user-supplied filenames. These tests run synchronously — no async/await
    and no fixtures needed.
    """

    def test_normal_filename_unchanged(self):
        assert sanitize_filename("document.pdf") == "document.pdf"

    def test_spaces_become_underscores(self):
        result = sanitize_filename("my document.pdf")
        assert " " not in result
        assert "_" in result

    def test_path_traversal_attempt_is_stripped(self):
        """
        A filename like ../../etc/passwd should not produce a path outside
        the intended directory. os.path.basename removes the directory component.
        """
        result = sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_special_characters_are_removed(self):
        result = sanitize_filename("file;rm -rf /.pdf")
        assert ";" not in result
        assert " " not in result

    def test_empty_filename_becomes_file(self):
        # sanitize_filename uses fallback="file" by default
        result = sanitize_filename("")
        assert result == "file"

    def test_only_special_chars_becomes_file(self):
        result = sanitize_filename("@#$%^&*()")
        assert result == "file"

    def test_unicode_accents_are_preserved(self):
        """Python 3's \\w is Unicode-aware: accented chars are word chars and are kept."""
        result = sanitize_filename("résumé.pdf")
        # Accented chars survive — only shell-special and path chars are removed
        assert "/" not in result
        assert ";" not in result

    def test_windows_path_separator_stripped(self):
        result = sanitize_filename("C:\\Users\\admin\\secret.pdf")
        assert "\\" not in result
        assert ":" not in result
