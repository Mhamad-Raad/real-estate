"""Offline document file store — safe human-readable names over stable-ID folders (§6.7).

The DB is authoritative: we always look files up by `Document.file_path`, never by parsing a
name. Every filename component is whitelist-sanitized, so path traversal is impossible and
Sorani/Arabic names survive on NTFS/APFS.

Layout: `<CATEGORY>/<CODE>_<PID>/<label>__<shortid>.pdf`, where the label is the Sorani name of
the issuing body or of the paper itself — the archive has to be navigable by hand, without the
app, by people who do not know what `INST_S4_B` is (UC-060).
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

from catalog import document_types, institutes

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


def merge_pdfs(parts: list[bytes]) -> bytes:
    """Join already-validated PDFs into one, in order.

    An ID card is one document with two sides, so the front and back belong in a single file:
    one row, one entry in the case folder, and a reader that sees page 1 and page 2 of the same
    card rather than two loose scans it has to pair up.
    """
    from pypdf import PdfWriter

    writer = PdfWriter()
    for part in parts:
        for page in PdfReader(BytesIO(part)).pages:
            writer.add_page(page)
    buffer = BytesIO()
    writer.write(buffer)
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
    """NFC-normalize, strip illegal/control chars and trailing dots/spaces, cap length.

    Inner spaces **survive** (UC-060): the names are Sorani phrases the office reads and searches
    by hand, and `بەڵگەنامەی_خانووبەرە` is harder to scan than the words it is made of. Runs of
    whitespace collapse to one so a stray double space cannot make two names look different.
    """
    if not text:
        return fallback
    text = unicodedata.normalize("NFC", text)
    text = _ILLEGAL.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(". ")
    text = text[:max_len].strip("._ ")
    return text or fallback


def document_label(document_type: str, entry=None) -> str:
    """What a file is *called*: the body that issued it, or the paper's own name (§6.7, UC-060).

    Sorani, for the same reason the generated documents are — this archive is read by the office,
    and `INST_S4_B` tells a person looking for the land map nothing. The names are code constants,
    so they are as stable as the codes were; correcting one renames later files, never filed ones.
    """
    if entry is None:
        return sanitize(document_types.name_ckb(document_type), "Document")
    if entry.is_custom:
        return sanitize(entry.custom_name, "Custom")
    return sanitize(institutes.name_ckb(entry.institute_code), "Document")


def compose_display_name(*, unique_code: str, category_code: str, person_name: str, label: str) -> str:
    """The **download** name: `<CODE>_<person>_<label>.pdf` (§6.7, UC-060).

    Self-describing, because a downloaded file lands in someone's Downloads folder with no
    surrounding path to give it context — but no `__<shortid>` and no machine type code, which
    said nothing to the people who actually open these files. The case code leads, and it already
    starts with the category letter, so naming the category again would only repeat it.
    """
    lead = sanitize(unique_code, "", 12) or sanitize(category_code, "NA", 10)
    return f"{lead}_{sanitize(person_name, 'Unknown')}_{label}.pdf"


def compose_stored_name(*, label: str, sid: str) -> str:
    """The **on-disk** name. Shorter than the download name: the folders above already say the
    case and the person, so repeating them buys nothing and makes a name correction rewrite the
    filesystem.

    The `__<shortid>` stays here and only here. It is what keeps two files apart when a slot
    legitimately holds more than one — `RealEstate` expects two papers (UC-055) — and what lets a
    file survive any number of re-filings. A download has no such constraint: the browser numbers
    a repeat, and the name is free to stay clean.
    """
    return f"{label}__{sid}.pdf"


def case_dir(*, unique_code: str, pid: str) -> str:
    """One folder per **case**: `<CODE>_<PID>` (§3.7, §6.7, UC-060).

    The PID stays because it is the identity the whole system turns on — and because a client row
    can be re-entered, so keying on `client.id` would scatter one person's papers. The code is in
    front of it because a person may hold more than one case over time (a re-application after a
    rejection), and their papers were previously landing in one undifferentiated folder.

    Cases opened before codes existed have none; they keep the plain PID folder they already had.
    """
    person = sanitize(pid, "NA", 40)
    code = sanitize(unique_code, "", 12)
    return f"{code}_{person}" if code else person


def relative_path(*, category_code: str, unique_code: str, pid: str, stored_filename: str) -> Path:
    """`<CATEGORY>/<CODE>_<PID>/<label>__<shortid>.pdf`, relative to DOCUMENTS_ROOT."""
    return (
        Path(sanitize(category_code, "NA", 10))
        / case_dir(unique_code=unique_code, pid=pid)
        / stored_filename
    )


def write_pdf(rel_path: Path, content: bytes) -> Path:
    dest = settings.DOCUMENTS_ROOT / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return dest



# What the office calls each bulk output, in Sorani like every other filename here. Keyed by
# `GenerationJob.Kind` — the literals rather than the enum, so this naming module stays free of
# the model layer. The job id stays on the end: two code lists printed the same day are different
# papers.
BULK_JOB_NAMES = {
    "process_list": "لیستی کەیسەکان",
    "process_codes": "لیستی کۆدەکان",
}


def bulk_job_filename(job) -> str:
    """The download name for a bulk job's PDF (§6.7, UC-066).

    Lives beside the other naming rules rather than in `generation.py`: the endpoint that serves
    the file used to invent `list_<id>.pdf` for **every** kind, so a code list arrived called a
    case list. One module decides what a file is called.
    """
    return f"{sanitize(BULK_JOB_NAMES.get(job.kind, 'بەڵگەنامە'), 'Document')}_{job.id}.pdf"

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


def write_template(*, template_type: str, name: str, content: bytes, suffix: str) -> Path:
    """Store a template file under LETTER_TEMPLATES_ROOT, returning its relative path.

    Same naming discipline as documents: sanitized name plus a short id, so re-uploading a
    template never overwrites the file the previous version still points at. `suffix` is the
    caller's already-validated format — a letter is a `.docx`, a blank form a `.pdf` (§6.6).
    Required, not defaulted: only the validator knows which one it just proved, and a default
    would quietly file the next non-Word template under a name that misdescribes it.
    """
    rel = Path(sanitize(template_type, "template", 32)) / (
        f"{sanitize(name, 'template')}__{short_id()}{suffix}"
    )
    dest = Path(settings.LETTER_TEMPLATES_ROOT) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return rel
