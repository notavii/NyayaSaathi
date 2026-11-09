"""
Unit and Integration Tests for ChromaDB Vector Storage (Phase 3C.1).

Verifies:
1. Three strictly segregated collections exist with exact counts:
   - nyaya_saathi_current_law (232 statutory records in force)
   - nyaya_saathi_procedural_guidance (13 official procedural guide records)
   - nyaya_saathi_future_law (6 future-effective amendment records)
2. Historical chunks (Consumer Handbook 2015) are strictly excluded from all collections.
3. NCH web-only source is excluded from all collections.
4. Procedural guidance is strictly isolated in nyaya_saathi_procedural_guidance.
5. Statutory collection contains ONLY legislation (ACT, RULES, CORRIGENDUM, AMENDMENT_RULES).
6. 2026 amendment chunks remain FUTURE_EFFECTIVE with effective_from = 2027-01-01.
7. All stored records retain full provenance metadata (all required metadata keys).
8. Chroma collections persist after client reinitialisation.
9. Running index build twice does not create duplicates (idempotency).
10. Stale records are pruned safely.
11. Indexed text matches the verbatim legal text.
12. Original canonical legal_chunks.json remains unchanged.
13. Vector index manifest exists, is valid JSON, and records accurate metadata.
14. Mediation rules provenance: Verified to belong to CPA 2019 Chapter V without rogue catalogue entries.
15. Zero duplicate vector IDs across any collection.
"""

import json
from pathlib import Path
import pytest

from src.vector_store import (
    ALL_COLLECTIONS,
    COLLECTION_CURRENT_LAW,
    COLLECTION_FUTURE_LAW,
    COLLECTION_PROCEDURAL_GUIDANCE,
    DEFAULT_CHROMA_DIR,
    REQUIRED_METADATA_KEYS,
    VectorStoreManager,
    sanitize_metadata,
)
from scripts.build_vector_index import (
    CHUNKS_FILE,
    DERIVED_RECORDS_FILE,
    HISTORICAL_CHUNKS_FILE,
    MANIFEST_FILE,
    CATALOG_FILE,
    build_vector_index,
    compute_file_sha256,
)


@pytest.fixture(scope="module")
def persistent_store():
    """Initializes the VectorStoreManager pointing to the actual database."""
    assert DEFAULT_CHROMA_DIR.exists(), f"Chroma directory not found at {DEFAULT_CHROMA_DIR}"
    return VectorStoreManager(persist_dir=DEFAULT_CHROMA_DIR)


