"""
Unit and Integration Tests for Citation and Claim Verification.

Blueprint Step 18: Citation Verification, Source Validation, and Unsupported Claim Detection.
Implements 30 Rigorous Test Cases matching Blueprint Part M specifications.
"""

from datetime import date
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import citation_checker


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
        "source_url": "https://consumeraffairs.gov.in/public/upload/files/CP%20Act%202019_1732700731.pdf",
        "exact_original_text": "83. A product liability action may be brought by a complainant against a product manufacturer or a product service provider or a product seller, as the case may be, for any harm caused to him on account of a defective product.",
    },
    {
        "chunk_id": "CPA_2019_SECTION_2_PART_007",
        "embedding_record_id": "CPA_2019_SECTION_2_PART_007",
        "document_id": "CPA_2019",
        "document_title": "The Consumer Protection Act, 2019",
        "provision_type": "Section",
        "provision_number": "2(10)",
        "provision_heading": "Defect Definition",
        "legal_review_status": "REQUIRES_LEGAL_REVIEW",
        "applicability_status": "CURRENTLY_IN_FORCE",
        "effective_from": "2020-07-20",
        "source_url": "https://consumeraffairs.gov.in/public/upload/files/CP%20Act%202019_1732700731.pdf",
        "exact_original_text": 'defect means any fault, imperfection or shortcoming in the quality, quantity, potency, purity or standard which is required to be maintained by or under any law for the time being in force.',
    },
    {
        "chunk_id": "CP_ECOMMERCE_RULES_2020_RULE_4",
        "embedding_record_id": "CP_ECOMMERCE_RULES_2020_RULE_4",
        "document_id": "CP_ECOMMERCE_RULES_2020",
        "document_title": "Consumer Protection (E-Commerce) Rules, 2020",
        "provision_type": "Rule",
        "provision_number": "4",
        "provision_heading": "Duties of e-commerce entities",
        "legal_review_status": "REQUIRES_LEGAL_REVIEW",
        "applicability_status": "CURRENTLY_IN_FORCE",
        "effective_from": "2020-07-23",
        "source_url": "https://consumeraffairs.gov.in/public/upload/files/Consumer%20Commission%20Rules%20&%20General%20Rules_1732703661.pdf",
        "exact_original_text": "4. (1) Every e-commerce entity shall establish an adequate grievance redressal mechanism and appoint a grievance officer for consumer grievance redressal.",
    },
    {
        "chunk_id": "CP_ECOMMERCE_AMENDMENT_2026_ITEM_1",
        "embedding_record_id": "CP_ECOMMERCE_AMENDMENT_2026_ITEM_1",
        "document_id": "CP_ECOMMERCE_AMENDMENT_2026",
        "document_title": "Consumer Protection (E-Commerce) (Amendment) Rules, 2026",
        "provision_type": "Rule",
        "provision_number": "1",
        "provision_heading": "Short title and commencement",
        "legal_review_status": "REQUIRES_LEGAL_REVIEW",
        "applicability_status": "FUTURE_EFFECTIVE",
        "effective_from": "2027-01-01",
        "gazette_reference": "G.S.R. 789(E)",
        "exact_original_text": "1. (1) These rules may be called the Consumer Protection (E-Commerce) (Amendment) Rules, 2026. (2) They shall come into force on the 1st day of January, 2027.",
    },
    {
        "chunk_id": "CONSUMER_HANDBOOK_2015_PAGE_2",
        "embedding_record_id": "CONSUMER_HANDBOOK_2015_PAGE_2",
        "document_id": "CONSUMER_HANDBOOK_2015",
        "document_title": "Consumer Handbook (2015)",
        "provision_type": "Guidance",
        "provision_number": "1",
        "provision_heading": "Historical Consumer Rights",
        "legal_review_status": "NOT_REVIEWED",
        "applicability_status": "HISTORICAL_REFERENCE",
        "effective_from": "2015-01-01",
        "exact_original_text": "Under the Consumer Protection Act 1986, District Forum entertained complaints up to twenty lakhs.",
    },
]


