import asyncio
import copy
import io
import logging
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Optional

from docx import Document as DocxDocument
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.jwt import get_current_analyst
from app.config import Settings, get_settings
from app.database import get_db
from app.models.analyst import Analyst
from app.models.audit import AuditLog
from app.models.contract_template import ContractTemplate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["contract-templates"])

# Contract templates are only available for these three provider types.
# agencia_seguros is excluded because they use a different contract framework.
VALID_PROVIDER_TYPES = {
    "colaborador_externo",
    "generador_leads",
    "correduria_seguros",
}

VALID_ENTITY_TYPES = {"PF", "PJ"}

PROVIDER_TYPE_LABELS = {
    "correduria_seguros": "Correduría de Seguros",
    "colaborador_externo": "Colaborador Externo",
    "generador_leads": "Generador de Leads",
}

ENTITY_TYPE_LABELS = {
    "PJ": "Persona Jurídica",
    "PF": "Persona Física",
}

# Accepted MIME type for DOCX uploads
DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

# ---------------------------------------------------------------------------
# Placeholder maps
# ---------------------------------------------------------------------------

# Placeholders filled from partner_info for Persona Física submissions
PARTNER_PF_MAP = {
    "[REPRESENTANTE]": "nombre_apellidos",
    "[NOMBRE Y APELLIDOS DEL PARTNER]": "nombre_apellidos",
    "[NIF]": "nif",
    "[DOMICILIO]": "domicilio",
    "[DIRECCIÓN]": "direccion_notificaciones",
    "[EMAIL]": "email",
    "[CONTACTO]": "contacto_notificaciones",
    "[CLAVE DGS]": "clave_dgs",  # correduria only but safe to include for all
    "[CORREDURÍA]": "nombre_apellidos",  # PF contracts: company name = individual's name
}

# Placeholders filled from partner_info for Persona Jurídica submissions
PARTNER_PJ_MAP = {
    "[REPRESENTANTE]": "nombre_representante",
    "[NIF]": "nif_representante",
    "[CIF]": "cif",
    "[SOCIEDAD]": "razon_social",
    "[CORREDURÍA]": "razon_social",  # PJ contracts: company name = razón social
    "[DOMICILIO]": "domicilio_social",
    "[DOMICILIO SOCIAL]": "domicilio_social",
    "[PODER]": "poder",
    "[DIRECCIÓN]": "direccion_notificaciones",
    "[EMAIL]": "email",
    "[CONTACTO]": "contacto_notificaciones",
    "[CLAVE DGS]": "clave_dgs",  # correduria only but safe to include for all
}

# Placeholders filled by the analyst (only used in generate-full)
ANALYST_MAP = {
    "[ACTIVIDAD]": "actividad",
}

# Commission table placeholders — handled separately via row duplication
COMMISSION_PLACEHOLDERS = [
    "[PRODUCTO DE SEGURO]",
    "[PRIMA NETA TRAMO 1]",
    "[COMISIÓN NP]",
    "[COMISIÓN CARTERA]",
]

# Spanish month names for date placeholders
_MESES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ContractTemplateInfo(BaseModel):
    provider_type: str
    entity_type: str
    provider_type_label: str
    entity_type_label: str
    original_filename: str
    uploaded_at: datetime
    uploaded_by_name: Optional[str] = None

    model_config = {"from_attributes": True}


class AllTemplatesResponse(BaseModel):
    templates: list[ContractTemplateInfo]


class GenerateRequest(BaseModel):
    partner_info: dict


class GenerateFullRequest(BaseModel):
    partner_info: dict
    contract_data: dict  # { "fields": { "actividad": "..." }, "commissions": [...] }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _log_audit(
    db: AsyncSession,
    action: str,
    analyst_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> None:
    log_entry = AuditLog(
        id=uuid.uuid4(),
        analyst_id=analyst_id,
        action=action,
        timestamp=datetime.now(timezone.utc),
        metadata_=metadata,
    )
    db.add(log_entry)
    await db.flush()


def _sanitize_filename(filename: str) -> str:
    filename = os.path.basename(filename)
    filename = filename.replace(" ", "_")
    filename = re.sub(r"[^\w\-.]", "", filename)
    if not filename:
        filename = "contract"
    return filename


def _get_template_dir(documents_base_path: str) -> str:
    template_dir = os.path.join(documents_base_path, "contract_templates")
    os.makedirs(template_dir, exist_ok=True)
    return template_dir


