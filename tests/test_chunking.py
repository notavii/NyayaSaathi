"""
Tests for Legal-Aware Chunking module (Phase 3B: Step 11 & Phase 3B.1).

Verifies:
1. Section identifiers are preserved (1 to 107 in CPA 2019).
2. Rule identifiers are preserved across Rules documents.
3. Subsections, clauses, provisos, and explanations remain attached.
4. Unusually long provisions (Section 2 Definitions) have linked child chunks.
5. Amendment 2021 remains G.S.R. 328(E).
6. Amendment 2026 remains FUTURE_EFFECTIVE with effective_from = 2027-01-01.
7. Procedural guidance is not classified as legislation; no invented section numbers.
8. No duplicate chunks exist across primary and historical datasets.
9. Every chunk has valid page references and document ID.
10. Verbatim statutory text is preserved without invention.
11. Primary retrieval dataset has exactly 206 retrieval-eligible chunks.
12. Historical reference dataset has exactly 74 chunks segregated from primary retrieval.
13. Fine-grained verification statuses: extraction_status, extraction_integrity_status, legal_review_status.
14. No historical chunk marked CURRENTLY_IN_FORCE or retrieval_eligible.
"""

import json
from pathlib import Path
import pytest

PRIMARY_CHUNKS_PATH = Path("data/legal_sources/legal_chunks.json")
HISTORICAL_CHUNKS_PATH = Path("data/legal_sources/historical_reference_chunks.json")


