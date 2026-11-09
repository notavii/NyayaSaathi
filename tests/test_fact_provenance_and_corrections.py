"""
Unit and Integration Tests for Fact Provenance, Timeline Precision,
Fact-Correction UI, Confirmation vs. Completeness, and Claim-Level Citations.

Part 9 Acceptance Verification Suite for Nyaya Saathi.
"""

import pytest
from typing import Any, Dict

from src import case_builder
from src import citation_checker
from src import safety_guard
from src import workflow_service


# ---------------------------------------------------------------------------
# Requirement 1: Generic seller non-response does not generate telephone event
# ---------------------------------------------------------------------------
def test_generic_seller_non_response_does_not_generate_telephone_timeline_event():
    case = case_builder.create_empty_case(
        issue_category="Defective or damaged goods",
        original_user_story="I got damaged mobile from Myntra.",
    )
    case_builder.extract_case_facts_deterministically(case, "I got damaged mobile from Myntra.")

    # User follow-up provides generic non-response without specifying contact method
    case_builder.extract_case_facts_deterministically(case, "yes, no response from seller")

    assert case["seller_contact"]["contacted"] is True
    assert case["seller_contact"]["contact_method"] in ("Unknown", "Not provided")
    assert case["seller_contact"]["seller_response"] == "Seller is not receiving calls / no response"

    # Verify timeline events
    events = [ev["event"] for ev in case.get("events", [])]
    # Must NOT hallucinate phone contact
    assert not any("phone" in ev.lower() for ev in events)
    assert not any("calls unanswered" in ev.lower() for ev in events)
    # Must explicitly state method and date not provided
    assert any("method and date not provided" in ev.lower() for ev in events)


# ---------------------------------------------------------------------------
# Requirement 2: Explicit phone contact generates a phone event
# ---------------------------------------------------------------------------
def test_explicit_phone_contact_generates_phone_event():
    case = case_builder.create_empty_case()
    case_builder.extract_case_facts_deterministically(
        case, "I phoned customer care three times, but they are not answering calls."
    )

    assert case["seller_contact"]["contacted"] is True
    assert case["seller_contact"]["contact_method"] == "phone call"
    events = [ev["event"] for ev in case.get("events", [])]
    assert any("via phone; calls unanswered" in ev for ev in events)


# ---------------------------------------------------------------------------
# Requirement 3: Explicit email contact generates an email event
# ---------------------------------------------------------------------------
def test_explicit_email_contact_generates_email_event():
    case = case_builder.create_empty_case()
    case_builder.extract_case_facts_deterministically(
        case, "I emailed customer support, but got no response from seller."
    )

    assert case["seller_contact"]["contacted"] is True
    assert case["seller_contact"]["contact_method"] == "email"
    events = [ev["event"] for ev in case.get("events", [])]
    assert any("via email; response not received" in ev for ev in events)


# ---------------------------------------------------------------------------
# Requirement 4: Missing contact method remains unknown
# ---------------------------------------------------------------------------
def test_missing_contact_method_remains_unknown():
    case = case_builder.create_empty_case()
    case_builder.extract_case_facts_deterministically(case, "The seller is not responding.")

    assert case["seller_contact"]["contacted"] is True
    assert case["seller_contact"]["contact_method"] in ("Unknown", "Not provided")


# ---------------------------------------------------------------------------
# Requirement 5: Missing event date remains unknown
# ---------------------------------------------------------------------------
def test_missing_event_date_remains_unknown():
    case = case_builder.create_empty_case()
    case_builder.add_event(case, "Delivered defective item")

    ev = case["events"][0]
    assert ev["date"] in ("Not provided", "Not specified")


# ---------------------------------------------------------------------------
# Requirement 6: Contradictory contact methods trigger clarification
# ---------------------------------------------------------------------------
def test_contradictory_contact_methods_trigger_clarification():
    case = case_builder.create_empty_case()
    case_builder.extract_case_facts_deterministically(
        case, "I never contacted the seller and I called them yesterday."
    )

    assert "CONTRADICTORY_CONTACT_METHOD" in case.get("safety_flags", [])


# ---------------------------------------------------------------------------
# Requirement 7: Purchase amount correction updates only purchase_amount
# ---------------------------------------------------------------------------
def test_purchase_amount_correction_updates_only_purchase_amount():
    case = case_builder.create_empty_case()
    case_builder.update_case_fact(case, "seller_or_platform", "Myntra")
    assert case["seller_or_platform"] == "Myntra"
    assert case["purchase_amount"] is None

    success = case_builder.correct_case_fact(case, "purchase_amount", "26000")
    assert success is True
    assert case["purchase_amount"] == "₹26,000"
    assert case["seller_or_platform"] == "Myntra"  # Platform must be untouched!