# OOXML Word namespace — used to find <w:t> elements via lxml
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _replace_in_paragraph_elem(p_elem, replacements: dict[str, str]) -> None:
    """
    Replace placeholder strings in a single paragraph XML element.

    Three-pass strategy:
      Pass 1 — replace within each individual <w:t> element (handles placeholders
               fully contained in one run; preserves per-run formatting).
      Pass 2 — sliding-window for split-run placeholders: handles the common Word
               pattern where the opening '[' is the last char of run N, the inner
               name is the entirety of run N+1, and ']' is the first char of run N+2.
               Only the three involved characters are modified; all other runs keep
               their original text and formatting unchanged.
      Pass 3 — full-collapse fallback for any remaining cross-run placeholders.
               Loses per-run formatting for the paragraph but always works.
    """
    w_t_elems = p_elem.findall(".//" + _W_NS + "t")
    if not w_t_elems:
        return

    # Pass 1: per-run replacement (preserves formatting)
    for elem in w_t_elems:
        if not elem.text:
            continue
        for placeholder, value in replacements.items():
            if placeholder in elem.text:
                elem.text = elem.text.replace(placeholder, value)

    # Pass 2: sliding-window for split-run placeholders
    # Pattern: w_t[i-1] ends with "[", w_t[i] == "INNER_NAME", w_t[i+1] starts with "]"
    for placeholder, value in replacements.items():
        if len(placeholder) < 3 or placeholder[0] != "[" or placeholder[-1] != "]":
            continue
        inner = placeholder[1:-1]  # strip the [ and ]
        i = 1
        while i < len(w_t_elems) - 1:
            curr_text = w_t_elems[i].text or ""
            if curr_text == inner:
                prev_text = w_t_elems[i - 1].text or ""
                next_text = w_t_elems[i + 1].text or ""
                if prev_text.endswith("[") and next_text.startswith("]"):
                    # Found a split placeholder — fix it in-place
                    w_t_elems[i - 1].text = prev_text[:-1]   # strip trailing [
                    w_t_elems[i].text = value                # fill replacement
                    w_t_elems[i + 1].text = next_text[1:]    # strip leading ]
                    i += 2  # skip past the replaced placeholder
                    continue
            i += 1

    # Pass 3: full-collapse fallback for any remaining cross-run placeholders
    full_text = "".join(elem.text or "" for elem in w_t_elems)
    remaining = {ph: v for ph, v in replacements.items() if ph in full_text}
    if not remaining:
        return

    new_text = full_text
    for placeholder, value in remaining.items():
        new_text = new_text.replace(placeholder, value)
    w_t_elems[0].text = new_text
    for elem in w_t_elems[1:]:
        elem.text = ""


def _iter_all_tables_inline(doc_or_cells):
    """
    BFS generator that yields every table in the document including nested ones.
    Accepts either a Document (uses doc.tables) or a list of cells.
    This is defined early so _replace_placeholders_in_docx can use it.
    """
    if hasattr(doc_or_cells, "tables"):
        queue = list(doc_or_cells.tables)
    else:
        queue = list(doc_or_cells)
    while queue:
        table = queue.pop(0)
        yield table
        for row in table.rows:
            for cell in row.cells:
                queue.extend(cell.tables)


def _replace_placeholders_in_docx(doc: DocxDocument, replacements: dict[str, str]) -> None:
    """
    Replace placeholder strings (e.g. '[CAMPO]') everywhere in a python-docx Document.

    Covers:
      - All body paragraphs (top-level text)
      - All table cells, including tables nested inside table cells
        (python-docx's doc.tables only returns top-level tables; we need BFS)
    """
    # Body paragraphs
    for para in doc.paragraphs:
        _replace_in_paragraph_elem(para._p, replacements)

    # All tables — BFS to reach nested tables too
    for table in _iter_all_tables_inline(doc):
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    _replace_in_paragraph_elem(para._p, replacements)


