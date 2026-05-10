"""
Project file manager for PDF Merger.

Handles saving and loading .pdfm project files (JSON format).
Each project captures the PDF list order, bookmark data, file locations
(both absolute and relative to the project file), output directory, and
output filename.
"""

import json
import os
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional

from model import PDFDocument

PROJECT_VERSION = 1
PROJECT_EXTENSION = ".pdfm"


def save_project(
    project_path: str,
    pdf_list: List[PDFDocument],
    output_dir: str,
    output_name: str,
) -> None:
    """
    Save the current merge session to a .pdfm JSON file.

    Relative paths are computed relative to the project file's directory
    so that moving a folder of PDFs + project file together preserves
    portability.
    """
    project_dir = os.path.dirname(os.path.abspath(project_path))

    pdf_entries = []
    for pdf in pdf_list:
        entry: Dict[str, Any] = {
            "absolute_path": os.path.abspath(pdf.file_path),
            "relative_path": _safe_relpath(pdf.file_path, project_dir),
            "name": pdf.name,
            "size_kb": pdf.size_kb,
            "modified_dt": pdf.modified_dt.isoformat(),
            "pages": pdf.pages,
        }
        if pdf.custom_toc is not None:
            entry["custom_toc"] = pdf.custom_toc
        pdf_entries.append(entry)

    project_data = {
        "version": PROJECT_VERSION,
        "output_dir_absolute": os.path.abspath(output_dir) if output_dir else "",
        "output_dir_relative": _safe_relpath(output_dir, project_dir) if output_dir else "",
        "output_name": output_name,
        "pdfs": pdf_entries,
    }

    with open(project_path, "w", encoding="utf-8") as f:
        json.dump(project_data, f, indent=2, ensure_ascii=False)


def load_project(
    project_path: str,
) -> Dict[str, Any]:
    """
    Load a .pdfm project file.

    Returns a dict with keys:
        - pdfs: List[PDFDocument]  (with .missing flag set on each)
        - output_dir: str
        - output_name: str
        - missing_files: List[str]  (names of files that could not be found)
    """
    with open(project_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    project_dir = os.path.dirname(os.path.abspath(project_path))

    pdfs: List[PDFDocument] = []
    missing_files: List[str] = []

    for entry in data.get("pdfs", []):
        resolved_path, found = _resolve_path(
            entry.get("absolute_path", ""),
            entry.get("relative_path", ""),
            project_dir,
        )

        modified_dt = _parse_datetime(entry.get("modified_dt", ""))

        pdf = PDFDocument(
            file_path=resolved_path,
            name=entry.get("name", os.path.basename(resolved_path)),
            size_kb=entry.get("size_kb", 0.0),
            modified_dt=modified_dt,
            pages=entry.get("pages", 0),
            custom_toc=entry.get("custom_toc", None),
            missing=not found,
        )

        if not found:
            missing_files.append(pdf.name)

        pdfs.append(pdf)

    # Resolve output directory
    output_dir, _ = _resolve_path(
        data.get("output_dir_absolute", ""),
        data.get("output_dir_relative", ""),
        project_dir,
    )
    # If the output dir doesn't exist, fall back to the project file's directory
    if not os.path.isdir(output_dir):
        output_dir = project_dir

    output_name = data.get("output_name", "")

    return {
        "pdfs": pdfs,
        "output_dir": output_dir,
        "output_name": output_name,
        "missing_files": missing_files,
    }


def _resolve_path(
    absolute_path: str,
    relative_path: str,
    project_dir: str,
) -> Tuple[str, bool]:
    """
    Try to locate a file using absolute path first, then relative path
    as a fallback. Returns (resolved_path, found_bool).
    """
    # Try absolute path first
    if absolute_path and os.path.exists(absolute_path):
        return absolute_path, True

    # Try relative path
    if relative_path:
        candidate = os.path.normpath(os.path.join(project_dir, relative_path))
        if os.path.exists(candidate):
            return candidate, True

    # Not found — return whichever path we have for display purposes
    return absolute_path or relative_path or "", False


def _safe_relpath(path: str, base: str) -> str:
    """
    Compute a relative path, returning the absolute path as fallback
    if relpath fails (e.g. different drives on Windows).
    """
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return os.path.abspath(path)


def _parse_datetime(dt_str: str) -> datetime:
    """Parse an ISO 8601 datetime string, returning a fallback on failure."""
    if not dt_str:
        return datetime.now()
    try:
        return datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        return datetime.now()


def refresh_pdf_metadata(pdf: PDFDocument) -> List[str]:
    """
    Re-read a PDF's file metadata from disk, updating in place.
    Preserves custom_toc. Returns a list of human-readable change descriptions.
    If the file cannot be read, marks it as missing and returns an error message.
    """
    import fitz

    changes: List[str] = []
    file_path = pdf.file_path

    if not os.path.exists(file_path):
        if not pdf.missing:
            pdf.missing = True
            changes.append(f"{pdf.name}: file no longer found")
        return changes

    try:
        file_stats = os.stat(file_path)
        new_size_kb = file_stats.st_size / 1024.0
        new_modified_dt = datetime.fromtimestamp(file_stats.st_mtime)

        doc = fitz.open(file_path)
        new_pages = doc.page_count
        doc.close()
    except Exception as e:
        changes.append(f"{pdf.name}: error reading file — {e}")
        return changes

    # Compare and collect changes
    if pdf.pages != new_pages:
        changes.append(f"{pdf.name}: page count changed ({pdf.pages} → {new_pages})")
    if abs(pdf.size_kb - new_size_kb) > 0.1:
        changes.append(f"{pdf.name}: file size changed ({pdf.size_kb:.1f} KB → {new_size_kb:.1f} KB)")
    if pdf.modified_dt != new_modified_dt:
        changes.append(f"{pdf.name}: modified date changed")

    # Apply updates
    pdf.pages = new_pages
    pdf.size_kb = new_size_kb
    pdf.modified_dt = new_modified_dt
    pdf.missing = False

    return changes


def verify_all_pdf_metadata(pdfs: List[PDFDocument]) -> List[str]:
    """
    Verify metadata for all non-missing PDFs in the list.
    Returns a combined list of change descriptions across all files.
    """
    all_changes: List[str] = []
    for pdf in pdfs:
        if not pdf.missing:
            all_changes.extend(refresh_pdf_metadata(pdf))
    return all_changes

