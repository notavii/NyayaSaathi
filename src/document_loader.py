"""
Document Loader module for Nyaya Saathi.

Extracts text from official Government of India PDF documents page-by-page using PyMuPDF (fitz),
preserving physical PDF page numbers, printed page numbers, source metadata,
and handling combined document boundaries and historical educational materials.
"""

import hashlib
import json
from pathlib import Path
import re
from typing import Dict, List, Optional, Any
import fitz


def compute_sha256(file_path: Path) -> str:
    """Computes the SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def detect_printed_page_number(page_text: str, physical_page: int) -> Optional[int]:
    """
    Attempts to detect printed page numbers from headers or footers.
    Returns integer printed page number or None.
    """
    lines = [l.strip() for l in page_text.split("\n") if l.strip()]
    if not lines:
        return None

    for candidate in [lines[0], lines[-1]]:
        if candidate.isdigit():
            val = int(candidate)
            if 1 <= val <= 2000:
                return val
        m = re.search(r"^(?:\[|\bPage\s+)?(\d+)(?:\]|\.|\b)?$", candidate, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 2000:
                return val
    return None


def extract_pdf_document(
    pdf_path: Path,
    document_id: str,
    catalog_entry: Optional[Dict[str, Any]] = None,
    page_range: Optional[tuple] = None,
) -> Dict[str, Any]:
    """
    Extracts text page-by-page from a PDF using PyMuPDF without modifying the original.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    total_physical_pages = len(doc)
    file_sha256 = compute_sha256(pdf_path)

    start_idx = 0
    end_idx = total_physical_pages - 1

    if page_range:
        start_p, end_p = page_range
        start_idx = max(0, start_p - 1)
        end_idx = min(total_physical_pages - 1, end_p - 1)

    extracted_pages = []
    empty_pages = []
    low_text_pages = []

    for idx in range(start_idx, end_idx + 1):
        page = doc[idx]
        physical_page_num = idx + 1
        raw_text = page.get_text("text")
        clean_text = raw_text.strip()
        char_count = len(clean_text)

        if char_count == 0:
            status = "EMPTY"
            empty_pages.append(physical_page_num)
        elif char_count < 100:
            status = "WARNING_LOW_TEXT"
            low_text_pages.append(physical_page_num)
        else:
            status = "SUCCESS"

        printed_page = detect_printed_page_number(raw_text, physical_page_num)

        extracted_pages.append({
            "pdf_page_number": physical_page_num,
            "printed_page_number": printed_page,
            "text": raw_text,
            "character_count": char_count,
            "extraction_status": status,
        })

    doc.close()

    result = {
        "document_id": document_id,
        "document_title": catalog_entry.get("document_title") if catalog_entry else document_id,
        "original_filename": pdf_path.name,
        "source_url": catalog_entry.get("official_source_url", "") if catalog_entry else "",
        "sha256": file_sha256,
        "total_pdf_pages": total_physical_pages,
        "extracted_page_count": len(extracted_pages),
        "page_range": list(page_range) if page_range else [1, total_physical_pages],
        "extraction_method": "PyMuPDF",
        "empty_pages": empty_pages,
        "low_text_pages": low_text_pages,
        "pages": extracted_pages,
    }
    return result


def extract_all_catalog_documents(
    catalog_path: Path = Path("data/legal_sources/source_catalog.json"),
    originals_dir: Path = Path("data/legal_sources/originals"),
    output_dir: Path = Path("data/legal_sources/extracted"),
) -> Dict[str, Any]:
    """
    Processes all documents in source_catalog.json and saves structured JSON.
    Handles combined documents, web-only sources, and historical educational references.
    """
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    summary = {
        "processed": [],
        "web_only": [],
        "missing": [],
        "warnings": [],
    }

    CUSTOM_BOUNDARIES = {
        "CP_CDRC_RULES_2020": (9, 16),
        "CP_GENERAL_RULES_2020": (17, 18),
    }

    for source in catalog.get("sources", []):
        doc_id = source["document_id"]
        filename = source.get("original_filename")

        if not filename:
            summary["web_only"].append({
                "document_id": doc_id,
                "url": source.get("official_source_url"),
                "status": "Official web resource without local PDF"
            })
            continue

        pdf_path = originals_dir / filename
        if not pdf_path.exists():
            shared_fname = source.get("shared_original_filename")
            if shared_fname and (originals_dir / shared_fname).exists():
                pdf_path = originals_dir / shared_fname
            else:
                summary["missing"].append({
                    "document_id": doc_id,
                    "expected_file": filename,
                    "reason": "File not found on disk"
                })
                continue

        page_range = CUSTOM_BOUNDARIES.get(doc_id)
        extraction = extract_pdf_document(
            pdf_path=pdf_path,
            document_id=doc_id,
            catalog_entry=source,
            page_range=page_range,
        )

        out_file = output_dir / f"{doc_id}_extracted.json"
        with open(out_file, "w", encoding="utf-8") as out_f:
            json.dump(extraction, out_f, indent=2, ensure_ascii=False)

        results[doc_id] = extraction
        summary["processed"].append({
            "document_id": doc_id,
            "filename": pdf_path.name,
            "page_count": extraction["extracted_page_count"],
            "sha256": extraction["sha256"],
            "empty_pages": extraction["empty_pages"],
            "low_text_pages": extraction["low_text_pages"],
            "output_path": str(out_file),
        })

    return {"summary": summary, "extractions": results}


if __name__ == "__main__":
    report = extract_all_catalog_documents()
    print(f"Extraction complete. Processed: {len(report['summary']['processed'])}, Web-only: {len(report['summary']['web_only'])}, Missing: {len(report['summary']['missing'])}")
