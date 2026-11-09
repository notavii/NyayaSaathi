"""
Developer CLI & Benchmark Runner for Citation and Claim Verification.

Blueprint Step 18: Citation Verification, Source Validation, and Unsupported Claim Detection.

Executes 20 synthetic test scenarios against src/citation_checker.py verifying:
1. Valid source ID and valid section.
2. Invented source ID.
3. Correct section with wrong Act title.
4. Non-existent section.
5. Wrong rule number.
6. Correct source ID but source not supplied to Gemini (allowlist check).
7. Verbatim quotation.
8. Altered quotation.
9. Paraphrase presented as an exact quotation.
10. Unsupported claim without citation.
11. Valid citation with unsupported attached claim.
12. Future-effective 2026 amendment (G.S.R. 789(E) commencement date 2027-01-01).
13. Historical provision (e.g. Consumer Handbook 2015).
14. Superseded source.
15. Legal-review-pending source (REQUIRES_LEGAL_REVIEW).
16. Transitional applicability (pre-commencement transaction with ongoing events).
17. Multiple source citations.
18. Missing source metadata.
19. Duplicate citation.
20. Empty or malformed answer.

Usage:
    python scripts/test_citation_checker.py --scenario 1
    python scripts/test_citation_checker.py --scenario all
"""

import argparse
from datetime import date
import json
import os
import sys
from typing import Any, Dict, List, Optional

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import citation_checker


# ---------------------------------------------------------------------------
# Real Source Chunks from Knowledge Base used for Synthetic Scenarios
# ---------------------------------------------------------------------------

