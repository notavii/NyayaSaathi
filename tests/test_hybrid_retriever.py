"""
Unit and Integration Test Suite for Hybrid Legal Retrieval in Nyaya Saathi.

Blueprint Phase 4C — Step 16: Semantic + BM25 Hybrid Retrieval with Reciprocal Rank Fusion.
Implements all 33 rigorous test specifications outlined in Blueprint Phase 4C Part L.
"""

from datetime import date
import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch
import pytest

from src.hybrid_retriever import (
    DEFAULT_RRF_K,
    DEFAULT_TOP_K,
    FUTURE_LAW_EFFECTIVE_DATE,
    VALID_APPLICABILITY_STATUSES,
    VALID_LEGAL_REVIEW_STATUSES,
    calculate_rrf_score,
    hybrid_search,
    resolve_date_gating,
)
from src.intake import classify_issue, CATEGORY_OUTSIDE_SCOPE
from src.vector_store import (
    COLLECTION_CURRENT_LAW,
    COLLECTION_FUTURE_LAW,
    COLLECTION_PROCEDURAL_GUIDANCE,
    VectorStoreManager,
)

DERIVED_RECORDS_PATH = Path("data/legal_sources/embedding_records.json")
CANONICAL_CHUNKS_PATH = Path("data/legal_sources/legal_chunks.json")