async def _convert_docx_to_pdf_via_libreoffice(docx_bytes: bytes) -> bytes:
    """
    Convert DOCX bytes → PDF bytes using LibreOffice headless.

    LibreOffice is the only reliable way to produce a pixel-perfect PDF from a DOCX
    (it uses the same rendering engine as the desktop app).  We run it as a subprocess
    to avoid blocking the async event loop.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = os.path.join(tmpdir, "document.docx")
        with open(docx_path, "wb") as fh:
            fh.write(docx_bytes)

        # Give LibreOffice its own HOME so it never conflicts with another instance
        env = os.environ.copy()
        env["HOME"] = tmpdir

        try:
            proc = await asyncio.create_subprocess_exec(
                "libreoffice",
                "--headless",
                "--norestore",
                "--convert-to", "pdf",
                "--outdir", tmpdir,
                docx_path,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        except asyncio.TimeoutError:
            proc.kill()
            logger.error("LibreOffice PDF conversion timed out")
            raise HTTPException(
                status_code=500,
                detail="PDF conversion timed out",
            )

        if proc.returncode != 0:
            logger.error(
                "LibreOffice conversion failed (exit=%d): %s",
                proc.returncode,
                stderr.decode(errors="replace"),
            )
            raise HTTPException(
                status_code=500,
                detail="PDF conversion failed",
            )

        pdf_path = os.path.join(tmpdir, "document.pdf")
        if not os.path.exists(pdf_path):
            logger.error("LibreOffice ran successfully but produced no PDF output")
            raise HTTPException(
                status_code=500,
                detail="PDF conversion produced no output",
            )

        with open(pdf_path, "rb") as fh:
            return fh.read()


def _build_partner_replacements(entity_type: str, partner_info: dict) -> dict[str, str]:
    """Build placeholder → value mapping for partner fields + date."""
    today = datetime.now(timezone.utc)
    date_replacements = {
        "[DÍA]": str(today.day),
        "[MES]": _MESES[today.month],
        "[AÑO]": str(today.year),
    }

    field_map = PARTNER_PF_MAP if entity_type == "PF" else PARTNER_PJ_MAP

    replacements: dict[str, str] = {}
    for placeholder, field_key in field_map.items():
        value = partner_info.get(field_key, "")
        replacements[placeholder] = str(value)

    replacements.update(date_replacements)
    return replacements


def _build_full_replacements(
    entity_type: str,
    partner_info: dict,
    contract_fields: dict,
) -> dict[str, str]:
    """Build placeholder → value mapping for partner fields + analyst fields + date."""
    replacements = _build_partner_replacements(entity_type, partner_info)

    for placeholder, field_key in ANALYST_MAP.items():
        value = contract_fields.get(field_key, "")
        replacements[placeholder] = str(value)

    return replacements


# ---------------------------------------------------------------------------
# Commission row duplication helpers
# ---------------------------------------------------------------------------


def _replace_commission_placeholders_in_row(row, commission: dict) -> None:
    """Replace commission placeholders in an existing python-docx table row."""
    replacements = {
        "[PRODUCTO DE SEGURO]": commission.get("producto", ""),
        "[PRIMA NETA TRAMO 1]": commission.get("prima", ""),
        "[PRIMA NETA TRAMO 2]": commission.get("prima_tramo2", ""),
        "[COMISIÓN NP]": commission.get("comision_np", ""),
        "[COMISIÓN CARTERA]": commission.get("comision_cartera", ""),
    }
    for cell in row.cells:
        for para in cell.paragraphs:
            _replace_in_paragraph_elem(para._p, replacements)


def _replace_commission_in_tr(tr_elem, commission: dict) -> None:
    """Replace commission placeholders directly in a raw lxml <w:tr> element."""
    replacements = {
        "[PRODUCTO DE SEGURO]": commission.get("producto", ""),
        "[PRIMA NETA TRAMO 1]": commission.get("prima", ""),
        "[PRIMA NETA TRAMO 2]": commission.get("prima_tramo2", ""),
        "[COMISIÓN NP]": commission.get("comision_np", ""),
        "[COMISIÓN CARTERA]": commission.get("comision_cartera", ""),
    }
    # Use _replace_in_paragraph_elem for each <w:p> inside this row,
    # so split-run placeholders are also handled correctly.
    for p_elem in tr_elem.findall(".//" + _W_NS + "p"):
        _replace_in_paragraph_elem(p_elem, replacements)


def _iter_all_tables(doc: DocxDocument):
    """
    Yield all tables in the document, including nested ones inside table cells.
    python-docx's doc.tables only returns top-level tables; nested tables require
    recursive traversal via cell.tables.
    """
    queue = list(doc.tables)
    while queue:
        table = queue.pop(0)
        yield table
        for row in table.rows:
            for cell in row.cells:
                queue.extend(cell.tables)


def _fill_commission_rows(doc: DocxDocument, commission_rows: list[dict]) -> None:
    """
    Find the commission template rows and fill them with commission data.

    The DOCX template has TWO consecutive rows with [PRODUCTO DE SEGURO]:
      - Row A: contains [PRIMA NETA TRAMO 1]
      - Row B: contains [PRIMA NETA TRAMO 2]

    For each commission entry the analyst provides:
      - Both rows A and B are duplicated as a pair.
      - Each pair is filled with the commission data.

    If commission_rows is empty, both template rows are removed.

    Uses _iter_all_tables to also search inside nested tables.
    """
    for table in _iter_all_tables(doc):
        for i, row in enumerate(table.rows):
            row_text = "".join(cell.text for cell in row.cells)
            if "[PRODUCTO DE SEGURO]" not in row_text:
                continue

            # Found the first template row. Check if the immediately following row
            # is also a commission template row (the TRAMO 2 row).
            template_trs = [row._tr]
            if i + 1 < len(table.rows):
                next_row = table.rows[i + 1]
                next_text = "".join(cell.text for cell in next_row.cells)
                if "[PRODUCTO DE SEGURO]" in next_text or "[PRIMA NETA TRAMO 2]" in next_text:
                    template_trs.append(next_row._tr)

            parent = template_trs[0].getparent()
            insert_after = template_trs[-1]  # insert new pairs after the last template row

            if not commission_rows:
                # No data — remove all template rows
                for tr in template_trs:
                    parent.remove(tr)
                return

            # ① Make deep copies of ALL template rows BEFORE modifying them.
            #    Each commission (after the first) gets its own copy of the pair.
            additional: list[tuple[list, dict]] = []
            for commission in commission_rows[1:]:
                tr_copies = [copy.deepcopy(tr) for tr in template_trs]
                additional.append((tr_copies, commission))

            # ② Fill the original template rows with the first commission.
            for tr in template_trs:
                _replace_commission_in_tr(tr, commission_rows[0])

            # ③ Insert and fill the copies for remaining commissions.
            for tr_copies, commission in additional:
                for new_tr in tr_copies:
                    insert_idx = list(parent).index(insert_after) + 1
                    parent.insert(insert_idx, new_tr)
                    insert_after = new_tr
                    _replace_commission_in_tr(new_tr, commission)

            return  # Only process the first matching commission table


def _extract_placeholder_context(doc: DocxDocument, placeholder: str) -> str | None:
    """
    Return the full text of the first paragraph that contains the given placeholder.
    Searches both body paragraphs and table cells (including nested tables).
    Returns None if the placeholder is not found.
    """
    for para in doc.paragraphs:
        if placeholder in para.text:
            return para.text.strip()
    for table in _iter_all_tables(doc):
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    if placeholder in para.text:
                        return para.text.strip()
    return None


def _extract_si_no_fields(doc: DocxDocument) -> list[str]:
    """
    Return the label (first-cell text) of every table row that contains [SI/NO].
    Used to discover which insurance products in Annex I need a Sí/No selection.
    Searches all tables including nested ones.
    """
    results: list[str] = []
    for table in _iter_all_tables(doc):
        for row in table.rows:
            row_text = "".join(cell.text for cell in row.cells)
            if "[SI/NO]" not in row_text:
                continue
            if not row.cells:
                continue
            label = row.cells[0].text.strip()
            if label and label not in results:
                results.append(label)
    return results


def _fill_si_no_fields(doc: DocxDocument, si_no_values: dict[str, str]) -> None:
    """
    For each table row containing [SI/NO], look up the row's label (first-cell text)
    in si_no_values and replace [SI/NO] with the corresponding value ("Sí" or "No").
    Processes all tables including nested ones.
    """
    for table in _iter_all_tables(doc):
        for row in table.rows:
            row_text = "".join(cell.text for cell in row.cells)
            if "[SI/NO]" not in row_text:
                continue
            label = row.cells[0].text.strip() if row.cells else ""
            value = si_no_values.get(label, "")
            if value:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        _replace_in_paragraph_elem(para._p, {"[SI/NO]": value})


# ---------------------------------------------------------------------------
# GET /api/contract-templates  (JWT required — list all for admin)
# ---------------------------------------------------------------------------


@router.get("/contract-templates", response_model=AllTemplatesResponse)
async def list_all_templates(
    db: AsyncSession = Depends(get_db),
    current_analyst: Analyst = Depends(get_current_analyst),
):
    """
    Return all contract templates (one per provider_type × entity_type combination).
    Used by the admin UI to show what has been uploaded.
    """
    result = await db.execute(
        select(ContractTemplate).options(
            selectinload(ContractTemplate.uploaded_by_analyst)
        )
    )
    templates = result.scalars().all()

    template_map = {
        (t.provider_type, t.entity_type): t for t in templates
    }

    items = []
    for pt in sorted(VALID_PROVIDER_TYPES):
        for et in ("PJ", "PF"):
            t = template_map.get((pt, et))
            if t:
                items.append(
                    ContractTemplateInfo(
                        provider_type=t.provider_type,
                        entity_type=t.entity_type,
                        provider_type_label=PROVIDER_TYPE_LABELS.get(t.provider_type, t.provider_type),
                        entity_type_label=ENTITY_TYPE_LABELS.get(t.entity_type, t.entity_type),
                        original_filename=t.original_filename,
                        uploaded_at=t.uploaded_at,
                        uploaded_by_name=(
                            t.uploaded_by_analyst.full_name
                            if t.uploaded_by_analyst
                            else None
                        ),
                    )
                )

    return AllTemplatesResponse(templates=items)


# ---------------------------------------------------------------------------
# GET /api/contract-templates/{provider_type}/{entity_type}  (PUBLIC)
# ---------------------------------------------------------------------------


@router.get("/contract-templates/{provider_type}/{entity_type}")
async def get_template_info(
    provider_type: str,
    entity_type: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Public endpoint: returns metadata about a contract template if it exists.
    Used by the partner invite page to decide whether to show a download button.
    Returns 404 if no template has been uploaded for this combination.
    """
    if provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid provider_type. Must be one of: {', '.join(sorted(VALID_PROVIDER_TYPES))}",
        )
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="entity_type must be 'PF' or 'PJ'",
        )

    result = await db.execute(
        select(ContractTemplate).where(
            ContractTemplate.provider_type == provider_type,
            ContractTemplate.entity_type == entity_type,
        )
    )
    template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No template uploaded")

    return {
        "provider_type": template.provider_type,
        "entity_type": template.entity_type,
        "original_filename": template.original_filename,
        "uploaded_at": template.uploaded_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /api/contract-templates/{provider_type}/{entity_type}/download  (PUBLIC)
# ---------------------------------------------------------------------------


@router.get("/contract-templates/{provider_type}/{entity_type}/download")
async def download_template(
    provider_type: str,
    entity_type: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Public endpoint: download the raw DOCX template for a provider type + entity type.
    """
    if provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid provider_type",
        )
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="entity_type must be 'PF' or 'PJ'",
        )

    result = await db.execute(
        select(ContractTemplate).where(
            ContractTemplate.provider_type == provider_type,
            ContractTemplate.entity_type == entity_type,
        )
    )
    template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No template found")

    if not os.path.exists(template.file_path):
        logger.error(
            "Contract template file missing on disk: %s (provider=%s entity=%s)",
            template.file_path,
            provider_type,
            entity_type,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template file not found on disk",
        )

    return FileResponse(
        path=template.file_path,
        media_type=DOCX_MIME_TYPE,
        filename=template.original_filename,
        headers={
            "Content-Disposition": f'attachment; filename="{template.original_filename}"'
        },
    )


# ---------------------------------------------------------------------------
# POST /api/contract-templates/{provider_type}/{entity_type}/generate  (PUBLIC)
# ---------------------------------------------------------------------------


@router.post("/contract-templates/{provider_type}/{entity_type}/generate")
async def generate_contract_pdf(
    provider_type: str,
    entity_type: str,
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Public endpoint (partner version): fill partner fields + date in the contract
    template and return a personalised PDF.

    Commission placeholders ([PRODUCTO DE SEGURO], etc.) and analyst fields
    ([ACTIVIDAD]) are intentionally left unchanged — they will be filled later
    by the analyst via the /generate-full endpoint.

    Pipeline:
      1. Load DOCX from disk
      2. Replace partner placeholders only (lxml approach)
      3. Convert patched DOCX → PDF via LibreOffice headless subprocess
      4. Stream the PDF back to the caller
    """
    if provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid provider_type. Must be one of: {', '.join(sorted(VALID_PROVIDER_TYPES))}",
        )
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="entity_type must be 'PF' or 'PJ'",
        )

    result = await db.execute(
        select(ContractTemplate).where(
            ContractTemplate.provider_type == provider_type,
            ContractTemplate.entity_type == entity_type,
        )
    )
    template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No contract template found for this provider type and entity type",
        )

    if not os.path.exists(template.file_path):
        logger.error(
            "Contract template file missing on disk: %s", template.file_path
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template file not found on disk",
        )

    # ── 1. Load and patch the DOCX (partner fields + date only) ──────────────
    doc = DocxDocument(template.file_path)
    replacements = _build_partner_replacements(entity_type, body.partner_info)
    _replace_placeholders_in_docx(doc, replacements)
    # Commission placeholders and [ACTIVIDAD] are deliberately left as-is.

    # ── 2. Save patched DOCX to an in-memory buffer ───────────────────────────
    docx_buffer = io.BytesIO()
    doc.save(docx_buffer)
    docx_bytes = docx_buffer.getvalue()

    # ── 3. Convert patched DOCX → PDF via LibreOffice ────────────────────────
    pdf_bytes = await _convert_docx_to_pdf_via_libreoffice(docx_bytes)

    # ── 4. Stream back ────────────────────────────────────────────────────────
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="contrato.pdf"',
        },
    )