@pytest.fixture
def primary_chunks():
    assert PRIMARY_CHUNKS_PATH.exists(), f"legal_chunks.json not found at {PRIMARY_CHUNKS_PATH}"
    with open(PRIMARY_CHUNKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def historical_chunks():
    assert HISTORICAL_CHUNKS_PATH.exists(), f"historical_reference_chunks.json not found at {HISTORICAL_CHUNKS_PATH}"
    with open(HISTORICAL_CHUNKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_01_primary_chunks_count_and_retrieval_eligibility(primary_chunks):
    """Verifies legal_chunks.json exists and contains exactly 206 retrieval-eligible chunks."""
    assert isinstance(primary_chunks, list)
    assert len(primary_chunks) == 206
    for c in primary_chunks:
        assert c["retrieval_eligible"] is True, f"Chunk {c['chunk_id']} in primary dataset has retrieval_eligible=False"


def test_02_section_identifiers_preserved_in_cpa_2019(primary_chunks):
    """Verifies that CPA 2019 chunks contain sections 1 to 107."""
    cpa_sections = [
        c for c in primary_chunks
        if c["document_id"] == "CPA_2019" and c["provision_type"] == "SECTION"
    ]
    assert len(cpa_sections) == 107
    sec_nums = {c["provision_number"] for c in cpa_sections}
    # Check key consumer sections
    assert "1" in sec_nums    # Short title
    assert "2" in sec_nums    # Definitions
    assert "34" in sec_nums   # District commission jurisdiction
    assert "35" in sec_nums   # Manner of filing complaint
    assert "47" in sec_nums   # State commission jurisdiction
    assert "58" in sec_nums   # National commission jurisdiction
    assert "82" in sec_nums   # Product liability application
    assert "107" in sec_nums  # Repeal and savings


def test_03_rule_identifiers_preserved_in_rules_documents(primary_chunks):
    """Verifies that Rules documents preserve rule numbers."""
    ecom_rules = [
        c for c in primary_chunks
        if c["document_id"] == "CP_ECOMMERCE_RULES_2020" and c["provision_type"] == "RULE"
    ]
    assert len(ecom_rules) == 8
    ecom_rule_nums = {c["provision_number"] for c in ecom_rules}
    assert {"1", "2", "3", "4", "5", "6", "7", "8"}.issubset(ecom_rule_nums)

    # Check Jurisdiction rules
    jur_rules = [
        c for c in primary_chunks
        if c["document_id"] == "CP_JURISDICTION_RULES_2021" and c["provision_type"] == "RULE"
    ]
    assert len(jur_rules) == 5
    jur_nums = {c["provision_number"] for c in jur_rules}
    assert {"1", "2", "3", "4", "5"}.issubset(jur_nums)

    # Check CDRC rules
    cdrc_rules = [
        c for c in primary_chunks
        if c["document_id"] == "CP_CDRC_RULES_2020" and c["provision_type"] == "RULE"
    ]
    assert len(cdrc_rules) == 17

    # Check General rules
    gen_rules = [
        c for c in primary_chunks
        if c["document_id"] == "CP_GENERAL_RULES_2020" and c["provision_type"] == "RULE"
    ]
    assert len(gen_rules) == 5


def test_04_subsections_and_clauses_remain_attached(primary_chunks):
    """Verifies that subsections (1), (2) and clauses (a), (b) remain attached to parent section."""
    sec_35 = next((c for c in primary_chunks if c["chunk_id"] == "CPA_2019_SECTION_35"), None)
    assert sec_35 is not None
    assert "(1)" in sec_35["text"]
    assert "(a)" in sec_35["text"]
    assert "(b)" in sec_35["text"]
    assert "(2)" in sec_35["text"]


def test_05_provisos_and_explanations_preserved(primary_chunks):
    """Verifies that statutory provisos and explanations are preserved in parent chunks."""
    sec_34 = next((c for c in primary_chunks if c["chunk_id"] == "CPA_2019_SECTION_34"), None)
    assert sec_34 is not None
    assert "Provided that" in sec_34["text"] or "provided that" in sec_34["text"].lower()

    # Rule 2 of E-Commerce Rules has a proviso
    ecom_rule_2 = next((c for c in primary_chunks if c["chunk_id"] == "CP_ECOMMERCE_RULES_2020_RULE_2"), None)
    assert ecom_rule_2 is not None
    assert "Provided that" in ecom_rule_2["text"]


def test_06_unusually_long_provisions_have_linked_child_chunks(primary_chunks):
    """Verifies that Section 2 Definitions has linked child chunks referencing the parent."""
    parent_sec_2 = next((c for c in primary_chunks if c["chunk_id"] == "CPA_2019_SECTION_2"), None)
    assert parent_sec_2 is not None

    child_defs = [
        c for c in primary_chunks
        if c["document_id"] == "CPA_2019" and c["provision_type"] == "DEFINITION_CLAUSE"
    ]
    assert len(child_defs) == 47
    for cd in child_defs:
        assert cd["parent_provision"] == "CPA_2019_SECTION_2"
        assert cd["provision_heading"].startswith("Definition of")


def test_07_2021_amendment_metadata_retains_gsr_328_e(primary_chunks):
    """Verifies that 2021 E-Commerce Amendment chunks reference G.S.R. 328(E)."""
    amend_2021 = [c for c in primary_chunks if c["document_id"] == "CP_ECOMMERCE_AMENDMENT_2021"]
    assert len(amend_2021) == 1
    chunk = amend_2021[0]
    assert chunk["amends_document_id"] == "CP_ECOMMERCE_RULES_2020"
    assert "328" in chunk["text"]
    assert chunk["applicability_status"] == "CURRENTLY_IN_FORCE"


def test_08_2026_amendment_is_strictly_future_effective(primary_chunks):
    """
    CRITICAL TEMPORAL COMPLIANCE TEST:
    Verifies that all 2026 E-Commerce Amendment chunks are marked FUTURE_EFFECTIVE
    and carry effective_from = 2027-01-01.
    """
    amend_2026 = [c for c in primary_chunks if c["document_id"] == "CP_ECOMMERCE_AMENDMENT_2026"]
    assert len(amend_2026) == 2
    for c in amend_2026:
        assert c["applicability_status"] == "FUTURE_EFFECTIVE"
        assert c["effective_from"] == "2027-01-01"
        assert c["publication_date"] == "2026-09-09"
        assert c["amends_document_id"] == "CP_ECOMMERCE_RULES_2020"


def test_09_procedural_guidance_in_primary_dataset(primary_chunks):
    """
    Verifies that only e-Jagriti procedural guide is in primary dataset (13 chunks),
    classified as PROCEDURAL_GUIDE / PROCEDURAL_GUIDANCE with null provision numbers.
    """
    proc_chunks = [c for c in primary_chunks if c["document_type"] == "PROCEDURAL_GUIDE"]
    assert len(proc_chunks) == 13
    for pc in proc_chunks:
        assert pc["provision_type"] == "PROCEDURAL_GUIDANCE"
        assert pc["provision_number"] is None
        assert pc["document_id"] == "EJAGRITI_FILING_GUIDE"


def test_10_historical_reference_chunks_segregation(historical_chunks):
    """
    PHASE 3B.1 PART B & H.3, H.8 TEST:
    Verifies that Consumer Handbook 2015 chunks are stored in historical_reference_chunks.json,
    are marked retrieval_eligible=False, applicability_status=HISTORICAL_REFERENCE,
    and NOT A SINGLE ONE is marked CURRENTLY_IN_FORCE.
    """
    assert len(historical_chunks) == 74
    for hc in historical_chunks:
        assert hc["document_id"] == "CONSUMER_HANDBOOK_2015"
        assert hc["document_type"] == "HISTORICAL_EDUCATIONAL_REFERENCE"
        assert hc["retrieval_eligible"] is False
        assert hc["applicability_status"] == "HISTORICAL_REFERENCE"
        assert hc["applicability_status"] != "CURRENTLY_IN_FORCE"


def test_11_verification_statuses_on_all_chunks(primary_chunks, historical_chunks):
    """
    PHASE 3B.1 PART E & H.9 TEST:
    Verifies fine-grained status fields on all chunks across primary and historical sets:
    - extraction_status == 'SUCCESS'
    - extraction_integrity_status == 'CHECKED'
    - legal_review_status == 'REQUIRES_LEGAL_REVIEW'
    Ensures programmatic extraction is never labeled as human legal verification.
    """
    all_chunks = primary_chunks + historical_chunks
    assert len(all_chunks) == 280

    for c in all_chunks:
        assert c["extraction_status"] == "SUCCESS"
        assert c["extraction_integrity_status"] == "CHECKED"
        assert c["legal_review_status"] == "REQUIRES_LEGAL_REVIEW"
        assert c["legal_review_status"] != "VERIFIED"


def test_12_no_duplicate_chunks(primary_chunks, historical_chunks):
    """Verifies that all chunk IDs are unique within each dataset and across both datasets."""
    p_ids = [c["chunk_id"] for c in primary_chunks]
    h_ids = [c["chunk_id"] for c in historical_chunks]

    assert len(p_ids) == len(set(p_ids)), "Duplicate chunk IDs found in primary chunks"
    assert len(h_ids) == len(set(h_ids)), "Duplicate chunk IDs found in historical chunks"
    assert len(set(p_ids).intersection(set(h_ids))) == 0, "Overlap found between primary and historical chunk IDs"


def test_13_every_chunk_has_valid_page_references_and_document_id(primary_chunks):
    """Verifies that every primary chunk has positive physical page references and valid metadata."""
    valid_doc_ids = {
        "CPA_2019",
        "CP_GENERAL_RULES_2020",
        "CP_CDRC_RULES_2020",
        "CP_ECOMMERCE_RULES_2020",
        "CP_ECOMMERCE_CORRIGENDUM_2020",
        "CP_ECOMMERCE_AMENDMENT_2021",
        "CP_JURISDICTION_RULES_2021",
        "CP_ECOMMERCE_AMENDMENT_2026",
        "EJAGRITI_FILING_GUIDE",
    }
    for c in primary_chunks:
        assert c["document_id"] in valid_doc_ids
        assert isinstance(c["pdf_page_start"], int) and c["pdf_page_start"] >= 1
        assert isinstance(c["pdf_page_end"], int) and c["pdf_page_end"] >= c["pdf_page_start"]
        assert len(c["text"]) > 20


def test_14_verbatim_statutory_text_preserved(primary_chunks):
    """Verifies that statutory text is verbatim and not paraphrased."""
    sec_107 = next((c for c in primary_chunks if c["chunk_id"] == "CPA_2019_SECTION_107"), None)
    assert sec_107 is not None
    assert "The Consumer Protection Act, 1986 is hereby repealed." in sec_107["text"]
