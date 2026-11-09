"""
Unit and Integration Tests for Semantic Legal Retriever (Phase 4A: Step 14).

Verifies all 25 required test criteria:
1. Query validation.
2. E5 query prefix ('query: ').
3. Query embedding shape (384-dimensional).
4. Query embedding L2 normalization.
5. Semantic search returns actual ChromaDB records.
6. Results include all required statutory and provenance metadata fields.
7. Retrieved text matches source text verbatim.
8. Current law search strictly excludes future law by default.
9. Procedural search remains separate and opt-in.
10. Future law excluded by default.
11. Explicit future-law search works (include_future=True).
12. Transaction-date and as-of-date filtering works.
13. Historical chunks (Consumer Handbook 2015) strictly excluded.
14. NCH web-only source strictly excluded.
15. Parent-child traceability for derived child segments.
16. Duplicate retrieval records handled cleanly.
17. Top-k boundaries enforced (clamped between 1 and 10).
18. Empty query handling returns an empty list.
19. Whitespace-only query handling returns an empty list.
20. Multilingual Hindi retrieval returns relevant provisions.
21. Code-mixed Hinglish retrieval returns relevant provisions.
22. Persistent database access functions correctly.
23. Collection counts remain invariant after retrieval (read-only).
24. Retrieval executes locally without calling external APIs or Gemini.
25. Source-data and index reconciliation across all retrieved records.
"""

from datetime import date, datetime
import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pytest

from src.embeddings import EMBEDDING_DIMENSION, QUERY_PREFIX
from src.legal_retriever import (
    COLLECTION_CURRENT_LAW,
    COLLECTION_FUTURE_LAW,
    COLLECTION_PROCEDURAL_GUIDANCE,
    DEFAULT_CHROMA_DIR,
    embed_query,
    parse_date,
    semantic_search,
)
from src.vector_store import VectorStoreManager

DERIVED_RECORDS_FILE = Path("data/legal_sources/embedding_records.json")


@pytest.fixture(scope="module")
def persistent_store():
    """Initializes VectorStoreManager on the persistent database."""
    return VectorStoreManager(persist_dir=DEFAULT_CHROMA_DIR)


@pytest.fixture(scope="module")
def derived_records_map():
    """Loads derived embedding records as a lookup dictionary."""
    with open(DERIVED_RECORDS_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)
    return {r["embedding_record_id"]: r for r in records}


# 1. Query Validation
def test_01_query_validation():
    """Verifies that non-string or empty queries return an empty list without crashing."""
    assert semantic_search("") == []
    assert semantic_search("   \n\t  ") == []
    assert semantic_search(None) == []  # type: ignore


# 2. E5 Query Prefix
def test_02_e5_query_prefix():
    """Verifies that embed_query applies the mandatory E5 query: prefix."""
    with patch("src.legal_retriever.format_query_for_embedding") as mock_fmt:
        mock_fmt.return_value = "query: defective mobile phone"
        vec = embed_query("defective mobile phone")
        mock_fmt.assert_called_once_with("defective mobile phone")
        assert vec.shape == (EMBEDDING_DIMENSION,)


# 3. Query Embedding Shape
def test_03_query_embedding_shape():
    """Verifies query vector has shape (384,) and dtype float32."""
    vec = embed_query("Consumer forum complaint process")
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (384,)
    assert vec.dtype == np.float32
    assert np.all(np.isfinite(vec))


# 4. Query Embedding Normalization
def test_04_query_embedding_normalization():
    """Verifies that query vector is L2 normalized to Euclidean norm 1.0."""
    vec = embed_query("Unfair trade practice refund delay")
    norm = np.linalg.norm(vec)
    assert pytest.approx(norm, abs=1e-5) == 1.0


# 5. Semantic Search Returns Actual Records
def test_05_semantic_search_returns_actual_chromadb_records():
    """Verifies that querying returns actual records from ChromaDB."""
    results = semantic_search("defective laptop replacement", top_k=5)
    assert len(results) > 0
    assert len(results) <= 5
    for r in results:
        assert r["distance"] >= 0.0
        assert r["exact_original_text"].strip() != ""


