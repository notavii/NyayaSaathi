"""
Comprehensive Unit and Integration Test Suite for Safety, Escalation, and Explicit Abstention.

Blueprint Step 19: Safety, Escalation, and Explicit Abstention.
Implements all 35 rigorous test specifications required by Blueprint Part I.
"""

from datetime import date
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import abstention
from src import answer_generator
from src import case_builder
from src import citation_checker
from src import safety_guard


SAMPLE_CASE = {
    "case_id": "CASE-TEST-SAFETY-001",
    "product_or_service": "smartphone",
    "seller_or_platform": "Tech Retailer",
    "purchase_amount": "₹15,000",
    "desired_resolution": "Replacement with non-defective product",
    "pending_question": "What is the name of the seller or platform where you purchased the smartphone?",
    "facts_confirmed_by_user": True,
    "events": [],
    "evidence": [],
    "missing_information": [],
    "conversation_history": [],
}

SAMPLE_RETRIEVED_SOURCES = [
    {
        "chunk_id": "CPA_2019_SECTION_83",
        "embedding_record_id": "CPA_2019_SECTION_83",
        "document_id": "CPA_2019",
        "document_title": "The Consumer Protection Act, 2019",
        "provision_type": "Section",
        "provision_number": "83",
        "provision_heading": "Product Liability Action",
        "legal_review_status": "REQUIRES_LEGAL_REVIEW",
        "applicability_status": "CURRENTLY_IN_FORCE",
        "effective_from": "2020-07-20",
        "exact_original_text": "83. A product liability action may be brought by a complainant against a product manufacturer or a product service provider or a product seller, as the case may be, for any harm caused to him on account of a defective product.",
    }
]


