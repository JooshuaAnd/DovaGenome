"""Safe extraction of recipe source documents for admin-only AI drafting.

The extractor never marks a recipe verified and never writes directly to the
recipe tables. It only converts an uploaded document into bounded text that is
shown to the AI draft service and then reviewed by an admin.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from pathlib import Path
from typing import Any

from app.core.errors import ValidationError

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_EXTRACTED_CHARS = 120_000
ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".csv", ".txt", ".md"}


def extract_recipe_document(filename: str, content: bytes) -> dict[str, Any]:
    """Extract text and redacted metadata from a supported recipe document."""
    safe_name = Path(filename or "recipe").name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            "Format dokumen belum didukung. Gunakan PDF, XLSX, CSV, TXT, atau MD.",
            details={"allowed_extensions": sorted(ALLOWED_EXTENSIONS)},
        )
    if not content:
        raise ValidationError("Dokumen resep kosong.")
    if len(content) > MAX_FILE_BYTES:
        raise ValidationError("Ukuran dokumen maksimal 10 MB.")

    if suffix in {".txt", ".md", ".csv"}:
        text = _decode_text(content)
        if suffix == ".csv":
            text = _normalise_csv(text)
    elif suffix == ".xlsx":
        text = _extract_xlsx(content)
    else:
        text = _extract_pdf(content)

    text = _clean_text(text)
    if not text:
        raise ValidationError("Dokumen tidak memiliki teks/tabel resep yang bisa dibaca.")
    if len(text) > MAX_EXTRACTED_CHARS:
        text = text[:MAX_EXTRACTED_CHARS] + "\n[TRUNCATED_BY_SERVER]"

    return {
        "source_name": safe_name,
        "source_type": suffix.lstrip("."),
        "sha256": hashlib.sha256(content).hexdigest(),
        "byte_size": len(content),
        "text": text,
        "truncated": len(text) >= MAX_EXTRACTED_CHARS,
    }


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationError("Encoding dokumen tidak dapat dibaca. Simpan sebagai UTF-8.")


def _normalise_csv(value: str) -> str:
    rows = csv.reader(io.StringIO(value))
    return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows)


def _extract_xlsx(content: bytes) -> str:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - deployment dependency guard
        raise ValidationError("Parser XLSX belum terpasang di backend.") from exc

    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise ValidationError("File XLSX tidak dapat dibaca.") from exc
    lines: list[str] = []
    for sheet in workbook.worksheets:
        lines.append(f"[SHEET: {sheet.title}]")
        for row in sheet.iter_rows(values_only=True):
            values = [str(value).strip() for value in row if value is not None and str(value).strip()]
            if values:
                lines.append(" | ".join(values))
    return "\n".join(lines)


def _extract_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValidationError(
            "Parser PDF belum terpasang. Tambahkan dependency pypdf pada backend."
        ) from exc
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise ValidationError("PDF tidak dapat dibaca atau rusak.") from exc
    return "\n\n".join(pages)


def _clean_text(value: str) -> str:
    value = value.replace("\x00", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()