REAL_CHUNK_CPA_SEC_83 = {
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

REAL_CHUNK_CPA_SEC_2_10 = {
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
    "exact_original_text": 'defect means any fault, imperfection or shortcoming in the quality, quantity, potency, purity or standard which is required to be maintained by or under any law for the time being in force.',
}

REAL_CHUNK_ECOM_RULE_4 = {
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
    "exact_original_text": "4. (1) Every e-commerce entity shall establish an adequate grievance redressal mechanism and appoint a grievance officer for consumer grievance redressal.",
}

REAL_CHUNK_ECOM_2026_AMEND = {
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
}

REAL_CHUNK_HISTORICAL_HANDBOOK = {
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
}


# ---------------------------------------------------------------------------
# 20 Synthetic Test Scenarios (Part L)
# ---------------------------------------------------------------------------

SYNTHETIC_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "1": {
        "name": "Valid source ID and valid section",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": "Under Section 83, a product liability action may be brought against a product seller for harm caused by a defective product.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        },
        "retrieved_sources": [REAL_CHUNK_CPA_SEC_83],
        "expected_check": lambda r: (
            r["citations"][0]["retrieval_status"] == "SOURCE_FOUND"
            and r["citations"][0]["provision_status"] == "REFERENCE_FOUND"
            and len(r["unsupported_references"]) == 0
        ),
    },
    "2": {
        "name": "Invented source ID",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_999_FAKE",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 999",
                }
            ],
            "what_the_source_says": "Section 999 grants automatic refunds.",
            "source_ids_used": ["CPA_2019_SECTION_999_FAKE"],
        },
        "retrieved_sources": [REAL_CHUNK_CPA_SEC_83],
        "expected_check": lambda r: (
            r["citations"][0]["retrieval_status"] == "SOURCE_NOT_FOUND"
            and len(r["unsupported_references"]) > 0
            and r["overall_status"] == "FAILED"
        ),
    },
    "3": {
        "name": "Correct section with wrong Act title",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "Consumer Protection (E-Commerce) Rules, 2020",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": "Section 83 of E-Commerce Rules provides product liability.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        },
        "retrieved_sources": [REAL_CHUNK_CPA_SEC_83],
        "expected_check": lambda r: (
            r["citations"][0]["title_status"] == "MISMATCH"
            and len(r["unsupported_references"]) > 0
        ),
    },
    "4": {
        "name": "Non-existent section in document",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 888",
                }
            ],
            "what_the_source_says": "Section 888 states that seller must pay treble damages.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        },
        "retrieved_sources": [REAL_CHUNK_CPA_SEC_83],
        "expected_check": lambda r: (
            r["citations"][0]["provision_status"] == "REFERENCE_NOT_FOUND"
            and any("888" in u for u in r["unsupported_references"])
        ),
    },
    "5": {
        "name": "Wrong rule number in Rules document",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CP_ECOMMERCE_RULES_2020_RULE_4",
                    "document_title": "Consumer Protection (E-Commerce) Rules, 2020",
                    "provision_reference": "Rule 99",
                }
            ],
            "what_the_source_says": "Rule 99 governs marketplace disclosures.",
            "source_ids_used": ["CP_ECOMMERCE_RULES_2020_RULE_4"],
        },
        "retrieved_sources": [REAL_CHUNK_ECOM_RULE_4],
        "expected_check": lambda r: (
            r["citations"][0]["provision_status"] == "REFERENCE_NOT_FOUND"
            and any("Rule 99" in u for u in r["unsupported_references"])
        ),
    },
    "6": {
        "name": "Correct source ID but source not supplied to Gemini",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CP_ECOMMERCE_RULES_2020_RULE_4",
                    "document_title": "Consumer Protection (E-Commerce) Rules, 2020",
                    "provision_reference": "Rule 4",
                }
            ],
            "what_the_source_says": "Rule 4 requires appointing grievance officer.",
            "source_ids_used": ["CP_ECOMMERCE_RULES_2020_RULE_4"],
        },
        "retrieved_sources": [REAL_CHUNK_CPA_SEC_83],  # Only CPA Sec 83 supplied
        "expected_check": lambda r: (
            r["citations"][0]["retrieval_status"] == "SOURCE_NOT_RETRIEVED"
            and any("not supplied" in u.lower() or "unsupplied" in u.lower() for u in r["unsupported_references"])
        ),
    },
    "7": {
        "name": "Verbatim quotation matching source text",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": 'Section 83 states that "A product liability action may be brought by a complainant against a product manufacturer" for defect harm.',
            "source_ids_used": ["CPA_2019_SECTION_83"],
        },
        "retrieved_sources": [REAL_CHUNK_CPA_SEC_83],
        "expected_check": lambda r: r["citations"][0]["quote_status"] == "VERBATIM_QUOTE_MATCH",
    },
    "8": {
        "name": "Altered quotation with modified wording",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": 'Section 83 says "A consumer lawsuit must be filed immediately against a manufacturer or seller" for all defective items.',
            "source_ids_used": ["CPA_2019_SECTION_83"],
        },
        "retrieved_sources": [REAL_CHUNK_CPA_SEC_83],
        "expected_check": lambda r: r["citations"][0]["quote_status"] in ("QUOTE_MISMATCH", "PARAPHRASE_NOT_VERIFIED_AS_QUOTE"),
    },
    "9": {
        "name": "Paraphrase presented as an exact quotation",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": 'The law states "sellers are strictly responsible for broken items sold to buyers."',
            "source_ids_used": ["CPA_2019_SECTION_83"],
        },
        "retrieved_sources": [REAL_CHUNK_CPA_SEC_83],
        "expected_check": lambda r: r["citations"][0]["quote_status"] in ("QUOTE_MISMATCH", "PARAPHRASE_NOT_VERIFIED_AS_QUOTE"),
    },
    "10": {
        "name": "Unsupported claim without citation",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [],
            "what_the_source_says": "Section 99 of the Act gives you an absolute immediate refund from the platform within 24 hours.",
            "source_ids_used": [],
        },
        "retrieved_sources": [REAL_CHUNK_CPA_SEC_83],
        "expected_check": lambda r: (
            len(r["unsupported_claims"]) > 0
            or any(c["support_status"] == "UNSUPPORTED_NO_CITATION" for c in r["claims"])
        ),
    },
    "11": {
        "name": "Valid citation with unsupported attached claim",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": "Under Section 83, the police must arrest the CEO of the seller company within 48 hours for non-bailable imprisonment.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        },
        "retrieved_sources": [REAL_CHUNK_CPA_SEC_83],
        "expected_check": lambda r: any(c["support_status"] == "SUPPORT_NOT_ESTABLISHED" for c in r["claims"]),
    },
    "12": {
        "name": "Future-effective 2026 amendment (commencement 2027-01-01)",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CP_ECOMMERCE_AMENDMENT_2026_ITEM_1",
                    "document_title": "Consumer Protection (E-Commerce) (Amendment) Rules, 2026",
                    "provision_reference": "Rule 1",
                }
            ],
            "what_the_source_says": "Under Rule 1 of G.S.R. 789(E), these amendment rules commence on 1 January 2027.",
            "source_ids_used": ["CP_ECOMMERCE_AMENDMENT_2026_ITEM_1"],
        },
        "retrieved_sources": [REAL_CHUNK_ECOM_2026_AMEND],
        "as_of_date": "2026-11-08",
        "expected_check": lambda r: (
            r["citations"][0]["temporal_status"] == "FUTURE_EFFECTIVE"
            and any("FUTURE-EFFECTIVE" in lim for lim in r["citations"][0]["limitations"])
        ),
    },
    "13": {
        "name": "Historical provision (Consumer Handbook 2015)",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CONSUMER_HANDBOOK_2015_PAGE_2",
                    "document_title": "Consumer Handbook (2015)",
                    "provision_reference": "Guidance 1",
                }
            ],
            "what_the_source_says": "District Forum entertains matters up to 20 lakhs under repealed 1986 Act.",
            "source_ids_used": ["CONSUMER_HANDBOOK_2015_PAGE_2"],
        },
        "retrieved_sources": [REAL_CHUNK_HISTORICAL_HANDBOOK],
        "expected_check": lambda r: (
            r["citations"][0]["temporal_status"] == "HISTORICAL_REFERENCE"
            and any("cannot be presented" in lim for lim in r["citations"][0]["limitations"])
        ),
    },
    "14": {
        "name": "Superseded source flagged properly",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CONSUMER_HANDBOOK_2015_PAGE_2",
                    "document_title": "Consumer Handbook (2015)",
                    "provision_reference": "Guidance 1",
                }
            ],
            "what_the_source_says": "Historical guidance on District Forums.",
            "source_ids_used": ["CONSUMER_HANDBOOK_2015_PAGE_2"],
        },
        "retrieved_sources": [REAL_CHUNK_HISTORICAL_HANDBOOK],
        "expected_check": lambda r: any("HISTORICAL_REFERENCE" in w for w in r["warnings"]),
    },
    "15": {
        "name": "Legal-review-pending source",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": "The Consumer Protection Act, 2019",
                    "provision_reference": "Section 83",
                }
            ],
            "what_the_source_says": "Section 83 sets out product liability actions.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        },
        "retrieved_sources": [REAL_CHUNK_CPA_SEC_83],
        "expected_check": lambda r: (
            r["citations"][0]["legal_review_status"] == "REQUIRES_LEGAL_REVIEW"
            and r["requires_professional_review"] is True
        ),
    },
    "16": {
        "name": "Transitional applicability spanning pre-commencement transaction",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CP_ECOMMERCE_AMENDMENT_2026_ITEM_1",
                    "document_title": "Consumer Protection (E-Commerce) (Amendment) Rules, 2026",
                    "provision_reference": "Rule 1",
                }
            ],
            "what_the_source_says": "Transitional rule applied to continuing dispute.",
            "source_ids_used": ["CP_ECOMMERCE_AMENDMENT_2026_ITEM_1"],
        },
        "retrieved_sources": [REAL_CHUNK_ECOM_2026_AMEND],
        "transaction_date": "2026-11-01",
        "event_date": "2027-01-15",
        "expected_check": lambda r: (
            r["citations"][0]["temporal_status"] == "NEEDS_LEGAL_REVIEW"
            and r["requires_professional_review"] is True
        ),
    },
    "17": {
        "name": "Multiple source citations verified independently",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
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
            "what_the_source_says": "Section 83 product liability works with Section 2(10) defect definition.",
            "source_ids_used": ["CPA_2019_SECTION_83", "CPA_2019_SECTION_2_PART_007"],
        },
        "retrieved_sources": [REAL_CHUNK_CPA_SEC_83, REAL_CHUNK_CPA_SEC_2_10],
        "expected_check": lambda r: len(r["citations"]) == 2 and all(c["retrieval_status"] == "SOURCE_FOUND" for c in r["citations"]),
    },
    "18": {
        "name": "Missing source metadata handled gracefully",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
            "relevant_official_sources": [
                {
                    "source_id": "CPA_2019_SECTION_83",
                    "document_title": None,
                    "provision_reference": None,
                }
            ],
            "what_the_source_says": "Product liability relief details.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        },
        "retrieved_sources": [REAL_CHUNK_CPA_SEC_83],
        "expected_check": lambda r: (
            len(r["citations"]) == 1
            and r["citations"][0]["title_status"] == "NOT_SPECIFIED"
        ),
    },
    "19": {
        "name": "Duplicate citation deduplicated cleanly",
        "answer": {
            "response_status": "SOURCE_GROUNDED_INFORMATION",
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
            "what_the_source_says": "Section 83 is cited twice in the response.",
            "source_ids_used": ["CPA_2019_SECTION_83"],
        },
        "retrieved_sources": [REAL_CHUNK_CPA_SEC_83],
        "expected_check": lambda r: len(r["citations"]) == 1,
    },
    "20": {
        "name": "Empty or malformed answer handled without crashing",
        "answer": "NOT_A_VALID_JSON_OBJECT{{{",
        "retrieved_sources": [REAL_CHUNK_CPA_SEC_83],
        "expected_check": lambda r: r["overall_status"] == "FAILED" and len(r["unsupported_references"]) > 0,
    },
}


