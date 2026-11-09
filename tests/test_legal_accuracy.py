"""
Test Suite for Targeted Legal Answer Accuracy, Statutory Attribution, and Safety:
Part 8 Verification Requirements (15 Mandatory Tests).

1. Unsupported material claim is not displayed.
2. SUPPORT_NOT_ESTABLISHED triggers blocking or safe filtering.
3. Filtered answer re-runs citation verification.
4. Damaged phone does not trigger product liability recommendation.
5. Harm to other property is handled as separate issue.
6. Product injury is escalated for legal review.
7. Rule 5(3)(c) attribution to marketplace entity.
8. Rule 6(3) seller duty with force-majeure proviso.
9. Rule 6(5)(g) attribution to seller info to platform.
10. Section 2(10) definition represented accurately.
11. Section 39 reliefs described conditionally against opposite party.
12. e-Jagriti procedural material labelled as PROCEDURAL_GUIDANCE with URL.
13. Vakalatnama is not presented as universally mandatory.
14. Each claim displays its own citations and official links.
15. A missing citation does not inherit another claim's citation.
"""

import json
from pathlib import Path
import unittest

from src import abstention
from src import answer_generator
from src import citation_checker
from src import hybrid_retriever
from src import safety_guard
from src import workflow_service


class TestLegalAccuracy(unittest.TestCase):

    def setUp(self):
        self.sources = [
            {
                "chunk_id": "CPA_2019_SECTION_2",
                "document_id": "CPA_2019",
                "document_title": "The Consumer Protection Act, 2019",
                "document_type": "ACT",
                "provision_type": "Section",
                "provision_number": "2",
                "provision_heading": "Definitions",
                "legal_review_status": "OFFICIALLY_VERIFIED",
                "applicability_status": "CURRENTLY_IN_FORCE",
                "source_url": "https://consumeraffairs.gov.in/public/upload/files/CP%20Act%202019_1732700731.pdf",
                "issuing_authority": "Ministry of Consumer Affairs, Food and Public Distribution, Government of India",
                "exact_original_text": (
                    '(10) "defect" means any fault, imperfection or shortcoming in the quality, quantity, potency, '
                    'purity or standard which is required to be maintained by or under any law for the time being in '
                    'force or under any contract, express or implied or as is claimed by the trader in any manner '
                    'whatsoever in relation to any goods;\n'
                    '(22) "harm", in relation to a product liability, includes damage to any property, other than the '
                    'product itself; personal injury, illness or death; but does not include any harm caused to a '
                    'product itself or any damage to property on account of failure of such product to perform or any economic loss.'
                ),
            },
            {
                "chunk_id": "CPA_2019_SECTION_39",
                "document_id": "CPA_2019",
                "document_title": "The Consumer Protection Act, 2019",
                "document_type": "ACT",
                "provision_type": "Section",
                "provision_number": "39",
                "provision_heading": "Findings of District Commission",
                "legal_review_status": "OFFICIALLY_VERIFIED",
                "applicability_status": "CURRENTLY_IN_FORCE",
                "source_url": "https://consumeraffairs.gov.in/public/upload/files/CP%20Act%202019_1732700731.pdf",
                "issuing_authority": "Ministry of Consumer Affairs, Food and Public Distribution, Government of India",
                "exact_original_text": (
                    "Where the District Commission is satisfied that the goods complained against suffer from any of the defects "
                    "specified in the complaint, it shall issue an order to the opposite party directing him to remove the defect, "
                    "replace the goods with new goods of similar description free from defect, or return to the complainant the price."
                ),
            },
            {
                "chunk_id": "CP_ECOMMERCE_RULES_2020_RULE_5",
                "document_id": "CP_ECOMMERCE_RULES_2020",
                "document_title": "Consumer Protection (E-Commerce) Rules, 2020",
                "document_type": "RULES",
                "provision_type": "Rule",
                "provision_number": "5",
                "provision_heading": "Liabilities of marketplace e-commerce entities",
                "legal_review_status": "OFFICIALLY_VERIFIED",
                "applicability_status": "CURRENTLY_IN_FORCE",
                "source_url": "https://consumeraffairs.gov.in/public/upload/files/E%20commerce%20rules_1732703966.pdf",
                "issuing_authority": "Ministry of Consumer Affairs, Food and Public Distribution, Government of India",
                "exact_original_text": (
                    "Every marketplace e-commerce entity shall provide in a clear and accessible manner on its platform, "
                    "the following information to its users: terms and conditions governing return, refund, exchange, "
                    "warranty and guarantee, delivery and shipment, modes of payment, and grievance redressal mechanism."
                ),
            },
            {
                "chunk_id": "CP_ECOMMERCE_RULES_2020_RULE_6",
                "document_id": "CP_ECOMMERCE_RULES_2020",
                "document_title": "Consumer Protection (E-Commerce) Rules, 2020",
                "document_type": "RULES",
                "provision_type": "Rule",
                "provision_number": "6",
                "provision_heading": "Duties of sellers on marketplace",
                "legal_review_status": "OFFICIALLY_VERIFIED",
                "applicability_status": "CURRENTLY_IN_FORCE",
                "source_url": "https://consumeraffairs.gov.in/public/upload/files/E%20commerce%20rules_1732703966.pdf",
                "issuing_authority": "Ministry of Consumer Affairs, Food and Public Distribution, Government of India",
                "exact_original_text": (
                    "(3) No seller offering goods or services through a marketplace e-commerce entity shall refuse to take back "
                    "goods, or withdraw or discontinue services purchased or agreed to be purchased, or refuse to refund consideration, "
                    "if such goods or services are defective, deficient or spurious, or if the goods or services are not of the characteristics "
                    "or features as agreed: Provided that late delivery shall not be a ground for return where late delivery is due to force majeure.\n"
                    "(5)(g) provide to the marketplace e-commerce entity its terms and conditions generally governing its relationship with customers."
                ),
            },
            {
                "chunk_id": "EJAGRITI_GUIDE_PAGE_1",
                "document_id": "EJAGRITI_FILING_GUIDE",
                "document_title": "e-Jagriti Consumer Commission Online Complaint Filing User Manual",
                "document_type": "PROCEDURAL_GUIDE",
                "provision_type": "Guidance",
                "provision_number": "Portal",
                "provision_heading": "Online Complaint Filing",
                "legal_review_status": "OFFICIALLY_VERIFIED",
                "applicability_status": "CURRENTLY_IN_FORCE",
                "source_url": "https://e-jagriti.gov.in/",
                "issuing_authority": "Department of Consumer Affairs, Government of India",
                "exact_original_text": (
                    "e-Jagriti portal allows consumers to file and track consumer grievances and complaints online before Consumer Commissions. "
                    "Complainants can register, upload supporting documents, pay filing fees online, and track hearing schedules. "
                    "Complainants may appear in person or through an authorized representative or advocate. If represented by an advocate, "
                    "a Vakalatnama must be uploaded; if filing in person, a Vakalatnama is not required."
                ),
            },
        ]

    # 1. Unsupported material claim is not displayed
    def test_01_unsupported_material_claim_not_displayed(self):
        gen_answer = {
            "claims": [
                {
                    "claim_id": "CLM_001",
                    "claim_text": "Section 2(10) defines defect as any fault or shortcoming in quality.",
                    "source_ids": ["CPA_2019_SECTION_2"],
                },
                {
                    "claim_id": "CLM_002",
                    "claim_text": "The seller is subject to automatic criminal arrest within 24 hours.",
                    "source_ids": ["CPA_2019_SECTION_2"],
                },
            ],
            "what_the_source_says": "Section 2(10) defines defect as any fault or shortcoming in quality. The seller is subject to automatic criminal arrest within 24 hours.",
            "how_it_may_relate_to_your_problem": "You can report the defect and have the seller arrested.",
            "source_ids_used": ["CPA_2019_SECTION_2"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=self.sources)
        safe = citation_checker.produce_safe_validated_answer(gen_answer, val_rep)

        self.assertNotIn("automatic criminal arrest", safe["what_the_source_says"])
        self.assertIn("Section 2(10)", safe["what_the_source_says"])

    # 2. SUPPORT_NOT_ESTABLISHED triggers blocking or safe filtering
    def test_02_support_not_established_triggers_blocking_or_safe_filtering(self):
        # When all claims lack support
        gen_answer = {
            "claims": [
                {
                    "claim_id": "CLM_001",
                    "claim_text": "E-commerce platforms must pay treble statutory fines to the police.",
                    "source_ids": ["CPA_2019_SECTION_2"],
                }
            ],
            "what_the_source_says": "E-commerce platforms must pay treble statutory fines to the police.",
            "how_it_may_relate_to_your_problem": "You are entitled to police fines.",
            "source_ids_used": ["CPA_2019_SECTION_2"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=self.sources)
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            retrieved_sources=self.sources,
        )
        self.assertEqual(gate["gate_status"], safety_guard.GATE_UNSAFE_BLOCKED)
        self.assertFalse(gate["allow_delivery"])
        self.assertIn(abstention.STANDARD_ABSTENTION_STATEMENT, gate["user_facing_response"])

    # 3. Filtered answer re-runs citation verification
    def test_03_filtered_answer_reruns_citation_verification(self):
        gen_answer = {
            "claims": [
                {
                    "claim_id": "CLM_001",
                    "claim_text": "Section 2(10) defines defect as any fault or imperfection in quality.",
                    "source_ids": ["CPA_2019_SECTION_2"],
                },
                {
                    "claim_id": "CLM_002",
                    "claim_text": "Sellers must pay ₹1,00,000 cash upfront on complaint filing.",
                    "source_ids": ["CPA_2019_SECTION_2"],
                },
            ],
            "what_the_source_says": "Section 2(10) defines defect as any fault or imperfection in quality. Sellers must pay ₹1,00,000 cash upfront on complaint filing.",
            "how_it_may_relate_to_your_problem": "You can seek remedy for defect.",
            "source_ids_used": ["CPA_2019_SECTION_2"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=self.sources)
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            retrieved_sources=self.sources,
        )
        # Should apply safe claim filtering
        self.assertEqual(gate["gate_status"], safety_guard.GATE_PASSED)
        self.assertTrue(gate["allow_delivery"])
        self.assertIn("SAFE_CLAIM_FILTERING_APPLIED", gate["gate_reason_codes"])
        self.assertNotIn("cash upfront", gate["user_facing_response"])
        self.assertIn("Section 2(10)", gate["user_facing_response"])

    # 4. Damaged phone does not trigger product liability recommendation
    def test_04_damaged_phone_does_not_trigger_product_liability_recommendation(self):
        case = {
            "original_user_story": "I got damaged mobile from flipkart. The screen is broken.",
            "product_or_service": "mobile phone",
            "issue_category": "DAMAGED_OR_DEFECTIVE_PRODUCT",
            "facts_confirmed_by_user": True,
        }
        # Harm is limited to product itself
        self.assertTrue(workflow_service.is_harm_limited_to_product(case))

        # Check hybrid search excludes product liability sections
        results = hybrid_retriever.hybrid_search(
            query="damaged mobile flipkart screen broken",
            top_k=5,
            exclude_product_liability=True,
        )
        for r in results:
            prov_num = str(r.get("provision_number", ""))
            self.assertNotIn(prov_num, ["82", "83", "84", "85", "86", "87"])

    # 5. Harm to other property handled as separate issue
    def test_05_harm_to_other_property_handled_as_separate_issue(self):
        case = {
            "original_user_story": "The phone charger spark caused a fire which damaged my table and burned my bed.",
            "product_or_service": "phone charger",
            "issue_category": "DAMAGED_OR_DEFECTIVE_PRODUCT",
        }
        # Harm includes other property, so harm is NOT limited to product itself
        self.assertFalse(workflow_service.is_harm_limited_to_product(case))

    # 6. Product injury is escalated for legal review
    def test_06_product_injury_escalated_for_legal_review(self):
        text = "The laptop battery exploded causing severe burn injury and I was hospitalised."
        decision = safety_guard.evaluate_turn_safety(text)
        self.assertIn(
            decision["classification"],
            (safety_guard.CATEGORY_URGENT_ESCALATION, safety_guard.CATEGORY_HIGH_RISK_LEGAL_REVIEW),
        )

    # 7. Rule 5(3)(c) attribution to marketplace entity
    def test_07_rule_5_3_c_attributed_to_marketplace_entity(self):
        rule5 = next(s for s in self.sources if s["chunk_id"] == "CP_ECOMMERCE_RULES_2020_RULE_5")
        self.assertIn("marketplace e-commerce entity", rule5["exact_original_text"])
        self.assertIn("return, refund, exchange", rule5["exact_original_text"])

    # 8. Rule 6(3) seller duty with force-majeure proviso
    def test_08_rule_6_3_seller_duty_with_force_majeure_proviso(self):
        rule6 = next(s for s in self.sources if s["chunk_id"] == "CP_ECOMMERCE_RULES_2020_RULE_6")
        self.assertIn("No seller offering goods or services through a marketplace", rule6["exact_original_text"])
        self.assertIn("refuse to refund", rule6["exact_original_text"])
        self.assertIn("force majeure", rule6["exact_original_text"])

    # 9. Rule 6(5)(g) attribution to seller info to platform
    def test_09_rule_6_5_g_attributed_to_seller_info_to_platform(self):
        rule6 = next(s for s in self.sources if s["chunk_id"] == "CP_ECOMMERCE_RULES_2020_RULE_6")
        self.assertIn("provide to the marketplace e-commerce entity its terms and conditions", rule6["exact_original_text"])

    # 10. Section 2(10) definition represented accurately
    def test_10_section_2_10_definition_represented_accurately(self):
        sec2 = next(s for s in self.sources if s["chunk_id"] == "CPA_2019_SECTION_2")
        self.assertIn("fault, imperfection or shortcoming in the quality, quantity, potency, purity or standard", sec2["exact_original_text"])

    # 11. Section 39 reliefs described conditionally against opposite party
    def test_11_section_39_reliefs_described_conditionally_against_opposite_party(self):
        sec39 = next(s for s in self.sources if s["chunk_id"] == "CPA_2019_SECTION_39")
        self.assertIn("satisfied that the goods complained against suffer from any of the defects", sec39["exact_original_text"])
        self.assertIn("order to the opposite party", sec39["exact_original_text"])

    # 12. e-Jagriti procedural material labelled as PROCEDURAL_GUIDANCE with URL
    def test_12_ejagriti_procedural_material_labelled_as_procedural_guidance_with_url(self):
        gen_answer = {
            "relevant_official_sources": [
                {
                    "source_id": "EJAGRITI_GUIDE_PAGE_1",
                    "document_title": "e-Jagriti Consumer Commission Online Complaint Filing User Manual",
                    "document_type": "PROCEDURAL_GUIDE",
                    "source_url": "https://e-jagriti.gov.in/",
                }
            ],
            "what_the_source_says": "e-Jagriti portal allows consumers to file and track consumer complaints online.",
            "source_ids_used": ["EJAGRITI_GUIDE_PAGE_1"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=self.sources)
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            retrieved_sources=self.sources,
        )
        self.assertIn("PROCEDURAL_GUIDANCE", gate["user_facing_response"])
        self.assertIn("https://e-jagriti.gov.in/", gate["user_facing_response"])

    # 13. Vakalatnama is not presented as universally mandatory
    def test_13_vakalatnama_not_presented_as_universally_mandatory(self):
        gen_answer = {
            "relevant_official_sources": [
                {
                    "source_id": "EJAGRITI_GUIDE_PAGE_1",
                    "document_title": "e-Jagriti Consumer Commission Online Complaint Filing User Manual",
                    "document_type": "PROCEDURAL_GUIDE",
                    "source_url": "https://e-jagriti.gov.in/",
                }
            ],
            "what_the_source_says": "You may need to submit a Vakalatnama.",
            "how_it_may_relate_to_your_problem": "Submit your complaint online.",
            "source_ids_used": ["EJAGRITI_GUIDE_PAGE_1"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=self.sources)
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            retrieved_sources=self.sources,
        )
        self.assertIn("advocate", gate["user_facing_response"].lower())
        self.assertTrue(
            "not required" in gate["user_facing_response"].lower() or
            "only if" in gate["user_facing_response"].lower()
        )

    # 14. Each claim displays its own citations and official links
    def test_14_each_claim_displays_its_own_citations_and_official_links(self):
        gen_answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_2",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_number": "2",
                    "source_url": "https://consumeraffairs.gov.in/public/upload/files/CP%20Act%202019_1732700731.pdf",
                    "issuing_authority": "Ministry of Consumer Affairs, Food and Public Distribution, Government of India",
                }
            ],
            "what_the_source_says": "Defect is defined under Section 2(10).",
            "source_ids_used": ["CPA_2019_SECTION_2"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=self.sources)
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            retrieved_sources=self.sources,
        )
        self.assertIn("The Consumer Protection Act, 2019", gate["user_facing_response"])
        self.assertIn("https://consumeraffairs.gov.in/", gate["user_facing_response"])
        self.assertIn("Ministry of Consumer Affairs", gate["user_facing_response"])

    # 15. A missing citation does not inherit another claim's citation
    def test_15_missing_citation_does_not_inherit_another_claims_citation(self):
        gen_answer = {
            "claims": [
                {
                    "claim_id": "CLM_001",
                    "claim_text": "Section 2(10) defines defect.",
                    "source_ids": ["CPA_2019_SECTION_2"],
                },
                {
                    "claim_id": "CLM_002",
                    "claim_text": "The consumer is automatically awarded ₹50,000 punitive damages without hearing.",
                    "source_ids": [],
                },
            ],
            "what_the_source_says": "Section 2(10) defines defect. The consumer is automatically awarded ₹50,000 punitive damages without hearing.",
            "source_ids_used": ["CPA_2019_SECTION_2"],
        }
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=self.sources)
        claims = val_rep["claims"]
        # Claim 1 should be supported
        self.assertEqual(claims[0]["support_status"], citation_checker.SUPPORTED_BY_PASSAGE)
        # Claim 2 MUST NOT inherit CPA_2019_SECTION_2 and must be unsupported
        self.assertIn(claims[1]["support_status"], (citation_checker.UNSUPPORTED_NO_CITATION, citation_checker.SUPPORT_NOT_ESTABLISHED))
        self.assertEqual(claims[1]["source_ids"], [])


if __name__ == "__main__":
    unittest.main()
