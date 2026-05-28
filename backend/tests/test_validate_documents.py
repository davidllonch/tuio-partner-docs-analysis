"""
Tests for the document validation endpoints and helper functions.

Endpoints covered:
  GET  /api/document-requirements/{provider_type}/{entity_type}  (public)
  POST /api/validate-documents                                    (JWT required)

Pure functions covered:
  get_required_slots(provider_type, entity_type)
  _parse_validation_json(raw)

All tests use the shared in-memory SQLite fixtures from conftest.
"""

import json
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import create_analyst_in_db, make_token_for
from app.routers.validate_documents import get_required_slots, _parse_validation_json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_PDF_BYTES = b"%PDF-1.4 fake-content"
_PDF_MIME = "application/pdf"

_GOOD_AI_RESULT = {
    "results": [{"slot_id": "escrituras_constitucion", "status": "ok", "filename": "doc.pdf"}],
    "unmatched_files": [],
}


def _pdf_file(filename: str = "doc.pdf") -> tuple:
    """Return (field_name, (filename, file_obj, mime_type)) for httpx multipart."""
    return ("files", (filename, BytesIO(_VALID_PDF_BYTES), _PDF_MIME))


# ---------------------------------------------------------------------------
# get_required_slots — unit tests (sync, no DB)
# ---------------------------------------------------------------------------


def test_get_required_slots_correduria_pj_returns_13_slots():
    """PJ with correduria_seguros → 7 base + 6 extra = 13 slots."""
    slots = get_required_slots("correduria_seguros", "PJ")
    assert len(slots) == 13


def test_get_required_slots_agencia_pf_returns_11_slots():
    """PF with agencia_seguros → 5 base + 6 extra = 11 slots."""
    slots = get_required_slots("agencia_seguros", "PF")
    assert len(slots) == 11


def test_get_required_slots_colaborador_externo_pj_returns_8_slots():
    """PJ with colaborador_externo → 7 base + 1 declarations = 8 slots."""
    slots = get_required_slots("colaborador_externo", "PJ")
    assert len(slots) == 8


def test_get_required_slots_generador_leads_pf_returns_6_slots():
    """PF with generador_leads → 5 base + 1 declarations = 6 slots."""
    slots = get_required_slots("generador_leads", "PF")
    assert len(slots) == 6


def test_get_required_slots_cert_cuenta_cobros_is_conditional_for_distributor():
    """cert_cuenta_cobros must have is_conditional=True for distributor types."""
    slots = get_required_slots("correduria_seguros", "PJ")
    cobros = next((s for s in slots if s["id"] == "cert_cuenta_cobros"), None)
    assert cobros is not None
    assert cobros["is_conditional"] is True


def test_get_required_slots_declaraciones_is_not_conditional_for_distributor():
    """declaraciones must have is_conditional=False for distributor types."""
    slots = get_required_slots("agencia_seguros", "PF")
    declaraciones = next((s for s in slots if s["id"] == "declaraciones"), None)
    assert declaraciones is not None
    assert declaraciones["is_conditional"] is False


def test_get_required_slots_declaraciones_is_not_conditional_for_colaborador():
    """declaraciones must have is_conditional=False for colaborador_externo."""
    slots = get_required_slots("colaborador_externo", "PJ")
    declaraciones = next((s for s in slots if s["id"] == "declaraciones"), None)
    assert declaraciones is not None
    assert declaraciones["is_conditional"] is False


# ---------------------------------------------------------------------------
# _parse_validation_json — unit tests (sync, no DB)
# ---------------------------------------------------------------------------


def test_parse_validation_json_valid_json_returns_dict():
    """Valid JSON string → returns the parsed dict directly."""
    raw = json.dumps({"results": [], "unmatched_files": []})
    result = _parse_validation_json(raw)
    assert result == {"results": [], "unmatched_files": []}


def test_parse_validation_json_json_with_surrounding_text_extracts_via_regex():
    """JSON embedded inside surrounding text → extracted via the regex fallback."""
    raw = 'Here is the analysis: {"results": [{"slot_id": "dni"}], "unmatched_files": []} End of output.'
    result = _parse_validation_json(raw)
    assert result["results"][0]["slot_id"] == "dni"
    assert result["unmatched_files"] == []


def test_parse_validation_json_markdown_fenced_json_is_extracted():
    """JSON wrapped in ```json ... ``` markdown fences → extracted via regex fallback."""
    payload = {"results": [{"slot_id": "poliza_rc", "status": "ok"}], "unmatched_files": []}
    raw = f"```json\n{json.dumps(payload)}\n```"
    result = _parse_validation_json(raw)
    assert result["results"][0]["slot_id"] == "poliza_rc"


