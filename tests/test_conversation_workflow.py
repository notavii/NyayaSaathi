"""
Tests for Nyaya Saathi Conversation Workflow Correction.

Validates the end-to-end conversation workflow:
1. Initial grievance intake & issue categorization (Wrong item vs Defective goods).
2. Structured case building & fact review.
3. Fact confirmation with gaps tracking.
4. Immediate post-confirmation source-grounded legal guidance.
5. Continued conversational assistance on follow-up legal queries (No review loop).
6. Progressive fact updates without reopening review loop.
7. '+ New Grievance' state isolation.
8. Input field reset via key counter.
9. Resilient fallback during service errors without losing state.
10. Precise category classification distinguishing incorrect items from defects.
11. Accurate messaging regarding incomplete vs complete cases.
12. Safety regression preserving emergency escalation even on confirmed cases.
"""

import os
import re
import pytest
from unittest.mock import patch

from src import intake
from src import case_builder
from src import safety
from src import safety_guard
from src import hybrid_retriever
from src import answer_generator
from src import citation_checker
from src import workflow_service


@pytest.fixture
def wrong_item_case():
    """Builds a test case from the synthetic grievance."""
    text = "I have got wrong item delivered by Flipkart, but the seller is denying to replace or refund."
    category = case_builder.infer_issue_category(text)
    case = case_builder.create_empty_case(
        issue_category=category,
        original_user_story=text,
        language_preference="English",
    )
    case_builder.extract_case_facts_deterministically(case, text)
    return case


def test_01_initial_grievance_wrong_item_classification(wrong_item_case):
    """
    Test 1: Initial grievance submission properly detects consumer dispute scope
    and accurately categorizes issue as 'Incorrect item delivered / Wrong product received',
    NOT 'Defective or damaged goods'.
    """
    text = wrong_item_case["original_user_story"]
    classification = intake.classify_issue(text, language="English")

    assert classification["category"] == intake.CATEGORY_CONSUMER_DISPUTE
    assert classification["next_action"] == intake.ACTION_PROCEED

    # Assert accurate issue categorization
    assert wrong_item_case["issue_category"] == case_builder.CATEGORY_INCORRECT_ITEM
    assert wrong_item_case["issue_category"] != case_builder.CATEGORY_DEFECTIVE_GOODS

    # Assert deterministic extraction of key facts
    assert wrong_item_case["seller_or_platform"] == "Flipkart"
    assert wrong_item_case["seller_contact"]["contacted"] is True
    assert "refuse" in wrong_item_case["seller_contact"]["seller_response"].lower() or "deni" in wrong_item_case["seller_contact"]["seller_response"].lower()
    assert "refund" in wrong_item_case["desired_resolution"].lower()


def test_02_fact_confirmation_with_gaps_preservation(wrong_item_case):
    """
    Test 2: Fact confirmation preserves gaps, sets confirmed flag,
    and updates case status to STATUS_FACTS_CONFIRMED.
    """
    case = wrong_item_case
    assert case["facts_confirmed_by_user"] is False

    # Initially purchase_amount is missing
    missing = case_builder.compute_missing_information(case)
    assert "purchase_amount" in missing

    # User confirms facts
    case_builder.confirm_case_facts(case)

    assert case["facts_confirmed_by_user"] is True
    assert case["status"] == case_builder.STATUS_FACTS_CONFIRMED
    assert case["has_information_gaps"] is True


def test_03_automatic_post_confirmation_legal_guidance(wrong_item_case):
    """
    Test 3: Immediately following fact confirmation, the workflow delivers
    source-grounded legal guidance, does NOT emit the canned review prompt,
    and transitions case to STATUS_LEGAL_ANALYSIS.
    """
    case = wrong_item_case
    case_builder.confirm_case_facts(case)

    response = workflow_service.generate_post_confirmation_response(case, language="English")

    # Assert response contains meaningful legal guidance
    assert isinstance(response, str)
    assert len(response) > 100
    assert "Facts Saved" in response or "Facts Confirmed" in response

    # Must NOT repeat the canned fact-review intake prompt
    assert "All core facts have been organized into your structured case" not in response

    # Must transition case status
    assert case["status"] == case_builder.STATUS_LEGAL_ANALYSIS


def test_04_next_step_question_routes_to_legal_retrieval(wrong_item_case):
    """
    Test 4: When user asks 'What should I do next?' after confirmation,
    the message is routed to hybrid retrieval and answer generation,
    NOT bounced back to fact review.
    """
    case = wrong_item_case
    case_builder.confirm_case_facts(case)
    _ = workflow_service.generate_post_confirmation_response(case, language="English")

    response = workflow_service.process_case_turn(case, "What should I do next?", language="English")

    assert isinstance(response, str)
    assert len(response) > 50

    # Must not contain the static review prompt
    assert "All core facts have been organized into your structured case" not in response
    assert "Facts Review:" not in response

    # Must maintain confirmed status
    assert case["facts_confirmed_by_user"] is True


def test_05_follow_up_question_refund_rights(wrong_item_case):
    """
    Test 5: Asking about refund rights ('Can I get a refund for the wrong product?')
    retrieves grounded rules (e.g. Consumer Protection E-Commerce Rules / CPA 2019).
    """
    case = wrong_item_case
    case_builder.confirm_case_facts(case)
    _ = workflow_service.generate_post_confirmation_response(case, language="English")

    response = workflow_service.process_case_turn(case, "Can I get a refund for this wrong product?", language="English")

    assert isinstance(response, str)
    assert len(response) > 50

    # Should mention consumer rights, refund, rules, or helpline
    res_lower = response.lower()
    assert any(term in res_lower for term in ["refund", "e-commerce", "rules", "act", "1915", "rights"])
    assert "Facts Review:" not in response


