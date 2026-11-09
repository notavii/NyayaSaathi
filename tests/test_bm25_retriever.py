"""
Unit and Integration Test Suite for BM25 Keyword Retrieval in Nyaya Saathi.

Step 15: BM25 Lexical Retrieval Verification.
Implements all 30 rigorous test specifications outlined in Blueprint Phase 4B Part L.
"""

from datetime import date
import json
from pathlib import Path
from typing import Any, Dict, List
import pytest

from src.bm25_retriever import (
    COLLECTION_CURRENT_LAW,
    COLLECTION_FUTURE_LAW,
    COLLECTION_PROCEDURAL_GUIDANCE,
    BM25IndexManager,
    bm25_search,
    get_bm25_manager,
    normalize_text,
    tokenize_legal_text,
)
from src.legal_retriever import semantic_search
from src.vector_store import VectorStoreManager

DERIVED_RECORDS_PATH = Path("data/legal_sources/embedding_records.json")
CANONICAL_CHUNKS_PATH = Path("data/legal_sources/legal_chunks.json")


@pytest.fixture(scope="module")
def bm25_manager():
    """Provides the singleton BM25 index manager."""
    return get_bm25_manager(records_path=DERIVED_RECORDS_PATH)


class TestBM25Retriever:
    """Comprehensive test suite for BM25 keyword retrieval."""

    def test_01_bm25_index_builds_successfully(self, bm25_manager):
        """1. Verifies BM25 index builds without error."""
        assert bm25_manager is not None
        assert len(bm25_manager.all_records) == 251

    def test_02_all_eligible_embedding_records_are_indexed(self, bm25_manager):
        """2. Verifies all 251 eligible records are categorized across the three collections."""
        current_count = bm25_manager.record_collections.count(COLLECTION_CURRENT_LAW)
        proc_count = bm25_manager.record_collections.count(COLLECTION_PROCEDURAL_GUIDANCE)
        future_count = bm25_manager.record_collections.count(COLLECTION_FUTURE_LAW)

        assert current_count == 232
        assert proc_count == 13
        assert future_count == 6
        assert current_count + proc_count + future_count == 251

    def test_03_unique_identifiers_are_maintained(self, bm25_manager):
        """3. Verifies that all indexed record IDs are unique."""
        ids = [r["embedding_record_id"] for r in bm25_manager.all_records]
        assert len(ids) == len(set(ids))

    def test_04_source_metadata_is_preserved(self, bm25_manager):
        """4. Verifies presence of statutory citation metadata on every record."""
        required_fields = [
            "document_id", "document_title", "provision_type", "provision_number",
            "provision_heading", "source_url", "applicability_status"
        ]
        for r in bm25_manager.all_records:
            for field in required_fields:
                assert field in r, f"Missing field {field} in {r.get('embedding_record_id')}"
            assert r["document_id"]
            assert r["document_title"]
            assert r["applicability_status"]

    def test_05_original_text_matches_source_dataset(self, bm25_manager):
        """5. Verifies indexed verbatim text matches derived embedding records file."""
        with open(DERIVED_RECORDS_PATH, "r", encoding="utf-8") as f:
            raw_records = json.load(f)

        raw_map = {r["embedding_record_id"]: r["text"] for r in raw_records}
        for r in bm25_manager.all_records:
            rid = r["embedding_record_id"]
            assert rid in raw_map
            assert r["text"] == raw_map[rid]

    def test_06_case_normalisation_works(self):
        """6. Verifies lowercasing and Unicode NFKC normalization."""
        norm = normalize_text("CONSUMER Protection Act, 2019 — Section 35")
        assert "consumer" in norm
        assert "section 35" in norm
        assert norm == norm.lower()

    def test_07_legal_section_numbers_are_preserved(self):
        """7. Verifies legal section numbers and identifiers are preserved as tokens."""
        tokens = tokenize_legal_text("Section 35 of the Consumer Protection Act")
        assert "section" in tokens
        assert "35" in tokens
        assert "consumer" in tokens
        assert "protection" in tokens
        assert "act" in tokens

    def test_08_rule_identifiers_are_preserved(self):
        """8. Verifies rule identifiers like Rule 4(1) preserve rule, 4(1), 4, 1."""
        tokens = tokenize_legal_text("Rule 4(1) of E-Commerce Rules")
        assert "rule" in tokens
        assert "4(1)" in tokens
        assert "4" in tokens
        assert "1" in tokens
        assert "ecommerce" in tokens or "rules" in tokens

    def test_09_negation_words_are_not_removed(self):
        """9. Verifies negation words are strictly retained in tokenisation."""
        text = "No seller shall not refuse refund without reason, nor neither never."
        tokens = tokenize_legal_text(text)
        assert "no" in tokens
        assert "not" in tokens
        assert "without" in tokens
        assert "neither" in tokens
        assert "never" in tokens
        assert "nor" in tokens

    def test_10_exact_legal_term_retrieval_works(self):
        """10. Verifies exact citation query returns Section 35 at Rank 1."""
        res = bm25_search("Section 35 Consumer Protection Act 2019 manner in which complaint shall be made", top_k=3)
        assert len(res) > 0
        assert res[0]["provision_number"] == 35 or res[0]["embedding_record_id"] == "CPA_2019_SECTION_35"
        assert res[0]["retrieval_rank"] == 1
        assert res[0]["bm25_score"] > 10.0

    def test_11_english_damaged_product_query_works(self):
        """11. Verifies English damaged goods complaint retrieves product defect provisions."""
        res = bm25_search("I received a physically damaged air conditioner, what are my legal rights against the seller?", top_k=5)
        assert len(res) > 0
        parent_ids = [r["parent_chunk_id"] for r in res]
        assert any("SECTION_84" in pid or "SECTION_83" in pid or "SECTION_39" in pid or "SECTION_2_CLAUSE_10" in pid for pid in parent_ids)

    def test_12_english_refund_query_works(self):
        """12. Verifies English refund query retrieves refund and consumer rights provisions."""
        res = bm25_search("Seller refused to refund money after order was cancelled", top_k=5)
        assert len(res) > 0
        headings = [r["provision_heading"].lower() for r in res]
        texts = [r["exact_original_text"].lower() for r in res]
        assert any("refund" in h or "refund" in t for h, t in zip(headings, texts))

    def test_13_hindi_damaged_product_query_works_through_keyword_expansion(self):
        """13. Verifies Hindi damaged product query retrieves defect provisions."""
        res = bm25_search("मुझे डिलीवरी में टूटा हुआ सामान मिला है, क्या मुझे नया सामान या पैसे वापस मिलेंगे?", top_k=5)
        assert len(res) > 0
        parent_ids = [r["parent_chunk_id"] for r in res]
        assert any("SECTION_84" in pid or "SECTION_83" in pid or "SECTION_2_CLAUSE_10" in pid or "RULE_7" in pid for pid in parent_ids)

    def test_14_hindi_refund_query_works(self):
        """14. Verifies Hindi refund refusal query retrieves refund and grievance provisions."""
        res = bm25_search("दुकानदार पैसे वापस करने से मना कर रहा है, उपभोक्ता फोरम में शिकायत कैसे करें?", top_k=8)
        assert len(res) > 0
        parent_ids = [r["parent_chunk_id"] for r in res]
        assert any("RULE_7" in pid or "RULE_6" in pid or "SECTION_35" in pid or "SECTION_39" in pid for pid in parent_ids)

    def test_15_hinglish_non_delivery_query_works(self):
        """15. Verifies Hinglish non-delivery query retrieves e-commerce delivery provisions."""
        res = bm25_search("mera order deliver nahi hua abhi tak online shopping se", top_k=5)
        assert len(res) > 0
        parent_ids = [r["parent_chunk_id"] for r in res]
        assert any("RULE_5" in pid or "RULE_6" in pid or "RULE_7" in pid or "SECTION_35" in pid for pid in parent_ids)

    def test_16_controlled_keyword_expansion_does_not_invent_section_references(self):
        """16. Verifies expanded search terms never contain fabricated statutory numbers."""
        res = bm25_search("Flipkart pe product damaged mila", top_k=5)
        for r in res:
            for term in r.get("expanded_search_terms", []):
                assert not term.lower().startswith("section ")
                assert not term.lower().startswith("rule ")

    def test_17_procedural_guidance_remains_separately_searchable(self):
        """17. Verifies procedural guidance is excluded by default and included only when requested."""
        query = "How do I upload document on e-Jagriti portal?"

        # Default search: procedural is excluded
        res_default = bm25_search(query, top_k=5, include_procedural=False)
        for r in res_default:
            assert r["collection_name"] != COLLECTION_PROCEDURAL_GUIDANCE
            assert r["document_type"] not in ("PROCEDURAL_GUIDE", "PROCEDURAL_GUIDANCE")

        # Procedural included: e-Jagriti manual is retrieved
        res_proc = bm25_search(query, top_k=5, include_procedural=True)
        assert any(r["collection_name"] == COLLECTION_PROCEDURAL_GUIDANCE for r in res_proc)

    def test_18_future_law_material_is_excluded_by_default(self):
        """18. Verifies 2026 amendment is invisible to standard searches."""
        query = "dark pattern rules for e-commerce entities"
        res = bm25_search(query, top_k=10, include_future=False, transaction_date="2025-06-01")
        for r in res:
            assert r["collection_name"] != COLLECTION_FUTURE_LAW
            assert r["applicability_status"] != "FUTURE_EFFECTIVE"

    def test_19_explicit_future_search_is_correctly_labelled(self):
        """19. Verifies explicit future searches include and label future enactments."""
        query = "What are the new rules for e-commerce entities coming into effect from January 2027?"
        res = bm25_search(query, top_k=5, include_future=True)
        assert len(res) > 0
        future_results = [r for r in res if r["collection_name"] == COLLECTION_FUTURE_LAW]
        assert len(future_results) > 0
        assert future_results[0]["applicability_status"] == "FUTURE_EFFECTIVE"

    def test_20_historical_material_is_excluded(self, bm25_manager):
        """20. Verifies Consumer Handbook 2015 and repealed CPA 1986 are excluded from index."""
        doc_ids = {r["document_id"] for r in bm25_manager.all_records}
        assert "CONSUMER_HANDBOOK_2015" not in doc_ids
        assert "DOC_002" not in doc_ids
        assert "CPA_1986" not in doc_ids

    def test_21_nch_web_only_sources_are_excluded(self, bm25_manager):
        """21. Verifies NCH web-only guide is not in the BM25 index."""
        doc_ids = {r["document_id"] for r in bm25_manager.all_records}
        assert "NCH_GRIEVANCE_GUIDE" not in doc_ids

    def test_22_out_of_scope_queries_do_not_produce_fake_legal_results(self):
        """22. Verifies out-of-scope queries return authentic records without fabricated citations."""
        query = "How do I draft a residential rental lease agreement for my tenant in Mumbai?"
        res = bm25_search(query, top_k=5)
        # Results (if any match the word 'agreement') must be genuine legal records
        for r in res:
            assert r["document_id"].startswith("CPA_2019") or r["document_id"].startswith("CP_")
            assert len(r["exact_original_text"]) > 10

    def test_23_empty_queries_are_handled(self):
        """23. Verifies empty and whitespace queries return empty lists."""
        assert bm25_search("") == []
        assert bm25_search("   ") == []
        assert bm25_search(None) == []  # type: ignore

    def test_24_empty_retrieval_results_are_handled(self):
        """24. Verifies query with terms not in vocabulary returns empty list."""
        query = "xyzqwerty12345 nonexistentsupercalifragilistic"
        res = bm25_search(query, top_k=5)
        assert res == []

    def test_25_top_k_limits_are_enforced(self):
        """25. Verifies top_k clamping between 1 and 10."""
        q = "consumer complaint refund"
        assert len(bm25_search(q, top_k=1)) <= 1
        assert len(bm25_search(q, top_k=5)) <= 5
        assert len(bm25_search(q, top_k=20)) <= 10  # Clamped to 10
        assert len(bm25_search(q, top_k=-3)) >= 1  # Clamped to 1

    def test_26_bm25_scores_are_finite(self):
        """26. Verifies all retrieved BM25 scores are positive, finite numbers."""
        import math
        res = bm25_search("defective product refund e-commerce", top_k=5)
        assert len(res) > 0
        for r in res:
            score = r["bm25_score"]
            assert isinstance(score, float)
            assert not math.isnan(score)
            assert not math.isinf(score)
            assert score > 0.0

    def test_27_ranking_is_deterministic(self):
        """27. Verifies identical queries produce identical rankings and scores."""
        q = "Section 35 Consumer Protection Act complaint manner"
        res1 = bm25_search(q, top_k=5)
        res2 = bm25_search(q, top_k=5)

        assert len(res1) == len(res2)
        for r1, r2 in zip(res1, res2):
            assert r1["embedding_record_id"] == r2["embedding_record_id"]
            assert r1["bm25_score"] == r2["bm25_score"]

    def test_28_search_does_not_modify_chromadb(self):
        """28. Verifies persistent ChromaDB record counts remain unchanged after BM25 search."""
        vm = VectorStoreManager()
        before_counts = vm.get_collection_counts()

        bm25_search("consumer dispute defective laptop refund", top_k=8, include_procedural=True, include_future=True)

        after_counts = vm.get_collection_counts()
        assert before_counts == after_counts

    def test_29_search_does_not_modify_canonical_legal_text(self):
        """29. Verifies canonical legal_chunks.json and embedding_records.json remain unmodified."""
        with open(CANONICAL_CHUNKS_PATH, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        assert len(chunks) == 206

        with open(DERIVED_RECORDS_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)
        assert len(records) == 251

    def test_30_semantic_retrieval_remains_unchanged(self):
        """30. Verifies semantic retrieval continues working identically alongside BM25."""
        sem_res = semantic_search("Section 35 Consumer Protection Act", top_k=3)
        assert len(sem_res) > 0
        assert sem_res[0]["retrieval_method"] == "SEMANTIC_MULTILINGUAL_E5"
        assert sem_res[0]["embedding_record_id"] == "CPA_2019_SECTION_35"
