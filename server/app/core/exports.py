"""Export header formatting and sanitization utilities.

Enforces RFC 6266 and RFC 5987 standards for Content-Disposition headers.
Provides safe ASCII fallback filenames and UTF-8 percent-encoded filename* parameters.
Defends strictly against HTTP header injection, CR/LF control character splitting,
and Latin-1 encoding errors when processing Unicode/international filenames.
"""

from __future__ import annotations

import re
import unicodedata
import urllib.parse
from typing import Tuple


def sanitize_filename(
    name: str,
    fallback: str = "export",
    extension: str = "pdf"
) -> Tuple[str, str]:
    """
    Sanitize an untrusted filename string into safe ASCII fallback and UTF-8 components.
    
    1. Normalizes Unicode input using NFC.
    2. Strips all carriage returns, newlines, null bytes, and ASCII control characters (0x00-0x1F, 0x7F).
    3. Strips path separators (/ and \\) and path traversal elements.
    4. Normalizes and validates the extension parameter (alphanumeric only).
    5. Normalizes and validates the fallback string.
    6. Strips repeated expected extension suffixes (e.g. 'plan.pdf.pdf' -> 'plan').
    7. Bounds raw base name length to 100 characters to prevent filesystem overflow.
    8. Produces a safe ASCII-only fallback filename containing solely [a-zA-Z0-9_-].
    9. Produces a cleaned UTF-8 filename preserving international Unicode characters.
    """
    # Validate and normalize extension (alphanumeric only, lowercase, default 'pdf')
    ext_clean = re.sub(r"[^a-zA-Z0-9]", "", str(extension or "pdf")).lower()
    ext = ext_clean or "pdf"

    # Validate and sanitize fallback
    safe_fallback = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(fallback or "export")).strip("_")
    safe_fallback = safe_fallback[:50] or "export"

    # Normalize Unicode input (NFC)
    raw_str = unicodedata.normalize("NFC", str(name or ""))

    # Strictly strip all CR, LF, null bytes, control characters (0x00-0x1F, 0x7F), and path separators (/ and \)
    cleaned = re.sub(r"[\r\n\x00-\x1f\x7f/\\]", "", raw_str).strip()

    # Remove redundant path traversal sequences if any remain
    cleaned = cleaned.replace("..", "")

    # Remove repeated trailing extension(s) if already included by caller (e.g. '.pdf.pdf')
    while cleaned.lower().endswith(f".{ext}"):
        cleaned = cleaned[:-len(ext)-1].strip()

    # Bound raw base length to 100 characters
    base = cleaned[:100]

    # Produce safe ASCII fallback: replace anything not [a-zA-Z0-9_-] with '_'
    safe_ascii = re.sub(r"[^a-zA-Z0-9_\-]", "_", base)
    # Collapse multiple consecutive underscores and strip leading/trailing underscores
    safe_ascii = re.sub(r"_+", "_", safe_ascii).strip("_")
    if not safe_ascii:
        safe_ascii = safe_fallback

    safe_ascii_filename = f"{safe_ascii}.{ext}"

    # UTF-8 filename preserves user's Unicode characters (e.g. Hindi, Japanese, French accents)
    # Strip filesystem-prohibited and header-delimiters: / \ < > : " | ? * ; %
    utf8_clean = re.sub(r'[/\\<>:"|?*;%]', "_", base)
    utf8_clean = re.sub(r"_+", "_", utf8_clean).strip("_")
    # If title was punctuation-only, whitespace-only, or has no alphanumeric/Unicode word characters, fall back
    if not re.search(r"[^\W_]", base):
        utf8_base = safe_fallback
    else:
        utf8_base = utf8_clean or safe_fallback
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
    
    Guarantees:
    - Zero carriage returns (\\r) or newlines (\\n).
    - Standard ASCII filename attribute in quotes (safe for Latin-1 header encoders like Starlette/Uvicorn).
    - RFC 5987 filename* attribute with UTF-8 percent-encoding using safe="" (strict percent-encoding).
    - Validates disposition_type ('attachment' or 'inline').
    """
    # Restrict disposition_type to allowed RFC values
    disp_type = "inline" if str(disposition_type).strip().lower() == "inline" else "attachment"

    safe_ascii, utf8_file = sanitize_filename(name, fallback=fallback, extension=extension)
    # Explicitly use safe="" to strictly encode all non-attr-char characters per RFC 5987
    encoded_utf8 = urllib.parse.quote(utf8_file, safe="", encoding="utf-8")
    return f'{disp_type}; filename="{safe_ascii}"; filename*=UTF-8\'\'{encoded_utf8}'
