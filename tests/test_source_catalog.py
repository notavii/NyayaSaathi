"""
Unit and integration tests for Nyaya Saathi Legal Source Catalogue.

Explicitly separates and tests:
1. Catalogue schema and semantic validity.
2. Official source verification.
3. Actual physical file download and disk presence.
4. Actual PDF content and SHA-256 integrity.

Validates G.S.R. 328(E) corrections, 2026 future-effective rules,
combined document architecture, unverified date null-handling,
Consumer Handbook 2015 classification, e-Jagriti metadata,
and NCH web-only / unacquired status.
"""

import hashlib
import json
from pathlib import Path
import pytest
from pypdf import PdfReader

CATALOG_PATH = Path("data/legal_sources/source_catalog.json")
ORIGINALS_DIR = Path("data/legal_sources/originals")
README_PATH = Path("data/legal_sources/LEGAL_SOURCES_README.md")

EXPECTED_DOCUMENT_IDS = {
    "CPA_2019",
    "CP_GENERAL_RULES_2020",
    "CP_CDRC_RULES_2020",
    "CP_ECOMMERCE_RULES_2020",
    "CP_ECOMMERCE_CORRIGENDUM_2020",
    "CP_ECOMMERCE_AMENDMENT_2021",
    "CP_JURISDICTION_RULES_2021",
    "CP_ECOMMERCE_AMENDMENT_2026",
    "NCH_GRIEVANCE_GUIDE",
    "EJAGRITI_FILING_GUIDE",
    "CONSUMER_HANDBOOK_2015",
}

REQUIRED_METADATA_FIELDS = {
    "document_id",
    "document_title",
    "issuing_authority",
    "department",
    "document_type",
    "jurisdiction",
    "official_source_url",
    "source_page_url",
    "original_filename",
    "is_combined_document",
    "shared_original_filename",
    "document_boundary",
    "publication_date",
    "effective_from",
    "effective_to",
    "amends_document_id",
    "document_version",
    "download_status",
    "source_authenticity_status",
    "content_verification_status",
    "last_checked",
    "sha256",
    "notes",
    "applicability_status",
    "retrieval_eligible",
}

VALID_DOWNLOAD_STATUSES = {
    "MANUAL_DOWNLOAD_REQUIRED",
    "DOWNLOADED_UNVERIFIED",
    "OFFICIAL_SOURCE_CONFIRMED",
}

VALID_DOCUMENT_TYPES = {
    "ACT",
    "RULES",
    "CORRIGENDUM",
    "AMENDMENT_RULES",
    "PROCEDURAL_GUIDE",
    "HISTORICAL_EDUCATIONAL_REFERENCE",
}


@pytest.fixture
def catalog_data():
    """Loads and returns the parsed source catalog JSON."""
    assert CATALOG_PATH.exists(), f"Source catalog not found at {CATALOG_PATH}"
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@pytest.fixture
def catalog_sources(catalog_data):
    """Returns the list of source entries from the catalog."""
    assert "sources" in catalog_data, "Catalog missing 'sources' key"
    return catalog_data["sources"]


# ==============================================================================
# CATEGORY 1: CATALOGUE SCHEMA & SEMANTIC VALIDITY
# ==============================================================================

def test_catalog_file_exists_and_is_valid_json(catalog_data):
    """Verifies that source_catalog.json exists and is valid non-empty JSON."""
    assert isinstance(catalog_data, dict)
    assert len(catalog_data.get("sources", [])) > 0


def test_catalog_contains_all_eleven_official_documents(catalog_sources):
    """Verifies that all 11 priority legal, procedural, and historical documents are present."""
    found_ids = {entry["document_id"] for entry in catalog_sources}
    assert found_ids == EXPECTED_DOCUMENT_IDS, (
        f"Mismatch in expected documents. Missing: {EXPECTED_DOCUMENT_IDS - found_ids}, "
        f"Extra: {found_ids - EXPECTED_DOCUMENT_IDS}"
    )
    assert len(catalog_sources) == 11


