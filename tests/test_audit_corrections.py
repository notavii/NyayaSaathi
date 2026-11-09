"""
Test Suite for Audit Corrections:
1. Helpline Routing & Accurate Legal Aid (Parts 2 & 3)
2. Removal of Universal 30-Day Deadline Logic (Part 4)
3. Prohibited Guarantee Blocking & Abstention (Part 5)
4. Claim-Level Citation Verification (Part 6)
5. Historical Source Document Provenance (Part 7)
"""

import json
from pathlib import Path
import unittest

from src import abstention
from src import citation_checker
from src import safety
from src import safety_guard


class TestAuditCorrections(unittest.TestCase):

    # -----------------------------------------------------------------------
    # Part 3: Helpline Routing & Accurate Legal Aid
    # -----------------------------------------------------------------------

    def test_emergency_helpline_retains_112_and_omits_1930(self):
        """Urgent emergency message must prominently include 112 and omit 1930 for non-cyber threats."""
        msg = safety.get_urgent_escalation_message(language="English", safety_flags=["IMMEDIATE_DANGER"])
        self.assertIn("112", msg)
        self.assertNotIn("1930", msg)

        # Hindi message
        hindi_msg = safety.get_urgent_escalation_message(language="Hindi", safety_flags=["IMMEDIATE_DANGER"])
        self.assertIn("112", hindi_msg)
        self.assertNotIn("1930", hindi_msg)

    def test_1930_included_only_when_cyber_fraud_indicated(self):
        """1930 is included only when online cyber fraud is contextually indicated."""
        msg_cyber = safety.get_urgent_escalation_message(language="English", safety_flags=["CYBER_FRAUD"])
        self.assertIn("1930", msg_cyber)

        outside_cyber = safety.get_outside_scope_message("Unauthorized UPI debit and cyber banking fraud", language="English")
        self.assertIn("1930", outside_cyber)

    def test_outside_scope_generic_omits_1930(self):
        """Generic tenancy, employment, or property matters must NOT refer to 1930."""
        tenancy_msg = safety.get_outside_scope_message("Landlord refused to return rental deposit", language="English")
        self.assertNotIn("1930", tenancy_msg)

        employment_msg = safety.get_outside_scope_message("Employer has not paid salary", language="English")
        self.assertNotIn("1930", employment_msg)

    def test_legal_aid_accurate_routing_tlsc_dlsa_slsa(self):
        """Legal aid must accurately describe TLSC, DLSA, SLSA subject to statutory eligibility."""
        msg = safety.get_outside_scope_message("General property boundary dispute", language="English")
        self.assertIn("Taluk Legal Services Committee (TLSC)", msg)
        self.assertIn("District Legal Services Authority (DLSA)", msg)
        self.assertIn("State Legal Services Authority (SLSA)", msg)
        self.assertIn("eligibility criteria", msg)
        self.assertNotIn("binding statutory advice", msg)

    # -----------------------------------------------------------------------
    # Part 4: Removal of Universal 30-Day Deadline Logic
    # -----------------------------------------------------------------------

    def test_deadline_intervals_all_trigger_high_risk_legal_review(self):
        """Intervals of 10, 29, 30, 45, and 90 days must all trigger HIGH_RISK_LEGAL_REVIEW without fixed cutoff."""
        test_intervals = [
            ("I received a notice giving me 10 days to appeal", "10 days"),
            ("The summons says I have 29 days to respond", "29 days"),
            ("The 30 days limitation period is expiring", "30 days"),
            ("I was given a 45 days deadline to file an appeal", "45 days"),
            ("The order was passed and 90 days deadline is approaching", "90 days"),
            ("What is the limitation period to file my consumer case?", "general limitation"),
        ]

        for text, desc in test_intervals:
            decision = safety_guard.evaluate_turn_safety(text)
            self.assertEqual(
                decision["classification"],
                safety_guard.CATEGORY_HIGH_RISK_LEGAL_REVIEW,
                f"Failed for interval: {desc} ('{text}')",
            )
            self.assertIn("HIGH_RISK_LIMITATION_OR_DEADLINE", decision["reason_codes"])

    # -----------------------------------------------------------------------
    # Part 5: Prohibited Outcome Guarantees are BLOCKED (Not Scrubbed)
    # -----------------------------------------------------------------------

    def test_prohibited_guarantee_is_blocked_and_abstains(self):
        """Answers containing 'guarantee', '100% refund', or 'definitely win' are BLOCKED and return abstention."""
        gen_answer = {
            "relevant_official_sources": [
                {"source_id": "CPA_2019_SECTION_83", "document_title": "The Consumer Protection Act, 2019", "provision_reference": "Section 83"}
            ],
            "what_the_source_says": "Section 83 provides product liability actions against sellers for defective products.",
            "how_it_may_relate_to_your_problem": "Under this section, you will definitely win and we guarantee 100% refund from the seller.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        }
        sources = [
            {
                "chunk_id": "CPA_2019_SECTION_83",
                "document_id": "CPA_2019",
                "document_title": "The Consumer Protection Act, 2019",
                "provision_number": "83",
                "legal_review_status": "OFFICIALLY_VERIFIED",
                "applicability_status": "CURRENTLY_IN_FORCE",
                "exact_original_text": "An action for product liability may be brought by a complainant against a product manufacturer.",
            }
        ]
        val_rep = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=sources)
        gate = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_rep,
            retrieved_sources=sources,
        )

        # Gate MUST block delivery, NOT replace words and deliver
        self.assertEqual(gate["gate_status"], safety_guard.GATE_UNSAFE_BLOCKED)
        self.assertFalse(gate["allow_delivery"])
        self.assertIn("PROHIBITED_OUTCOME_PROMISE", gate["gate_reason_codes"])
        # User facing message must be the standard abstention message
        self.assertIn(abstention.STANDARD_ABSTENTION_STATEMENT, gate["user_facing_response"])
        # Raw unsafe response must NOT be exposed
        self.assertNotIn("definitely win", gate["user_facing_response"])
        self.assertNotIn("guarantee 100% refund", gate["user_facing_response"])

    # -----------------------------------------------------------------------
    # Part 6: Claim-Level Citation Verification (5 Required Scenarios)
    # -----------------------------------------------------------------------

    def setUp(self):
        self.sources = [
            {
                "chunk_id": "CPA_2019_SECTION_83",
                "document_id": "CPA_2019",
                "document_title": "The Consumer Protection Act, 2019",
                "provision_number": "83",
                "legal_review_status": "OFFICIALLY_VERIFIED",
                "applicability_status": "CURRENTLY_IN_FORCE",
                "exact_original_text": "An action for product liability may be brought by a complainant against a product manufacturer or seller.",
            },
            {
                "chunk_id": "CP_ECOMMERCE_RULES_2020_RULE_5",
                "document_id": "CP_ECOMMERCE_RULES_2020",
                "document_title": "Consumer Protection (E-Commerce) Rules, 2020",
                "provision_number": "5",
                "legal_review_status": "OFFICIALLY_VERIFIED",
                "applicability_status": "CURRENTLY_IN_FORCE",
                "exact_original_text": "Every marketplace e-commerce entity shall provide grievance redressal mechanism and appoint grievance officer.",
            },
        ]

    def test_claim_level_scenario_1_two_claims_with_separate_citations(self):
        """Scenario 1: Two legal claims with their own separate citations."""
        gen_answer = {
            "claims": [
                {
                    "claim_id": "CLM_001",
                    "claim_text": "Section 83 permits a product liability action against a product seller for harm caused by defective products.",
                    "source_ids": ["CPA_2019_SECTION_83"],
                },
                {
                    "claim_id": "CLM_002",
                    "claim_text": "Rule 5 requires marketplace e-commerce entities to appoint a grievance officer and provide redressal.",
                    "source_ids": ["CP_ECOMMERCE_RULES_2020_RULE_5"],
                },
            ],
            "relevant_official_sources": [
                {"source_id": "CPA_2019_SECTION_83", "document_title": "The Consumer Protection Act, 2019", "provision_reference": "Section 83"},
                {"source_id": "CP_ECOMMERCE_RULES_2020_RULE_5", "document_title": "Consumer Protection (E-Commerce) Rules, 2020", "provision_reference": "Rule 5"},
            ],
            "source_ids_used": ["CPA_2019_SECTION_83", "CP_ECOMMERCE_RULES_2020_RULE_5"],
        }
        report = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=self.sources)
        claims = report["claims"]
        self.assertEqual(len(claims), 2)
        self.assertEqual(claims[0]["support_status"], citation_checker.SUPPORTED_BY_PASSAGE)
        self.assertEqual(claims[1]["support_status"], citation_checker.SUPPORTED_BY_PASSAGE)
        self.assertEqual(claims[0]["source_ids"], ["CPA_2019_SECTION_83"])
        self.assertEqual(claims[1]["source_ids"], ["CP_ECOMMERCE_RULES_2020_RULE_5"])

    def test_claim_level_scenario_2_one_cited_and_one_uncited_claim(self):
        """Scenario 2: One cited claim and one uncited claim (global source_ids_used does not bleed)."""
        gen_answer = {
            "claims": [
                {
                    "claim_id": "CLM_001",
                    "claim_text": "Section 83 allows product liability claims against sellers.",
                    "source_ids": ["CPA_2019_SECTION_83"],
                },
                {
                    "claim_id": "CLM_002",
                    "claim_text": "The seller is required to pay triple damages under Section 999.",
                    "source_ids": [],
                },
            ],
            "relevant_official_sources": [
                {"source_id": "CPA_2019_SECTION_83", "document_title": "The Consumer Protection Act, 2019", "provision_reference": "Section 83"}
            ],
            "source_ids_used": ["CPA_2019_SECTION_83"],
        }
        report = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=self.sources)
        claims = report["claims"]
        self.assertEqual(claims[0]["support_status"], citation_checker.SUPPORTED_BY_PASSAGE)
        self.assertIn(claims[1]["support_status"], (citation_checker.UNSUPPORTED_NO_CITATION, citation_checker.SUPPORT_NOT_ESTABLISHED))

    def test_claim_level_scenario_3_valid_citation_attached_to_unrelated_claim(self):
        """Scenario 3: Valid citation attached to an unrelated claim (product liability chunk attached to e-commerce fee rule)."""
        gen_answer = {
            "claims": [
                {
                    "claim_id": "CLM_001",
                    "claim_text": "All marketplace sellers must pay a registration fee of ₹5,000 to the central government.",
                    "source_ids": ["CPA_2019_SECTION_83"],  # Section 83 is about product liability, nothing about fees
                }
            ],
            "relevant_official_sources": [
                {"source_id": "CPA_2019_SECTION_83", "document_title": "The Consumer Protection Act, 2019", "provision_reference": "Section 83"}
            ],
            "source_ids_used": ["CPA_2019_SECTION_83"],
        }
        report = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=self.sources)
        claim = report["claims"][0]
        self.assertEqual(claim["support_status"], citation_checker.SUPPORT_NOT_ESTABLISHED)
        self.assertTrue(any("substantial textual overlap" in lim for lim in claim["limitations"]))

    def test_claim_level_scenario_4_similar_keywords_without_supporting_passage(self):
        """Scenario 4: Claim with similar keywords but no actual supporting passage."""
        gen_answer = {
            "claims": [
                {
                    "claim_id": "CLM_001",
                    "claim_text": "Product liability actions require criminal prosecution of the marketplace director within Section 83.",
                    "source_ids": ["CPA_2019_SECTION_83"],
                }
            ],
            "relevant_official_sources": [
                {"source_id": "CPA_2019_SECTION_83", "document_title": "The Consumer Protection Act, 2019", "provision_reference": "Section 83"}
            ],
            "source_ids_used": ["CPA_2019_SECTION_83"],
        }
        report = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=self.sources)
        claim = report["claims"][0]
        self.assertEqual(claim["support_status"], citation_checker.SUPPORT_NOT_ESTABLISHED)

    def test_claim_level_scenario_5_claim_requiring_legal_interpretation_despite_text_overlap(self):
        """Scenario 5: Claim asserting definitive guilt/liability flagged as NEEDS_LEGAL_REVIEW despite keyword overlap."""
        gen_answer = {
            "claims": [
                {
                    "claim_id": "CLM_001",
                    "claim_text": "The seller is strictly liable and conclusively proves product liability under Section 83.",
                    "source_ids": ["CPA_2019_SECTION_83"],
                }
            ],
            "relevant_official_sources": [
                {"source_id": "CPA_2019_SECTION_83", "document_title": "The Consumer Protection Act, 2019", "provision_reference": "Section 83"}
            ],
            "source_ids_used": ["CPA_2019_SECTION_83"],
        }
        report = citation_checker.validate_legal_answer(gen_answer, retrieved_sources=self.sources)
        claim = report["claims"][0]
        self.assertEqual(claim["support_status"], citation_checker.CLAIM_NEEDS_LEGAL_REVIEW)
        self.assertTrue(any("professional advocate or judicial interpretation" in lim for lim in claim["limitations"]))

    # -----------------------------------------------------------------------
    # Part 7: Historical Source Provenance
    # -----------------------------------------------------------------------

    def test_historical_reference_chunks_provenance_integrity(self):
        """All 74 historical records must preserve Consumer Handbook (2015) provenance and be retrieval-ineligible."""
        path = Path("data/legal_sources/historical_reference_chunks.json")
        self.assertTrue(path.exists())
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)

        self.assertEqual(len(records), 74)
        for rec in records:
            self.assertEqual(rec["document_id"], "CONSUMER_HANDBOOK_2015")
            self.assertEqual(rec["original_source_document"], "Consumer Handbook (2015)")
            self.assertEqual(rec["original_filename"], "CONSUMER_HANDBOOK_2015.pdf")
            self.assertIn("1986", rec["underlying_legal_instrument"])
            self.assertEqual(rec["applicability_status"], "HISTORICAL_REFERENCE")
            self.assertFalse(rec["retrieval_eligible"])


    # -----------------------------------------------------------------------
    # Part 8: Knowledge Base Inventory Audit & Count Reconciliation
    # -----------------------------------------------------------------------

    def test_knowledge_base_inventory_audit_file_integrity(self):
        """Verifies that KB_INVENTORY_AUDIT.json exists and strictly validates exact counts."""
        audit_path = Path("data/legal_sources/KB_INVENTORY_AUDIT.json")
        self.assertTrue(audit_path.exists(), "KB_INVENTORY_AUDIT.json must exist")
        with open(audit_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        summary = data["reconciled_counts_summary"]
        self.assertEqual(summary["canonical_legal_chunks_count"], 206)
        self.assertEqual(summary["embedding_records_count"], 251)
        self.assertEqual(summary["historical_reference_chunks_count"], 74)
        self.assertEqual(summary["active_unique_identifiers_count"], 276)
        self.assertEqual(summary["total_knowledge_base_unique_identifiers_count"], 350)
        self.assertEqual(summary["chromadb_total_records_count"], 251)

        collections = data["chromadb_collections_breakdown"]["segregation_integrity"]
        self.assertEqual(collections["nyaya_saathi_current_law"]["count"], 232)
        self.assertEqual(collections["nyaya_saathi_procedural_guidance"]["count"], 13)
        self.assertEqual(collections["nyaya_saathi_future_law"]["count"], 6)

    def test_procedural_guidance_isolated_from_current_law_collection(self):
        """Verifies that e-Jagriti procedural chunks are isolated to procedural collection only."""
        chunks_path = Path("data/legal_sources/legal_chunks.json")
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        ejagriti_chunks = [c for c in chunks if c.get("document_id") == "EJAGRITI_FILING_GUIDE"]
        self.assertEqual(len(ejagriti_chunks), 13)
        for c in ejagriti_chunks:
            self.assertEqual(c["document_type"], "PROCEDURAL_GUIDE")

    def test_future_law_gated_to_future_collection(self):
        """Verifies that 2026 amendment chunks are isolated to future law collection."""
        records_path = Path("data/legal_sources/embedding_records.json")
        with open(records_path, "r", encoding="utf-8") as f:
            records = json.load(f)

        future_records = [r for r in records if r.get("document_id") == "CP_ECOMMERCE_AMENDMENT_2026"]
        self.assertEqual(len(future_records), 6)
        for r in future_records:
            self.assertEqual(r["applicability_status"], "FUTURE_EFFECTIVE")

        # Verify ChromaDB contains exactly 6 records in future collection
        from src.vector_store import VectorStoreManager
        vm = VectorStoreManager()
        c = vm.get_future_law_collection()
        self.assertEqual(c.count(), 6)


if __name__ == "__main__":
    unittest.main()
