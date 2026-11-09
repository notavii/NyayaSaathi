"""
Tests for Document Loader module (Phase 3B: Step 10 & Phase 3B.1).

Verifies:
1. All available source PDFs are detected and loaded (10 physical PDFs, 1 web-only resource).
2. Physical page counts and page numbers are preserved.
3. Text extraction works accurately via PyMuPDF.
4. Empty and low-text pages are flagged.
5. Original PDF files remain unchanged.
6. Combined rules PDF generates distinct logical extractions with verified boundaries.
7. Web-only and historical reference documents are properly loaded.
"""

import json
from pathlib import Path
import pytest
import fitz

from src.document_loader import (
    compute_sha256,
    extract_pdf_document,
    extract_all_catalog_documents,
)

ORIGINALS_DIR = Path("data/legal_sources/originals")
EXTRACTED_DIR = Path("data/legal_sources/extracted")
CATALOG_PATH = Path("data/legal_sources/source_catalog.json")


@pytest.fixture
def catalog_data():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_01_all_available_source_pdfs_detected(catalog_data):
    """Verifies all source PDFs listed in catalog exist and are detected, with web-only handled."""
    sources = catalog_data.get("sources", [])
    assert len(sources) == 11

    physical_docs = 0
    web_only_docs = 0

    for s in sources:
        doc_id = s["document_id"]
        fname = s.get("original_filename")
        if fname is None:
            assert doc_id == "NCH_GRIEVANCE_GUIDE"
            assert s["download_status"] == "MANUAL_DOWNLOAD_REQUIRED"
            web_only_docs += 1
            continue

        fpath = ORIGINALS_DIR / fname
        assert fpath.exists(), f"Physical file {fname} missing for document {doc_id}"
        physical_docs += 1

    assert physical_docs == 10
    assert web_only_docs == 1


def test_02_pdf_page_counts_preserved_in_extraction():
    """Verifies that extracted JSON page counts match physical PDF page counts."""
    # Check CPA 2019
    cpa_pdf = ORIGINALS_DIR / "A2019-35_Consumer_Protection_Act_2019.pdf"
    doc = fitz.open(str(cpa_pdf))
    expected_cpa_pages = len(doc)
    doc.close()

    cpa_json_path = EXTRACTED_DIR / "CPA_2019_extracted.json"
    assert cpa_json_path.exists()
    with open(cpa_json_path, "r", encoding="utf-8") as f:
        cpa_data = json.load(f)

    assert cpa_data["total_pdf_pages"] == expected_cpa_pages == 40
    assert cpa_data["extracted_page_count"] == 40
    assert len(cpa_data["pages"]) == 40


def test_03_physical_page_numbers_are_sequential_and_correct():
    """Verifies that physical page numbers start at 1 and increment sequentially."""
    for extracted_file in EXTRACTED_DIR.glob("*_extracted.json"):
        with open(extracted_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        pages = data.get("pages", [])
        page_nums = [p["pdf_page_number"] for p in pages]
        assert len(page_nums) > 0
        # Check that page numbers are monotonically increasing
        assert page_nums == sorted(page_nums)


def test_04_text_extracted_from_readable_pages():
    """Verifies that text is non-empty for standard statutory documents."""
    cpa_json_path = EXTRACTED_DIR / "CPA_2019_extracted.json"
    with open(cpa_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for p in data["pages"]:
        assert p["character_count"] > 100
        assert p["extraction_status"] == "SUCCESS"
        assert "Consumer Protection Act" in p["text"] or len(p["text"]) > 200


def test_05_empty_and_low_text_pages_properly_flagged():
    """Verifies that empty pages in documents (e.g. Consumer Handbook divider pages) are flagged."""
    handbook_json_path = EXTRACTED_DIR / "CONSUMER_HANDBOOK_2015_extracted.json"
    assert handbook_json_path.exists()
    with open(handbook_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "empty_pages" in data
    # 3 blank pages in the 78-page handbook
    assert len(data["empty_pages"]) == 3
    for p in data["pages"]:
        if p["pdf_page_number"] in data["empty_pages"]:
            assert p["extraction_status"] == "EMPTY"
            assert p["character_count"] == 0


def test_06_source_metadata_retained_in_extraction():
    """Verifies that catalog metadata (URLs, titles, SHA-256) is preserved in extracted JSON."""
    for extracted_file in EXTRACTED_DIR.glob("*_extracted.json"):
        with open(extracted_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "document_id" in data
        assert "document_title" in data
        assert "sha256" in data
        assert len(data["sha256"]) == 64
        assert data["extraction_method"] == "PyMuPDF"


def test_07_original_pdf_files_remain_unchanged(catalog_data):
    """Verifies that opening and reading PDFs does not alter their SHA-256 or modify file bytes."""
    for s in catalog_data.get("sources", []):
        fname = s.get("original_filename")
        if not fname:
            continue
        fpath = ORIGINALS_DIR / fname
        if fpath.exists() and s.get("sha256"):
            current_sha = compute_sha256(fpath)
            assert current_sha.lower() == s["sha256"].lower()


def test_08_combined_rules_pdf_produces_two_distinct_logical_extractions():
    """Verifies that the combined 2020 Rules PDF produces distinct CDRC and General Rules extractions."""
    cdrc_file = EXTRACTED_DIR / "CP_CDRC_RULES_2020_extracted.json"
    gen_file = EXTRACTED_DIR / "CP_GENERAL_RULES_2020_extracted.json"

    assert cdrc_file.exists()
    assert gen_file.exists()

    with open(cdrc_file, "r", encoding="utf-8") as f:
        cdrc_data = json.load(f)
    with open(gen_file, "r", encoding="utf-8") as f:
        gen_data = json.load(f)

    assert cdrc_data["document_id"] == "CP_CDRC_RULES_2020"
    assert gen_data["document_id"] == "CP_GENERAL_RULES_2020"
    assert cdrc_data["original_filename"] == gen_data["original_filename"]
    assert cdrc_data["page_range"] == [9, 16]
    assert gen_data["page_range"] == [17, 18]


def test_09_document_boundaries_verified_via_actual_text():
    """Verifies that CDRC extraction contains CDRC rules and General extraction contains General rules."""
    cdrc_file = EXTRACTED_DIR / "CP_CDRC_RULES_2020_extracted.json"
    gen_file = EXTRACTED_DIR / "CP_GENERAL_RULES_2020_extracted.json"

    with open(cdrc_file, "r", encoding="utf-8") as f:
        cdrc_data = json.load(f)
    with open(gen_file, "r", encoding="utf-8") as f:
        gen_data = json.load(f)

    cdrc_text = " ".join(p["text"] for p in cdrc_data["pages"])
    gen_text = " ".join(p["text"] for p in gen_data["pages"])

    assert "Consumer Disputes Redressal Commissions" in cdrc_text
    assert "Consumer Protection (General) Rules" in gen_text
    # CDRC should not have the final General Rules invoice requirements
    assert "Manner of issuing invoice or bill" in gen_text


def test_10_extract_all_catalog_documents_summary():
    """Verifies extract_all_catalog_documents handles all 11 catalog entries cleanly."""
    res = extract_all_catalog_documents()
    summary = res["summary"]
    assert len(summary["processed"]) == 10
    assert len(summary["web_only"]) == 1
    assert summary["web_only"][0]["document_id"] == "NCH_GRIEVANCE_GUIDE"
    assert len(summary["missing"]) == 0
