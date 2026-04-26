import os
import re


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