def test_catalog_unique_document_ids(catalog_sources):
    """Verifies that all document IDs in the catalog are unique."""
    ids = [entry["document_id"] for entry in catalog_sources]
    assert len(ids) == len(set(ids)), f"Duplicate document IDs detected: {ids}"


def test_required_metadata_fields_present_on_all_entries(catalog_sources):
    """Verifies that each entry contains all required metadata fields."""
    for entry in catalog_sources:
        doc_id = entry.get("document_id", "<UNKNOWN>")
        missing_fields = REQUIRED_METADATA_FIELDS - set(entry.keys())
        assert not missing_fields, (
            f"Document '{doc_id}' is missing required fields: {missing_fields}"
        )
        assert entry["document_type"] in VALID_DOCUMENT_TYPES, (
            f"Invalid document_type '{entry['document_type']}' in '{doc_id}'"
        )
        assert entry["download_status"] in VALID_DOWNLOAD_STATUSES, (
            f"Invalid download_status '{entry['download_status']}' in '{doc_id}'"
        )
        assert isinstance(entry["retrieval_eligible"], bool)


def test_unverified_procedural_dates_are_strictly_null(catalog_sources):
    """
    CRITICAL GROUNDING TEST (Part 3 & Phase 3B.1 Part D):
    Verifies that procedural guides and historical references with no formal gazette date
    (NCH, e-Jagriti, and Consumer Handbook 2015) have publication_date set to None/null.
    """
    undated_ids = {"NCH_GRIEVANCE_GUIDE", "EJAGRITI_FILING_GUIDE", "CONSUMER_HANDBOOK_2015"}
    for entry in catalog_sources:
        if entry["document_id"] in undated_ids:
            assert entry["publication_date"] is None, (
                f"{entry['document_id']} publication_date must be null, found {entry['publication_date']}"
            )
            assert entry["effective_from"] is None, (
                f"{entry['document_id']} effective_from must be null, found {entry['effective_from']}"
            )


# ==============================================================================
# CATEGORY 2: OFFICIAL METADATA ACCURACY & CORRECTIONS
# ==============================================================================

def test_corrected_2021_amendment_rules_metadata(catalog_sources):
    """
    CRITICAL METADATA ACCURACY TEST:
    Verifies that the 2021 E-Commerce Amendment Rules are accurately documented as:
    - Gazette G.S.R. 328(E) (and NOT G.S.R. 333(E))
    - Publication date: 2021-05-17
    - Effective date: 2021-05-17
    - Amends CP_ECOMMERCE_RULES_2020
    """
    entry = next(
        (e for e in catalog_sources if e["document_id"] == "CP_ECOMMERCE_AMENDMENT_2021"),
        None,
    )
    assert entry is not None
    assert "328(E)" in entry["document_version"], (
        f"Expected G.S.R. 328(E) in version, found {entry['document_version']}"
    )
    assert "333(E)" not in entry["document_version"], "Incorrect G.S.R. 333(E) still present"
    assert entry["publication_date"] == "2021-05-17"
    assert entry["effective_from"] == "2021-05-17"
    assert entry["amends_document_id"] == "CP_ECOMMERCE_RULES_2020"


def test_2026_amendment_rules_future_effective_handling(catalog_sources):
    """
    CRITICAL TEMPORAL COMPLIANCE TEST:
    Verifies that the 2026 E-Commerce Amendment Rules are accurately documented:
    - Published: 2026-09-09
    - Effective: 2027-01-01
    - G.S.R. 789(E)
    - Status: FUTURE_EFFECTIVE
    """
    entry = next(
        (e for e in catalog_sources if e["document_id"] == "CP_ECOMMERCE_AMENDMENT_2026"),
        None,
    )
    assert entry is not None
    assert entry["publication_date"] == "2026-09-09"
    assert entry["effective_from"] == "2027-01-01"
    assert "789(E)" in entry["document_version"]
    assert entry.get("gazette_reference") == "G.S.R. 789(E)"
    assert entry["amends_document_id"] == "CP_ECOMMERCE_RULES_2020"
    assert entry["applicability_status"] == "FUTURE_EFFECTIVE"
    assert "2027" in entry["notes"]