# ---------------------------------------------------------------------------
# POST /api/contract-templates/{provider_type}/{entity_type}/generate-full  (JWT)
# ---------------------------------------------------------------------------


@router.post("/contract-templates/{provider_type}/{entity_type}/generate-full")
async def generate_full_contract_pdf(
    provider_type: str,
    entity_type: str,
    body: GenerateFullRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_analyst: Analyst = Depends(get_current_analyst),
):
    """
    Analyst-only endpoint: fill all placeholders (partner + analyst fields + commissions)
    and return a fully completed contract PDF.

    Pipeline:
      1. Load DOCX from disk
      2. Replace all partner + analyst placeholders
      3. Duplicate commission table rows and fill them
      4. Convert to PDF via LibreOffice
      5. Stream the PDF back
    """
    if provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid provider_type. Must be one of: {', '.join(sorted(VALID_PROVIDER_TYPES))}",
        )
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="entity_type must be 'PF' or 'PJ'",
        )

    result = await db.execute(
        select(ContractTemplate).where(
            ContractTemplate.provider_type == provider_type,
            ContractTemplate.entity_type == entity_type,
        )
    )
    template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No contract template found for this provider type and entity type",
        )

    if not os.path.exists(template.file_path):
        logger.error(
            "Contract template file missing on disk: %s", template.file_path
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template file not found on disk",
        )

    contract_fields = body.contract_data.get("fields", {})
    commission_rows = body.contract_data.get("commissions", [])

    # ── 1. Load DOCX ─────────────────────────────────────────────────────────
    doc = DocxDocument(template.file_path)

    # ── 2. Replace all partner + analyst placeholders ─────────────────────────
    replacements = _build_full_replacements(entity_type, body.partner_info, contract_fields)
    _replace_placeholders_in_docx(doc, replacements)

    # ── 3. Handle SI/NO fields (Annex I) ─────────────────────────────────────
    si_no_fields = body.contract_data.get("si_no_fields", {})
    if si_no_fields:
        _fill_si_no_fields(doc, si_no_fields)

    # ── 4. Handle commission table rows ──────────────────────────────────────
    # Filter out empty rows (producto is required; rows with no producto are skipped)
    non_empty_commissions = [
        r for r in commission_rows if r.get("producto", "").strip()
    ]
    # Always call _fill_commission_rows — if the list is empty it removes the template row
    _fill_commission_rows(doc, non_empty_commissions)

    # ── 5. Save patched DOCX to an in-memory buffer ───────────────────────────
    docx_buffer = io.BytesIO()
    doc.save(docx_buffer)
    docx_bytes = docx_buffer.getvalue()

    # ── 6. Convert patched DOCX → PDF via LibreOffice ────────────────────────
    pdf_bytes = await _convert_docx_to_pdf_via_libreoffice(docx_bytes)

    # ── 7. Stream back ────────────────────────────────────────────────────────
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="contrato_completo.pdf"',
        },
    )


