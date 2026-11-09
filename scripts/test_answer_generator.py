"""
Developer CLI & Benchmark Runner for Source-Grounded Legal Answer Generation.

Blueprint Step 17: Source-Grounded Legal Answer Generation using Gemini.

Executes synthetic test scenarios against the hybrid retrieval engine and Gemini,
verifying:
- Exclusive source-grounding.
- Explicit abstention when sources are absent or insufficient.
- Facts confirmation gate (provisional vs confirmed).
- Temporal applicability gating (G.S.R. 789(E) commencement on 2027-01-01).
- Disclosure of pending legal review on unverified source passages.
- Valid structured JSON schema.

Usage:
    python scripts/test_answer_generator.py --scenario 1
    python scripts/test_answer_generator.py --scenario all
"""

import argparse
from datetime import date
import json
import os
import sys
from typing import Any, Dict, List, Optional, Union

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import case_builder
from src import hybrid_retriever
from src import answer_generator


# 13 Synthetic Test Scenarios conforming strictly to Part K specification
SYNTHETIC_SCENARIOS = {
    "1": {
        "name": "Defective Product (Mobile Phone Display Defect)",
        "question": "I purchased a smartphone and within 5 days the display stopped working. The seller refused replacement. What are my rights under consumer law regarding defective goods?",
        "query": "defective goods replacement liability seller consumer protection act",
        "case_data": {
            "product_or_service": "mobile phone",
            "seller_or_platform": "Electronics Retailer",
            "purchase_amount": "₹15,000",
            "desired_resolution": "Replacement with non-defective product",
            "seller_contact": {"contacted": True, "contact_method": "phone call", "seller_response": "Refused replacement"},
            "facts_confirmed_by_user": True,
        },
        "include_procedural": False,
        "include_future": False,
    },
    "2": {
        "name": "Missing Online Product (E-commerce Non-Delivery)",
        "question": "I ordered clothes on an e-commerce platform 3 weeks ago. The package was never delivered, and calls are unanswered. What do e-commerce rules say about non-delivery?",
        "query": "e-commerce rules non delivery refund seller marketplace",
        "case_data": {
            "product_or_service": "apparel / clothes",
            "seller_or_platform": "E-Commerce Marketplace",
            "purchase_amount": "₹3,500",
            "desired_resolution": "Full refund of purchase amount",
            "seller_contact": {"contacted": True, "contact_method": "phone call", "seller_response": "Calls unanswered"},
            "facts_confirmed_by_user": True,
        },
        "include_procedural": False,
        "include_future": False,
    },
    "3": {
        "name": "Refund Refusal (Approved Refund Withheld)",
        "question": "The seller agreed to refund my money after I returned the product, but has not refunded for 45 days. What do official rules say about delayed refunds?",
        "query": "refund timeline delay unfair trade practice e-commerce rules",
        "case_data": {
            "product_or_service": "home appliance",
            "seller_or_platform": "Online Store",
            "purchase_amount": "₹6,000",
            "desired_resolution": "Immediate refund with interest",
            "seller_contact": {"contacted": True, "contact_method": "email", "seller_response": "Refund approved but delayed"},
            "facts_confirmed_by_user": True,
        },
        "include_procedural": False,
        "include_future": False,
    },
    "4": {
        "name": "Wrong Product Delivered (Ordered Laptop, Got Soap)",
        "question": "I ordered a laptop online but the parcel contained soap bars. The marketplace declined my return request. How does consumer protection treat delivery of completely wrong goods?",
        "query": "wrong product delivered e-commerce misleading return refusal",
        "case_data": {
            "product_or_service": "laptop",
            "seller_or_platform": "Marketplace Platform",
            "purchase_amount": "₹50,000",
            "desired_resolution": "Full refund and investigation",
            "seller_contact": {"contacted": True, "contact_method": "in-app customer chat", "seller_response": "Declined return request"},
            "facts_confirmed_by_user": True,
        },
        "include_procedural": False,
        "include_future": False,
    },
    "5": {
        "name": "Service Deficiency (Broadband Outage / Flight Cancellation)",
        "question": "My internet provider had an outage for 25 days but still billed me the full monthly charges and refused compensation. What constitutes deficiency in service?",
        "query": "deficiency in service definition consumer protection act compensation",
        "case_data": {
            "product_or_service": "broadband internet",
            "seller_or_platform": "Telecom Service Provider",
            "purchase_amount": "₹1,200",
            "desired_resolution": "Bill waiver and compensation for service disruption",
            "seller_contact": {"contacted": True, "contact_method": "email", "seller_response": "Refused compensation"},
            "facts_confirmed_by_user": True,
        },
        "include_procedural": False,
        "include_future": False,
    },
    "6": {
        "name": "Exact Section 35 Question (District Commission Complaint Filing)",
        "question": "How can a consumer file a formal complaint before the District Consumer Commission under Section 35 of the Consumer Protection Act, 2019?",
        "query": "Section 35 Consumer Protection Act manner in which complaint shall be made District Commission",
        "case_data": {
            "facts_confirmed_by_user": True,
        },
        "include_procedural": True,
        "include_future": False,
    },
    "7": {
        "name": "Procedural e-Jagriti Question (Online Portal Steps)",
        "question": "What is the official procedure for e-filing a consumer case through the e-Jagriti portal?",
        "query": "e-Jagriti consumer online complaint e-filing procedure user guide",
        "case_data": {
            "facts_confirmed_by_user": True,
        },
        "include_procedural": True,
        "include_future": False,
    },
    "8": {
        "name": "Empty Retrieval Result (Safeguard Verification)",
        "question": "What are the rules for registering a spacecraft in municipal corporation records?",
        "query": "spacecraft municipal corporation registration interplanetary vehicle",
        "case_data": {
            "facts_confirmed_by_user": True,
        },
        "include_procedural": False,
        "include_future": False,
        "force_empty_retrieval": True,
    },
    "9": {
        "name": "Insufficient Source Coverage (Abstention Verification)",
        "question": "What are the specific statutory limitation periods and fee exemptions for cryptocurrency mining disputes under Consumer Protection Act?",
        "query": "cryptocurrency blockchain token mining dispute consumer protection fee exemption",
        "case_data": {
            "facts_confirmed_by_user": True,
        },
        "include_procedural": False,
        "include_future": False,
    },
    "10": {
        "name": "Future-Law Question (Prospective 2026 E-commerce Amendment)",
        "question": "What are the new rules notified in September 2026 regarding e-commerce platforms, and when do they come into force?",
        "query": "Consumer Protection E-Commerce Amendment Rules 2026 GSR 789 commencement",
        "case_data": {
            "facts_confirmed_by_user": True,
        },
        "include_procedural": False,
        "include_future": True,
    },
    "11": {
        "name": "Transitional Temporal Applicability (Pre-commencement Transaction with Continuing Dispute)",
        "question": "I bought a refrigerator in November 2026. The seller delayed repairs into 2027. Do the 2026 E-Commerce Amendment Rules apply to my past transaction?",
        "query": "Consumer Protection E-Commerce Amendment Rules 2026 applicability",
        "case_data": {
            "product_or_service": "refrigerator",
            "seller_or_platform": "Marketplace Seller",
            "purchase_amount": "₹28,000",
            "facts_confirmed_by_user": True,
        },
        "include_procedural": False,
        "include_future": True,
        "temporal_override": "NEEDS_LEGAL_REVIEW",
    },
    "12": {
        "name": "Unconfirmed Case Facts (Provisional Assessment Gate)",
        "question": "I think I was overcharged by an airline, but I don't have my ticket or exact amounts yet. What does the law say?",
        "query": "unfair contract airline tariff overcharging consumer protection",
        "case_data": {
            "product_or_service": "flight ticket",
            "seller_or_platform": "Airline",
            "facts_confirmed_by_user": False,  # Explicitly unconfirmed
            "missing_information": ["purchase_amount", "purchase_date", "seller_contact"],
        },
        "include_procedural": False,
        "include_future": False,
    },
    "13": {
        "name": "Retrieved Source Requiring Legal Review",
        "question": "What are the statutory guidelines regarding mediation procedures under the Consumer Protection Act?",
        "query": "Consumer Protection Mediation Rules 2020 procedure mediation cell",
        "case_data": {
            "facts_confirmed_by_user": True,
        },
        "include_procedural": False,
        "include_future": False,
    },
}


