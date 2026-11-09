"""
Verification script for all 7 consumer dispute flows in Nyaya Saathi.
Tests:
1. Damaged or defective goods
2. Wrong item delivered
3. Non-delivery / delayed delivery
4. Refund refusal
5. Service deficiency
6. Unsupported domain / honest abstention (RERA / SEBI)
7. Out of scope / Urgent escalation
"""

import sys
import io
import os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import intake
from src import case_builder
from src import safety_guard
from src import workflow_service


def verify_scenario_1_damaged_product():
    print("=" * 60)
    print("SCENARIO 1: Damaged Product (Flipkart Mobile)")
    print("=" * 60)
    text = "I received a mobile with a cracked screen from Flipkart, but seller refuses to refund."
    cat = case_builder.infer_issue_category(text)
    assert cat == case_builder.CATEGORY_DEFECTIVE_GOODS, f"Expected {case_builder.CATEGORY_DEFECTIVE_GOODS}, got {cat}"

    case = case_builder.create_empty_case(
        issue_category=cat,
        original_user_story=text,
        language_preference="English",
    )
    case_builder.extract_case_facts_deterministically(case, text)
    assert "mobile" in case.get("product_or_service").lower()
    assert case.get("seller_or_platform") == "Flipkart"

    harm_product_only = workflow_service.is_harm_limited_to_product(case, text)
    assert harm_product_only is True, "Harm must be limited to product only (no product liability under Sec 2(22))"
    print(f"  Category: {cat}")
    print(f"  Product: {case.get('product_or_service')}")
    print(f"  Platform: {case.get('seller_or_platform')}")
    print(f"  Harm limited to product: {harm_product_only}")
    print("  -> PASSED\n")


def verify_scenario_2_wrong_item():
    print("=" * 60)
    print("SCENARIO 2: Wrong Item Delivered (Amazon Shoes)")
    print("=" * 60)
    text = "Ordered Nike running shoes on Amazon, but received cheap rubber slippers instead."
    cat = case_builder.infer_issue_category(text)
    assert cat == case_builder.CATEGORY_INCORRECT_ITEM, f"Expected {case_builder.CATEGORY_INCORRECT_ITEM}, got {cat}"

    case = case_builder.create_empty_case(
        issue_category=cat,
        original_user_story=text,
        language_preference="English",
    )
    case_builder.extract_case_facts_deterministically(case, text)
    assert case.get("seller_or_platform") == "Amazon"
    print(f"  Category: {cat}")
    print(f"  Platform: {case.get('seller_or_platform')}")
    print("  -> PASSED\n")


def verify_scenario_3_delayed_delivery():
    print("=" * 60)
    print("SCENARIO 3: Non-delivery / Delayed Delivery")
    print("=" * 60)
    text = "Ordered laptop 3 weeks ago on Flipkart, courier status is stuck in transit and item not delivered."
    cat = case_builder.infer_issue_category(text)
    assert cat == case_builder.CATEGORY_NON_DELIVERY, f"Expected {case_builder.CATEGORY_NON_DELIVERY}, got {cat}"

    case = case_builder.create_empty_case(
        issue_category=cat,
        original_user_story=text,
        language_preference="English",
    )
    case_builder.extract_case_facts_deterministically(case, text)
    q1 = case_builder.get_next_follow_up_question(case, language="English")
    assert q1 is not None
    assert "delivery" in q1.lower() or "courier" in q1.lower() or "seller" in q1.lower() or "order" in q1.lower()
    print(f"  Category: {cat}")
    print(f"  Targeted Follow-up: {q1}")
    print("  -> PASSED\n")


def verify_scenario_4_refund_refusal():
    print("=" * 60)
    print("SCENARIO 4: Refund Refusal (Returned Item)")
    print("=" * 60)
    text = "Returned the item to seller within 7 days window, but seller is refusing to refund my money."
    cat = case_builder.infer_issue_category(text)
    assert cat == case_builder.CATEGORY_REFUND_REFUSAL, f"Expected {case_builder.CATEGORY_REFUND_REFUSAL}, got {cat}"

    case = case_builder.create_empty_case(
        issue_category=cat,
        original_user_story=text,
        language_preference="English",
    )
    case_builder.extract_case_facts_deterministically(case, text)
    print(f"  Category: {cat}")
    print(f"  Status: {case.get('status')}")
    print("  -> PASSED\n")


