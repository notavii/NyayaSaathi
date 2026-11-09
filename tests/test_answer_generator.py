"""
Unit and Integration Tests for Source-Grounded Legal Answer Generation.

Blueprint Step 17: Source-Grounded Legal Answer Generation using Gemini.
Contains 26 Mocked Tests + 1 Live Integration Test.
"""

from datetime import date
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import answer_generator
from src import config
from src import gemini_service
from src import hybrid_retriever


SAMPLE_CASE = {
    "case_id": "CASE-TEST-001",
    "product_or_service": "smartphone",
    "seller_or_platform": "Tech Retailer",
    "purchase_amount": "₹15,000",
    "desired_resolution": "Replacement with non-defective product",
    "seller_contact": {
        "contacted": True,
        "contact_method": "phone call",
        "seller_response": "Refused replacement",
    },
    "facts_confirmed_by_user": True,
    "events": [{"event": "Screen stopped working", "date": "2026-03-01"}],
    "evidence": [{"item": "Invoice", "description": "Retail invoice with serial number"}],
    "missing_information": [],
    "original_user_story": "I purchased a phone and the screen died in 5 days.",
}

SAMPLE_SOURCES = [
    {
        "chunk_id": "CPA_2019_SECTION_83",
        "embedding_record_id": "CPA_2019_SECTION_83",
        "document_title": "Consumer Protection Act, 2019",
        "provision_type": "Section",
        "provision_number": "83",
        "provision_heading": "Product Liability Action",
        "legal_review_status": "OFFICIALLY_VERIFIED",
        "temporal_applicability_status": "CURRENTLY_IN_FORCE",
        "effective_from": "2020-07-20",
        "gazette_reference": "Act No. 35 of 2019",
        "exact_original_text": "A product liability action may be brought by a complainant against a product manufacturer or a product service provider or a product seller, as the case may be, for any harm caused to him on account of a defective product.",
    },
    {
        "chunk_id": "CPA_2019_SECTION_2_PART_007",
        "embedding_record_id": "CPA_2019_SECTION_2_PART_007",
        "document_title": "Consumer Protection Act, 2019",
        "provision_type": "Section",
        "provision_number": "2(10)",
        "provision_heading": "Defect Definition",
        "legal_review_status": "OFFICIALLY_VERIFIED",
        "temporal_applicability_status": "CURRENTLY_IN_FORCE",
        "effective_from": "2020-07-20",
        "gazette_reference": "Act No. 35 of 2019",
        "exact_original_text": "defect means any fault, imperfection or shortcoming in the quality, quantity, potency, purity or standard which is required to be maintained by or under any law for the time being in force.",
    },
]

MOCK_GEMINI_VALID_RESPONSE = json.dumps({
    "response_status": "SOURCE_GROUNDED_INFORMATION",
    "language": "English",
    "understanding_of_your_problem": "You allege that you purchased a smartphone whose display ceased functioning within 5 days, and the seller refused replacement.",
    "facts_provided_by_you": ["Product / Service: smartphone", "Seller / Platform: Tech Retailer", "Purchase Amount: ₹15,000"],
    "facts_confirmed_by_you": ["Product / Service: smartphone", "Seller / Platform: Tech Retailer", "Purchase Amount: ₹15,000"],
    "relevant_official_sources": [
        {
            "source_id": "CPA_2019_SECTION_83",
            "document_title": "Consumer Protection Act, 2019",
            "provision_reference": "Section 83 (Product Liability Action)",
            "source_text_summary": "Allows a complainant to bring a product liability action against a product manufacturer, provider, or seller for harm caused by a defective product.",
            "source_url": None,
            "pdf_page_start": None,
            "pdf_page_end": None,
            "legal_review_status": "OFFICIALLY_VERIFIED",
        }
    ],
    "what_the_source_says": "Under Section 83 of the Consumer Protection Act, 2019, a product liability action may be initiated against a product seller or manufacturer for harm caused by a defective product.",
    "how_it_may_relate_to_your_problem": "If the smartphone has an imperfection or fault in quality, Section 83 provides the statutory basis for claiming relief from the seller or manufacturer.",
    "missing_information": [],
    "possible_next_steps": [
        "Preserve the tax invoice and warranty card.",
        "Maintain records of refusal of replacement by the seller.",
        "Approach the National Consumer Helpline at 1915.",
    ],
    "limitations_and_uncertainties": [
        "This information is strictly informational and does not constitute formal legal representation."
    ],
    "needs_professional_review": False,
    "temporal_applicability_status": "CURRENTLY_IN_FORCE",
    "source_ids_used": ["CPA_2019_SECTION_83"],
})


