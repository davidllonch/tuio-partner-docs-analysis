import asyncio
import logging
import os
import tempfile

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Limit concurrent LibreOffice processes. Each conversion spawns a full LibreOffice
# instance — running many in parallel exhausts CPU and memory quickly. Two concurrent
# conversions is enough for a small team and protects the server under load.
_LIBREOFFICE_SEMAPHORE = asyncio.Semaphore(2)


async def convert_docx_to_pdf_via_libreoffice(docx_bytes: bytes) -> bytes:
    """
    Convert DOCX bytes -> PDF bytes using LibreOffice headless.

    LibreOffice is the only reliable way to produce a pixel-perfect PDF from a DOCX
    (it uses the same rendering engine as the desktop app).  We run it as a subprocess
    to avoid blocking the async event loop.

    The semaphore limits concurrent conversions to 2 — each LibreOffice instance is
    CPU-heavy and starting too many in parallel would exhaust server resources.
    """
    async with _LIBREOFFICE_SEMAPHORE:
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
