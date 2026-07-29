"""Offline document file store — safe human-readable names over stable-ID folders (§6.7).

The DB is authoritative: we always look files up by `Document.file_path`, never by parsing a
name. Every filename component is whitelist-sanitized, so path traversal is impossible and
Sorani/Arabic names survive on NTFS/APFS. Layout: <CATEGORY>/<client_id>_<pid>/<name>__<id>.pdf
"""

import hashlib
import re
import shutil
import unicodedata
import uuid
from io import BytesIO
from pathlib import Path

from django.conf import settings
from pypdf import PdfReader

PDF_MAGIC = b"%PDF-"
# Windows-illegal characters + control chars — stripped from every name component.
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def looks_like_pdf(content: bytes) -> bool:
    """Magic-byte check only — cheap, and says nothing about whether the file is readable."""
    return content[:5] == PDF_MAGIC


# Formats a phone camera or scanner produces. Converted to PDF on arrival so the document store
# stays PDF-only (§6.7) — client-side conversion arrives with scan capture in It.6, but a lawyer
# can already photograph an ID today.
IMAGE_MAGIC = {
    b"\xff\xd8\xff": "JPEG",
    b"\x89PNG\r\n\x1a\n": "PNG",
    b"II*\x00": "TIFF",
    b"MM\x00*": "TIFF",
}


def looks_like_image(content: bytes) -> bool:
    return any(content.startswith(magic) for magic in IMAGE_MAGIC)


def image_to_pdf(content: bytes) -> bytes:
    """Wrap an image in a single-page PDF, preserving its pixels.

    No resampling: OCR accuracy depends on the original resolution, and a scan the office cannot
    read is worse than a large file.
    """
    from PIL import Image

    image = Image.open(BytesIO(content))
    # PDF has no alpha channel; flattening onto white avoids a black background where it was.
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        backdrop = Image.new("RGB", image.size, (255, 255, 255))
        backdrop.paste(image, mask=image.split()[-1])
        image = backdrop
    elif image.mode != "RGB":
        image = image.convert("RGB")

    buffer = BytesIO()
    image.save(buffer, format="PDF", resolution=300.0)
    return buffer.getvalue()


def is_readable_pdf(content: bytes) -> bool:
    """Parse the file rather than trusting its first five bytes.

    A truncated or corrupt scan starts with `%PDF-` and passes the magic-byte check, so it used
    to enter the store and only fail much later — when the case was compiled (§10.3) or, from
    It.5, when OCR tried to read it. Rejecting it at upload keeps unreadable files out of the
    document store entirely, which is where the damage is cheapest to prevent.
    """
    if not looks_like_pdf(content):
        return False
    try:
        return len(PdfReader(BytesIO(content)).pages) > 0
    except Exception:
        return False


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


# Scans wait here between upload and confirmation. Inside DOCUMENTS_ROOT so one backup covers it,
# and underscore-prefixed so it can never collide with a category folder (A/B/C/G).
STAGING_DIR = "_staging"


def staging_path(sid: str) -> Path:
    """Where a card scan lives before the client it describes exists (§6.7).

    Named by short id alone: the friendly name is composed from the person's category, PID and
    name, and none of those are known until the reading has been confirmed.
    """
    return Path(STAGING_DIR) / f"scan__{sanitize(sid, 'scan', 40)}.pdf"


def move_into_place(*, source: Path, rel_path: Path) -> Path:
    """Move a staged file to its final home, without rewriting the bytes.

    A rename keeps the sha256 meaningful (it is the hash of what was uploaded) and cannot half-copy
    a large scan. Falls back to copy+delete if the store ever spans two filesystems.
    """
    src = settings.DOCUMENTS_ROOT / source
    dest = settings.DOCUMENTS_ROOT / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        src.replace(dest)
    except OSError:  # cross-device: same result, slower path
        shutil.copy2(src, dest)
        src.unlink(missing_ok=True)
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