def test_parse_validation_json_completely_invalid_raises_502():
    """Completely non-JSON string → raises HTTPException with status 502."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        _parse_validation_json("This is not JSON at all, no braces, nothing useful here.")
    assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# GET /api/document-requirements/{provider_type}/{entity_type}  — integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_document_requirements_valid_combination_returns_200(client, db_session):
    """Valid provider_type + entity_type → 200 with expected fields."""
    response = await client.get("/api/document-requirements/correduria_seguros/PJ")
    assert response.status_code == 200
    body = response.json()
    assert body["provider_type"] == "correduria_seguros"
    assert body["entity_type"] == "PJ"
    assert "slots" in body
    assert isinstance(body["slots"], list)
    assert len(body["slots"]) > 0


@pytest.mark.asyncio
async def test_get_document_requirements_invalid_provider_type_returns_422(client, db_session):
    """Unknown provider_type → 422."""
    response = await client.get("/api/document-requirements/tipo_inexistente/PJ")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_document_requirements_invalid_entity_type_returns_422(client, db_session):
    """Unknown entity_type → 422."""
    response = await client.get("/api/document-requirements/correduria_seguros/SA")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_document_requirements_requires_no_jwt(client, db_session):
    """Public endpoint — request without Authorization header must return 200."""
    response = await client.get("/api/document-requirements/agencia_seguros/PF")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_document_requirements_correduria_pj_contains_conditional_cobros(client, db_session):
    """Slots for correduria/PJ must include cert_cuenta_cobros with is_conditional=True."""
    response = await client.get("/api/document-requirements/correduria_seguros/PJ")
    assert response.status_code == 200
    slots = response.json()["slots"]
    cobros = next((s for s in slots if s["id"] == "cert_cuenta_cobros"), None)
    assert cobros is not None
    assert cobros["is_conditional"] is True


@pytest.mark.asyncio
async def test_get_document_requirements_returns_correct_slot_count_for_colaborador_pf(client, db_session):
    """colaborador_externo + PF → 5 base + 1 declarations = 6 slots."""
    response = await client.get("/api/document-requirements/colaborador_externo/PF")
    assert response.status_code == 200
    assert len(response.json()["slots"]) == 6


# ---------------------------------------------------------------------------
# POST /api/validate-documents — integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_documents_without_jwt_returns_401(client, db_session):
    """No Authorization header → 401."""
    response = await client.post(
        "/api/validate-documents",
        data={"provider_type": "correduria_seguros", "entity_type": "PJ"},
        files=[_pdf_file()],
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_validate_documents_with_invalid_jwt_returns_401(client, db_session):
    """Malformed/invalid JWT → 401."""
    response = await client.post(
        "/api/validate-documents",
        data={"provider_type": "correduria_seguros", "entity_type": "PJ"},
        files=[_pdf_file()],
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_validate_documents_invalid_provider_type_returns_422(client, db_session):
    """Invalid provider_type with valid JWT → 422."""
    analyst = await create_analyst_in_db(db_session, email="vd_badprov@example.com")
    token = make_token_for(analyst)

    with patch(
        "app.routers.validate_documents.run_document_validation",
        new=AsyncMock(return_value=(json.dumps(_GOOD_AI_RESULT), "claude-sonnet-4-6")),
    ):
        response = await client.post(
            "/api/validate-documents",
            data={"provider_type": "tipo_invalido", "entity_type": "PJ"},
            files=[_pdf_file()],
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validate_documents_invalid_entity_type_returns_422(client, db_session):
    """Invalid entity_type with valid JWT → 422."""
    analyst = await create_analyst_in_db(db_session, email="vd_badentity@example.com")
    token = make_token_for(analyst)

    with patch(
        "app.routers.validate_documents.run_document_validation",
        new=AsyncMock(return_value=(json.dumps(_GOOD_AI_RESULT), "claude-sonnet-4-6")),
    ):
        response = await client.post(
            "/api/validate-documents",
            data={"provider_type": "correduria_seguros", "entity_type": "SA"},
            files=[_pdf_file()],
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validate_documents_disallowed_mime_type_returns_422(client, db_session):
    """File with a MIME type outside the allowed set → 422."""
    analyst = await create_analyst_in_db(db_session, email="vd_badmime@example.com")
    token = make_token_for(analyst)

    response = await client.post(
        "/api/validate-documents",
        data={"provider_type": "correduria_seguros", "entity_type": "PJ"},
        files=[("files", ("script.exe", BytesIO(b"MZ"), "application/octet-stream"))],
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validate_documents_valid_pdf_with_mocked_ai_returns_200(client, db_session):
    """Valid PDF + valid params + mocked AI → 200 with full response structure."""
    analyst = await create_analyst_in_db(db_session, email="vd_success@example.com")
    token = make_token_for(analyst)

    with patch(
        "app.routers.validate_documents.run_document_validation",
        new=AsyncMock(return_value=(json.dumps(_GOOD_AI_RESULT), "claude-sonnet-4-6")),
    ):
        response = await client.post(
            "/api/validate-documents",
            data={"provider_type": "correduria_seguros", "entity_type": "PJ"},
            files=[_pdf_file("escrituras.pdf")],
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["provider_type"] == "correduria_seguros"
    assert body["entity_type"] == "PJ"
    assert "results" in body
    assert "unmatched_files" in body
    assert "model_used" in body


@pytest.mark.asyncio
async def test_validate_documents_response_contains_model_used_from_ai(client, db_session):
    """The model_used field must reflect what the AI service returned."""
    analyst = await create_analyst_in_db(db_session, email="vd_modelused@example.com")
    token = make_token_for(analyst)

    with patch(
        "app.routers.validate_documents.run_document_validation",
        new=AsyncMock(return_value=(json.dumps(_GOOD_AI_RESULT), "claude-sonnet-4-6")),
    ):
        response = await client.post(
            "/api/validate-documents",
            data={"provider_type": "agencia_seguros", "entity_type": "PF"},
            files=[_pdf_file()],
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["model_used"] == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_validate_documents_ai_returns_bad_json_yields_502(client, db_session):
    """When the AI returns unparseable output → endpoint returns 502."""
    analyst = await create_analyst_in_db(db_session, email="vd_badjson@example.com")
    token = make_token_for(analyst)

    with patch(
        "app.routers.validate_documents.run_document_validation",
        new=AsyncMock(return_value=("completely unparseable output, no JSON here", "claude-sonnet-4-6")),
    ):
        response = await client.post(
            "/api/validate-documents",
            data={"provider_type": "correduria_seguros", "entity_type": "PJ"},
            files=[_pdf_file()],
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 502