# ---------------------------------------------------------------------------
# GET /api/contract-templates/{provider_type}/{entity_type}/placeholder-context  (JWT)
# ---------------------------------------------------------------------------


@router.get("/contract-templates/{provider_type}/{entity_type}/placeholder-context")
async def get_placeholder_context(
    provider_type: str,
    entity_type: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_analyst: Analyst = Depends(get_current_analyst),
):
    """
    Return the full paragraph text surrounding key placeholders ([ACTIVIDAD]).
    Used by the analyst UI to show context hints next to input fields.
    Returns an empty dict if no template has been uploaded.
    """
    if provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(status_code=422, detail="Invalid provider_type")
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(status_code=422, detail="entity_type must be 'PF' or 'PJ'")

    result = await db.execute(
        select(ContractTemplate).where(
            ContractTemplate.provider_type == provider_type,
            ContractTemplate.entity_type == entity_type,
        )
    )
    template = result.scalar_one_or_none()
    if template is None or not os.path.exists(template.file_path):
        return {"context": {}}

    try:
        doc = DocxDocument(template.file_path)
        context: dict[str, str] = {}
        actividad_ctx = _extract_placeholder_context(doc, "[ACTIVIDAD]")
        if actividad_ctx:
            context["ACTIVIDAD"] = actividad_ctx
        return {"context": context}
    except Exception as exc:
        logger.error("Error extracting placeholder context: %s", exc)
        return {"context": {}}