def run_scenario(scenario_key: str, scenario: Dict[str, Any], live_gemini: bool = True) -> Dict[str, Any]:
    print(f"\n{'='*75}")
    print(f"SCENARIO {scenario_key}: {scenario['name']}")
    print(f"{'='*75}")
    print(f"User Question: \"{scenario['question']}\"")
    print(f"Retrieval Query: \"{scenario['query']}\"")

    # 1. Build Case Object
    case = case_builder.create_empty_case(
        original_user_story=scenario["question"],
        language_preference="English",
    )
    for k, v in scenario.get("case_data", {}).items():
        case[k] = v

    print(f"Case Facts Confirmed by User: {case.get('facts_confirmed_by_user')}")

    # 2. Execute Hybrid Retrieval
    if scenario.get("force_empty_retrieval"):
        retrieved_sources = []
        print("Retrieval: [FORCED EMPTY RESULT SET]")
    else:
        retrieved_sources = hybrid_retriever.hybrid_search(
            query=scenario["query"],
            top_k=4,
            include_procedural=scenario.get("include_procedural", False),
            include_future=scenario.get("include_future", False),
        )
        print(f"Retrieved Sources Count: {len(retrieved_sources)}")
        for idx, s in enumerate(retrieved_sources, 1):
            sid = s.get("chunk_id")
            title = s.get("document_title")
            prov = f"{s.get('provision_type', '')} {s.get('provision_number', '')}".strip()
            rev = s.get("legal_review_status")
            temp = s.get("temporal_applicability_status")
            print(f"  [{idx}] {sid} | {title} | {prov} | Review: {rev} | Temp: {temp}")

    # 3. Resolve Temporal Context
    temporal_context = scenario.get("temporal_override")
    if not temporal_context and retrieved_sources:
        temporal_context = retrieved_sources[0].get("temporal_applicability_status")

    # 4. Generate Legal Explanation
    print("\nGenerating source-grounded legal explanation...")
    result = answer_generator.generate_legal_explanation(
        user_question=scenario["question"],
        confirmed_case=case,
        retrieved_sources=retrieved_sources,
        language="English",
        temporal_context=temporal_context,
    )

    # 5. Display Structured Output Diagnostics
    print("\n--- STRUCTURED RESULT DIAGNOSTICS ---")
    print(f"Response Status: {result.get('response_status')}")
    print(f"Needs Professional Review: {result.get('needs_professional_review')}")
    print(f"Temporal Status: {result.get('temporal_applicability_status')}")
    print(f"Source IDs Used: {result.get('source_ids_used')}")
    if result.get("unsupported_claims_detected"):
        print(f"WARNING: Unsupported Claims Detected: {result.get('unsupported_claims_detected')}")
    print(f"\nWhat the Source Says:\n{result.get('what_the_source_says')}")
    print(f"\nHow it May Relate:\n{result.get('how_it_may_relate_to_your_problem')}")
    print(f"\nLimitations & Uncertainties:\n{result.get('limitations_and_uncertainties')}")
    print(f"Possible Next Steps:\n{result.get('possible_next_steps')}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Nyaya Saathi Step 17 Answer Generator Developer CLI")
    parser.add_argument(
        "--scenario",
        type=str,
        default="1",
        help="Scenario key (1-13) or 'all' to run all 13 scenarios",
    )
    args = parser.parse_args()

    if args.scenario.lower() == "all":
        print(f"Running all {len(SYNTHETIC_SCENARIOS)} synthetic test scenarios...")
        for key in sorted(SYNTHETIC_SCENARIOS.keys(), key=lambda x: int(x)):
            run_scenario(key, SYNTHETIC_SCENARIOS[key])
    elif args.scenario in SYNTHETIC_SCENARIOS:
        run_scenario(args.scenario, SYNTHETIC_SCENARIOS[args.scenario])
    else:
        print(f"Invalid scenario '{args.scenario}'. Choose 1-13 or 'all'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