@pytest.fixture(scope="module")
def canonical_chunks_data():
    """Loads canonical legal_chunks.json."""
    assert CHUNKS_FILE.exists()
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def derived_records_data():
    """Loads derived embedding_records.json."""
    assert DERIVED_RECORDS_FILE.exists()
    with open(DERIVED_RECORDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def manifest_data():
    """Loads vector_index_manifest.json."""
    assert MANIFEST_FILE.exists(), f"Manifest not found at {MANIFEST_FILE}"
    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def test_01_three_collections_exist_and_counts_match_specification(persistent_store):
    """
    CRITICAL SEGREGATION TEST:
    Verifies that the three distinct collections exist with exact expected record counts:
    - nyaya_saathi_current_law: 232 records
    - nyaya_saathi_procedural_guidance: 13 records
    - nyaya_saathi_future_law: 6 records
    """
    counts = persistent_store.get_collection_counts()
    assert counts[COLLECTION_CURRENT_LAW] == 232, f"Expected 232 current law records, found {counts[COLLECTION_CURRENT_LAW]}"
    assert counts[COLLECTION_PROCEDURAL_GUIDANCE] == 13, f"Expected 13 procedural records, found {counts[COLLECTION_PROCEDURAL_GUIDANCE]}"
    assert counts[COLLECTION_FUTURE_LAW] == 6, f"Expected 6 future law records, found {counts[COLLECTION_FUTURE_LAW]}"


def test_02_historical_chunks_excluded_from_all_collections(persistent_store):
    """
    CRITICAL KNOWLEDGE BASE PURITY TEST:
    Verifies that zero chunks from CONSUMER_HANDBOOK_2015 appear in any Chroma collection.
    """
    for col_name in ALL_COLLECTIONS:
        coll = persistent_store.get_or_create_collection(col_name)
        data = coll.get()
        for cid in data["ids"]:
            assert "CONSUMER_HANDBOOK" not in cid
        for meta in data["metadatas"]:
            assert meta["document_id"] != "CONSUMER_HANDBOOK_2015"
            assert meta["applicability_status"] != "HISTORICAL_REFERENCE"


def test_03_nch_web_only_source_excluded(persistent_store):
    """Verifies that NCH_GRIEVANCE_GUIDE has zero records in all collections."""
    for col_name in ALL_COLLECTIONS:
        coll = persistent_store.get_or_create_collection(col_name)
        data = coll.get()
        for meta in data["metadatas"]:
            assert meta["document_id"] != "NCH_GRIEVANCE_GUIDE"


def test_04_procedural_guidance_strictly_isolated(persistent_store):
    """
    Verifies that procedural guide records (e-Jagriti guide) are in nyaya_saathi_procedural_guidance
    and completely absent from nyaya_saathi_current_law.
    """
    proc_coll = persistent_store.get_procedural_guidance_collection()
    proc_results = proc_coll.get()
    assert len(proc_results["ids"]) == 13
    for meta in proc_results["metadatas"]:
        assert meta["document_type"] in ("PROCEDURAL_GUIDE", "PROCEDURAL_GUIDANCE")
        assert meta["document_id"] == "EJAGRITI_FILING_GUIDE"

    current_coll = persistent_store.get_current_law_collection()
    curr_results = current_coll.get(where={"document_id": "EJAGRITI_FILING_GUIDE"})
    assert len(curr_results["ids"]) == 0, "Procedural guide must NOT be in current law collection"


def test_05_current_law_contains_only_statutory_legislation(persistent_store):
    """
    Verifies that nyaya_saathi_current_law contains ONLY legislation (ACT, RULES, CORRIGENDUM, AMENDMENT_RULES)
    and strictly CURRENTLY_IN_FORCE material.
    """
    current_coll = persistent_store.get_current_law_collection()
    data = current_coll.get()
    assert len(data["ids"]) == 232

    valid_statutory_types = {"CENTRAL_ACT", "ACT", "RULES", "CORRIGENDUM", "AMENDMENT_RULES"}
    for meta in data["metadatas"]:
        assert meta["document_type"] in valid_statutory_types, (
            f"Non-statutory document_type '{meta['document_type']}' found in current law collection"
        )
        assert meta["applicability_status"] == "CURRENTLY_IN_FORCE"


def test_06_future_law_collection_strictly_isolated(persistent_store):
    """
    CRITICAL TEMPORAL TEST:
    Verifies that nyaya_saathi_future_law contains exclusively the 2026 E-Commerce Amendment records,
    with applicability_status: FUTURE_EFFECTIVE and effective_from: 2027-01-01.
    """
    future_coll = persistent_store.get_future_law_collection()
    results = future_coll.get()

    assert len(results["ids"]) == 6
    for meta in results["metadatas"]:
        assert meta["document_id"] == "CP_ECOMMERCE_AMENDMENT_2026"
        assert meta["applicability_status"] == "FUTURE_EFFECTIVE"
        assert meta["effective_from"] == "2027-01-01"
        assert meta["publication_date"] == "2026-09-09"
        assert meta["retrieval_eligible"] is True

    # Ensure no future records appear in current law
    current_coll = persistent_store.get_current_law_collection()
    curr_future = current_coll.get(where={"applicability_status": "FUTURE_EFFECTIVE"})
    assert len(curr_future["ids"]) == 0


def test_07_metadata_preservation_on_all_stored_records(persistent_store):
    """Verifies that all stored records across all three collections retain all required metadata fields."""
    for col_name in ALL_COLLECTIONS:
        coll = persistent_store.get_or_create_collection(col_name)
        data = coll.get()
        for meta in data["metadatas"]:
            for req_key in REQUIRED_METADATA_KEYS:
                assert req_key in meta, f"Metadata key '{req_key}' missing from '{meta.get('embedding_record_id')}'"
                assert isinstance(meta[req_key], (str, int, float, bool)), (
                    f"Non-primitive type found for '{req_key}' in '{meta.get('embedding_record_id')}'"
                )


def test_08_persistence_after_client_reinitialisation():
    """Verifies that closing and reopening the PersistentClient preserves all collections and records."""
    manager1 = VectorStoreManager(persist_dir=DEFAULT_CHROMA_DIR)
    counts1 = manager1.get_collection_counts()

    # Re-instantiate a fresh client on the same directory
    manager2 = VectorStoreManager(persist_dir=DEFAULT_CHROMA_DIR)
    counts2 = manager2.get_collection_counts()

    assert counts1 == counts2
    assert counts2[COLLECTION_CURRENT_LAW] == 232
    assert counts2[COLLECTION_PROCEDURAL_GUIDANCE] == 13
    assert counts2[COLLECTION_FUTURE_LAW] == 6


def test_09_idempotent_index_build_no_duplicates(persistent_store):
    """
    IDEMPOTENCY TEST:
    Verifies that running index build multiple times produces zero duplicates.
    """
    counts_before = persistent_store.get_collection_counts()
    
    # Re-run index build
    res = build_vector_index(chunks_path=CHUNKS_FILE, persist_dir=DEFAULT_CHROMA_DIR, log_output=False)
    counts_after = persistent_store.get_collection_counts()

    assert counts_before == counts_after == {
        "nyaya_saathi_current_law": 232,
        "nyaya_saathi_procedural_guidance": 13,
        "nyaya_saathi_future_law": 6,
    }


def test_10_stale_record_pruning_in_isolated_collection(tmp_path):
    """
    Verifies that prune_stale_records removes stale items from a collection
    without affecting active records.
    """
    tmp_manager = VectorStoreManager(persist_dir=tmp_path)
    test_coll_name = "test_stale_pruning"
    
    mock_chunks = [
        {"embedding_record_id": "REC_1", "text": "Provision 1"},
        {"embedding_record_id": "REC_2", "text": "Provision 2"},
        {"embedding_record_id": "REC_3", "text": "Provision 3"},
    ]
    mock_embs = [[0.1] * 384, [0.2] * 384, [0.3] * 384]

    tmp_manager.upsert_records(test_coll_name, mock_chunks, mock_embs)
    coll = tmp_manager.get_or_create_collection(test_coll_name)
    assert coll.count() == 3

    # Active IDs only has REC_1 and REC_2 (REC_3 is stale)
    active_ids = {"REC_1", "REC_2"}
    pruned = tmp_manager.prune_stale_records(test_coll_name, active_ids)
    assert pruned == 1
    assert coll.count() == 2
    assert set(coll.get()["ids"]) == {"REC_1", "REC_2"}


def test_11_indexed_text_matches_verbatim_legal_text(persistent_store, canonical_chunks_data):
    """Verifies that non-split provisions stored in Chroma match verbatim canonical source legal text."""
    current_coll = persistent_store.get_current_law_collection()
    
    check_ids = ["CPA_2019_SECTION_1", "CPA_2019_SECTION_35", "CPA_2019_SECTION_107"]
    source_map = {c["chunk_id"]: c["text"] for c in canonical_chunks_data}

    results = current_coll.get(ids=check_ids)
    for cid, doc in zip(results["ids"], results["documents"]):
        assert doc == source_map[cid]


def test_12_original_legal_chunks_json_remains_unchanged(manifest_data):
    """Verifies that canonical legal_chunks.json byte hash matches the manifest declaration."""
    current_hash = compute_file_sha256(CHUNKS_FILE)
    manifest_hash = manifest_data["source_dataset"]["canonical_sha256"]
    assert current_hash == manifest_hash


def test_13_vector_index_manifest_integrity(manifest_data):
    """Verifies all required keys and counts in vector_index_manifest.json."""
    assert manifest_data["build_status"] == "SUCCESS"
    assert manifest_data["embedding_model"]["model_id"] == "intfloat/multilingual-e5-small"
    assert manifest_data["embedding_model"]["embedding_dimension"] == 384
    assert manifest_data["embedding_model"]["max_sequence_length"] == 512
    assert manifest_data["embedding_model"]["passage_prefix"] == "passage: "
    assert manifest_data["embedding_model"]["query_prefix"] == "query: "

    colls = manifest_data["collections"]
    assert colls["nyaya_saathi_current_law"]["record_count"] == 232
    assert colls["nyaya_saathi_procedural_guidance"]["record_count"] == 13
    assert colls["nyaya_saathi_future_law"]["record_count"] == 6

    assert manifest_data["exclusions"]["historical_chunks_count"] == 74
    assert manifest_data["exclusions"]["web_only_sources_count"] == 1
    assert manifest_data["token_limit_handling"]["silent_truncation_prevented"] is True


def test_14_mediation_rules_provenance_and_catalogue_consistency():
    """
    AUDIT TEST (Part B):
    Verifies that no unverified or unauthorized 'Mediation Rules' document exists in source_catalog.json,
    and confirms mediation provisions exist strictly under CPA_2019 Chapter V.
    """
    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    catalog_doc_ids = {s["document_id"] for s in catalog["sources"]}
    assert "CP_MEDIATION_RULES_2020" not in catalog_doc_ids
    assert "MEDIATION_RULES" not in catalog_doc_ids

    # Mediation exists within CPA 2019
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    mediation_chunks = [
        c for c in chunks
        if c["document_id"] == "CPA_2019" and "mediation" in c.get("text", "").lower()
    ]
    assert len(mediation_chunks) >= 8  # Chapter V Sections 74-81 + Section 2(25)


def test_15_no_duplicate_vector_ids_across_all_collections(persistent_store):
    """Verifies that across all three collections, every vector ID is completely unique."""
    all_seen_ids = set()
    for col_name in ALL_COLLECTIONS:
        coll = persistent_store.get_or_create_collection(col_name)
        data = coll.get()
        ids = data["ids"]
        # Check no duplicates within collection
        assert len(ids) == len(set(ids)), f"Duplicate IDs found within {col_name}"
        # Check no duplicates across collections
        for item_id in ids:
            assert item_id not in all_seen_ids, f"ID '{item_id}' duplicated across collections!"
            all_seen_ids.add(item_id)

    assert len(all_seen_ids) == 251