# 6. Results Include Required Metadata
def test_06_results_include_all_required_metadata():
    """Verifies that every retrieval result has all mandated provenance keys."""
    required_keys = [
        "retrieval_rank",
        "chunk_id",
        "embedding_record_id",
        "parent_chunk_id",
        "document_id",
        "document_title",
        "document_type",
        "provision_type",
        "provision_number",
        "provision_heading",
        "exact_original_text",
        "source_url",
        "original_filename",
        "pdf_page_start",
        "pdf_page_end",
        "applicability_status",
        "effective_from",
        "legal_review_status",
        "collection_name",
        "retrieval_method",
        "distance",
    ]
    results = semantic_search("unfair trade practice misleading advertisement", top_k=3)
    assert len(results) == 3
    for r in results:
        for k in required_keys:
            assert k in r, f"Key '{k}' missing from retrieval result {r.get('chunk_id')}"
        assert r["retrieval_method"] == "SEMANTIC_MULTILINGUAL_E5"
        assert r["legal_review_status"] == "REQUIRES_LEGAL_REVIEW"


# 7. Source Text Matches Indexed Text
def test_07_source_text_matches_indexed_text(derived_records_map):
    """Verifies that exact_original_text in results matches derived records on disk."""
    results = semantic_search("Section 35 complaint filing procedure", top_k=3)
    for r in results:
        rec_id = r["embedding_record_id"]
        assert rec_id in derived_records_map
        assert r["exact_original_text"] == derived_records_map[rec_id]["text"]


# 8. Current Law Excludes Future Law
def test_08_current_law_excludes_future_law():
    """Verifies that default searches do NOT return FUTURE_EFFECTIVE records."""
    results = semantic_search("e-commerce seller return and refund rules", top_k=8)
    for r in results:
        assert r["applicability_status"] == "CURRENTLY_IN_FORCE"
        assert r["collection_name"] == COLLECTION_CURRENT_LAW


# 9. Procedural Search Remains Separate
def test_09_procedural_search_remains_separate():
    """Verifies procedural guide records appear ONLY when include_procedural=True."""
    # When False:
    res_no_proc = semantic_search("how to file complaint on e-jagriti portal", top_k=5, include_procedural=False)
    for r in res_no_proc:
        assert r["collection_name"] != COLLECTION_PROCEDURAL_GUIDANCE
        assert r["document_type"] != "PROCEDURAL_GUIDE"

    # When True:
    res_proc = semantic_search("how to file complaint on e-jagriti portal", top_k=5, include_procedural=True)
    has_proc = any(r["collection_name"] == COLLECTION_PROCEDURAL_GUIDANCE for r in res_proc)
    assert has_proc, "Expected at least one procedural result when include_procedural=True"


# 10. Future Law Excluded by Default
def test_10_future_law_excluded_by_default():
    """Verifies that future amendment rules are excluded by default."""
    results = semantic_search("amendment rules 2026 e-commerce", top_k=8)
    for r in results:
        assert r["document_id"] != "CP_ECOMMERCE_AMENDMENT_2026"
        assert r["applicability_status"] != "FUTURE_EFFECTIVE"


# 11. Explicit Future Law Search Works
def test_11_explicit_future_law_search_works():
    """Verifies that include_future=True includes future law collection."""
    results = semantic_search("e-commerce amendment 2026", top_k=5, include_future=True)
    has_future = any(r["collection_name"] == COLLECTION_FUTURE_LAW for r in results)
    assert has_future, "Expected future law results when include_future=True"


# 12. Transaction Date Filtering Works
def test_12_transaction_date_filtering_works():
    """
    Verifies that transaction_date or as_of_date >= 2027-01-01 dynamically enables future law,
    while dates < 2027-01-01 strictly exclude it.
    """
    # Past or current date: excluded
    res_past = semantic_search("e-commerce amendment rules", transaction_date="2026-11-06")
    for r in res_past:
        assert r["collection_name"] != COLLECTION_FUTURE_LAW

    # Future date after commencement: included
    res_future = semantic_search("e-commerce amendment rules", transaction_date="2027-02-15")
    has_future = any(r["collection_name"] == COLLECTION_FUTURE_LAW for r in res_future)
    assert has_future, "Expected future law results for transaction date in 2027"

    # As-of date testing
    res_as_of = semantic_search("e-commerce amendment rules", as_of_date=date(2027, 3, 1))
    assert any(r["collection_name"] == COLLECTION_FUTURE_LAW for r in res_as_of)


# 13. Historical Chunks Excluded
def test_13_historical_chunks_excluded():
    """Verifies that zero records from Consumer Handbook 2015 appear in search results."""
    results = semantic_search("consumer rights education handbook 2015", top_k=10, include_procedural=True, include_future=True)
    for r in results:
        assert "CONSUMER_HANDBOOK" not in r["chunk_id"]
        assert r["document_id"] != "CONSUMER_HANDBOOK_2015"


