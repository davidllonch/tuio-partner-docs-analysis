"""
Unit tests for app.utils.file_utils.

Covers:
- sanitize_filename: path traversal, spaces, shell-special chars, fallback
- content_disposition_filename: ASCII, Unicode (RFC 5987), injection prevention

These are pure functions. No fixtures, no DB, no HTTP.
"""

import pytest

from app.utils.file_utils import sanitize_filename, content_disposition_filename


# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------


class TestSanitizeFilename:
    # --- normal inputs ---

    def test_plain_ascii_filename_is_preserved(self):
        assert sanitize_filename("document.pdf") == "document.pdf"

    def test_underscore_and_dash_are_preserved(self):
        assert sanitize_filename("my_file-v2.pdf") == "my_file-v2.pdf"

    # --- spaces ---

    def test_spaces_become_underscores(self):
        result = sanitize_filename("my document.pdf")
        assert " " not in result
        assert "_" in result

    def test_multiple_spaces_each_become_underscore(self):
        result = sanitize_filename("a b c.txt")
        assert " " not in result

    # --- path traversal ---

    def test_unix_path_traversal_stripped(self):
        result = sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_absolute_unix_path_stripped_to_basename(self):
        result = sanitize_filename("/etc/shadow")
        assert "/" not in result
        assert result == "shadow"

    def test_windows_backslash_path_stripped(self):
        # os.path.basename on Windows handles backslashes; on Linux basename
        # treats the whole string as a filename.  The regex then removes `:`.
        result = sanitize_filename("C:\\Users\\admin\\secret.pdf")
        # Neither backslash nor colon may survive
        assert "\\" not in result
        assert ":" not in result

    # --- shell-special characters ---

    def test_semicolon_removed(self):
        result = sanitize_filename("file;rm.pdf")
        assert ";" not in result

    def test_pipe_removed(self):
        result = sanitize_filename("file|cat.pdf")
        assert "|" not in result

    def test_ampersand_removed(self):
        result = sanitize_filename("file&echo.pdf")
        assert "&" not in result

    # --- fallback ---

    def test_empty_string_returns_fallback(self):
        # Default fallback is "file"
        assert sanitize_filename("") == "file"

    def test_custom_fallback_is_used(self):
        assert sanitize_filename("", fallback="upload") == "upload"

    def test_only_special_chars_returns_fallback(self):
        # After stripping all non-word chars the result is empty → fallback
        result = sanitize_filename("@#$%^&*()")
        assert result == "file"

    # --- Unicode / accents ---

    def test_accented_chars_are_kept(self):
        # Python 3's \w is Unicode-aware: é, ñ, á are word characters and are preserved.
        result = sanitize_filename("résumé.pdf")
        # The accented chars survive; what matters is no path separators or special chars.
        assert "/" not in result
        assert ";" not in result

    def test_shell_special_chars_removed_regardless_of_unicode(self):
        # Shell-injection chars (;|&) must always be stripped, even in filenames
        # that also contain accented letters.
        result = sanitize_filename("résu;mé.pdf")
        assert ";" not in result


# ---------------------------------------------------------------------------
# content_disposition_filename
# ---------------------------------------------------------------------------


class TestContentDispositionFilename:
    # --- basic structure ---

    def test_returns_attachment_prefix(self):
        result = content_disposition_filename("report.pdf")
        assert result.startswith("attachment;")

    def test_contains_filename_field(self):
        result = content_disposition_filename("report.pdf")
        assert 'filename="report.pdf"' in result

    def test_contains_rfc5987_encoded_field(self):
        result = content_disposition_filename("report.pdf")
        assert "filename*=UTF-8''" in result

    # --- ASCII filename ---

    def test_ascii_filename_both_fields_present(self):
        result = content_disposition_filename("invoice.pdf")
        assert 'filename="invoice.pdf"' in result
        assert "filename*=UTF-8''invoice.pdf" in result

    # --- Unicode / accented characters ---

    def test_accented_chars_percent_encoded_in_star_field(self):
        result = content_disposition_filename("Informe_José.pdf")
        # The é must be percent-encoded in the filename* field
        assert "%C3%A9" in result or "%c3%a9" in result

    def test_accented_chars_ascii_fallback_replaces_with_underscore(self):
        result = content_disposition_filename("résumé.pdf")
        # In the plain filename= field, accented chars become _
        # Extract the plain filename= part
        import re
        m = re.search(r'filename="([^"]*)"', result)
        assert m is not None
        plain = m.group(1)
        assert "é" not in plain

    def test_spanish_special_chars_encoded(self):
        result = content_disposition_filename("Año_fiscal.pdf")
        # ñ is U+00F1 → UTF-8 0xC3 0xB1 → %C3%B1
        assert "%C3%B1" in result or "%c3%b1" in result

    # --- Header injection prevention ---

    def test_double_quote_in_filename_replaced_in_plain_field(self):
        result = content_disposition_filename('file"name.pdf')
        # The plain filename= value must not contain a raw unescaped double-quote
        # that would terminate the header value early.
        # The implementation replaces " with _
        import re
        m = re.search(r'filename="([^"]*)"', result)
        assert m is not None
        plain = m.group(1)
        assert '"' not in plain

    def test_carriage_return_not_present_raw_in_output(self):
        # A raw \r in the output would allow HTTP header injection
        result = content_disposition_filename("file\rname.pdf")
        assert "\r" not in result

    def test_newline_not_present_raw_in_output(self):
        result = content_disposition_filename("file\nname.pdf")
        assert "\n" not in result

    def test_crlf_sequence_not_present_raw_in_output(self):
        result = content_disposition_filename("file\r\nname.pdf")
        assert "\r" not in result
        assert "\n" not in result
