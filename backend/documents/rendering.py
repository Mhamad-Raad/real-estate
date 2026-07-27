"""`.docx` → PDF via headless LibreOffice (§6.6, D5).

Pure I/O — no models, no audit. `docxtpl` fills the template, this converts the result, and the
generation services turn the output into a `Document` row. LibreOffice is used because it shapes
RTL Sorani/Arabic correctly; the lightweight HTML-to-PDF engines do not.
"""

import subprocess
import tempfile
from pathlib import Path

from django.conf import settings


class RenderError(RuntimeError):
    """Conversion failed — the caller marks the job failed and keeps the reason for the UI."""


def docx_to_pdf(docx_path: Path, out_dir: Path) -> Path:
    """Convert `docx_path` to a PDF of the same stem inside `out_dir`, returning its path."""
    docx_path = Path(docx_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    produced = out_dir / f"{docx_path.stem}.pdf"

    # Clear any earlier output at this path FIRST. LibreOffice exits 0 even when it converts
    # nothing, so a leftover file would otherwise pass the success check below and a failed
    # regeneration would hand back the superseded letter — stale data, presented as current.
    try:
        produced.unlink(missing_ok=True)
    except OSError as exc:
        raise RenderError(f"Could not clear previous output {produced}: {exc}") from exc

    # Every call gets a throwaway user profile: concurrent workers sharing the default one
    # silently hand the job to a single running instance and one of them comes back empty.
    with tempfile.TemporaryDirectory(prefix="lo-profile-") as profile:
        command = [
            settings.LIBREOFFICE_BIN,
            f"-env:UserInstallation=file://{profile}",
            "--headless",
            "--norestore",
            "--nolockcheck",
            "--nodefault",
            "--convert-to",
            "pdf:writer_pdf_Export",
            "--outdir",
            str(out_dir),
            str(docx_path),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=settings.LIBREOFFICE_TIMEOUT_SECONDS,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RenderError(f"LibreOffice binary not found: {settings.LIBREOFFICE_BIN}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RenderError(
                f"LibreOffice timed out after {settings.LIBREOFFICE_TIMEOUT_SECONDS}s"
            ) from exc

    # Having cleared the path above, the file existing now proves THIS call produced it.
    if not produced.is_file():
        detail = (result.stderr or result.stdout).decode("utf-8", "replace").strip()
        raise RenderError(f"LibreOffice produced no PDF (exit {result.returncode}): {detail}")
    return produced
