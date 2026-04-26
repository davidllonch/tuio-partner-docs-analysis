import os
import re
from urllib.parse import quote


def sanitize_filename(filename: str, fallback: str = "file") -> str:
    """
    Make a filename safe for storage on disk.
    Strips path separators (prevents path traversal), replaces spaces,
    and removes characters that could cause issues on any OS.
    """
    filename = os.path.basename(filename)
    filename = filename.replace(" ", "_")
    filename = re.sub(r"[^\w\-.]", "", filename)
    if not filename:
        filename = fallback
    return filename


def content_disposition_filename(filename: str) -> str:
    """
    Build a safe Content-Disposition header value with RFC 5987 encoding.

    Uses two fields:
    - filename="..."  ASCII fallback for old clients (non-ASCII chars replaced with _)
    - filename*=UTF-8''... percent-encoded for modern clients (full Unicode support)

    This prevents header injection: control characters (including \\r\\n) are
    percent-encoded so they can never split or inject extra HTTP headers.
    """
    ascii_fallback = re.sub(r"[^\x20-\x7E]", "_", filename).replace('"', "_")
    encoded = quote(filename, safe="")
    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'