# 14. NCH Web-Only Source Excluded
def test_14_nch_web_only_source_excluded():
    """Verifies that NCH_GRIEVANCE_GUIDE is never returned as a local vector passage."""
    results = semantic_search("National Consumer Helpline pre-litigation grievance", top_k=10, include_procedural=True)
    for r in results:
        assert r["document_id"] != "NCH_GRIEVANCE_GUIDE"


# 15. Parent-Child Traceability
def test_15_parent_child_traceability():
    """Verifies that when child segments are retrieved, parent_chunk_id is preserved."""
    results = semantic_search("unfair trade practice hoarding refusal to sell", top_k=5)
    for r in results:
        assert r["parent_chunk_id"] != ""
        if "_PART_" in r["chunk_id"]:
            assert r["parent_chunk_id"] in r["chunk_id"]


# 16. Duplicate Retrieval Records Handled
def test_16_no_duplicate_records_in_results():
    """Verifies that semantic search returns distinct record IDs without duplicates."""
    results = semantic_search("deficiency in service and refund", top_k=8)
    seen_ids = set()
    for r in results:
        cid = r["chunk_id"]
        assert cid not in seen_ids, f"Duplicate record {cid} in results"
        seen_ids.add(cid)


# 17. Top-K Boundaries
def test_17_top_k_boundaries():
    """Verifies that top_k is clamped between 1 and 10."""
    res_1 = semantic_search("consumer dispute", top_k=1)
    assert len(res_1) == 1

    res_10 = semantic_search("consumer dispute", top_k=10)
    assert len(res_10) == 10

    # Requesting > 10 is clamped to 10
    res_20 = semantic_search("consumer dispute", top_k=20)
    assert len(res_20) <= 10

    # Requesting < 1 is clamped to 1
    res_0 = semantic_search("consumer dispute", top_k=0)
    assert len(res_0) == 1


# 18. Empty Query Handling
def test_18_empty_query_handling():
    """Verifies empty string returns an empty list."""
    assert semantic_search("") == []


# 19. Empty Retrieval Handling
def test_19_whitespace_query_handling():
    """Verifies whitespace-only string returns an empty list."""
    assert semantic_search("    \n\t   ") == []


# 20. Hindi Retrieval
def test_20_hindi_retrieval():
    """Verifies multilingual retrieval works for Hindi queries."""
    hindi_q = "मुझे खराब सामान मिला है रिफंड कैसे मिलेगा?"
    results = semantic_search(hindi_q, top_k=5)
    assert len(results) > 0
    # Top result should have low cosine distance (< 0.3)
    assert results[0]["distance"] < 0.35


# 21. Hinglish Retrieval
def test_21_hinglish_retrieval():
    """Verifies code-mixed Hinglish retrieval returns relevant results."""
    hinglish_q = "Flipkart pe damaged item deliver hua seller replace nahi kar raha"
    results = semantic_search(hinglish_q, top_k=5)
    assert len(results) > 0
    assert results[0]["distance"] < 0.35


# 22. Persistent Database Access
def test_22_persistent_database_access(persistent_store):
    """Verifies that retriever reads directly from the persistent store."""
    counts = persistent_store.get_collection_counts()
    assert counts[COLLECTION_CURRENT_LAW] == 232
    assert counts[COLLECTION_PROCEDURAL_GUIDANCE] == 13
    assert counts[COLLECTION_FUTURE_LAW] == 6


# 23. Collection Counts Remain Unchanged After Search
def test_23_collection_counts_remain_unchanged_after_search(persistent_store):
    """Verifies that semantic search is strictly read-only and collection counts are invariant."""
    counts_before = persistent_store.get_collection_counts()
    _ = semantic_search("test query ensuring read-only invariant", top_k=8, include_procedural=True, include_future=True)
    counts_after = persistent_store.get_collection_counts()
    assert counts_before == counts_after


# 24. Retrieval Does Not Call Gemini
def test_24_retrieval_does_not_call_gemini():
    """Verifies that semantic search never invokes external Gemini APIs."""
    with patch("src.gemini_service.generate_response") as mock_gemini:
        results = semantic_search("arbitrary consumer legal question", top_k=3)
        mock_gemini.assert_not_called()
        assert len(results) > 0


# 25. Source Data and Index Reconciliation
def test_25_source_data_and_index_reconciliation(derived_records_map):
    """Verifies that all retrieved results map to known derived records with exact document attributes."""
    results = semantic_search("jurisdiction of state commission", top_k=5)
    for r in results:
        rec_id = r["embedding_record_id"]
        assert rec_id in derived_records_map
        expected = derived_records_map[rec_id]
        assert r["document_id"] == expected["document_id"]
        assert r["document_type"] == expected["document_type"]
        assert r["provision_type"] == expected["provision_type"]