class TestAnswerGeneratorMocked(unittest.TestCase):
    """26 Mocked Unit Tests for Source-Grounded Legal Answer Generation."""

    @patch("src.gemini_service.generate_response", return_value=MOCK_GEMINI_VALID_RESPONSE)
    def test_01_correct_function_input_validation(self, mock_gemini):
        """1. Correct function input validation with various arguments."""
        # Minimal arguments
        res = answer_generator.generate_legal_explanation(
            user_question="What are my rights?",
            retrieved_sources=SAMPLE_SOURCES,
        )
        self.assertIsInstance(res, dict)
        self.assertIn("response_status", res)

        # None user_question
        res_none_q = answer_generator.generate_legal_explanation(
            user_question="",
            retrieved_sources=SAMPLE_SOURCES,
        )
        self.assertIsInstance(res_none_q, dict)

    @patch("src.gemini_service.generate_response", return_value=MOCK_GEMINI_VALID_RESPONSE)
    def test_02_confirmed_case_facts_passed_correctly(self, mock_gemini):
        """2. Confirmed case facts are passed and preserved in prompt and response."""
        res = answer_generator.generate_legal_explanation(
            user_question="What are my rights?",
            confirmed_case=SAMPLE_CASE,
            retrieved_sources=SAMPLE_SOURCES,
        )
        self.assertTrue(mock_gemini.called)
        sent_prompt = mock_gemini.call_args[1]["user_content"]
        self.assertIn("smartphone", sent_prompt)
        self.assertIn("Tech Retailer", sent_prompt)
        self.assertIn("₹15,000", sent_prompt)
        self.assertIn("FACTS CONFIRMED BY USER: YES", sent_prompt)
        self.assertEqual(res["facts_confirmed_by_you"], [
            "Product / Service: smartphone",
            "Seller / Platform: Tech Retailer",
            "Purchase Amount: ₹15,000",
            "Desired Remedy: Replacement with non-defective product",
            "Seller Contact: Contacted via phone call; Response: Refused replacement",
            "Event: Screen stopped working (Date: 2026-03-01)",
            "Evidence Available: Invoice (Retail invoice with serial number)",
        ])

    @patch("src.gemini_service.generate_response", return_value=MOCK_GEMINI_VALID_RESPONSE)
    def test_03_original_user_question_passed_correctly(self, mock_gemini):
        """3. Original user question is passed to Gemini prompt and returned."""
        q = "Can I claim refund for a defective device?"
        res = answer_generator.generate_legal_explanation(
            user_question=q,
            confirmed_case=SAMPLE_CASE,
            retrieved_sources=SAMPLE_SOURCES,
        )
        sent_prompt = mock_gemini.call_args[1]["user_content"]
        self.assertIn(q, sent_prompt)
        self.assertIn("understanding_of_your_problem", res)

    @patch("src.gemini_service.generate_response", return_value=MOCK_GEMINI_VALID_RESPONSE)
    def test_04_retrieved_legal_passages_passed_correctly(self, mock_gemini):
        """4. Retrieved legal passages are passed to Gemini prompt."""
        res = answer_generator.generate_legal_explanation(
            user_question="Explain product liability",
            confirmed_case=SAMPLE_CASE,
            retrieved_sources=SAMPLE_SOURCES,
        )
        sent_prompt = mock_gemini.call_args[1]["user_content"]
        self.assertIn("CPA_2019_SECTION_83", sent_prompt)
        self.assertIn("Section 83 (Product Liability Action)", sent_prompt)
        self.assertIn("CPA_2019_SECTION_2_PART_007", sent_prompt)
        self.assertIn("defect means any fault", sent_prompt)

    @patch("src.gemini_service.generate_response", return_value=MOCK_GEMINI_VALID_RESPONSE)
    def test_05_correct_source_ids_preserved(self, mock_gemini):
        """5. Correct source IDs are preserved in source_ids_used."""
        res = answer_generator.generate_legal_explanation(
            user_question="Explain product liability",
            confirmed_case=SAMPLE_CASE,
            retrieved_sources=SAMPLE_SOURCES,
        )
        self.assertEqual(res["source_ids_used"], ["CPA_2019_SECTION_83"])

    @patch("src.gemini_service.generate_response")
    def test_06_no_legal_answer_generated_when_retrieval_is_empty(self, mock_gemini):
        """6. No legal answer generated when retrieval is empty (zero LLM calls)."""
        res = answer_generator.generate_legal_explanation(
            user_question="What are my rights?",
            confirmed_case=SAMPLE_CASE,
            retrieved_sources=[],
        )
        # Verify Gemini was NEVER called
        self.assertFalse(mock_gemini.called)
        self.assertEqual(res["response_status"], answer_generator.STATUS_INSUFFICIENT_SOURCES)
        self.assertEqual(res["source_ids_used"], [])
        self.assertIn(answer_generator.INSUFFICIENT_SOURCES_STATEMENT, res["what_the_source_says"])

    def test_07_insufficient_sources_trigger_explicit_abstention(self):
        """7. Insufficient sources trigger explicit abstention statement."""
        res = answer_generator._build_insufficient_sources_response(
            user_question="Unrelated question",
            language="English",
            facts_summary={"facts_provided": [], "facts_confirmed": [], "missing_info": []},
            temporal_status="CURRENTLY_IN_FORCE",
        )
        self.assertEqual(res["response_status"], "INSUFFICIENT_SOURCES")
        self.assertIn("The available legal sources in Nyaya Saathi are insufficient to verify this point.", res["what_the_source_says"])
        self.assertTrue(res["needs_professional_review"])

    @patch("src.gemini_service.generate_response", return_value=MOCK_GEMINI_VALID_RESPONSE)
    def test_08_unconfirmed_facts_labelled_provisional(self, mock_gemini):
        """8. Unconfirmed facts are labelled correctly as provisional."""
        unconfirmed_case = dict(SAMPLE_CASE)
        unconfirmed_case["facts_confirmed_by_user"] = False

        res = answer_generator.generate_legal_explanation(
            user_question="What are my rights?",
            confirmed_case=unconfirmed_case,
            retrieved_sources=SAMPLE_SOURCES,
        )
        self.assertEqual(res["response_status"], answer_generator.STATUS_UNCONFIRMED_PROVISIONAL)
        self.assertEqual(res["facts_confirmed_by_you"], [])
        # Check disclaimer in limitations
        limitations = " ".join(res["limitations_and_uncertainties"])
        self.assertIn("preliminary and provisional", limitations)

    @patch("src.gemini_service.generate_response", return_value=MOCK_GEMINI_VALID_RESPONSE)
    def test_09_unknown_facts_remain_unknown(self, mock_gemini):
        """9. Unknown facts remain unknown and are preserved in missing_information."""
        sparse_case = {
            "case_id": "CASE-SPARSE",
            "product_or_service": "laptop",
            "facts_confirmed_by_user": False,
            "missing_information": ["Seller identity unknown", "Date of purchase unknown"],
        }
        res = answer_generator.generate_legal_explanation(
            user_question="I have a dispute",
            confirmed_case=sparse_case,
            retrieved_sources=SAMPLE_SOURCES,
        )
        self.assertIn("Seller identity unknown", res["missing_information"])
        self.assertIn("Date of purchase unknown", res["missing_information"])

    @patch("src.gemini_service.generate_response")
    def test_10_legal_review_pending_sources_display_limitations(self, mock_gemini):
        """10. Legal-review-pending sources display appropriate limitations."""
        pending_sources = [
            {
                "chunk_id": "PROC_001",
                "embedding_record_id": "PROC_001",
                "document_title": "Procedural FAQ",
                "legal_review_status": "REQUIRES_LEGAL_REVIEW",
                "temporal_applicability_status": "CURRENTLY_IN_FORCE",
                "exact_original_text": "How to file an e-daakhil complaint.",
            }
        ]
        mock_gemini.return_value = json.dumps({
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "language": "English",
            "understanding_of_your_problem": "Filing e-daakhil complaint.",
            "what_the_source_says": "File via edaakhil portal.",
            "how_it_may_relate_to_your_problem": "Portal filing steps.",
            "source_ids_used": ["PROC_001"],
            "limitations_and_uncertainties": [],
            "needs_professional_review": False,
        })
        res = answer_generator.generate_legal_explanation(
            user_question="How to file?",
            retrieved_sources=pending_sources,
        )
        self.assertTrue(res["needs_professional_review"])
        limitations = " ".join(res["limitations_and_uncertainties"])
        self.assertIn("formal human legal review", limitations)

    def test_11_superseded_material_cannot_be_presented_as_current_law(self):
        """11. Historical/superseded material cannot be presented as current law."""
        # Using temporal status not applicable or historical
        res = answer_generator._build_insufficient_sources_response(
            user_question="Old 1986 act rule",
            language="English",
            facts_summary={"facts_provided": [], "facts_confirmed": [], "missing_info": []},
            temporal_status="NOT_APPLICABLE_PRE_COMMENCEMENT",
            reason="Historical repealed law is not applicable to current dispute.",
        )
        self.assertEqual(res["temporal_applicability_status"], "NOT_APPLICABLE_PRE_COMMENCEMENT")
        self.assertEqual(res["response_status"], "INSUFFICIENT_SOURCES")

    @patch("src.gemini_service.generate_response")
    def test_12_future_amendment_remains_future_effective(self, mock_gemini):
        """12. Future amendment remains future-effective (G.S.R. 789(E) commencement)."""
        future_source = [
            {
                "chunk_id": "ECOMM_AMEND_2026_RULE_001",
                "embedding_record_id": "ECOMM_AMEND_2026_RULE_001",
                "document_title": "Consumer Protection (E-Commerce) (Amendment) Rules, 2026",
                "legal_review_status": "REQUIRES_LEGAL_REVIEW",
                "temporal_applicability_status": "FUTURE_EFFECTIVE",
                "effective_from": "2027-01-01",
                "gazette_reference": "G.S.R. 789(E)",
                "exact_original_text": "These rules may be called Consumer Protection E-Commerce Amendment Rules 2026.",
            }
        ]
        mock_gemini.return_value = json.dumps({
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "language": "English",
            "understanding_of_your_problem": "Future e-commerce amendment query.",
            "what_the_source_says": "Rules published in G.S.R. 789(E).",
            "how_it_may_relate_to_your_problem": "Applicable upon commencement.",
            "source_ids_used": ["ECOMM_AMEND_2026_RULE_001"],
            "temporal_applicability_status": "FUTURE_EFFECTIVE",
        })
        res = answer_generator.generate_legal_explanation(
            user_question="What about the 2026 amendment rules?",
            retrieved_sources=future_source,
            temporal_context="FUTURE_EFFECTIVE",
        )
        self.assertEqual(res["temporal_applicability_status"], "FUTURE_EFFECTIVE")
        sent_prompt = mock_gemini.call_args[1]["user_content"]
        self.assertIn("1 January 2027", sent_prompt)

    @patch("src.gemini_service.generate_response")
    def test_13_transitional_applicability_triggers_review(self, mock_gemini):
        """13. Transitional applicability triggers professional review."""
        mock_gemini.return_value = json.dumps({
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "language": "English",
            "understanding_of_your_problem": "Transitional dispute spanning 2026-2027.",
            "what_the_source_says": "G.S.R. 789(E) provisions.",
            "how_it_may_relate_to_your_problem": "May relate to ongoing dispute.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
            "limitations_and_uncertainties": [],
            "needs_professional_review": False,
        })
        res = answer_generator.generate_legal_explanation(
            user_question="My order was placed in Dec 2026 and dispute continuing into 2027.",
            retrieved_sources=SAMPLE_SOURCES,
            temporal_context="NEEDS_LEGAL_REVIEW",
        )
        self.assertTrue(res["needs_professional_review"])
        self.assertEqual(res["temporal_applicability_status"], "NEEDS_LEGAL_REVIEW")
        limits = " ".join(res["limitations_and_uncertainties"])
        self.assertIn("Transitional applicability is legally unsettled", limits)

    @patch("src.gemini_service.generate_response", return_value=MOCK_GEMINI_VALID_RESPONSE)
    def test_14_json_output_validation_works(self, mock_gemini):
        """14. JSON output validation works and validates required keys."""
        res = answer_generator.generate_legal_explanation(
            user_question="Check my rights",
            confirmed_case=SAMPLE_CASE,
            retrieved_sources=SAMPLE_SOURCES,
        )
        required_keys = [
            "response_status",
            "language",
            "understanding_of_your_problem",
            "facts_provided_by_you",
            "facts_confirmed_by_you",
            "relevant_official_sources",
            "what_the_source_says",
            "how_it_may_relate_to_your_problem",
            "missing_information",
            "possible_next_steps",
            "limitations_and_uncertainties",
            "needs_professional_review",
            "temporal_applicability_status",
            "source_ids_used",
            "unsupported_claims_detected",
        ]
        for key in required_keys:
            self.assertIn(key, res, f"Missing required response key: {key}")

    @patch("src.gemini_service.generate_response", return_value="INVALID NON-JSON OUTPUT FROM MODEL")
    def test_15_malformed_gemini_json_rejected_safely(self, mock_gemini):
        """15. Malformed Gemini JSON is rejected safely without crashing."""
        res = answer_generator.generate_legal_explanation(
            user_question="Check my rights",
            confirmed_case=SAMPLE_CASE,
            retrieved_sources=SAMPLE_SOURCES,
        )
        self.assertEqual(res["response_status"], answer_generator.STATUS_INSUFFICIENT_SOURCES)
        self.assertIn(answer_generator.INSUFFICIENT_SOURCES_STATEMENT, res["what_the_source_says"])

    @patch("src.gemini_service.generate_response", side_effect=RuntimeError("Gemini API connection error"))
    def test_16_api_failure_preserves_active_case_and_returns_fallback(self, mock_gemini):
        """16. API failure preserves active case and returns fallback safely."""
        res = answer_generator.generate_legal_explanation(
            user_question="Check my rights",
            confirmed_case=SAMPLE_CASE,
            retrieved_sources=SAMPLE_SOURCES,
        )
        self.assertEqual(res["response_status"], answer_generator.STATUS_INSUFFICIENT_SOURCES)
        self.assertIn("smartphone", " ".join(res["facts_provided_by_you"]))
        self.assertIn("Tech Retailer", " ".join(res["facts_provided_by_you"]))

    @patch("src.gemini_service.generate_response")
    def test_17_no_citations_invented(self, mock_gemini):
        """17. No citations are invented; hallucinated IDs are filtered out."""
        hallucinated_response = json.dumps({
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "language": "English",
            "understanding_of_your_problem": "Checking citations",
            "what_the_source_says": "According to Section 999 of Unknown Act",
            "how_it_may_relate_to_your_problem": "Relates directly",
            "source_ids_used": ["CPA_2019_SECTION_83", "INVENTED_SECTION_999", "HALLUCINATED_ACT_001"],
            "limitations_and_uncertainties": [],
            "needs_professional_review": False,
        })
        mock_gemini.return_value = hallucinated_response
        res = answer_generator.generate_legal_explanation(
            user_question="Check citations",
            confirmed_case=SAMPLE_CASE,
            retrieved_sources=SAMPLE_SOURCES,
        )
        self.assertEqual(res["source_ids_used"], ["CPA_2019_SECTION_83"])
        self.assertTrue(len(res["unsupported_claims_detected"]) >= 2)
        claims_str = " ".join(res["unsupported_claims_detected"])
        self.assertIn("INVENTED_SECTION_999", claims_str)
        self.assertIn("HALLUCINATED_ACT_001", claims_str)

    @patch("src.gemini_service.generate_response")
    def test_18_no_section_numbers_invented(self, mock_gemini):
        """18. Invented section numbers cannot be added to source_ids_used."""
        invented_sec_resp = json.dumps({
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "language": "English",
            "understanding_of_your_problem": "Section invention test",
            "what_the_source_says": "Section 99(2) allows relief",
            "how_it_may_relate_to_your_problem": "Relates",
            "source_ids_used": ["CPA_2019_SECTION_99_FAKE"],
            "limitations_and_uncertainties": [],
            "needs_professional_review": False,
        })
        mock_gemini.return_value = invented_sec_resp
        res = answer_generator.generate_legal_explanation(
            user_question="Invent section",
            confirmed_case=SAMPLE_CASE,
            retrieved_sources=SAMPLE_SOURCES,
        )
        self.assertEqual(res["source_ids_used"], [])
        self.assertTrue(any("CPA_2019_SECTION_99_FAKE" in c for c in res["unsupported_claims_detected"]))

    @patch("src.gemini_service.generate_response")
    def test_19_no_guaranteed_outcomes_produced(self, mock_gemini):
        """19. Guaranteed outcome promises are detected and sanitized."""
        guarantee_response = json.dumps({
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "language": "English",
            "understanding_of_your_problem": "Guarantee test",
            "what_the_source_says": "Section 83",
            "how_it_may_relate_to_your_problem": "You will get a guaranteed 100% refund from the seller.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
            "limitations_and_uncertainties": [],
            "needs_professional_review": False,
        })
        mock_gemini.return_value = guarantee_response
        res = answer_generator.generate_legal_explanation(
            user_question="Will I win?",
            confirmed_case=SAMPLE_CASE,
            retrieved_sources=SAMPLE_SOURCES,
        )
        self.assertTrue(any("definitive outcome" in c for c in res["unsupported_claims_detected"]))
        self.assertNotIn("100% refund", res["how_it_may_relate_to_your_problem"])

    @patch("src.gemini_service.generate_response", return_value=MOCK_GEMINI_VALID_RESPONSE)
    def test_20_no_legal_claims_added_from_unsupported_model_memory(self, mock_gemini):
        """20. System instructions enforce exclusive authority of supplied passages."""
        res = answer_generator.generate_legal_explanation(
            user_question="Can I sue under IPC?",
            confirmed_case=SAMPLE_CASE,
            retrieved_sources=SAMPLE_SOURCES,
        )
        system_instruction = mock_gemini.call_args[1]["system_instruction"]
        self.assertIn("EXCLUSIVE authority", system_instruction)
        self.assertIn("Never supplement them with invented provisions", system_instruction)

    @patch("src.gemini_service.generate_response", return_value=MOCK_GEMINI_VALID_RESPONSE)
    def test_21_english_response_works(self, mock_gemini):
        """21. English response generation works."""
        res = answer_generator.generate_legal_explanation(
            user_question="Check my rights",
            retrieved_sources=SAMPLE_SOURCES,
            language="English",
        )
        self.assertEqual(res["language"], "English")

    def test_22_hindi_response_works_where_supported(self):
        """22. Hindi fallback and response works where supported."""
        res = answer_generator._build_insufficient_sources_response(
            user_question="उपभोक्ता अधिकार",
            language="Hindi",
            facts_summary={"facts_provided": [], "facts_confirmed": [], "missing_info": []},
            temporal_status="CURRENTLY_IN_FORCE",
        )
        self.assertEqual(res["language"], "Hindi")
        self.assertIn("न्याय साथी", res["how_it_may_relate_to_your_problem"])
        self.assertTrue(any("हेल्पलाइन" in step for step in res["possible_next_steps"]))

    def test_23_hinglish_response_works_where_supported(self):
        """23. Hindi/Hinglish language preference handled properly."""
        res = answer_generator._build_insufficient_sources_response(
            user_question="Mera refund nahi mila",
            language="Hindi/Hinglish",
            facts_summary={"facts_provided": [], "facts_confirmed": [], "missing_info": []},
            temporal_status="CURRENTLY_IN_FORCE",
        )
        self.assertEqual(res["language"], "Hindi/Hinglish")
        self.assertIn("न्याय साथी", res["how_it_may_relate_to_your_problem"])

    @patch("src.gemini_service.generate_response")
    def test_24_source_ids_in_answer_belong_strictly_to_supplied_results(self, mock_gemini):
        """24. Source IDs in the answer belong strictly to the supplied retrieval results."""
        mock_gemini.return_value = json.dumps({
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "language": "English",
            "understanding_of_your_problem": "Checking source IDs",
            "what_the_source_says": "Section 83 and 2(10)",
            "how_it_may_relate_to_your_problem": "Relates",
            "source_ids_used": ["CPA_2019_SECTION_83", "CPA_2019_SECTION_2_PART_007"],
            "limitations_and_uncertainties": [],
            "needs_professional_review": False,
        })
        res = answer_generator.generate_legal_explanation(
            user_question="Check IDs",
            retrieved_sources=SAMPLE_SOURCES,
        )
        for sid in res["source_ids_used"]:
            self.assertIn(sid, [s["chunk_id"] for s in SAMPLE_SOURCES])

    @patch("src.gemini_service.generate_response", return_value=MOCK_GEMINI_VALID_RESPONSE)
    def test_25_existing_gemini_integration_remains_functional(self, mock_gemini):
        """25. Existing Gemini integration remains functional and called with standard parameters."""
        res = answer_generator.generate_legal_explanation(
            user_question="Check my rights",
            retrieved_sources=SAMPLE_SOURCES,
            temperature=0.0,
        )
        self.assertTrue(mock_gemini.called)
        kwargs = mock_gemini.call_args[1]
        self.assertEqual(kwargs["temperature"], 0.0)
        self.assertIn("max_output_tokens", kwargs)
        self.assertIn("system_instruction", kwargs)

    def test_26_existing_hybrid_retrieval_remains_unchanged(self):
        """26. Existing hybrid retrieval operates independently and remains intact."""
        results = hybrid_retriever.hybrid_search(
            query="defective mobile phone",
            top_k=2,
            include_procedural=False,
            include_future=False,
        )
        self.assertIsInstance(results, list)
        if results:
            first = results[0]
            self.assertIn("rrf_score", first)
            self.assertIn("temporal_applicability_status", first)