def verify_scenario_5_service_deficiency():
    print("=" * 60)
    print("SCENARIO 5: Service Deficiency (Broadband Downtime)")
    print("=" * 60)
    text = "Airtel broadband connection is down for 15 days, no technician visited despite 5 complaints."
    cat = case_builder.infer_issue_category(text)
    assert cat == case_builder.CATEGORY_SERVICE_DEFICIENCY, f"Expected {case_builder.CATEGORY_SERVICE_DEFICIENCY}, got {cat}"

    case = case_builder.create_empty_case(
        issue_category=cat,
        original_user_story=text,
        language_preference="English",
    )
    case_builder.extract_case_facts_deterministically(case, text)
    assert case.get("seller_or_platform") == "Airtel"
    print(f"  Category: {cat}")
    print(f"  Provider: {case.get('seller_or_platform')}")
    print("  -> PASSED\n")


def verify_scenario_6_unsupported_domain_rera():
    print("=" * 60)
    print("SCENARIO 6: Unsupported Domain Honest Abstention (RERA)")
    print("=" * 60)
    text = "Flat possession delayed by 3 years and builder is refusing delay interest under RERA."
    is_covered, framework, expl = intake.check_source_coverage(text)
    assert is_covered is False, "Must detect out-of-corpus statutory domain"
    assert "RERA" in framework or "Real Estate" in framework
    assert "Real Estate" in expl or "RERA" in expl

    # Verify classification also annotates coverage
    classification = intake.classify_issue(text, language="English")
    assert classification["category"] == intake.CATEGORY_CONSUMER_DISPUTE
    assert classification["coverage_status"] == intake.COVERAGE_UNAVAILABLE
    assert classification["coverage_framework"] == framework

    # Verify reanalyse_case cleanly abstains without hallucinating citations
    case = case_builder.create_empty_case(
        issue_category="Service deficiency",
        original_user_story=text,
        language_preference="English",
    )
    analysis = workflow_service.reanalyse_case(case, language="English")
    assert analysis["gate_status"] == "ABSTAIN"
    assert analysis["coverage_status"] == intake.COVERAGE_UNAVAILABLE
    assert analysis["citations"] == []
    print(f"  Is Covered in Knowledge Base: {is_covered}")
    print(f"  Specialized Framework: {framework}")
    print(f"  Gate Status: {analysis['gate_status']}")
    print(f"  Citations Count: {len(analysis['citations'])} (zero hallucination)")
    print("  -> PASSED\n")


def verify_scenario_7_out_of_scope_or_urgent():
    print("=" * 60)
    print("SCENARIO 7: Out of Scope & Urgent Escalation")
    print("=" * 60)
    # Part A: Employment salary dispute
    salary_text = "My employer has not paid my salary for 4 months and terminated me without notice."
    salary_scope = intake.classify_issue(salary_text, language="English")
    assert salary_scope["category"] == intake.CATEGORY_OUTSIDE_SCOPE
    print(f"  Salary Dispute Scope: {salary_scope['category']} (Correctly Out of Scope)")

    # Part B: Threat / Violence
    threat_text = "The recovery agent is threatening physical violence at my home right now."
    threat_safety = safety_guard.evaluate_turn_safety(threat_text)
    assert threat_safety["classification"] == safety_guard.CATEGORY_URGENT_ESCALATION
    print(f"  Threat Classification: {threat_safety['classification']} (Correctly Urgent Escalation)")
    print("  -> PASSED\n")


def main():
    print("\n" + "=" * 60)
    print("RUNNING NYAYA SAATHI 7-SCENARIO VERIFICATION")
    print("=" * 60 + "\n")
    verify_scenario_1_damaged_product()
    verify_scenario_2_wrong_item()
    verify_scenario_3_delayed_delivery()
    verify_scenario_4_refund_refusal()
    verify_scenario_5_service_deficiency()
    verify_scenario_6_unsupported_domain_rera()
    verify_scenario_7_out_of_scope_or_urgent()
    print("=" * 60)
    print("ALL 7 SCENARIOS VERIFIED SUCCESSFULLY!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