def run_scenario(scenario_id: str, verbose: bool = True) -> bool:
    """Runs a single synthetic scenario and evaluates results."""
    scenario = SYNTHETIC_SCENARIOS.get(scenario_id)
    if not scenario:
        print(f"Error: Unknown scenario ID '{scenario_id}'. Available: 1-20.")
        return False

    name = scenario["name"]
    answer_payload = scenario["answer"]
    retrieved_sources = scenario.get("retrieved_sources", [])
    as_of_date = scenario.get("as_of_date")
    tx_date = scenario.get("transaction_date")
    ev_date = scenario.get("event_date")
    check_fn = scenario.get("expected_check")

    if verbose:
        print(f"\n==================================================")
        print(f"SCENARIO {scenario_id}: {name}")
        print("==================================================")

    # Execute deterministic validation
    report = citation_checker.validate_legal_answer(
        generated_answer=answer_payload,
        retrieved_sources=retrieved_sources,
        as_of_date=as_of_date,
        transaction_date=tx_date,
        event_date=ev_date,
    )

    is_passed = False
    try:
        is_passed = bool(check_fn(report))
    except Exception as e:
        print(f"Assertion check exception: {e}")
        is_passed = False

    status_str = "PASS" if is_passed else "FAIL"

    if verbose:
        print(f"Overall Status: {report['overall_status']}")
        print(f"Requires Professional Review: {report['requires_professional_review']}")
        print(f"Citations Verified: {len(report['citations'])}")
        print(f"Claims Evaluated: {len(report['claims'])}")
        print(f"Unsupported References: {report['unsupported_references']}")
        print(f"Unsupported Claims: {report['unsupported_claims']}")
        print(f"Warnings: {report['warnings']}")
        print(f"Result: {status_str}")

    return is_passed