# ---------------------------------------------------------------------------
# GET /api/contract-templates/{provider_type}/{entity_type}/si-no-fields  (JWT)
# ---------------------------------------------------------------------------


@router.get("/contract-templates/{provider_type}/{entity_type}/si-no-fields")
async def get_si_no_fields(
    provider_type: str,
    entity_type: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_analyst: Analyst = Depends(get_current_analyst),
):
    """
    Return the list of insurance product labels that have a [SI/NO] placeholder
    in the contract template's Annex I table.
    Returns an empty list if no template has been uploaded.
    """
    if provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(status_code=422, detail="Invalid provider_type")
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(status_code=422, detail="entity_type must be 'PF' or 'PJ'")

    result = await db.execute(
        select(ContractTemplate).where(
            ContractTemplate.provider_type == provider_type,
            ContractTemplate.entity_type == entity_type,
        )
    )
    template = result.scalar_one_or_none()
    if template is None or not os.path.exists(template.file_path):
        return {"fields": []}

    try:
        doc = DocxDocument(template.file_path)
        fields = _extract_si_no_fields(doc)
        return {"fields": fields}
    except Exception as exc:
        logger.error("Error extracting SI/NO fields: %s", exc)
        return {"fields": []}


# ---------------------------------------------------------------------------
# PUT /api/contract-templates/{provider_type}/{entity_type}  (JWT required)
# ---------------------------------------------------------------------------