def test_combined_document_mapping_general_and_cdrc(catalog_sources):
    """
    COMBINED DOCUMENT ARCHITECTURE TEST:
    Verifies that General Rules 2020 and CDRC Rules 2020 reference the same shared PDF,
    with explicit boundary definitions.
    """
    sources_by_id = {e["document_id"]: e for e in catalog_sources}
    gen_entry = sources_by_id["CP_GENERAL_RULES_2020"]
    cdrc_entry = sources_by_id["CP_CDRC_RULES_2020"]

    assert gen_entry["is_combined_document"] is True
    assert cdrc_entry["is_combined_document"] is True
    assert gen_entry["shared_original_filename"] == cdrc_entry["shared_original_filename"]
    assert gen_entry["shared_original_filename"] == "Consumer_Commission_Rules_and_General_Rules_2020.pdf"

    # Boundaries must be articulated
    assert gen_entry["document_boundary"] is not None
    assert cdrc_entry["document_boundary"] is not None
    assert "17" in gen_entry["document_boundary"]  # General Rules pages 17-18
    assert "9" in cdrc_entry["document_boundary"]   # CDRC Rules pages 9-16


def test_consumer_handbook_2015_catalog_classification(catalog_sources):
    """
    PHASE 3B.1 PART B & H.1, H.2, H.3 TEST:
    Verifies Consumer Handbook 2015 classification:
    - document_type == 'HISTORICAL_EDUCATIONAL_REFERENCE'
    - publication_year == 2015
    - retrieval_eligible == False
    - applicability_status == 'HISTORICAL_REFERENCE'
    - Distinct from NCH_GRIEVANCE_GUIDE
    """
    entry = next(
        (e for e in catalog_sources if e["document_id"] == "CONSUMER_HANDBOOK_2015"),
        None,
    )
    assert entry is not None
    assert entry["document_type"] == "HISTORICAL_EDUCATIONAL_REFERENCE"
    assert entry.get("publication_year") == 2015
    assert entry["retrieval_eligible"] is False
    assert entry["applicability_status"] == "HISTORICAL_REFERENCE"
    assert entry["document_id"] != "NCH_GRIEVANCE_GUIDE"
    assert "81-86641-57-2" in entry["notes"] or "2015" in entry["notes"]


def test_nch_source_record_unacquired_or_web_only(catalog_sources):
    """
    PHASE 3B.1 PART C & H.4 TEST:
    Verifies NCH Grievance Guide remains unacquired/web-only:
    - download_status == 'MANUAL_DOWNLOAD_REQUIRED'
    - original_filename is None (no fabricated filename)
    - retrieval_eligible == False
    - official_source_url points to official portal
    """
    entry = next(
        (e for e in catalog_sources if e["document_id"] == "NCH_GRIEVANCE_GUIDE"),
        None,
    )
    assert entry is not None
    assert entry["download_status"] == "MANUAL_DOWNLOAD_REQUIRED"
    assert entry["original_filename"] is None
    assert entry["retrieval_eligible"] is False
    assert entry["official_source_url"] == "https://consumerhelpline.gov.in/"


def test_ejagriti_metadata_and_no_invented_day(catalog_sources):
    """
    PHASE 3B.1 PART D & H.5, H.6, H.7 TEST:
    Verifies e-Jagriti metadata:
    - document_type == 'PROCEDURAL_GUIDE'
    - publication_month == '2025-03'
    - publication_date is None (no invented day)
    - retrieval_eligible is True
    """
    entry = next(
        (e for e in catalog_sources if e["document_id"] == "EJAGRITI_FILING_GUIDE"),
        None,
    )
    assert entry is not None
    assert entry["document_type"] == "PROCEDURAL_GUIDE"
    assert entry["publication_month"] == "2025-03"
    assert entry["publication_date"] is None
    assert entry["retrieval_eligible"] is True


