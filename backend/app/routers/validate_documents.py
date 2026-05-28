"""
Router for ad-hoc document validation.

Endpoints:
  GET  /api/document-requirements/{provider_type}/{entity_type}  (public)
       Returns the ordered list of required document slots for the given
       partner type and entity type. This is the single source of truth —
       the frontend reads from here instead of having a local copy.

  POST /api/validate-documents  (JWT required, rate-limited)
       Accepts N uploaded files + provider/entity type, calls the AI to
       match each uploaded file against the required document slots, and
       returns a structured JSON result. Nothing is saved to the database.

# SYNC: the document slot lists below must be kept in sync with
# frontend/src/lib/documentRequirements.ts
"""

import json
import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import List, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.auth.jwt import get_current_analyst
from app.config import Settings, get_settings
from app.models.analyst import Analyst
from app.routers.submissions import (
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE_BYTES,
    MAX_TOTAL_SIZE_BYTES,
    _verify_magic_bytes,
)
from app.schemas.submission import VALID_ENTITY_TYPES, VALID_PROVIDER_TYPES
from app.services.ai_analysis import run_document_validation
from app.services.extraction import extract_documents
from app.utils.file_utils import sanitize_filename
from app.utils.rate_limit import limiter as _limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["validate-documents"])

# ---------------------------------------------------------------------------
# Document slot definitions
# SYNC: keep in sync with frontend/src/lib/documentRequirements.ts
# ---------------------------------------------------------------------------

_PJ_BASE_SLOTS = [
    {"id": "escrituras_constitucion", "label": "Escrituras de constitución", "is_conditional": False},
    {"id": "escrituras_apoderamiento", "label": "Escrituras de apoderamiento de representantes legales", "is_conditional": False},
    {"id": "dni_representante", "label": "DNI del representante legal", "is_conditional": False},
    {"id": "cert_cuenta_gastos", "label": "Certificado de titularidad de cuenta bancaria (gastos generales)", "is_conditional": False},
    {"id": "titularidad_real", "label": "Acta de titularidad real (antigüedad menor de 12 meses) o último Modelo 200 presentado", "is_conditional": False},
    {"id": "cert_ss_pj", "label": "Certificado de estar al corriente con la Seguridad Social", "is_conditional": False},
    {"id": "cert_hacienda_pj", "label": "Certificado de estar al corriente con Hacienda", "is_conditional": False},
]

_PF_BASE_SLOTS = [
    {"id": "doc_identidad", "label": "Documento de identidad", "is_conditional": False},
    {"id": "doc_alta_censal", "label": "Documento acreditativo de alta / situación censal / actividad económica", "is_conditional": False},
    {"id": "cert_cuenta_bancaria", "label": "Certificado de titularidad de cuenta bancaria propia", "is_conditional": False},
    {"id": "cert_hacienda_pf", "label": "Certificado de estar al corriente con Hacienda", "is_conditional": False},
    {"id": "cert_ss_pf", "label": "Certificado de estar al corriente con la Seguridad Social", "is_conditional": False},
]

_DISTRIBUTOR_EXTRA_SLOTS = [
    {"id": "resolucion_dgsfp", "label": "Resolución de la DGSFP de otorgamiento de clave", "is_conditional": False},
    {"id": "cert_cuenta_cobros", "label": "Certificado de titularidad de la cuenta dedicada a cobros de clientes", "is_conditional": True},
    {"id": "poliza_rc", "label": "Póliza de RC profesional en vigor", "is_conditional": False},
    {"id": "justificante_pago_rc", "label": "Justificante de pago de la póliza RC", "is_conditional": False},
    {"id": "cert_formacion", "label": "Certificado de formación del responsable de la distribución", "is_conditional": False},
    {"id": "declaraciones", "label": "Declaraciones firmadas del proveedor", "is_conditional": False},
]

_DECLARATIONS_SLOT = [
    {"id": "declaraciones", "label": "Declaraciones firmadas", "is_conditional": False},
]


def get_required_slots(provider_type: str, entity_type: str) -> list[dict]:
    """Return the ordered list of required document slots for the given combination."""
    base = _PJ_BASE_SLOTS if entity_type == "PJ" else _PF_BASE_SLOTS
    if provider_type in ("correduria_seguros", "agencia_seguros"):
        return base + _DISTRIBUTOR_EXTRA_SLOTS
    if provider_type in ("colaborador_externo", "generador_leads"):
        return base + _DECLARATIONS_SLOT
    return base


# ---------------------------------------------------------------------------
# GET /api/document-requirements/{provider_type}/{entity_type}  (public)
# ---------------------------------------------------------------------------

