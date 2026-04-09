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
    image_b64: Optional[str]  # Base64-encoded image bytes (for JPG/PNG or scanned PDF pages)
    mime_type: str


def _extract_pdf_text(file_path: str) -> Optional[str]:
    """
    Extract text from a PDF using PyMuPDF.
    Returns the text if meaningful (>= 50 chars), or None if the PDF appears to be scanned.
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

        if len(full_text.strip()) >= 50:
            return full_text.strip()

        return None  # Too little text — caller should try image rendering

    except Exception as exc:
        logger.warning("Failed to extract text from PDF %s: %s", file_path, exc)
        return None


def _pdf_pages_to_images(
    file_path: str, max_pages: int = 5, dpi: int = 200
) -> list[tuple[str, str]]:
    """
    Render PDF pages as base64-encoded PNG images.

    Used for scanned PDFs (passports, ID cards, certificates) where text extraction
    returns too little content. Sending the rendered page images to Claude Vision
    gives much better analysis quality than OCR text.

    Returns a list of (base64_string, mime_type) tuples, one per page.
    """
    try:
        import fitz
    except ImportError:
        logger.error("PyMuPDF (fitz) is not installed — cannot render PDF pages")
        return []

    try:
        doc = fitz.open(file_path)
        pages_to_process = min(max_pages, len(doc))
        images = []

        for page_num in range(pages_to_process):
            page = doc[page_num]
            # 200 DPI: good quality for document analysis without excessive file size
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            images.append((b64, "image/png"))

        doc.close()
        return images

    except Exception as exc:
        logger.warning(
            "Failed to render PDF pages as images for %s: %s", file_path, exc
        )
        return []


def _ocr_pdf(file_path: str) -> Optional[str]:
    """
    OCR fallback: render PDF pages and run pytesseract on them.
    Used only when _pdf_pages_to_images() also fails.
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
            mat = fitz.Matrix(200 / 72, 200 / 72)
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

    For scanned PDFs (passports, ID cards, certificates): renders pages as images
    and sends them to Claude Vision instead of doing OCR. This gives significantly
    better analysis quality for identity documents.

    Args:
        documents: List of dicts with keys: filename, label, file_path, mime_type

    Returns:
        List of ExtractedDoc objects. A scanned PDF may produce multiple ExtractedDoc
        objects (one per page). Failed extractions have both text=None and image_b64=None.
    """
    results: list[ExtractedDoc] = []

    for doc in documents:
        filename = doc["filename"]
        label = doc["label"]
        file_path = doc["file_path"]
        mime_type = doc["mime_type"]

        try:
            if mime_type == "application/pdf":
                # First: try text extraction
                text = _extract_pdf_text(file_path)

                if text:
                    # PDF has meaningful text — use it directly
                    results.append(
                        ExtractedDoc(
                            filename=filename,
                            label=label,
                            text=text,
                            image_b64=None,
                            mime_type=mime_type,
                        )
                    )
                else:
                    # Scanned PDF — render pages as images for Claude Vision
                    logger.info(
                        "PDF '%s' has little text — rendering pages as images for Claude Vision",
                        filename,
                    )
                    page_images = _pdf_pages_to_images(file_path)

                    if page_images:
                        # Send each page as a separate image block to Claude Vision
                        for i, (b64, img_mime) in enumerate(page_images):
                            page_label = (
                                f"{label} — p.{i + 1}"
                                if len(page_images) > 1
                                else label
                            )
                            results.append(
                                ExtractedDoc(
                                    filename=filename,
                                    label=page_label,
                                    text=None,
                                    image_b64=b64,
                                    mime_type=img_mime,
                                )
                            )
                    else:
                        # Image rendering failed — fall back to OCR
                        logger.warning(
                            "Image rendering failed for '%s' — falling back to OCR",
                            filename,
                        )
                        ocr_text = _ocr_pdf(file_path)
                        results.append(
                            ExtractedDoc(
                                filename=filename,
                                label=label,
                                text=ocr_text,
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
                # For images, hand the raw pixels directly to Claude Vision —
                # no OCR, which would reduce quality and lose visual information.
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