def main():
    parser = argparse.ArgumentParser(description="Developer Citation Checker CLI & Benchmark")
    parser.add_argument("--scenario", default="all", help="Scenario number 1-20, or 'all'")
    parser.add_argument("--verbose", action="store_true", help="Print detailed validation logs")
    args = parser.parse_args()

    print("==================================================")
    print("NYAYA SAATHI — CITATION CHECKER BENCHMARK RUNNER")
    print("==================================================")

    if args.scenario.lower() == "all":
        passed_count = 0
        total_count = len(SYNTHETIC_SCENARIOS)

        print(f"Executing all {total_count} synthetic scenarios...\n")
        print(f"{'#':<3} | {'Scenario Name':<45} | {'Result'}")
        print("-" * 60)

        for s_id in sorted(SYNTHETIC_SCENARIOS.keys(), key=lambda x: int(x)):
            s_name = SYNTHETIC_SCENARIOS[s_id]["name"]
            ok = run_scenario(s_id, verbose=False)
            res_str = "PASS" if ok else "FAIL"
            if ok:
                passed_count += 1
            print(f"{s_id:<3} | {s_name[:45]:<45} | {res_str}")

        print("-" * 60)
        print(f"Summary: {passed_count}/{total_count} Scenarios Passed.")
        if passed_count == total_count:
            print("STATUS: ALL PASS")
            sys.exit(0)
        else:
            print("STATUS: SOME SCENARIOS FAILED")
            sys.exit(1)
    else:
        ok = run_scenario(args.scenario, verbose=True)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