class TestSafetyGuard(unittest.TestCase):
    """35 Comprehensive Test Cases covering all Step 19 requirements."""

    def test_01_ordinary_missing_product_complaint(self):
        """1. Ordinary missing-product complaint is classified as NORMAL_CONSUMER_DISPUTE."""
        msg = "I ordered clothes on an online shopping portal 2 weeks ago and the package was never delivered."
        dec = safety_guard.evaluate_turn_safety(msg)
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_NORMAL_CONSUMER_DISPUTE)
        self.assertTrue(dec["allow_normal_legal_generation"])
        self.assertEqual(dec["risk_level"], safety_guard.RISK_LOW)

    def test_02_defective_product_without_immediate_danger(self):
        """2. Defective product without immediate danger is NORMAL_CONSUMER_DISPUTE."""
        msg = "I purchased a television and the display is showing vertical green lines. Seller refused replacement."
        dec = safety_guard.evaluate_turn_safety(msg)
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_NORMAL_CONSUMER_DISPUTE)
        self.assertTrue(dec["allow_normal_legal_generation"])

    def test_03_product_smoking_or_catching_fire(self):
        """3. Product smoking or catching fire triggers URGENT_ESCALATION with 112 guidance."""
        msg = "The mixer grinder started smoking, there is a burning smell and sparks are flying out."
        dec = safety_guard.evaluate_turn_safety(msg)
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_URGENT_ESCALATION)
        self.assertEqual(dec["risk_level"], safety_guard.RISK_CRITICAL)
        self.assertFalse(dec["allow_normal_legal_generation"])
        self.assertIn("112", dec["user_message"])
        self.assertIn("URGENT_FIRE_HAZARD", dec["reason_codes"])

    def test_04_immediate_physical_threat(self):
        """4. Immediate physical threat triggers URGENT_ESCALATION."""
        msg = "The seller sent three goons to my house who threatened to physically attack and kill me."
        dec = safety_guard.evaluate_turn_safety(msg)
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_URGENT_ESCALATION)
        self.assertEqual(dec["risk_level"], safety_guard.RISK_CRITICAL)
        self.assertIn("112", dec["user_message"])

    def test_05_ordinary_refund_delay_not_misclassified_as_emergency(self):
        """5. Ordinary refund delay must NOT be incorrectly classified as an emergency."""
        msg = "The seller promised to refund my ₹6,000 within 7 days, but it has been delayed for 45 days."
        dec = safety_guard.evaluate_turn_safety(msg)
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_NORMAL_CONSUMER_DISPUTE)
        self.assertNotEqual(dec["classification"], safety_guard.CATEGORY_URGENT_ESCALATION)
        self.assertTrue(dec["allow_normal_legal_generation"])

    def test_06_court_notice_received(self):
        """6. Receipt of court notice triggers HIGH_RISK_LEGAL_REVIEW."""
        msg = "I received a formal court notice from the district court regarding this merchant dispute."
        dec = safety_guard.evaluate_turn_safety(msg)
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_HIGH_RISK_LEGAL_REVIEW)
        self.assertEqual(dec["risk_level"], safety_guard.RISK_HIGH)
        self.assertTrue(dec["requires_human_review"])
        self.assertFalse(dec["allow_normal_legal_generation"])

    def test_07_imminent_legal_deadline(self):
        """7. Imminent legal/limitation deadline triggers HIGH_RISK_LEGAL_REVIEW."""
        msg = "The 30 days appeal deadline is expiring tomorrow and I must file immediately."
        dec = safety_guard.evaluate_turn_safety(msg)
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_HIGH_RISK_LEGAL_REVIEW)
        self.assertTrue(dec["requires_human_review"])

    def test_08_complex_transitional_law_question(self):
        """8. Complex transitional-law question triggers HIGH_RISK_LEGAL_REVIEW."""
        msg = "My purchase was before the commencement date and dispute continues after, is the amendment retrospective?"
        dec = safety_guard.evaluate_turn_safety(msg)
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_HIGH_RISK_LEGAL_REVIEW)

    def test_09_non_consumer_relationship_question(self):
        """9. Non-consumer relationship question triggers OUTSIDE_SCOPE."""
        msg = "How do I talk to my boyfriend about our relationship issues?"
        dec = safety_guard.evaluate_turn_safety(msg)
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_OUTSIDE_SCOPE)
        self.assertFalse(dec["allow_normal_legal_generation"])

    def test_10_unrelated_coding_question(self):
        """10. Unrelated coding question triggers OUTSIDE_SCOPE."""
        msg = "Can you write a Python code for binary search tree traversal?"
        dec = safety_guard.evaluate_turn_safety(msg)
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_OUTSIDE_SCOPE)
        self.assertFalse(dec["allow_normal_legal_generation"])

    def test_11_ambiguous_initial_message(self):
        """11. Ambiguous initial message triggers NEEDS_CLARIFICATION."""
        msg = "I need legal help with a problem."
        dec = safety_guard.evaluate_turn_safety(msg)
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_NEEDS_CLARIFICATION)
        self.assertIn("👉", dec["user_message"])

    def test_12_followup_introducing_emergency_into_ordinary_case(self):
        """12. Follow-up message introducing an emergency into an ordinary case escalates immediately."""
        active_case = dict(SAMPLE_CASE)
        # Turn 2: User says the appliance caught fire
        followup_msg = "The laptop charger exploded and caught fire while plugged in!"
        dec = safety_guard.evaluate_turn_safety(followup_msg, active_case=active_case)
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_URGENT_ESCALATION)
        self.assertFalse(dec["allow_normal_legal_generation"])
        self.assertIn("112", dec["user_message"])

    def test_13_followup_introducing_high_risk_legal_issue(self):
        """13. Follow-up message introducing a high-risk issue triggers HIGH_RISK_LEGAL_REVIEW."""
        active_case = dict(SAMPLE_CASE)
        followup_msg = "The seller has now served me a legal notice from advocate threatening court proceedings."
        dec = safety_guard.evaluate_turn_safety(followup_msg, active_case=active_case)
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_HIGH_RISK_LEGAL_REVIEW)
        self.assertTrue(dec["requires_human_review"])

    def test_14_empty_legal_retrieval_result(self):
        """14. Empty legal retrieval triggers explicit abstention."""
        gen_answer = {"what_the_source_says": "Something", "how_it_may_relate_to_your_problem": "Relates"}
        val_rep = {"overall_status": "VALIDATED", "citations": [], "unsupported_references": []}
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            retrieved_sources=[],  # Empty retrieval
        )
        self.assertEqual(gate["gate_status"], safety_guard.GATE_ABSTENTION_REQUIRED)
        self.assertIn(safety_guard.STANDARD_ABSTENTION_STATEMENT, gate["user_facing_response"])

    def test_15_relevant_source_exists_but_was_not_retrieved(self):
        """15. Citing a source not retrieved in allowlist triggers unretrieved citation failure."""
        gen_answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CP_ECOMMERCE_RULES_2020_RULE_4",
                    "document_title": "Consumer Protection (E-Commerce) Rules, 2020",
                    "provision_reference": "Rule 4",
                }
            ],
            "what_the_source_says": "Rule 4 requirements.",
            "source_ids_used": ["CP_ECOMMERCE_RULES_2020_RULE_4"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            retrieved_sources=SAMPLE_RETRIEVED_SOURCES,
        )
        self.assertEqual(gate["gate_status"], safety_guard.GATE_UNSAFE_BLOCKED)

    def test_16_invented_source_id(self):
        """16. Invented source ID is blocked by safety gate."""
        gen_answer = {
            "relevant_official_sources": [
                {"source_id": "FAKE_SOURCE_ID_999", "document_title": "Fake Act", "provision_reference": "Section 999"}
            ],
            "what_the_source_says": "Fake rules.",
            "source_ids_used": ["FAKE_SOURCE_ID_999"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            retrieved_sources=SAMPLE_RETRIEVED_SOURCES,
        )
        self.assertEqual(gate["gate_status"], safety_guard.GATE_UNSAFE_BLOCKED)

    def test_17_non_existent_statutory_provision(self):
        """17. Non-existent statutory provision reference is blocked by safety gate."""
        gen_answer = {
            "relevant_official_sources": [
                {"source_id": "CPA_2019_SECTION_83", "document_title": "The Consumer Protection Act, 2019", "provision_reference": "Section 888"}
            ],
            "what_the_source_says": "Section 888 text.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            retrieved_sources=SAMPLE_RETRIEVED_SOURCES,
        )
        self.assertEqual(gate["gate_status"], safety_guard.GATE_UNSAFE_BLOCKED)

    def test_18_wrong_act_or_rule_attribution(self):
        """18. Attributing a provision to the wrong Act is blocked by safety gate."""
        gen_answer = {
            "relevant_official_sources": [
                {"source_id": "CPA_2019_SECTION_83", "document_title": "Consumer Protection (E-Commerce) Rules, 2020", "provision_reference": "Section 83"}
            ],
            "what_the_source_says": "Section 83 in E-Commerce Rules.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            retrieved_sources=SAMPLE_RETRIEVED_SOURCES,
        )
        self.assertEqual(gate["gate_status"], safety_guard.GATE_UNSAFE_BLOCKED)

    def test_19_unsupported_legal_claim(self):
        """19. Unsupported high-impact legal claims are detected and flagged."""
        gen_answer = {
            "relevant_official_sources": [
                {"source_id": "CPA_2019_SECTION_83", "document_title": "The Consumer Protection Act, 2019", "provision_reference": "Section 83"}
            ],
            "what_the_source_says": "Section 83 allows product liability.",
            "how_it_may_relate_to_your_problem": "Under Section 83, the police must arrest the CEO immediately for non-bailable imprisonment.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertTrue(len(val_rep["unsupported_claims"]) > 0 or any(c["support_status"] != "SUPPORTED_BY_PASSAGE" for c in val_rep["claims"]))

    def test_20_claim_with_text_overlap_does_not_equal_legal_verification(self):
        """20. Textual overlap does NOT produce a 'Legally Verified' label."""
        gen_answer = {
            "relevant_official_sources": [
                {"source_id": "CPA_2019_SECTION_83", "document_title": "The Consumer Protection Act, 2019", "provision_reference": "Section 83"}
            ],
            "what_the_source_says": "Section 83 product liability may be brought for defective goods.",
            "how_it_may_relate_to_your_problem": "You may potentially seek relief under Section 83.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            retrieved_sources=SAMPLE_RETRIEVED_SOURCES,
        )
        # Verify "Legally Verified" is NEVER in user response
        self.assertNotIn("Legally Verified", gate["user_facing_response"])
        self.assertNotIn("Legally Verified", json.dumps(gate["safe_structured_answer"]))

    def test_21_historical_source_used_as_current_law(self):
        """21. Historical source cannot be presented as current operative law."""
        gen_answer = {
            "relevant_official_sources": [
                {"source_id": "CONSUMER_HANDBOOK_2015_PAGE_2", "document_title": "Consumer Handbook (2015)", "provision_reference": "Guidance 1"}
            ],
            "what_the_source_says": "District Forum limits under 1986 Act.",
            "source_ids_used": ["CONSUMER_HANDBOOK_2015_PAGE_2"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertTrue(any("HISTORICAL_REFERENCE" in w for w in val_rep["warnings"]))

    def test_22_future_effective_amendment_presented_as_current_law(self):
        """22. Future-effective amendment (G.S.R. 789(E)) receives commencement notice before 2027-01-01."""
        gen_answer = {
            "relevant_official_sources": [
                {"source_id": "CP_ECOMMERCE_AMENDMENT_2026_ITEM_1", "document_title": "Consumer Protection (E-Commerce) (Amendment) Rules, 2026", "provision_reference": "Rule 1"}
            ],
            "what_the_source_says": "Rule 1 commencement details.",
            "source_ids_used": ["CP_ECOMMERCE_AMENDMENT_2026_ITEM_1"],
        }
        sources = [
            {
                "chunk_id": "CP_ECOMMERCE_AMENDMENT_2026_ITEM_1",
                "document_id": "CP_ECOMMERCE_AMENDMENT_2026",
                "document_title": "Consumer Protection (E-Commerce) (Amendment) Rules, 2026",
                "provision_number": "1",
                "legal_review_status": "REQUIRES_LEGAL_REVIEW",
                "applicability_status": "FUTURE_EFFECTIVE",
                "effective_from": "2027-01-01",
                "exact_original_text": "These rules may be called E-Commerce Amendment Rules 2026. Come into force 1 Jan 2027.",
            }
        ]
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=sources, as_of_date="2026-11-08")
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            retrieved_sources=sources,
        )
        self.assertTrue(any("2027-01-01" in lim for lim in gate["limitations_and_disclaimers"]))

    def test_23_pre_commencement_transaction_with_post_commencement_dispute(self):
        """23. Pre-commencement transaction with ongoing post-commencement dispute triggers transitional review."""
        gen_answer = {
            "relevant_official_sources": [
                {"source_id": "CP_ECOMMERCE_AMENDMENT_2026_ITEM_1", "document_title": "Consumer Protection (E-Commerce) (Amendment) Rules, 2026", "provision_reference": "Rule 1"}
            ],
            "what_the_source_says": "Transitional rules applied.",
            "source_ids_used": ["CP_ECOMMERCE_AMENDMENT_2026_ITEM_1"],
        }
        val_rep = citation_checker.validate_legal_answer(
            gen_answer,
            retrieved_sources=SAMPLE_RETRIEVED_SOURCES,
            transaction_date="2026-11-01",
            event_date="2027-02-01",
        )
        self.assertTrue(val_rep["requires_professional_review"])

    def test_24_unconfirmed_facts_used_in_legal_conclusion(self):
        """24. Unconfirmed facts enforce provisional explanation in final gate."""
        unconfirmed_case = dict(SAMPLE_CASE)
        unconfirmed_case["facts_confirmed_by_user"] = False

        gen_answer = {
            "relevant_official_sources": [
                {"source_id": "CPA_2019_SECTION_83", "document_title": "The Consumer Protection Act, 2019", "provision_reference": "Section 83"}
            ],
            "what_the_source_says": "Section 83 product liability text.",
            "how_it_may_relate_to_your_problem": "Section 83 may apply.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            case=unconfirmed_case,
            retrieved_sources=SAMPLE_RETRIEVED_SOURCES,
        )
        self.assertIn("UNCONFIRMED_FACTS_PROVISIONAL", gate["gate_reason_codes"])
        self.assertTrue(any("PROVISIONAL" in lim for lim in gate["limitations_and_disclaimers"]))

    def test_25_new_grievance_does_not_inherit_previous_case_risk_flags(self):
        """25. Creating a new grievance completely resets and does NOT inherit old risk flags."""
        # Case 1 had urgent smoking issue
        case1 = case_builder.create_empty_case(
            issue_category="Defective or damaged goods",
            original_user_story="Appliance smoking and burning smell",
        )
        case1["safety_flags"] = ["IMMEDIATE_DANGER"]

        # User starts New Grievance
        case2 = case_builder.create_empty_case(
            issue_category="Refund or replacement refusal",
            original_user_story="I bought a book and was billed twice.",
        )
        # Verify isolation: Case 2 is clean
        self.assertEqual(case2["safety_flags"], [])
        self.assertNotEqual(case2["case_id"], case1["case_id"])
        self.assertFalse(case2["facts_confirmed_by_user"])

    def test_26_safe_answer_passes_through_final_validation_gate(self):
        """26. Safe, well-sourced answer passes through final validation gate."""
        gen_answer = {
            "relevant_official_sources": [
                {"source_id": "CPA_2019_SECTION_83", "document_title": "The Consumer Protection Act, 2019", "provision_reference": "Section 83"}
            ],
            "what_the_source_says": "Section 83 provides product liability actions against sellers for defective products.",
            "how_it_may_relate_to_your_problem": "You may potentially seek remedies if the smartphone is defective.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
            "limitations_and_uncertainties": ["Informational assistance only."],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            case=SAMPLE_CASE,
            retrieved_sources=SAMPLE_RETRIEVED_SOURCES,
        )
        self.assertEqual(gate["gate_status"], safety_guard.GATE_PASSED)
        self.assertTrue(gate["allow_delivery"])
        self.assertIn("Official Legal Information", gate["user_facing_response"])

    def test_27_unsafe_answer_blocked_before_being_shown_to_user(self):
        """27. Unsafe answer with invented sources is blocked by gate before delivery."""
        gen_answer = {
            "relevant_official_sources": [
                {"source_id": "INVENTED_999", "document_title": "Fake Law", "provision_reference": "Section 999"}
            ],
            "what_the_source_says": "Fake rules.",
            "source_ids_used": ["INVENTED_999"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            case=SAMPLE_CASE,
            retrieved_sources=SAMPLE_RETRIEVED_SOURCES,
        )
        self.assertEqual(gate["gate_status"], safety_guard.GATE_UNSAFE_BLOCKED)
        # Raw unsafe response is suppressed and safe abstention message shown
        self.assertIn(safety_guard.STANDARD_ABSTENTION_STATEMENT, gate["user_facing_response"])

    def test_28_gemini_failure_produces_safe_fallback(self):
        """28. API or generation failure produces safe abstention response without crashing."""
        resp = abstention.build_explicit_abstention_response(
            reason_code="API_ERROR_FALLBACK",
            specific_details="Service temporarily unavailable.",
            language="English",
        )
        self.assertEqual(resp["response_status"], "EXPLICIT_ABSTENTION")
        self.assertIn(safety_guard.STANDARD_ABSTENTION_STATEMENT, resp["what_the_source_says"])
        self.assertTrue(resp["needs_professional_review"])

    def test_29_hindi_urgent_message_detected(self):
        """29. Hindi urgent message is detected and outputs Hindi 112 guidance."""
        msg = "उपकरण में बहुत ज्यादा धुआं निकल रहा है और आग लग गई है"
        dec = safety_guard.evaluate_turn_safety(msg, language="Hindi")
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_URGENT_ESCALATION)
        self.assertIn("112", dec["user_message"])
        self.assertIn("आपातकालीन", dec["user_message"])

    def test_30_hinglish_urgent_message_detected(self):
        """30. Hinglish urgent message is detected properly."""
        msg = "Appliance me aag lag gayi hai aur current mar raha hai"
        dec = safety_guard.evaluate_turn_safety(msg, language="Hindi/Hinglish")
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_URGENT_ESCALATION)
        self.assertIn("112", dec["user_message"])

    def test_31_normal_followup_not_repeatedly_flagged_as_clarification(self):
        """31. Normal follow-up answering active question is NOT flagged as needing clarification."""
        active_case = dict(SAMPLE_CASE)
        active_case["pending_question"] = "What was the purchase amount?"
        followup_msg = "₹15,000"
        dec = safety_guard.evaluate_turn_safety(followup_msg, active_case=active_case)
        self.assertEqual(dec["classification"], safety_guard.CATEGORY_NORMAL_CONSUMER_DISPUTE)
        self.assertTrue(dec["allow_normal_legal_generation"])

    def test_32_existing_active_grievance_continuity_remains_intact(self):
        """32. Active grievance continuity is preserved across sequential messages."""
        case = case_builder.create_empty_case(issue_category="Defective or damaged goods", original_user_story="Ordered a laptop")
        case_builder.extract_case_facts_deterministically(case, "Ordered a laptop for ₹45,000")
        case_builder.compute_missing_information(case)
        self.assertEqual(case["product_or_service"], "laptop")
        self.assertEqual(case["purchase_amount"], "₹45,000")

    def test_33_existing_new_grievance_isolation_remains_intact(self):
        """33. New Grievance reset isolates state and case ID cleanly."""
        case1 = case_builder.create_empty_case(issue_category="Defective goods", original_user_story="Laptop broke")
        case2 = case_builder.create_empty_case(issue_category="Wrong product", original_user_story="Ordered soap, got brick")
        self.assertNotEqual(case1["case_id"], case2["case_id"])
        self.assertNotEqual(case1["original_user_story"], case2["original_user_story"])

    def test_34_safety_check_executes_on_every_turn_not_just_first(self):
        """34. Turn-by-turn safety check is applied sequentially across multiple turns."""
        turns = [
            ("I ordered a refrigerator online.", safety_guard.CATEGORY_NORMAL_CONSUMER_DISPUTE),
            ("The delivery was 3 days late.", safety_guard.CATEGORY_NORMAL_CONSUMER_DISPUTE),
            ("Now the compressor is smoking and sparks are flying!", safety_guard.CATEGORY_URGENT_ESCALATION),
        ]
        case = dict(SAMPLE_CASE)
        for text, expected_cat in turns:
            dec = safety_guard.evaluate_turn_safety(text, active_case=case)
            self.assertEqual(dec["classification"], expected_cat)

    def test_35_citation_checking_result_does_not_produce_legally_verified_label(self):
        """35. Verification result NEVER generates a 'Legally Verified' label."""
        gen_answer = {
            "relevant_official_sources": [
                {"source_id": "CPA_2019_SECTION_83", "document_title": "The Consumer Protection Act, 2019", "provision_reference": "Section 83"}
            ],
            "what_the_source_says": "Section 83 product liability text.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            retrieved_sources=SAMPLE_RETRIEVED_SOURCES,
        )
        full_json = json.dumps(gate)
        self.assertNotIn("Legally Verified", full_json)
        self.assertNotIn("Legally Verified", gate["user_facing_response"])


if __name__ == "__main__":
    unittest.main()
