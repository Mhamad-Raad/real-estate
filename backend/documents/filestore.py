"""Offline document file store — safe human-readable names over stable-ID folders (§6.7).

The DB is authoritative: we always look files up by `Document.file_path`, never by parsing a
name. Every filename component is whitelist-sanitized, so path traversal is impossible and
Sorani/Arabic names survive on NTFS/APFS. Layout: <CATEGORY>/<client_id>_<pid>/<name>__<id>.pdf
"""

import hashlib
import re
import unicodedata
import uuid
from pathlib import Path

from django.conf import settings

PDF_MAGIC = b"%PDF-"
# Windows-illegal characters + control chars — stripped from every name component.
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def looks_like_pdf(content: bytes) -> bool:
    return content[:5] == PDF_MAGIC


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def short_id() -> str:
    """8 hex chars — guarantees filename uniqueness and stays constant across renames (§6.7)."""
    return uuid.uuid4().hex[:8]


def sanitize(text: str, fallback: str = "NA", max_len: int = 60) -> str:
    """NFC-normalize, spaces→_, strip illegal/control chars and trailing dots/spaces, cap length."""
    if not text:
        return fallback
    text = unicodedata.normalize("NFC", text).replace(" ", "_")
    text = _ILLEGAL.sub("", text).strip(". ")
    text = text[:max_len].strip("._ ")
    return text or fallback


def institute_label(entry) -> str:
    """Canonical (stable) institute label for the filename — never the per-user UI translation."""
    if entry is None:
        return "General"  # Step-1 client papers & generated PDFs have no institute
    if entry.is_custom:
        return sanitize(entry.custom_name, "Custom")
    return entry.institute_code or "General"


def compose_display_name(
    *, category_code: str, institute: str, person_name: str, document_type: str, sid: str
) -> str:
    parts = [
        sanitize(category_code, "NA", 10),
        sanitize(institute, "General"),
        sanitize(person_name, "Unknown"),
        sanitize(document_type, "Document"),
    ]
    return "_".join(parts) + f"__{sid}.pdf"


def relative_path(*, category_code: str, client_id: int, pid: str, display_filename: str) -> Path:
    """Physical path relative to DOCUMENTS_ROOT — folder keyed by stable id (never moves on edit)."""
    person_dir = f"{client_id:06d}_{sanitize(pid, 'NA', 30)}"
    return Path(sanitize(category_code, "NA", 10)) / person_dir / display_filename


def write_pdf(rel_path: Path, content: bytes) -> Path:
    dest = settings.DOCUMENTS_ROOT / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return dest


# A .docx is a zip archive; this is its magic number.
DOCX_MAGIC = b"PK\x03\x04"


def looks_like_docx(content: bytes) -> bool:
    return content[:4] == DOCX_MAGIC


def write_template(*, template_type: str, name: str, content: bytes) -> Path:
    """Store an uploaded .docx under LETTER_TEMPLATES_ROOT, returning its relative path.

    Same naming discipline as documents: sanitized name plus a short id, so re-uploading a
    template never overwrites the file the previous version still points at.
    """
    rel = Path(sanitize(template_type, "template", 32)) / (
        f"{sanitize(name, 'template')}__{short_id()}.docx"
    )
    dest = Path(settings.LETTER_TEMPLATES_ROOT) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return rel
