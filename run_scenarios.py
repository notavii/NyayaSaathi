"""
Live synthetic scenario execution script for Myntra and Flipkart cases.
Captures exact state, fact provenance, timeline events, gaps, and citation blocks.
"""

import io
import json
import os
import sys

# Ensure UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from src import case_builder
from src import intake
from src import workflow_service
from src import safety_guard


def run_myntra_scenario():
    print("=" * 60)
    print("SCENARIO 1: MYNTRA DAMAGED MOBILE RUN")
    print("=" * 60)

    # Turn 1
    t1_text = "I got damaged mobile from Myntra."
    scope1 = intake.classify_issue(t1_text, language="English")
    case = case_builder.create_empty_case(
        issue_category="Defective or damaged goods",
        original_user_story=t1_text,
        language_preference="English",
    )
    case_builder.extract_case_facts_deterministically(case, t1_text)
    case["conversation_history"].append({"role": "user", "content": t1_text})

    q1 = case_builder.get_next_follow_up_question(case, language="English")
    case["pending_question"] = q1
    case["conversation_history"].append({"role": "assistant", "content": q1})

    print(f"Case ID: {case['case_id']}")
    print(f"Turn 1 Input: {t1_text}")
    print(f"Scope Category: {scope1['category']}")
    print(f"Product: {case.get('product_or_service')}")
    print(f"Platform: {case.get('seller_or_platform')}")
    print(f"Follow-up Question: {q1}\n")

    # Turn 2
    t2_text = "yes, no response from seller"
    case["conversation_history"].append({"role": "user", "content": t2_text})
    case_builder.extract_case_facts_deterministically(case, t2_text, pending_question=q1)

    print(f"Turn 2 Input: {t2_text}")
    print(f"Seller Contacted: {case['seller_contact']['contacted']}")
    print(f"Contact Method: {case['seller_contact']['contact_method']}")
    print(f"Seller Response: {case['seller_contact']['seller_response']}")
    print(f"Timeline Events:")
    for ev in case.get("events", []):
        print(f"  - Event: {ev['event']} (Date: {ev.get('date', 'Not provided')})")

    # User performs correction: purchase_amount = "26000"
    print("\nApplying Fact Correction via UI widget:")
    is_valid, err, cleaned_amt = case_builder.validate_fact_value("purchase_amount", "26000")
    print(f"  Validation: is_valid={is_valid}, cleaned='{cleaned_amt}'")
    case_builder.correct_case_fact(case, "purchase_amount", cleaned_amt, message_id="MSG_CORR_01")
    case_builder.compute_missing_information(case)
    print(f"  Purchase Amount updated to: {case.get('purchase_amount')}")
    print(f"  Platform remains: {case.get('seller_or_platform')}")
    print(f"  Correction History: {case.get('correction_history')}")

    # User clicks Confirm All Facts as Correct
    print("\nConfirming Facts & Generating Legal Explanation:")
    case_builder.confirm_case_facts(case)
    print(f"  Facts Confirmed: {case.get('facts_confirmed_by_user')}")
    print(f"  Case Status: {case.get('status')}")

    post_resp = workflow_service.generate_post_confirmation_response(case, language="English")
    print("\n--- GENERATED POST-CONFIRMATION RESPONSE ---")
    print(post_resp)
    print("--------------------------------------------\n")

    return case, post_resp


def run_flipkart_scenario():
    print("=" * 60)
    print("SCENARIO 2: FLIPKART DAMAGED MOBILE RUN")
    print("=" * 60)

    # Turn 1
    t1_text = "I got damaged mobile from Flipkart."
    scope1 = intake.classify_issue(t1_text, language="English")
    case = case_builder.create_empty_case(
        issue_category="Defective or damaged goods",
        original_user_story=t1_text,
        language_preference="English",
    )
    case_builder.extract_case_facts_deterministically(case, t1_text)
    case["conversation_history"].append({"role": "user", "content": t1_text})

    q1 = case_builder.get_next_follow_up_question(case, language="English")
    case["pending_question"] = q1
    case["conversation_history"].append({"role": "assistant", "content": q1})

    print(f"Case ID: {case['case_id']}")
    print(f"Turn 1 Input: {t1_text}")
    print(f"Scope Category: {scope1['category']}")
    print(f"Product: {case.get('product_or_service')}")
    print(f"Platform: {case.get('seller_or_platform')}")
    print(f"Follow-up Question: {q1}\n")

    # Turn 2
    t2_text = "yess, the seller is not responding"
    case["conversation_history"].append({"role": "user", "content": t2_text})
    case_builder.extract_case_facts_deterministically(case, t2_text, pending_question=q1)

    print(f"Turn 2 Input: {t2_text}")
    print(f"Seller Contacted: {case['seller_contact']['contacted']}")
    print(f"Contact Method: {case['seller_contact']['contact_method']}")
    print(f"Seller Response: {case['seller_contact']['seller_response']}")
    print(f"Timeline Events:")
    for ev in case.get("events", []):
        print(f"  - Event: {ev['event']} (Date: {ev.get('date', 'Not provided')})")

    # Confirm facts
    print("\nConfirming Facts & Generating Legal Explanation:")
    case_builder.confirm_case_facts(case)
    post_resp = workflow_service.generate_post_confirmation_response(case, language="English")
    print("\n--- GENERATED POST-CONFIRMATION RESPONSE ---")
    print(post_resp)
    print("--------------------------------------------\n")

    return case, post_resp


if __name__ == "__main__":
    c1, r1 = run_myntra_scenario()
    c2, r2 = run_flipkart_scenario()
