"""Export header formatting and sanitization utilities.

Enforces RFC 6266 and RFC 5987 standards for Content-Disposition headers.
Provides safe ASCII fallback filenames and UTF-8 percent-encoded filename* parameters.
Defends strictly against HTTP header injection, CR/LF control character splitting,
and Latin-1 encoding errors when processing Unicode/international filenames.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Tuple


def sanitize_filename(
    name: str,
    fallback: str = "export",
    extension: str = "pdf"
) -> Tuple[str, str]:
    """
    Sanitize an untrusted filename string into safe ASCII fallback and UTF-8 components.
    
    1. Strips all carriage returns, newlines, null bytes, and ASCII control characters (0x00-0x1F, 0x7F).
    2. Strips redundant extension suffixes if already present.
    3. Produces a safe ASCII-only fallback filename containing solely [a-zA-Z0-9_-].
    4. Produces a cleaned UTF-8 filename preserving international Unicode characters.
    """
    ext = extension.lstrip(".").lower()
    
    # Strictly strip all CR, LF, null bytes, and control characters to prevent header injection
    cleaned = re.sub(r"[\r\n\x00-\x1f\x7f]", "", str(name or "")).strip()

    # Remove redundant trailing extension if already included by caller
    if cleaned.lower().endswith(f".{ext}"):
        cleaned = cleaned[:-len(ext)-1].strip()

    # Produce safe ASCII fallback: replace anything not [a-zA-Z0-9_-] with '_'
    safe_ascii = re.sub(r"[^a-zA-Z0-9_\-]", "_", cleaned)
    # Collapse multiple consecutive underscores and strip leading/trailing underscores
    safe_ascii = re.sub(r"_+", "_", safe_ascii).strip("_")
    if not safe_ascii:
        safe_ascii = fallback

    safe_ascii_filename = f"{safe_ascii}.{ext}"

    # UTF-8 filename preserves user's Unicode characters (e.g. Hindi, Japanese, French accents)
    utf8_base = cleaned or fallback
    utf8_filename = f"{utf8_base}.{ext}"

    return safe_ascii_filename, utf8_filename


def format_content_disposition(
    name: str,
    fallback: str = "export",
    extension: str = "pdf",
    disposition_type: str = "attachment"
) -> str:
    """
    Format a standards-compliant Content-Disposition header according to RFC 6266 and RFC 5987.
    
    Example output for non-ASCII title:
        attachment; filename="business_plan.pdf"; filename*=UTF-8''%E0%A4%B5%E0%A5%8D%E0%A4%AF%E0%A4%BE%E0%A4%AA%E0%A4%BE%E0%A4%B0.pdf
        
    Guarantees:
    - Zero carriage returns (\\r) or newlines (\\n).
    - Standard ASCII filename attribute in quotes (safe for Latin-1 header encoders like Starlette/Uvicorn).
    - RFC 5987 filename* attribute with UTF-8 percent-encoding.
    """
    safe_ascii, utf8_file = sanitize_filename(name, fallback=fallback, extension=extension)
    encoded_utf8 = urllib.parse.quote(utf8_file, encoding="utf-8")
    return f'{disposition_type}; filename="{safe_ascii}"; filename*=UTF-8\'\'{encoded_utf8}'