# ---------------------------------------------------------------------------
# Requirement 8: Seller/platform correction updates only seller_or_platform
# ---------------------------------------------------------------------------
def test_seller_platform_correction_updates_only_seller_or_platform():
    case = case_builder.create_empty_case()
    case_builder.update_case_fact(case, "purchase_amount", "₹26,000")
    case_builder.update_case_fact(case, "seller_or_platform", "Amazon")

    success = case_builder.correct_case_fact(case, "seller_or_platform", "Flipkart")
    assert success is True
    assert case["seller_or_platform"] == "Flipkart"
    assert case["purchase_amount"] == "₹26,000"  # Amount must be untouched!


# ---------------------------------------------------------------------------
# Requirement 9: Invalid monetary value is rejected
# ---------------------------------------------------------------------------
def test_invalid_monetary_value_is_rejected():
    is_valid, err_msg, cleaned = case_builder.validate_fact_value("purchase_amount", "flipkart")
    assert is_valid is False
    assert "Invalid monetary amount" in err_msg

    case = case_builder.create_empty_case()
    applied = case_builder.correct_case_fact(case, "purchase_amount", "flipkart")
    assert applied is False
    assert case.get("purchase_amount") != "flipkart"


# ---------------------------------------------------------------------------
# Requirement 10: Correction preview displays correct field and value
# ---------------------------------------------------------------------------
def test_correction_preview_displays_correct_field_and_value():
    is_valid, err_msg, cleaned = case_builder.validate_fact_value("purchase_amount", "26000")
    assert is_valid is True
    assert cleaned == "₹26,000"

    # Preview for platform should reject numeric string
    is_valid_plat, err_plat, _ = case_builder.validate_fact_value("seller_or_platform", "26000")
    assert is_valid_plat is False
    assert "numeric amount" in err_plat


# ---------------------------------------------------------------------------
# Requirement 11: Correction history records original and revised values
# ---------------------------------------------------------------------------
def test_correction_history_records_original_and_revised_values():
    case = case_builder.create_empty_case()
    case_builder.update_case_fact(case, "purchase_amount", "₹10,000")

    case_builder.correct_case_fact(case, "purchase_amount", "26000", message_id="MSG_005")

    assert len(case["correction_history"]) == 1
    record = case["correction_history"][0]
    assert record["field"] == "purchase_amount"
    assert record["old_value"] == "₹10,000"
    assert record["new_value"] == "₹26,000"
    assert record["message_id"] == "MSG_005"
    assert "timestamp" in record


# ---------------------------------------------------------------------------
# Requirement 12: Input value does not become associated with stale selection
# ---------------------------------------------------------------------------
def test_input_value_does_not_become_associated_with_stale_widget_selection():
    # Attempting to assign 26000 to seller_or_platform fails validation
    is_valid, err_msg, _ = case_builder.validate_fact_value("seller_or_platform", "26000")
    assert is_valid is False

    case = case_builder.create_empty_case()
    case_builder.update_case_fact(case, "seller_or_platform", "Myntra")
    res = case_builder.correct_case_fact(case, "seller_or_platform", "26000")
    assert res is False
    assert case["seller_or_platform"] == "Myntra"  # Never corrupted to 26000


# ---------------------------------------------------------------------------
# Requirement 13: Missing information remains visible after fact confirmation
# ---------------------------------------------------------------------------
def test_missing_information_remains_visible_after_fact_confirmation():
    case = case_builder.create_empty_case(original_user_story="I got damaged mobile from Myntra.")
    case_builder.extract_case_facts_deterministically(case, "I got damaged mobile from Myntra.")
    case_builder.confirm_case_facts(case)

    assert case["facts_confirmed_by_user"] is True
    gaps = workflow_service.format_missing_information_summary(case, language="English")
    assert len(gaps) > 0
    assert any("Amount paid" in g for g in gaps)
    assert any("Order or purchase date" in g for g in gaps)


# ---------------------------------------------------------------------------
# Requirement 14: Confirmed facts are not described as a filing-ready complaint
# ---------------------------------------------------------------------------
def test_confirmed_facts_not_described_as_filing_ready_complaint():
    case = case_builder.create_empty_case(original_user_story="I got damaged mobile from Myntra.")
    case_builder.extract_case_facts_deterministically(case, "I got damaged mobile from Myntra.")
    case_builder.confirm_case_facts(case)

    resp = workflow_service.generate_post_confirmation_response(case, language="English")
    resp_lower = resp.lower()
    assert "filing-ready complaint" not in resp_lower
    assert "ready to file in court" not in resp_lower
    assert "court complaint filed" not in resp_lower