@router.put(
    "/contract-templates/{provider_type}/{entity_type}",
    response_model=ContractTemplateInfo,
)
async def upload_template(
    provider_type: str,
    entity_type: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_analyst: Analyst = Depends(get_current_analyst),
    settings: Settings = Depends(get_settings),
):
    """
    Upload or replace the contract template DOCX for a given provider type
    and entity type. Only DOCX files are accepted.
    """
    if provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid provider_type. Must be one of: {', '.join(sorted(VALID_PROVIDER_TYPES))}",
        )
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="entity_type must be 'PF' or 'PJ'",
        )

    filename_lower = (file.filename or "").lower()
    content_type_ok = file.content_type == DOCX_MIME_TYPE
    extension_ok = filename_lower.endswith(".docx")
    if not content_type_ok and not extension_ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only DOCX files are accepted for contract templates",
        )

    # Read content and check size (max 20 MB)
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File exceeds the 20 MB size limit",
        )

    # Save to disk — fixed path: contract_templates/{provider_type}_{entity_type}.docx
    template_dir = _get_template_dir(settings.DOCUMENTS_BASE_PATH)
    file_path = os.path.join(template_dir, f"{provider_type}_{entity_type}.docx")

    with open(file_path, "wb") as f:
        f.write(content)

    safe_original = _sanitize_filename(
        file.filename or f"{provider_type}_{entity_type}_contrato.docx"
    )

    # Upsert in DB
    result = await db.execute(
        select(ContractTemplate).where(
            ContractTemplate.provider_type == provider_type,
            ContractTemplate.entity_type == entity_type,
        )
    )
    existing = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if existing:
        existing.file_path = file_path
        existing.original_filename = safe_original
        existing.uploaded_at = now
        existing.uploaded_by_analyst_id = current_analyst.id
        template_record = existing
    else:
        template_record = ContractTemplate(
            id=uuid.uuid4(),
            provider_type=provider_type,
            entity_type=entity_type,
            file_path=file_path,
            original_filename=safe_original,
            uploaded_at=now,
            uploaded_by_analyst_id=current_analyst.id,
        )
        db.add(template_record)

    await _log_audit(
        db=db,
        action="contract_template_uploaded",
        analyst_id=current_analyst.id,
        metadata={
            "provider_type": provider_type,
            "entity_type": entity_type,
            "original_filename": safe_original,
            "analyst_email": current_analyst.email,
        },
    )
    await db.commit()
    await db.refresh(template_record, ["uploaded_by_analyst"])

    return ContractTemplateInfo(
        provider_type=template_record.provider_type,
        entity_type=template_record.entity_type,
        provider_type_label=PROVIDER_TYPE_LABELS.get(template_record.provider_type, template_record.provider_type),
        entity_type_label=ENTITY_TYPE_LABELS.get(template_record.entity_type, template_record.entity_type),
        original_filename=template_record.original_filename,
        uploaded_at=template_record.uploaded_at,
        uploaded_by_name=(
            template_record.uploaded_by_analyst.full_name
            if template_record.uploaded_by_analyst
            else None
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/contract-templates/{provider_type}/{entity_type}/debug  (JWT)
# Diagnostic endpoint — dumps all text runs in the DOCX to help identify
# why placeholders are not being found or replaced.
# ---------------------------------------------------------------------------


@router.get("/contract-templates/{provider_type}/{entity_type}/debug")
async def debug_template(
    provider_type: str,
    entity_type: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_analyst: Analyst = Depends(get_current_analyst),
):
    """
    Diagnostic endpoint: returns the full text content of the contract template
    at run level, so we can see exactly how placeholders are stored in the DOCX XML.
    Only accessible to authenticated analysts.
    """
    if provider_type not in VALID_PROVIDER_TYPES:
        raise HTTPException(status_code=422, detail="Invalid provider_type")
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(status_code=422, detail="entity_type must be 'PF' or 'PJ'")

    result = await db.execute(
        select(ContractTemplate).where(
            ContractTemplate.provider_type == provider_type,
            ContractTemplate.entity_type == entity_type,
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        return {"error": "No template uploaded for this combination"}
    if not os.path.exists(template.file_path):
        return {"error": "Template file missing on disk", "path": template.file_path}

    try:
        doc = DocxDocument(template.file_path)
    except Exception as exc:
        return {"error": f"Could not open DOCX: {exc}"}

    # All expected placeholders (so we can report which ones are found)
    all_expected = list(PARTNER_PF_MAP.keys()) + list(PARTNER_PJ_MAP.keys()) + list(ANALYST_MAP.keys()) + COMMISSION_PLACEHOLDERS + ["[SI/NO]", "[DÍA]", "[MES]", "[AÑO]"]

    def _para_debug(para, location: str) -> dict | None:
        runs = [r.text for r in para.runs]
        full = para.text
        found_phs = [ph for ph in all_expected if ph in full]
        # Also detect partial/split placeholders by looking for bracket chars
        has_bracket = "[" in full or "]" in full
        if not full.strip() and not has_bracket:
            return None
        return {
            "location": location,
            "full_text": full[:200],
            "runs": runs,
            "placeholders_found": found_phs,
            "has_bracket": has_bracket,
        }

    paragraphs_info = []

    # Body paragraphs
    for i, para in enumerate(doc.paragraphs):
        info = _para_debug(para, f"body_para_{i}")
        if info:
            paragraphs_info.append(info)

    # All table cells (including nested)
    table_idx = 0
    for table in _iter_all_tables(doc):
        for ri, row in enumerate(table.rows):
            for ci, cell in enumerate(row.cells):
                for pi, para in enumerate(cell.paragraphs):
                    info = _para_debug(
                        para, f"table{table_idx}_row{ri}_cell{ci}_para{pi}"
                    )
                    if info:
                        paragraphs_info.append(info)
        table_idx += 1

    # Summary: which expected placeholders were found anywhere
    all_text = " ".join(p["full_text"] for p in paragraphs_info)
    found_summary = {ph: (ph in all_text) for ph in all_expected}

    return {
        "filename": template.original_filename,
        "placeholder_summary": found_summary,
        "paragraphs": paragraphs_info,
        "total_paragraphs_with_content": len(paragraphs_info),
    }


# ---------------------------------------------------------------------------
# GET /api/diag/{secret}  — PUBLIC diagnostic (no JWT, protected by secret)
# Temporary endpoint to diagnose DOCX templates from the browser.
# Visit: /api/diag/tuio2024  in any browser tab (must be logged in to the app
# so the server is reachable, but no JWT header needed).
# ---------------------------------------------------------------------------


@router.get("/diag/{secret}")
async def diag_all_templates(
    secret: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Temporary public diagnostic endpoint. Returns analysis of all uploaded
    contract templates — which placeholders exist and how they are split across
    XML runs.  Protected by a simple URL secret so it is not completely open.
    Remove this endpoint once diagnosis is complete.
    """
    if secret != "tuio2024":
        raise HTTPException(status_code=404, detail="Not found")

    result = await db.execute(select(ContractTemplate))
    templates = result.scalars().all()

    if not templates:
        return {"error": "No contract templates uploaded yet"}

    all_expected = (
        list(PARTNER_PF_MAP.keys())
        + list(PARTNER_PJ_MAP.keys())
        + list(ANALYST_MAP.keys())
        + COMMISSION_PLACEHOLDERS
        + ["[SI/NO]", "[DÍA]", "[MES]", "[AÑO]"]
    )
    # Deduplicate
    all_expected = list(dict.fromkeys(all_expected))

    output = {}

    for tmpl in templates:
        key = f"{tmpl.provider_type}/{tmpl.entity_type}"
        if not os.path.exists(tmpl.file_path):
            output[key] = {"error": "file missing on disk"}
            continue

        try:
            doc = DocxDocument(tmpl.file_path)
        except Exception as exc:
            output[key] = {"error": str(exc)}
            continue

        entries = []

        def _collect(para, loc: str) -> None:
            text = para.text
            if "[" not in text and "]" not in text:
                return
            runs = [r.text for r in para.runs if r.text]
            entries.append({
                "loc": loc,
                "full_text": text,
                "runs": runs,
            })

        for i, p in enumerate(doc.paragraphs):
            _collect(p, f"body_p{i}")

        queue = list(doc.tables)
        ti = 0
        while queue:
            tbl = queue.pop(0)
            for ri, row in enumerate(tbl.rows):
                for ci, cell in enumerate(row.cells):
                    for pi, p in enumerate(cell.paragraphs):
                        _collect(p, f"t{ti}r{ri}c{ci}p{pi}")
                    queue.extend(cell.tables)
            ti += 1

        all_text = " ".join(e["full_text"] for e in entries)
        summary = {ph: (ph in all_text) for ph in all_expected}

        output[key] = {
            "filename": tmpl.original_filename,
            "placeholder_summary": summary,
            "bracket_paragraphs": entries,
        }

    return output