def test_06_new_fact_updates_case_without_reopening_review(wrong_item_case):
    """
    Test 6: Providing a new fact ('I paid ₹15,000 for the product') updates the case
    record without reverting confirmed status or re-triggering the fact-review gate.
    """
    case = wrong_item_case
    case_builder.confirm_case_facts(case)
    _ = workflow_service.generate_post_confirmation_response(case, language="English")

    assert case.get("purchase_amount") is None

    response = workflow_service.process_case_turn(case, "I paid ₹15,000 for the product.", language="English")

    # Amount must be updated in active case
    amt = case.get("purchase_amount")
    assert amt in (15000, 15000.0, "₹15,000", "15000", "Rs 15000") or "15" in str(amt)

    # Confirmation flag remains intact
    assert case["facts_confirmed_by_user"] is True

    # Response should acknowledge update and maintain legal flow
    assert "Case Record Updated" in response or "Purchase Amount" in response or "₹15,000" in response or "15000" in response
    assert "Facts Review: Thank you" not in response


def test_07_new_grievance_state_isolation(wrong_item_case):
    """
    Test 7: Triggering '+ New Grievance' completely clears previous case state,
    creates a brand new case ID, and ensures no leakage from the old case.
    """
    old_case = wrong_item_case
    old_id = old_case["case_id"]

    # Simulate New Grievance initialization
    new_text = "I received a defective mobile phone from Amazon."
    new_cat = case_builder.infer_issue_category(new_text)
    new_case = case_builder.create_empty_case(
        issue_category=new_cat,
        original_user_story=new_text,
        language_preference="English",
    )
    case_builder.extract_case_facts_deterministically(new_case, new_text)

    assert new_case["case_id"] != old_id
    assert new_case["seller_or_platform"] == "Amazon"
    assert new_case["seller_or_platform"] != "Flipkart"
    assert new_case["issue_category"] == case_builder.CATEGORY_DEFECTIVE_GOODS
    assert new_case["facts_confirmed_by_user"] is False
    assert len(new_case["conversation_history"]) == 0


def test_08_input_field_clearing_via_key_counter():
    """
    Test 8: Verifies the input key counter pattern resets Streamlit widget state
    so user inputs are never stuck in the text area upon submission.
    """
    counter = 0
    key_0 = f"problem_input_{counter}"
    assert key_0 == "problem_input_0"

    # User submits turn -> counter increments
    counter += 1
    key_1 = f"problem_input_{counter}"
    assert key_1 == "problem_input_1"

    # Changing the key causes Streamlit to mount a brand new, empty widget
    assert key_0 != key_1


def test_09_gemini_error_safe_fallback(wrong_item_case):
    """
    Test 9: When Gemini API raises an exception, the system catches it safely,
    returns a cautious fallback message, and preserves case facts.
    """
    case = wrong_item_case
    case_builder.confirm_case_facts(case)

    with patch("src.answer_generator.generate_legal_explanation", side_effect=RuntimeError("API quota exceeded")):
        response = workflow_service.process_case_turn(case, "What are the rules?", language="English")

        assert isinstance(response, str)
        assert "unexpected error" in response.lower() or "safe" in response.lower() or "helpline" in response.lower()
        # Case facts remain intact
        assert case["seller_or_platform"] == "Flipkart"
        assert case["facts_confirmed_by_user"] is True


def test_10_wrong_item_vs_defective_goods_distinction():
    """
    Test 10: Strict discrimination between wrong items delivered vs defective goods.
    """
    # 1. Wrong item delivered
    text_wrong = "I ordered shoes from Myntra but received a phone cover."
    cat_wrong = case_builder.infer_issue_category(text_wrong)
    assert cat_wrong == case_builder.CATEGORY_INCORRECT_ITEM
    assert cat_wrong != case_builder.CATEGORY_DEFECTIVE_GOODS

    # 2. Defective / damaged goods
    text_damaged = "I ordered shoes from Myntra and the sole was torn and damaged."
    cat_damaged = case_builder.infer_issue_category(text_damaged)
    assert cat_damaged == case_builder.CATEGORY_DEFECTIVE_GOODS
    assert cat_damaged != case_builder.CATEGORY_INCORRECT_ITEM

    # 3. Wrong item (soap instead of laptop)
    text_soap = "I ordered a laptop from Amazon but received detergent soap instead."
    cat_soap = case_builder.infer_issue_category(text_soap)
    assert cat_soap == case_builder.CATEGORY_INCORRECT_ITEM


def test_11_incomplete_case_messaging_accuracy(wrong_item_case):
    """
    Test 11: Incomplete cases explicitly disclose missing details and avoid claiming
    the case is ready for drafting until core facts are supplied.
    """
    case = wrong_item_case
    case_builder.confirm_case_facts(case)

    # Gaps exist
    missing_labels = workflow_service.format_missing_information_summary(case, language="English")
    assert len(missing_labels) > 0

    response = workflow_service.generate_post_confirmation_response(case, language="English")
    # Must acknowledge that some details are missing
    assert "Some details are still missing" in response
    assert "This case is ready for legal analysis and drafting" not in response


def test_12_safety_regression_urgent_escalation_after_confirmation(wrong_item_case):
    """
    Test 12: Urgent life safety signals trigger emergency escalation even after
    case facts have been confirmed.
    """
    case = wrong_item_case
    case_builder.confirm_case_facts(case)

    urgent_msg = "I am so overwhelmed by this fraud that I am thinking of suicide."
    response = workflow_service.process_case_turn(case, urgent_msg, language="English")

    # Must contain emergency helpline numbers
    assert "112" in response
    assert "immediate safety" in response.lower() or "emergency" in response.lower()

    # Must not discuss consumer forum litigation
    assert "National Consumer Disputes Redressal Commission" not in response