@router.get(
    "/document-requirements/{provider_type}/{entity_type}",
    tags=["document-requirements"],
)
async def get_document_requirements(provider_type: str, entity_type: str):
    """
    Public endpoint — returns the required document slots for a given
    partner type and entity type combination.

    Used by both the "Listado de Documentación" page and the
    "Validación de Documentos" page on the frontend.
    """
    if provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"provider_type must be one of: {', '.join(sorted(VALID_PROVIDER_TYPES))}",
        )
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"entity_type must be one of: {', '.join(sorted(VALID_ENTITY_TYPES))}",
        )

    slots = get_required_slots(provider_type, entity_type)
    return {
        "provider_type": provider_type,
        "entity_type": entity_type,
        "slots": slots,
    }


# ---------------------------------------------------------------------------
# POST /api/validate-documents  (JWT required)
# ---------------------------------------------------------------------------

@router.post("/validate-documents")
@_limiter.limit("10/hour")
async def validate_documents(
    request: Request,
    provider_type: str = Form(...),
    entity_type: str = Form(...),
    files: Union[List[UploadFile], UploadFile] = File(...),
    current_analyst: Analyst = Depends(get_current_analyst),
    settings: Settings = Depends(get_settings),
):
    """
    Ad-hoc document validation.

    Accepts N uploaded files, matches each one against the required
    document slots for the given partner/entity type using AI, and
    returns a structured JSON result. Nothing is saved to the database.
    """
    # Normalise: FastAPI may return a bare UploadFile when only one file is sent
    if isinstance(files, UploadFile):
        files = [files]

    # --- Input validation ---
    if provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"provider_type must be one of: {', '.join(sorted(VALID_PROVIDER_TYPES))}",
        )
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"entity_type must be one of: {', '.join(sorted(VALID_ENTITY_TYPES))}",
        )
    if not files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one file is required.",
        )
    if len(files) > 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Maximum 50 files per validation.",
        )

    # --- Read, validate and write files to a temp directory ---
    tmp_dir = tempfile.mkdtemp(prefix="kyc_validate_")
    try:
        doc_entries: list[dict] = []
        total_size = 0

        for upload_file in files:
            if upload_file.content_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"File '{upload_file.filename}' has unsupported type "
                        f"'{upload_file.content_type}'. Allowed: PDF, JPEG, PNG, DOCX."
                    ),
                )

            content = await upload_file.read()

            if len(content) > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"File '{upload_file.filename}' exceeds the 20 MB limit.",
                )

            if not _verify_magic_bytes(content, upload_file.content_type):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"File '{upload_file.filename}' content does not match "
                        f"its declared type."
                    ),
                )

            total_size += len(content)
            if total_size > MAX_TOTAL_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Total file size exceeds the 100 MB limit.",
                )

            # Write to temp dir so the extraction service can read it
            safe_filename = sanitize_filename(upload_file.filename or "file")
            tmp_path = Path(tmp_dir) / safe_filename
            # Avoid name collisions
            counter = 1
            while tmp_path.exists():
                stem = Path(safe_filename).stem
                suffix = Path(safe_filename).suffix
                tmp_path = Path(tmp_dir) / f"{stem}_{counter}{suffix}"
                counter += 1

            tmp_path.write_bytes(content)
            doc_entries.append({
                "file_path": str(tmp_path),
                "label": tmp_path.name,
                "filename": tmp_path.name,
                "mime_type": upload_file.content_type,
            })

        # --- Extract document content ---
        extracted_docs = await extract_documents(doc_entries)

        # --- Get required slots ---
        required_slots = get_required_slots(provider_type, entity_type)

        # --- Call AI ---
        logger.info(
            "Analyst %s starting validation: %s/%s, %d files",
            current_analyst.email,
            provider_type,
            entity_type,
            len(files),
        )
        raw_json, model_used = await run_document_validation(
            provider_type=provider_type,
            entity_type=entity_type,
            required_slots=required_slots,
            extracted_docs=extracted_docs,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            openai_api_key=settings.OPENAI_API_KEY,
        )

        # --- Parse AI response ---
        validation_data = _parse_validation_json(raw_json)

        logger.info(
            "Validation complete for analyst %s: %s/%s — model: %s",
            current_analyst.email,
            provider_type,
            entity_type,
            model_used,
        )

        return {
            "provider_type": provider_type,
            "entity_type": entity_type,
            "results": validation_data.get("results", []),
            "unmatched_files": validation_data.get("unmatched_files", []),
            "model_used": model_used,
        }

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _extract_first_json_object(text: str) -> str | None:
    """
    Walk *text* character by character and return the first balanced {...}
    substring.  This avoids the catastrophic backtracking risk of a greedy
    r"\\{.*\\}" regex on large AI responses.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_validation_json(raw: str) -> dict:
    """
    Parse the AI's JSON response, with a balanced-brace fallback in case the
    model wrapped the JSON in markdown code fences or added explanatory text.

    Raises HTTPException 502 if the JSON cannot be extracted at all.
    """
    # Direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Fallback: extract the first balanced {...} block
    candidate = _extract_first_json_object(raw)
    if candidate:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    logger.error("AI returned non-parseable response for validation: %r", raw[:500])
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=(
            "La IA no ha podido generar una respuesta estructurada. "
            "Por favor, inténtalo de nuevo."
        ),
    )
