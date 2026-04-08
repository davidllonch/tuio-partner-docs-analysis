import base64
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ExtractedDoc:
    filename: str
    label: str
    text: Optional[str]       # Extracted text content (for PDFs and DOCX)
    image_b64: Optional[str]  # Base64-encoded image bytes (for JPG/PNG)
    mime_type: str


def _extract_pdf(file_path: str) -> Optional[str]:
    """
    Extract text from a PDF file using PyMuPDF (fitz).
    If the text is too short (scanned document), fall back to OCR via pytesseract.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) is not installed — cannot extract PDF text")
        return None

    try:
        doc = fitz.open(file_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        doc.close()

        # If extracted text is meaningful, return it directly
        if len(full_text.strip()) >= 50:
            return full_text.strip()

        # Text is too short — likely a scanned PDF. Fall back to OCR.
        logger.info(
            "PDF text extraction returned < 50 chars for %s — attempting OCR", file_path
        )
        return _ocr_pdf(file_path)

    except Exception as exc:
        logger.warning("Failed to extract text from PDF %s: %s", file_path, exc)
        return None


def _ocr_pdf(file_path: str) -> Optional[str]:
    """
    Render the first 10 pages of a PDF as images and run pytesseract OCR on them.
    This handles scanned documents where the text is embedded as an image.
    """
    try:
        import fitz
        import pytesseract
        from PIL import Image
        import io
    except ImportError as exc:
        logger.error("Missing dependency for OCR: %s", exc)
        return None

    try:
        doc = fitz.open(file_path)
        pages_to_process = min(10, len(doc))
        ocr_texts = []

        for page_num in range(pages_to_process):
            page = doc[page_num]
            # Render at 150 DPI — good balance between quality and speed
            mat = fitz.Matrix(150 / 72, 150 / 72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            page_text = pytesseract.image_to_string(img, lang="spa+eng")
            if page_text.strip():
                ocr_texts.append(page_text.strip())

        doc.close()
        result = "\n\n".join(ocr_texts)
        return result if result.strip() else None

    except Exception as exc:
        logger.warning("OCR failed for %s: %s", file_path, exc)
        return None


def _extract_docx(file_path: str) -> Optional[str]:
    """Extract all paragraph text from a Word (.docx) file."""
    try:
        from docx import Document
    except ImportError:
        logger.error("python-docx is not installed — cannot extract DOCX text")
        return None

    try:
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs) if paragraphs else None
    except Exception as exc:
        logger.warning("Failed to extract text from DOCX %s: %s", file_path, exc)
        return None


def _encode_image(file_path: str) -> Optional[str]:
    """Read an image file and return its base64-encoded bytes."""
    try:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as exc:
        logger.warning("Failed to read image file %s: %s", file_path, exc)
        return None


async def extract_documents(documents: list[dict]) -> list[ExtractedDoc]:
    """
    Extract content from a list of documents.

    Args:
        documents: List of dicts with keys: filename, label, file_path, mime_type

    Returns:
        List of ExtractedDoc objects. A document that fails extraction will have
        both text=None and image_b64=None — we log a warning and continue rather
        than crashing the entire pipeline.
    """
    results: list[ExtractedDoc] = []

    for doc in documents:
        filename = doc["filename"]
        label = doc["label"]
        file_path = doc["file_path"]
        mime_type = doc["mime_type"]

        try:
            if mime_type == "application/pdf":
                text = _extract_pdf(file_path)
                results.append(
                    ExtractedDoc(
                        filename=filename,
                        label=label,
                        text=text,
                        image_b64=None,
                        mime_type=mime_type,
                    )
                )

            elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                text = _extract_docx(file_path)
                results.append(
                    ExtractedDoc(
                        filename=filename,
                        label=label,
                        text=text,
                        image_b64=None,
                        mime_type=mime_type,
                    )
                )

            elif mime_type in ("image/jpeg", "image/png"):
                # For images, we hand the raw pixels to Claude Vision —
                # no OCR here, that would reduce quality.
                image_b64 = _encode_image(file_path)
                results.append(
                    ExtractedDoc(
                        filename=filename,
                        label=label,
                        text=None,
                        image_b64=image_b64,
                        mime_type=mime_type,
                    )
                )

            else:
                logger.warning(
                    "Unsupported mime_type %s for file %s — skipping extraction",
                    mime_type,
                    filename,
                )
                results.append(
                    ExtractedDoc(
                        filename=filename,
                        label=label,
                        text=None,
                        image_b64=None,
                        mime_type=mime_type,
                    )
                )

        except Exception as exc:
            logger.warning(
                "Unexpected error extracting %s (%s): %s", filename, mime_type, exc
            )
            results.append(
                ExtractedDoc(
                    filename=filename,
                    label=label,
                    text=None,
                    image_b64=None,
                    mime_type=mime_type,
                )
            )

    return results