def test_official_source_urls_are_well_formed(catalog_sources):
    """Verifies that official URLs are well-formed and point to authentic government/portal domains."""
    legitimate_domains = [
        "indiacode.nic.in",
        "consumeraffairs.gov.in",
        "egazette.gov.in",
        "consumerhelpline.gov.in",
        "e-jagriti.gov.in",
    ]
    for entry in catalog_sources:
        doc_id = entry["document_id"]
        url = entry["official_source_url"]
        assert url.startswith("https://") or url.startswith("http://")
        assert any(domain in url for domain in legitimate_domains), (
            f"Document '{doc_id}' URL '{url}' is not from a recognized official portal"
        )


# ==============================================================================
# CATEGORY 3: PHYSICAL FILE EXISTENCE & MISSING FILE DETECTION
# ==============================================================================

def test_physical_file_presence_and_missing_file_detection(catalog_sources):
    """
    PHYSICAL FILE INVENTORY TEST:
    Strictly verifies which files actually exist on disk and ensures that missing/web-only
    files are explicitly recognized without fabricating presence.
    """
    downloaded_ids = {
        "CPA_2019",
        "CP_GENERAL_RULES_2020",
        "CP_CDRC_RULES_2020",
        "CP_ECOMMERCE_RULES_2020",
        "CP_ECOMMERCE_CORRIGENDUM_2020",
        "CP_ECOMMERCE_AMENDMENT_2021",
        "CP_JURISDICTION_RULES_2021",
        "CP_ECOMMERCE_AMENDMENT_2026",
        "EJAGRITI_FILING_GUIDE",
        "CONSUMER_HANDBOOK_2015",
    }

    for entry in catalog_sources:
        doc_id = entry["document_id"]
        filename = entry.get("original_filename")

        if doc_id == "NCH_GRIEVANCE_GUIDE":
            assert filename is None
            assert entry["download_status"] == "MANUAL_DOWNLOAD_REQUIRED"
            assert entry["retrieval_eligible"] is False
            continue

        assert filename is not None, f"Missing original_filename for {doc_id}"
        file_path = ORIGINALS_DIR / filename
        assert file_path.exists(), f"Physical file {filename} missing for {doc_id}"
        assert file_path.stat().st_size > 50000, f"File {filename} is suspiciously small"
        assert entry["download_status"] == "OFFICIAL_SOURCE_CONFIRMED"
        assert entry["sha256"] is not None


# ==============================================================================
# CATEGORY 4: PDF CONTENT VALIDATION & SHA-256 INTEGRITY
# ==============================================================================

def test_downloaded_pdf_integrity_and_sha256(catalog_sources):
    """
    INTEGRITY TEST:
    For all downloaded PDFs on disk:
    1. Recomputes the SHA-256 byte hash and confirms match with the catalogue.
    2. Opens with pypdf and confirms it is an authentic readable PDF.
    """
    for entry in catalog_sources:
        if entry["download_status"] != "OFFICIAL_SOURCE_CONFIRMED":
            continue
        filename = entry["original_filename"]
        if not filename:
            continue
        file_path = ORIGINALS_DIR / filename
        assert file_path.exists(), f"File {filename} missing"

        # SHA-256 check
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        disk_hash = hasher.hexdigest().lower()
        catalog_hash = entry["sha256"].lower()
        assert disk_hash == catalog_hash, f"SHA-256 hash mismatch for {filename}"

        # pypdf readability check
        reader = PdfReader(str(file_path))
        assert len(reader.pages) > 0, f"PDF {filename} has no pages"


def test_legal_sources_readme_exists_and_covers_corrections():
    """Verifies that the legal sources provenance README exists and documents corrections."""
    assert README_PATH.exists(), f"README not found at {README_PATH}"
    content = README_PATH.read_text(encoding="utf-8")
    assert "328(E)" in content, "README must document G.S.R. 328(E)"
    assert "FUTURE_EFFECTIVE" in content
    assert "2027-01-01" in content
    assert "Consumer_Commission_Rules_and_General_Rules_2020.pdf" in content
    assert "data/legal_sources/originals" in content