# ---------------------------------------------------------------------------
# Requirement 15: Section 2(10) receives a precise citation
# ---------------------------------------------------------------------------
def test_section_2_10_receives_precise_citation():
    safe_answer = {
        "what_the_source_says": "Under Section 2(10) of the Consumer Protection Act, 2019, a defect is defined as any fault, imperfection or shortcoming in quality.",
        "how_it_may_relate_to_your_problem": "A cracked or damaged mobile phone delivered by the seller falls under this statutory definition of defect.",
        "claims": [
            {
                "claim_id": "CLM_001",
                "claim_text": "Under Section 2(10) of the Consumer Protection Act, 2019, a defect is defined as any fault, imperfection or shortcoming.",
                "referenced_provision": "Section 2(10)",
                "source_ids": ["CPA_2019_SEC_2_10"],
                "support_status": citation_checker.SUPPORTED_BY_PASSAGE,
            }
        ],
    }
    validation_report = {
        "overall_status": citation_checker.STATUS_VALIDATED,
        "claims": safe_answer["claims"],
        "citations": [
            {
                "source_id": "CPA_2019_SEC_2_10",
                "document_title": "Consumer Protection Act, 2019",
                "document_type": "ACT",
                "provision_number": "2(10)",
                "provision_type": "Section",
                "provision_heading": "Definition of defect",
                "source_url": "https://consumeraffairs.gov.in/public/upload/files/CP%20Act%202019_1732700731.pdf",
                "issuing_authority": "Ministry of Consumer Affairs, Food and Public Distribution, Government of India",
                "exact_original_text": "'defect' means any fault, imperfection or shortcoming in the quality, quantity, potency, purity or standard...",
            }
        ],
    }

    formatted = safety_guard._format_user_facing_explanation_with_citations(
        safe_answer=safe_answer,
        validation_report=validation_report,
        retrieved_sources=[],
        existing_limits=[],
        language="English",
    )

    assert "Section 2(10)" in formatted
    assert "Definition of defect" in formatted
    assert "https://consumeraffairs.gov.in/public/upload/files/CP%20Act%202019_1732700731.pdf" in formatted
    assert "Legally Verified" not in formatted


# ---------------------------------------------------------------------------
# Requirement 16: Section 39(1)(b) and (c) receive own citation associations
# ---------------------------------------------------------------------------
def test_section_39_1_b_and_c_receive_own_citation_associations():
    safe_answer = {
        "what_the_source_says": "Under Section 39(1)(b) and Section 39(1)(c), the Commission may order replacement of defective goods or refund of price.",
        "how_it_may_relate_to_your_problem": "You may seek replacement of the damaged mobile or a full refund of ₹26,000.",
        "claims": [
            {
                "claim_id": "CLM_002",
                "claim_text": "Under Section 39(1)(b) and Section 39(1)(c), the Commission may order replacement of defective goods or refund of price.",
                "referenced_provision": "Section 39(1)(b)",
                "source_ids": ["CPA_2019_SEC_39"],
                "support_status": citation_checker.SUPPORTED_BY_PASSAGE,
            }
        ],
    }
    validation_report = {
        "overall_status": citation_checker.STATUS_VALIDATED,
        "claims": safe_answer["claims"],
        "citations": [
            {
                "source_id": "CPA_2019_SEC_39",
                "document_title": "Consumer Protection Act, 2019",
                "document_type": "ACT",
                "provision_number": "39",
                "provision_type": "Section",
                "provision_heading": "Findings of District Commission",
                "source_url": "https://consumeraffairs.gov.in/public/upload/files/CP%20Act%202019_1732700731.pdf",
                "issuing_authority": "Ministry of Consumer Affairs, Food and Public Distribution, Government of India",
                "exact_original_text": "to remove the defect... to replace the goods with new goods of similar description... to return to the complainant the price...",
            }
        ],
    }

    formatted = safety_guard._format_user_facing_explanation_with_citations(
        safe_answer=safe_answer,
        validation_report=validation_report,
        retrieved_sources=[],
        existing_limits=[],
        language="English",
    )

    assert "Section 39(1)(b) and Section 39(1)(c)" in formatted
    assert "Possible replacement or refund remedy" in formatted
    assert "Legally Verified" not in formatted


