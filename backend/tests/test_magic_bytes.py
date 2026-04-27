"""
Unit tests for _verify_magic_bytes in app.routers.submissions.

Magic-byte verification checks that a file's actual binary content matches
the MIME type the caller declared. Think of it as opening a box labelled
"apples" and checking whether it actually contains apples.

These are pure function tests — no DB, no HTTP, no fixtures.
"""

import pytest

from app.routers.submissions import _verify_magic_bytes


class TestVerifyMagicBytes:
    # ---------------------------------------------------------------------------
    # PDF
    # ---------------------------------------------------------------------------

    def test_valid_pdf_bytes_accepted(self):
        data = b"%PDF-1.4 rest of file content"
        assert _verify_magic_bytes(data, "application/pdf") is True

    def test_zip_bytes_rejected_as_pdf(self):
        # PK\x03\x04 is a ZIP/DOCX header — not a PDF
        data = b"PK\x03\x04" + b"\x00" * 100
        assert _verify_magic_bytes(data, "application/pdf") is False

    def test_jpeg_bytes_rejected_as_pdf(self):
        data = b"\xFF\xD8\xFF\xE0" + b"\x00" * 100
        assert _verify_magic_bytes(data, "application/pdf") is False

    def test_empty_bytes_rejected_as_pdf(self):
        # Empty data cannot have %PDF header
        assert _verify_magic_bytes(b"", "application/pdf") is False

    # ---------------------------------------------------------------------------
    # JPEG
    # ---------------------------------------------------------------------------

    def test_valid_jpeg_bytes_accepted(self):
        data = b"\xFF\xD8\xFF\xE0" + b"\x00" * 100
        assert _verify_magic_bytes(data, "image/jpeg") is True

    def test_jpeg_variant_e1_accepted(self):
        # EXIF JPEGs start with \xFF\xD8\xFF\xE1
        data = b"\xFF\xD8\xFF\xE1" + b"\x00" * 100
        assert _verify_magic_bytes(data, "image/jpeg") is True

    def test_pdf_bytes_rejected_as_jpeg(self):
        data = b"%PDF-1.4 not a jpeg"
        assert _verify_magic_bytes(data, "image/jpeg") is False

    def test_empty_bytes_rejected_as_jpeg(self):
        assert _verify_magic_bytes(b"", "image/jpeg") is False

    def test_truncated_jpeg_header_rejected(self):
        # Only 2 bytes — can't match the 3-byte magic
        data = b"\xFF\xD8"
        assert _verify_magic_bytes(data, "image/jpeg") is False

    # ---------------------------------------------------------------------------
    # PNG
    # ---------------------------------------------------------------------------

    def test_valid_png_bytes_accepted(self):
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert _verify_magic_bytes(data, "image/png") is True

    def test_jpeg_bytes_rejected_as_png(self):
        data = b"\xFF\xD8\xFF\xE0" + b"\x00" * 100
        assert _verify_magic_bytes(data, "image/png") is False

    def test_empty_bytes_rejected_as_png(self):
        assert _verify_magic_bytes(b"", "image/png") is False

    # ---------------------------------------------------------------------------
    # DOCX (ZIP container)
    # ---------------------------------------------------------------------------

    def test_valid_docx_bytes_accepted(self):
        # DOCX is a ZIP — all ZIPs start with PK\x03\x04
        data = b"PK\x03\x04" + b"\x00" * 100
        assert _verify_magic_bytes(
            data,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ) is True

    def test_pdf_bytes_rejected_as_docx(self):
        data = b"%PDF-1.4 not a docx"
        assert _verify_magic_bytes(
            data,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ) is False

    def test_empty_bytes_rejected_as_docx(self):
        assert _verify_magic_bytes(
            b"",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ) is False

    # ---------------------------------------------------------------------------
    # Unknown / not-in-allowlist MIME type
    # ---------------------------------------------------------------------------

    def test_unknown_mime_type_passes_through(self):
        # The function returns True for MIME types it does not know about,
        # deferring the rejection to the MIME-type allowlist check upstream.
        data = b"<html>not a real document</html>"
        assert _verify_magic_bytes(data, "text/html") is True

    def test_unknown_mime_empty_bytes_passes_through(self):
        # Even empty bytes pass for an unknown MIME type
        assert _verify_magic_bytes(b"", "application/octet-stream") is True