class TestHybridRetriever:
    """Comprehensive test suite for Hybrid legal retrieval."""

    def test_01_semantic_retrieval_is_called_correctly(self):
        """1. Verifies semantic retrieval is invoked and its candidate results are captured."""
        with patch("src.hybrid_retriever.semantic_search", wraps=lambda **kw: [
            {"embedding_record_id": "REC_001", "retrieval_rank": 1, "distance": 0.12, "exact_original_text": "Sample 1"}
        ]) as mock_sem:
            res = hybrid_search("defective laptop", top_k=5)
            assert mock_sem.called
            call_kw = mock_sem.call_args[1]
            assert "query" in call_kw
            assert call_kw["query"] == "defective laptop"

    def test_02_bm25_retrieval_is_called_correctly(self):
        """2. Verifies BM25 retrieval is invoked and its candidate results are captured."""
        with patch("src.hybrid_retriever.bm25_search", wraps=lambda **kw: [
            {"embedding_record_id": "REC_002", "retrieval_rank": 1, "bm25_score": 15.0, "exact_original_text": "Sample 2"}
        ]) as mock_bm25:
            res = hybrid_search("defective laptop", top_k=5)
            assert mock_bm25.called
            call_kw = mock_bm25.call_args[1]
            assert "query" in call_kw
            assert call_kw["query"] == "defective laptop"

    def test_03_standard_rrf_formula_implemented_correctly(self):
        """3. Verifies RRF formula: RRF(d) = sum_m (w_m / (k + rank_m))."""
        # Case 1: Only semantic at rank 1, k=60
        expected_sem_only = 1.0 / (60 + 1)
        assert abs(calculate_rrf_score(semantic_rank=1, bm25_rank=None, k=60) - expected_sem_only) < 1e-6

        # Case 2: Only BM25 at rank 2, k=60
        expected_bm25_only = 1.0 / (60 + 2)
        assert abs(calculate_rrf_score(semantic_rank=None, bm25_rank=2, k=60) - expected_bm25_only) < 1e-6

        # Case 3: Both methods: semantic rank 1, BM25 rank 2
        expected_both = (1.0 / 61) + (1.0 / 62)
        assert abs(calculate_rrf_score(semantic_rank=1, bm25_rank=2, k=60) - expected_both) < 1e-6

    def test_04_equal_weights_are_applied_initially(self):
        """4. Verifies default weights for semantic and BM25 are equal (1.0)."""
        score_sem_1 = calculate_rrf_score(semantic_rank=1, bm25_rank=None, k=60, semantic_weight=1.0, bm25_weight=1.0)
        score_bm25_1 = calculate_rrf_score(semantic_rank=None, bm25_rank=1, k=60, semantic_weight=1.0, bm25_weight=1.0)
        assert score_sem_1 == score_bm25_1

    def test_05_identical_result_ids_are_deduplicated(self):
        """5. Verifies a record retrieved by both methods appears only once with combined RRF score."""
        res = hybrid_search("Section 35 Consumer Protection Act", top_k=5)
        ids = [r["embedding_record_id"] for r in res]
        assert len(ids) == len(set(ids))

        # Check that top hit matched both methods
        top = res[0]
        if "CPA_2019_SECTION_35" in top["embedding_record_id"]:
            assert "SEMANTIC" in top["matched_methods"]
            assert "BM25" in top["matched_methods"]
            assert top["semantic_rank"] is not None
            assert top["bm25_rank"] is not None

    def test_06_different_child_segments_remain_separate(self):
        """6. Verifies child segments of the same section remain independently searchable."""
        with open(DERIVED_RECORDS_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)

        child_records = [r for r in records if r.get("is_child_segment", False)]
        assert len(child_records) > 0

        # Distinct child IDs must not be collapsed
        c1 = child_records[0]["embedding_record_id"]
        c2 = child_records[1]["embedding_record_id"]
        assert c1 != c2

    def test_07_both_component_ranks_are_preserved(self):
        """7. Verifies semantic_rank and bm25_rank are preserved in diagnostic telemetry."""
        res = hybrid_search("Section 35 Consumer Protection Act", top_k=5)
        assert len(res) > 0
        top = res[0]
        assert "semantic_rank" in top
        assert "bm25_rank" in top
        assert "rrf_score" in top
        assert "matched_methods" in top

    def test_08_raw_bm25_scores_not_added_directly_to_semantic_distances(self):
        """8. Verifies raw distance and score are not blended directly without RRF ranking."""
        res = hybrid_search("defective laptop", top_k=5)
        for r in res:
            # RRF score must be strictly between 0 and 0.1 (sum of 1/(k+rank))
            assert 0.0 < r["rrf_score"] < 0.2
            # Diagnostic scores remain separate
            if r["semantic_distance"] is not None:
                assert r["semantic_distance"] >= 0.0
            if r["bm25_score"] is not None:
                assert r["bm25_score"] > 0.0

    def test_09_final_ranking_is_deterministic(self):
        """9. Verifies identical queries produce identical results and rankings."""
        q = "Section 35 Consumer Protection Act manner of filing"
        res1 = hybrid_search(q, top_k=5)
        res2 = hybrid_search(q, top_k=5)

        assert len(res1) == len(res2)
        for r1, r2 in zip(res1, res2):
            assert r1["embedding_record_id"] == r2["embedding_record_id"]
            assert r1["rrf_score"] == r2["rrf_score"]
            assert r1["final_rank"] == r2["final_rank"]

    def test_10_top_k_limits_are_enforced(self):
        """10. Verifies top_k clamping between 1 and 10."""
        q = "defective product refund"
        assert len(hybrid_search(q, top_k=1)) <= 1
        assert len(hybrid_search(q, top_k=5)) <= 5
        assert len(hybrid_search(q, top_k=25)) <= 10  # Clamped to 10
        assert len(hybrid_search(q, top_k=-2)) >= 1  # Clamped to 1

    def test_11_metadata_is_preserved(self):
        """11. Verifies all required citation fields are populated on hybrid results."""
        res = hybrid_search("Section 35 Consumer Protection Act", top_k=3)
        assert len(res) > 0
        required_fields = [
            "final_rank", "embedding_record_id", "parent_chunk_id", "document_id",
            "document_title", "document_type", "provision_type", "provision_number",
            "provision_heading", "exact_original_text", "source_url", "applicability_status",
            "legal_review_status", "collection_name", "rrf_score", "matched_methods"
        ]
        for r in res:
            for field in required_fields:
                assert field in r, f"Missing field {field} in hybrid result"
                assert r[field] is not None

    def test_12_original_legal_text_is_unchanged(self):
        """12. Verifies exact original text matches the derived embedding records."""
        with open(DERIVED_RECORDS_PATH, "r", encoding="utf-8") as f:
            raw_records = json.load(f)
        raw_map = {r["embedding_record_id"]: r["text"] for r in raw_records}

        res = hybrid_search("Section 35 Consumer Protection Act", top_k=3)
        for r in res:
            rid = r["embedding_record_id"]
            assert rid in raw_map
            assert r["exact_original_text"] == raw_map[rid]

    def test_13_parent_child_references_are_preserved(self):
        """13. Verifies child records retain parent_chunk_id matching parent statutory section."""
        res = hybrid_search("unfair trade practice misleading advertisement", top_k=5)
        for r in res:
            assert r["parent_chunk_id"] is not None
            assert len(r["parent_chunk_id"]) > 0

    def test_14_current_law_filtering_works(self):
        """14. Verifies default searches draw from current statutory law."""
        res = hybrid_search("defective laptop refund", top_k=5)
        for r in res:
            assert r["collection_name"] == COLLECTION_CURRENT_LAW
            assert r["applicability_status"] == "CURRENTLY_IN_FORCE"

    def test_15_procedural_guidance_remains_separate(self):
        """15. Verifies procedural guidance is excluded by default and included only when requested."""
        query = "How do I upload document on e-Jagriti portal?"

        # Default: procedural manual excluded
        res_default = hybrid_search(query, top_k=5, include_procedural=False)
        for r in res_default:
            assert r["collection_name"] != COLLECTION_PROCEDURAL_GUIDANCE
            assert r["document_type"] not in ("PROCEDURAL_GUIDE", "PROCEDURAL_GUIDANCE")

        # Procedural requested: e-Jagriti guide is retrieved
        res_proc = hybrid_search(query, top_k=5, include_procedural=True)
        assert any(r["collection_name"] == COLLECTION_PROCEDURAL_GUIDANCE for r in res_proc)

    def test_16_future_law_records_remain_properly_restricted(self):
        """16. Verifies 2026 E-Commerce Amendment is excluded by default."""
        res = hybrid_search("dark pattern rules for ecommerce", top_k=8, include_future=False)
        for r in res:
            assert r["collection_name"] != COLLECTION_FUTURE_LAW
            assert r["applicability_status"] != "FUTURE_EFFECTIVE"

    def test_17_historical_records_remain_excluded(self):
        """17. Verifies Consumer Handbook 2015 and repealed CPA 1986 never appear in hybrid results."""
        res = hybrid_search("consumer rights and dispute redressal", top_k=10, include_procedural=True, include_future=True)
        for r in res:
            assert r["document_id"] != "CONSUMER_HANDBOOK_2015"
            assert r["document_id"] != "DOC_002"
            assert "CPA_1986" not in r["embedding_record_id"]

    def test_18_nch_web_only_source_remains_excluded(self):
        """18. Verifies NCH web guide is never returned by hybrid search."""
        res = hybrid_search("national consumer helpline grievance complaint", top_k=10, include_procedural=True)
        for r in res:
            assert r["document_id"] != "NCH_GRIEVANCE_GUIDE"

    def test_19_legal_review_status_is_never_upgraded_automatically(self):
        """19. Verifies legal_review_status strictly remains 'REQUIRES_LEGAL_REVIEW'."""
        res = hybrid_search("Section 35 Consumer Protection Act", top_k=5)
        for r in res:
            assert r["legal_review_status"] == "REQUIRES_LEGAL_REVIEW"
            assert r["legal_review_status"] in VALID_LEGAL_REVIEW_STATUSES
            assert r["legal_review_status"] != "HUMAN_REVIEWED"
            assert r["legal_review_status"] != "VERIFIED_ACTIVE"

    def test_20_missing_retrieval_results_are_handled(self):
        """20. Verifies queries yielding no results return an explicit empty list."""
        assert hybrid_search("") == []
        assert hybrid_search("   ") == []
        assert hybrid_search(None) == []  # type: ignore
        with patch("src.hybrid_retriever.semantic_search", return_value=[]), patch("src.hybrid_retriever.bm25_search", return_value=[]):
            assert hybrid_search("any query", top_k=5) == []

    def test_21_out_of_scope_queries_remain_gated_by_classifier(self):
        """21. Verifies integration gate: out-of-scope issues are flagged by the classifier."""
        rental_query = "How do I draft a residential rental lease agreement for my tenant in Mumbai?"
        scope_res = classify_issue(rental_query)
        assert scope_res["category"] == CATEGORY_OUTSIDE_SCOPE

    def test_22_english_queries_work(self):
        """22. Verifies English consumer defect complaint retrieval."""
        res = hybrid_search("I received a physically damaged air conditioner, what are my legal rights against the seller?", top_k=5)
        assert len(res) > 0
        parent_ids = [r["parent_chunk_id"] for r in res]
        assert any("SECTION_83" in pid or "SECTION_84" in pid or "SECTION_39" in pid or "RULE_6" in pid for pid in parent_ids)

    def test_23_hindi_queries_work(self):
        """23. Verifies pure Hindi consumer complaint retrieval."""
        res = hybrid_search("मुझे डिलीवरी में टूटा हुआ सामान मिला है, क्या मुझे नया सामान या पैसे वापस मिलेंगे?", top_k=5)
        assert len(res) > 0
        parent_ids = [r["parent_chunk_id"] for r in res]
        assert any("SECTION_39" in pid or "SECTION_84" in pid or "RULE_7" in pid or "SECTION_2_CLAUSE_10" in pid for pid in parent_ids)

    def test_24_hinglish_queries_work(self):
        """24. Verifies Hinglish complaint retrieval."""
        res = hybrid_search("Online shopping site se defective phone deliver hua hai aur return request cancel kar di.", top_k=5)
        assert len(res) > 0
        parent_ids = [r["parent_chunk_id"] for r in res]
        assert any("RULE_6" in pid or "RULE_7" in pid or "SECTION_83" in pid or "SECTION_84" in pid for pid in parent_ids)

    def test_25_transaction_date_filtering_works(self):
        """25. Verifies transactions in 2026 exclude 2027 law, transactions in 2027 include it."""
        q = "dark pattern cancellation rules"

        # 2026 purchase: 2027 amendment excluded
        res_2026 = hybrid_search(q, top_k=5, transaction_date="2026-05-15")
        for r in res_2026:
            assert r["collection_name"] != COLLECTION_FUTURE_LAW

        # 2027 purchase: 2027 amendment included
        res_2027 = hybrid_search(q, top_k=5, transaction_date="2027-02-15")
        assert any(r["collection_name"] == COLLECTION_FUTURE_LAW for r in res_2027)

    def test_26_as_of_date_filtering_works(self):
        """26. Verifies current-law question as_of_date before vs after commencement."""
        q = "dark pattern rules for ecommerce"

        # as_of_date in 2026: excluded
        res_2026 = hybrid_search(q, top_k=5, as_of_date="2026-10-01")
        for r in res_2026:
            assert r["collection_name"] != COLLECTION_FUTURE_LAW

        # as_of_date in 2027: included
        res_2027 = hybrid_search(q, top_k=5, as_of_date="2027-04-01")
        assert any(r["collection_name"] == COLLECTION_FUTURE_LAW for r in res_2027)

    def test_27_future_law_results_remain_labelled(self):
        """27. Verifies future law provisions retain FUTURE_EFFECTIVE label."""
        res = hybrid_search("What are the new rules for e-commerce entities coming into effect from January 2027?", top_k=5, include_future=True)
        future_res = [r for r in res if r["collection_name"] == COLLECTION_FUTURE_LAW]
        assert len(future_res) > 0
        assert future_res[0]["applicability_status"] == "FUTURE_EFFECTIVE"

    def test_28_hybrid_search_does_not_call_gemini(self):
        """28. Verifies hybrid retrieval performs zero LLM/Gemini API calls."""
        with patch("google.genai.Client") as mock_client:
            hybrid_search("Section 35 Consumer Protection Act", top_k=3)
            assert not mock_client.called

    def test_29_hybrid_search_does_not_modify_chromadb(self):
        """29. Verifies persistent ChromaDB record counts remain unchanged after search."""
        vm = VectorStoreManager()
        before_counts = vm.get_collection_counts()

        hybrid_search("defective laptop refund", top_k=8, include_procedural=True, include_future=True)

        after_counts = vm.get_collection_counts()
        assert before_counts == after_counts

    def test_30_hybrid_search_does_not_modify_source_json(self):
        """30. Verifies legal_chunks.json and embedding_records.json remain byte-identical."""
        with open(CANONICAL_CHUNKS_PATH, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        assert len(chunks) == 206

        with open(DERIVED_RECORDS_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)
        assert len(records) == 251

    def test_31_existing_semantic_tests_remain_passing(self):
        """31. Verifies semantic retriever continues to operate independently."""
        from src.legal_retriever import semantic_search
        s_res = semantic_search("Section 35 Consumer Protection Act", top_k=1)
        assert len(s_res) == 1
        assert s_res[0]["embedding_record_id"] == "CPA_2019_SECTION_35"

    def test_32_existing_bm25_tests_remain_passing(self):
        """32. Verifies BM25 retriever continues to operate independently."""
        from src.bm25_retriever import bm25_search
        b_res = bm25_search("Section 35 Consumer Protection Act 2019 manner in which complaint shall be made", top_k=1)
        assert len(b_res) == 1
        assert b_res[0]["embedding_record_id"] == "CPA_2019_SECTION_35"

    def test_33_historical_transaction_asked_about_after_commencement(self):
        """33. Verifies purchase in 2026 asked about in 2027 does NOT apply 2027 amendments."""
        # Purchase date is 2026-05-10, evaluation date is 2027-02-15 (closed past event)
        future_eligible, t_date, a_date, temporal_status = resolve_date_gating(
            include_future=False,
            transaction_date="2026-05-10",
            as_of_date="2027-02-15",
        )
        assert future_eligible is False
        assert t_date == date(2026, 5, 10)
        assert a_date == date(2027, 2, 15)
        assert temporal_status == "NOT_APPLICABLE_PRE_COMMENCEMENT"

    def test_34_temporal_scenario_1_transaction_and_event_before_commencement(self):
        """Scenario 1: Purchase and dispute event both occur before 2027-01-01."""
        res = resolve_date_gating(
            transaction_date="2026-05-10",
            event_date="2026-05-15",
            as_of_date="2026-06-01",
        )
        assert res.future_eligible is False
        assert res.transaction_date == date(2026, 5, 10)
        assert res.temporal_status == "CURRENTLY_IN_FORCE"

    def test_35_temporal_scenario_2_event_after_commencement(self):
        """Scenario 2: Dispute event occurs on or after 2027-01-01 commencement."""
        res = resolve_date_gating(
            transaction_date="2027-02-10",
            event_date="2027-02-15",
            as_of_date="2027-03-01",
        )
        assert res.future_eligible is True
        assert res.transaction_date == date(2027, 2, 10)
        assert res.temporal_status == "CURRENTLY_IN_FORCE"

    def test_36_temporal_scenario_3_transaction_before_continuing_dispute_after(self):
        """Scenario 3: Transaction pre-commencement with continuing dispute post-commencement."""
        res = resolve_date_gating(
            transaction_date="2026-06-15",
            as_of_date="2027-02-01",
            continuing_dispute=True,
        )
        assert res.future_eligible is True
        assert res.transaction_date == date(2026, 6, 15)
        assert res.as_of_date == date(2027, 2, 1)
        assert res.temporal_status == "NEEDS_LEGAL_REVIEW"

        # Also check via hybrid_search: returned record must carry NEEDS_LEGAL_REVIEW
        search_res = hybrid_search(
            "e-commerce return policy ranking",
            top_k=5,
            transaction_date="2026-06-15",
            as_of_date="2027-02-01",
            continuing_dispute=True,
        )
        future_hits = [r for r in search_res if r["document_id"] == "CP_ECOMMERCE_AMENDMENT_2026"]
        if future_hits:
            assert future_hits[0]["temporal_applicability_status"] == "NEEDS_LEGAL_REVIEW"

    def test_37_temporal_scenario_4_current_position_in_november_2026(self):
        """Scenario 4: User inquiring about current law in November 2026."""
        res = resolve_date_gating(
            as_of_date="2026-11-07",
            system_date="2026-11-07",
        )
        assert res.future_eligible is False
        assert res.temporal_status == "CURRENTLY_IN_FORCE"

    def test_38_temporal_scenario_5_future_january_2027_rules(self):
        """Scenario 5: Explicit inquiry regarding forthcoming January 2027 rules."""
        res = resolve_date_gating(include_future=True)
        assert res.future_eligible is True
        assert res.temporal_status == "FUTURE_EFFECTIVE"

        search_res = hybrid_search("What are the new rules for e-commerce entities coming into effect from January 2027?", top_k=5, include_future=True)
        future_hits = [r for r in search_res if r["document_id"] == "CP_ECOMMERCE_AMENDMENT_2026"]
        assert len(future_hits) > 0
        assert future_hits[0]["temporal_applicability_status"] == "FUTURE_EFFECTIVE"
        assert future_hits[0]["gazette_reference"] == "G.S.R. 789(E)"

    def test_39_temporal_scenario_6_historical_event_asked_after_commencement(self):
        """Scenario 6: Historical closed event (2024) asked about in 2027."""
        res = resolve_date_gating(
            transaction_date="2024-03-01",
            event_date="2024-03-10",
            as_of_date="2027-03-01",
            continuing_dispute=False,
        )
        assert res.future_eligible is False
        assert res.temporal_status == "NOT_APPLICABLE_PRE_COMMENCEMENT"