class TestCitationChecker(unittest.TestCase):
    """30 Comprehensive Unit Tests for Citation, Source, and Claim Verification."""

    def test_01_valid_source_id(self):
        """1. Verifies that a valid source ID in retrieved sources is marked SOURCE_FOUND."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": "Section 83 product liability action may be brought.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["citations"][0]["retrieval_status"], "SOURCE_FOUND")
        self.assertEqual(len(rep["unsupported_references"]), 0)

    def test_02_invalid_source_id(self):
        """2. Verifies that an invented or non-existent source ID is marked SOURCE_NOT_FOUND."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_999_FAKE",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 999",
                }
            ],
            "what_the_source_says": "Fake section says refund is guaranteed.",
            "source_ids_used": ["CPA_2019_SECTION_999_FAKE"],
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["citations"][0]["retrieval_status"], "SOURCE_NOT_FOUND")
        self.assertEqual(rep["overall_status"], "FAILED")
        self.assertTrue(any("CPA_2019_SECTION_999_FAKE" in u for u in rep["unsupported_references"]))

    def test_03_source_not_in_retrieved_allowlist(self):
        """3. Verifies that a source existing in catalog but NOT supplied is marked SOURCE_NOT_RETRIEVED."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CP_ECOMMERCE_RULES_2020_RULE_4",
                    "document_title": "Consumer Protection (E-Commerce) Rules, 2020",
                    "provision_reference": "Rule 4",
                }
            ],
            "what_the_source_says": "Rule 4 grievance officer requirement.",
            "source_ids_used": ["CP_ECOMMERCE_RULES_2020_RULE_4"],
        }
        # Pass only CPA Sec 83 in retrieved_sources
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=[SAMPLE_RETRIEVED_SOURCES[0]])
        self.assertEqual(rep["citations"][0]["retrieval_status"], "SOURCE_NOT_RETRIEVED")
        self.assertTrue(any("CP_ECOMMERCE_RULES_2020_RULE_4" in u for u in rep["unsupported_references"]))

    def test_04_correct_act_title(self):
        """4. Verifies that an official Act title matches the catalogue."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": "Section 83 product liability.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["citations"][0]["title_status"], "MATCHED")

    def test_05_wrong_act_title(self):
        """5. Verifies that attributing a provision to the wrong document is flagged as MISMATCH."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "Consumer Protection (E-Commerce) Rules, 2020",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": "Section 83 in E-Commerce Rules.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["citations"][0]["title_status"], "MISMATCH")
        self.assertTrue(len(rep["unsupported_references"]) > 0)

    def test_06_existing_section_reference(self):
        """6. Verifies that an existing section reference is marked REFERENCE_FOUND."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": "Section 83 applies to product sellers.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["citations"][0]["provision_status"], "REFERENCE_FOUND")

    def test_07_non_existent_section_reference(self):
        """7. Verifies that a non-existent section number is marked REFERENCE_NOT_FOUND."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 888",
                }
            ],
            "what_the_source_says": "Section 888 treble damages.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["citations"][0]["provision_status"], "REFERENCE_NOT_FOUND")
        self.assertTrue(any("888" in u for u in rep["unsupported_references"]))

    def test_08_correct_rule_number(self):
        """8. Verifies that a correct rule number in a Rules document is marked REFERENCE_FOUND."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CP_ECOMMERCE_RULES_2020_RULE_4",
                    "document_title": "Consumer Protection (E-Commerce) Rules, 2020",
                    "provision_reference": "Rule 4",
                }
            ],
            "what_the_source_says": "Rule 4 establishes duties.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["citations"][0]["provision_status"], "REFERENCE_FOUND")

    def test_09_incorrect_rule_number(self):
        """9. Verifies that an incorrect rule number is marked REFERENCE_NOT_FOUND."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CP_ECOMMERCE_RULES_2020_RULE_4",
                    "document_title": "Consumer Protection (E-Commerce) Rules, 2020",
                    "provision_reference": "Rule 99",
                }
            ],
            "what_the_source_says": "Rule 99 governs marketplace disclosures.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["citations"][0]["provision_status"], "REFERENCE_NOT_FOUND")

    def test_10_subsection_validation(self):
        """10. Verifies subsection and clause references (e.g. Section 2(10), Section 35)."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_2_PART_007",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 2(10)",
                }
            ],
            "what_the_source_says": "Section 2(10) defines defect in goods.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["citations"][0]["provision_status"], "REFERENCE_FOUND")

    def test_11_verbatim_quote_matching(self):
        """11. Verifies that an exact verbatim quotation from a source is marked VERBATIM_QUOTE_MATCH."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": 'Section 83 states that "A product liability action may be brought by a complainant against a product manufacturer" for harm.',
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["citations"][0]["quote_status"], "VERBATIM_QUOTE_MATCH")

    def test_12_quotation_mismatch(self):
        """12. Verifies that altered wording in quotation marks is detected as QUOTE_MISMATCH."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": 'Section 83 states that "A consumer lawsuit must be filed immediately against a manufacturer or seller" for all defective items.',
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertIn(rep["citations"][0]["quote_status"], ["QUOTE_MISMATCH", "PARAPHRASE_NOT_VERIFIED_AS_QUOTE"])

    def test_13_paraphrase_distinction(self):
        """13. Verifies that an approximate paraphrase is not certified as an exact quote."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": 'The law states "sellers are strictly responsible for broken items sold to buyers."',
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertNotEqual(rep["citations"][0]["quote_status"], "VERBATIM_QUOTE_MATCH")

    def test_14_unsupported_claim(self):
        """14. Verifies that an unsupported legal claim is caught and flagged."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": "Section 83 product liability rules.",
            "how_it_may_relate_to_your_problem": "Under Section 83 you are guaranteed a 100% full refund within 3 days without court procedure.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertTrue(len(rep["unsupported_claims"]) > 0 or any(c["support_status"] != "SUPPORTED_BY_PASSAGE" for c in rep["claims"]))

    def test_15_claim_without_citation(self):
        """15. Verifies that a specific statutory assertion without a supporting citation is flagged."""
        answer = {
            "relevant_official_sources": [],
            "what_the_source_says": "Section 99 gives you an absolute immediate refund within 24 hours.",
            "source_ids_used": [],
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertTrue(any(c["support_status"] == "UNSUPPORTED_NO_CITATION" for c in rep["claims"]))

    def test_16_citation_attached_to_an_unrelated_claim(self):
        """16. Verifies that citing a valid source for an unrelated claim returns SUPPORT_NOT_ESTABLISHED."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": "Under Section 83, the police must arrest the CEO of the company within 48 hours for non-bailable imprisonment.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertTrue(any(c["support_status"] == "SUPPORT_NOT_ESTABLISHED" for c in rep["claims"]))

    def test_17_correct_source_url(self):
        """17. Verifies that a source URL matching the catalogue is marked MATCHED."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                    "source_url": "https://consumeraffairs.gov.in/public/upload/files/CP%20Act%202019_1732700731.pdf",
                }
            ],
            "what_the_source_says": "Section 83 product liability text.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["citations"][0]["source_url_status"], "MATCHED")

    def test_18_incorrect_source_url(self):
        """18. Verifies that an incorrect source URL is detected and flagged."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                    "source_url": "https://fake-phishing-url.com/act.pdf",
                }
            ],
            "what_the_source_says": "Section 83 product liability text.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["citations"][0]["source_url_status"], "URL_MISMATCH")

    def test_19_source_superseded_status(self):
        """19. Verifies that a historical/superseded source generates an appropriate warning."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CONSUMER_HANDBOOK_2015_PAGE_2",
                    "document_title": "Consumer Handbook (2015)",
                    "provision_reference": "Guidance 1",
                }
            ],
            "what_the_source_says": "Historical handbook text on district forum limits.",
            "source_ids_used": ["CONSUMER_HANDBOOK_2015_PAGE_2"],
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["citations"][0]["temporal_status"], "HISTORICAL_REFERENCE")
        self.assertTrue(any("HISTORICAL_REFERENCE" in w for w in rep["warnings"]))

    def test_20_source_requiring_legal_review(self):
        """20. Verifies that a source marked REQUIRES_LEGAL_REVIEW preserves that status."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": "Section 83 product liability.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["citations"][0]["legal_review_status"], "REQUIRES_LEGAL_REVIEW")
        self.assertTrue(rep["requires_professional_review"])

    def test_21_future_law_effective_date(self):
        """21. Verifies that G.S.R. 789(E) is evaluated as FUTURE_EFFECTIVE before 2027-01-01."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CP_ECOMMERCE_AMENDMENT_2026_ITEM_1",
                    "document_title": "Consumer Protection (E-Commerce) (Amendment) Rules, 2026",
                    "provision_reference": "Rule 1",
                }
            ],
            "what_the_source_says": "Rule 1 commences on 1 January 2027.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES, as_of_date="2026-11-08")
        self.assertEqual(rep["citations"][0]["temporal_status"], "FUTURE_EFFECTIVE")
        self.assertTrue(any("FUTURE-EFFECTIVE" in lim for lim in rep["citations"][0]["limitations"]))

    def test_22_historical_transaction(self):
        """22. Verifies that a transaction date in the past evaluated against historical materials retains warnings."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CONSUMER_HANDBOOK_2015_PAGE_2",
                    "document_title": "Consumer Handbook (2015)",
                    "provision_reference": "Guidance 1",
                }
            ],
            "what_the_source_says": "Historical guidance rules.",
        }
        rep = citation_checker.validate_legal_answer(
            answer,
            retrieved_sources=SAMPLE_RETRIEVED_SOURCES,
            transaction_date="2016-05-10",
        )
        self.assertEqual(rep["citations"][0]["temporal_status"], "HISTORICAL_REFERENCE")

    def test_23_transitional_applicability(self):
        """23. Verifies that a dispute spanning before and after 2027-01-01 triggers NEEDS_LEGAL_REVIEW."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CP_ECOMMERCE_AMENDMENT_2026_ITEM_1",
                    "document_title": "Consumer Protection (E-Commerce) (Amendment) Rules, 2026",
                    "provision_reference": "Rule 1",
                }
            ],
            "what_the_source_says": "Amendment rules applied to continuing dispute.",
        }
        rep = citation_checker.validate_legal_answer(
            answer,
            retrieved_sources=SAMPLE_RETRIEVED_SOURCES,
            transaction_date="2026-10-15",
            event_date="2027-02-01",
        )
        self.assertEqual(rep["citations"][0]["temporal_status"], "NEEDS_LEGAL_REVIEW")
        self.assertTrue(rep["requires_professional_review"])

    def test_24_invented_source_ids_flagged_in_safe_answer(self):
        """24. Verifies that produce_safe_validated_answer suppresses unverified claims and flags invented IDs."""
        answer = {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "INVENTED_SECTION_999",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 999",
                }
            ],
            "what_the_source_says": "Section 999 fake relief.",
            "limitations_and_uncertainties": [],
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        safe = citation_checker.produce_safe_validated_answer(answer, rep)
        self.assertEqual(safe["response_status"], "UNSUPPORTED_CLAIMS_SUPPRESSED")
        self.assertTrue(any("SAFETY WARNING" in lim for lim in safe["limitations_and_uncertainties"]))
        self.assertIn("original_unvalidated_answer", safe)

    def test_25_legal_review_status_never_upgraded(self):
        """25. Verifies that validation never upgrades REQUIRES_LEGAL_REVIEW to HUMAN_REVIEWED."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": "Section 83 product liability text.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertNotEqual(rep["citations"][0]["legal_review_status"], "HUMAN_REVIEWED")
        self.assertEqual(rep["citations"][0]["legal_review_status"], "REQUIRES_LEGAL_REVIEW")

    def test_26_malformed_answer_handling(self):
        """26. Verifies that malformed JSON or invalid answer object is rejected safely without crashing."""
        rep = citation_checker.validate_legal_answer("{{NOT_A_VALID_JSON", retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["overall_status"], "FAILED")
        self.assertTrue(len(rep["unsupported_references"]) > 0)

    def test_27_missing_metadata_handling(self):
        """27. Verifies that missing source metadata (None title, None provision) is handled gracefully."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": None,
                    "provision_reference": None,
                }
            ],
            "what_the_source_says": "Section 83 text.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(rep["citations"][0]["title_status"], "NOT_SPECIFIED")
        self.assertEqual(len(rep["citations"]), 1)

    def test_28_multiple_citations(self):
        """28. Verifies that multiple citations are verified independently and thoroughly."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                },
                {
                    "source_id": "CPA_2019_SECTION_2_PART_007",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 2(10)",
                },
            ],
            "what_the_source_says": "Section 83 product liability and Section 2(10) defect definition.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(len(rep["citations"]), 2)
        self.assertEqual(rep["citations"][0]["provision_status"], "REFERENCE_FOUND")
        self.assertEqual(rep["citations"][1]["provision_status"], "REFERENCE_FOUND")

    def test_29_duplicate_citations(self):
        """29. Verifies that duplicate citations in the response are deduplicated cleanly."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                },
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                },
            ],
            "what_the_source_says": "Section 83 cited twice.",
        }
        rep = citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        self.assertEqual(len(rep["citations"]), 1)

    @patch("src.gemini_service.generate_response")
    def test_30_no_gemini_call_during_deterministic_validation(self, mock_gemini):
        """30. Verifies that deterministic citation validation NEVER calls Gemini API."""
        answer = {
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": "Section 83 product liability action text.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        }
        citation_checker.validate_legal_answer(answer, retrieved_sources=SAMPLE_RETRIEVED_SOURCES)
        # Gemini service must NEVER have been called
        self.assertFalse(mock_gemini.called)


if __name__ == "__main__":
    unittest.main()