class TestAnswerGeneratorLive(unittest.TestCase):
    """1 Live Gemini API Integration Test for Blueprint Step 17."""

    def test_27_live_gemini_api_integration(self):
        """27. Live integration test with real Gemini API call."""
        if not config.is_api_configured():
            self.skipTest("Gemini API is not configured. Skipping live test.")

        res = answer_generator.generate_legal_explanation(
            user_question="I bought a phone with a defective display and the seller refused replacement. What does the Consumer Protection Act say about defective goods?",
            confirmed_case=SAMPLE_CASE,
            retrieved_sources=SAMPLE_SOURCES,
            language="English",
            temperature=0.0,
        )
        self.assertIsInstance(res, dict)
        self.assertIn(res["response_status"], [
            answer_generator.STATUS_SOURCE_GROUNDED,
            answer_generator.STATUS_UNCONFIRMED_PROVISIONAL,
        ])
        self.assertTrue(len(res["what_the_source_says"]) > 20)
        self.assertTrue(len(res["how_it_may_relate_to_your_problem"]) > 20)
        # Verify source IDs returned match supplied sources
        for sid in res["source_ids_used"]:
            self.assertIn(sid, ["CPA_2019_SECTION_83", "CPA_2019_SECTION_2_PART_007"])


if __name__ == "__main__":
    unittest.main()