# ---------------------------------------------------------------------------
# Requirement 17: Unsupported claims remain blocked
# ---------------------------------------------------------------------------
def test_unsupported_claims_remain_blocked():
    safe_answer = {
        "what_the_source_says": "Supported text.",
        "how_it_may_relate_to_your_problem": "Unsupported allegation of punitive 10x compensation.",
        "claims": [
            {
                "claim_id": "CLM_001",
                "claim_text": "Supported claim.",
                "source_ids": ["CPA_2019_SEC_2_10"],
                "support_status": citation_checker.SUPPORTED_BY_PASSAGE,
            },
            {
                "claim_id": "CLM_002",
                "claim_text": "Unsupported allegation of punitive 10x compensation.",
                "source_ids": [],
                "support_status": citation_checker.SUPPORT_NOT_ESTABLISHED,
            },
        ],
    }
    val_report = {
        "overall_status": citation_checker.STATUS_UNSUPPORTED_CLAIMS_DETECTED,
        "claims": safe_answer["claims"],
        "citations": [{"source_id": "CPA_2019_SEC_2_10", "provision_number": "2(10)"}],
        "unsupported_claims": ["Unsupported allegation of punitive 10x compensation."],
    }

    formatted = safety_guard._format_user_facing_explanation_with_citations(
        safe_answer=safe_answer,
        validation_report=val_report,
        retrieved_sources=[{"chunk_id": "CPA_2019_SEC_2_10"}],
        existing_limits=[],
        language="English",
    )

    # Unsupported claim must NOT appear under structured claim sections
    assert "punitive 10x compensation" not in formatted


# ---------------------------------------------------------------------------
# Requirement 18: Product-only harm is distinguished from unknown harm scope
# ---------------------------------------------------------------------------
def test_product_only_harm_distinguished_from_unknown_harm_scope():
    # Initial statement without confirmation
    case_unconfirmed = case_builder.create_empty_case(
        original_user_story="I got damaged mobile from Myntra."
    )
    scope_unknown = safety_guard.classify_harm_scope(case_unconfirmed, "I got damaged mobile from Myntra.")
    assert scope_unknown == safety_guard.HARM_SCOPE_UNKNOWN

    # Explicit confirmation of product damage only
    scope_confirmed_explicit = safety_guard.classify_harm_scope(
        case_unconfirmed, "Only the mobile is damaged, no one was injured."
    )
    assert scope_confirmed_explicit == safety_guard.HARM_PRODUCT_DAMAGE_ONLY

    # Formally confirmed case facts
    case_builder.confirm_case_facts(case_unconfirmed)
    scope_confirmed_case = safety_guard.classify_harm_scope(case_unconfirmed)
    assert scope_confirmed_case == safety_guard.HARM_PRODUCT_DAMAGE_ONLY


# ---------------------------------------------------------------------------
# Requirement 19: Reported injury triggers appropriate safety route
# ---------------------------------------------------------------------------
def test_reported_injury_triggers_appropriate_safety_route():
    injury_query = "The mobile battery exploded, causing severe burns to my hand and I was hospitalized in ICU."
    scope = safety_guard.classify_harm_scope(None, injury_query)
    assert scope == safety_guard.HARM_OTHER_REPORTED

    decision = safety_guard.evaluate_turn_safety(injury_query)
    assert decision["classification"] in (
        safety_guard.CATEGORY_HIGH_RISK_LEGAL_REVIEW,
        safety_guard.CATEGORY_URGENT_ESCALATION,
    )
    assert decision["allow_normal_legal_generation"] is False


# ---------------------------------------------------------------------------
# Requirement 20: New grievance isolation preserved
# ---------------------------------------------------------------------------
def test_new_grievance_isolation_preserved():
    # Case 1 setup
    case1 = case_builder.create_empty_case(original_user_story="First grievance about laptop.")
    case_builder.update_case_fact(case1, "purchase_amount", "₹45,000")
    case_builder.update_case_fact(case1, "seller_or_platform", "Amazon")
    case_builder.add_event(case1, "Laptop delivered defective")

    # New Grievance clicked -> Case 2
    case2 = case_builder.create_empty_case(original_user_story="I received a defective mobile phone.")

    assert case2["case_id"] != case1["case_id"]
    assert case2["original_user_story"] == "I received a defective mobile phone."
    assert case2["purchase_amount"] is None
    assert case2["seller_or_platform"] is None
    assert len(case2["events"]) == 0
    assert len(case2["conversation_history"]) == 0
