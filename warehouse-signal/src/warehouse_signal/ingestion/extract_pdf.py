"""PDF → text extraction for transcript uploads.

We accept text-based PDFs (most provider exports). Scanned/image-only
PDFs are rejected with a clear error message — no OCR in v1.
"""

from __future__ import annotations

import io

from pypdf import PdfReader

# If a PDF is bigger than this but yields almost no text, it's probably scanned.
_SCANNED_PDF_BYTE_THRESHOLD = 50_000
_SCANNED_PDF_TEXT_THRESHOLD = 1_000


class PdfExtractionError(Exception):
    """Raised when a PDF can't be turned into useful text."""


def pdf_bytes_to_text(data: bytes) -> str:
    """Extract concatenated page text from a PDF byte string.

    Raises PdfExtractionError on scanned-only PDFs or unreadable files.
    """
    if not data:
        raise PdfExtractionError("Empty file uploaded.")

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001 — pypdf raises a wide range
        raise PdfExtractionError(f"Could not parse PDF: {e}") from e

    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            pages.append("")

    text = "\n\n".join(p.strip() for p in pages if p.strip())

    if (
        len(data) > _SCANNED_PDF_BYTE_THRESHOLD
        and len(text) < _SCANNED_PDF_TEXT_THRESHOLD
    ):
        raise PdfExtractionError(
            "This PDF appears to be image-based (scanned). "
            "Upload a text-based PDF or paste the transcript instead."
        )

    return text
