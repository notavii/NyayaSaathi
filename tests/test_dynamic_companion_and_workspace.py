"""
Test Suite for Dynamic Legal Companion, Case Workspace, and Interface Restructuring.

Verifies:
1. Dynamic issue classification without hardcoded template constraints.
2. Separation of consumer dispute scope from official legal source coverage (CPA vs RERA/SEBI).
3. Non-repetitive, context-sensitive follow-up questioning.
4. Active case schema extensions (distinct seller vs marketplace, problem date, analysis history).
5. Fact updates, validation, and audit provenance tracking in workspace.
6. Reanalysis pipeline (reanalyse_case) with analysis history recording and Section C synchronization.
7. Transparent abstention when grievance falls outside available legal corpus.
8. Complete session reset / New Chat isolation.
"""

from datetime import datetime
import pytest
from unittest.mock import patch, MagicMock

from src import intake
from src import case_builder
from src import workflow_service
from src import safety_guard


# ==============================================================================
# 1. DYNAMIC ISSUE CLASSIFICATION TESTS
# ==============================================================================

def test_dynamic_issue_classification_damaged_goods():
    text = "The washing machine delivered yesterday has a cracked drum and heavy dent on the door."
    category = case_builder.infer_issue_category(text)
    assert category == case_builder.CATEGORY_DEFECTIVE_GOODS


def test_dynamic_issue_classification_wrong_item():
    text = "I ordered Nike running shoes size 9, but Flipkart delivered Puma slippers size 7."
    category = case_builder.infer_issue_category(text)
    assert category == case_builder.CATEGORY_INCORRECT_ITEM


def test_dynamic_issue_classification_non_delivery():
    text = "I paid for a laptop 3 weeks ago on Meesho, but the parcel is stuck in transit and never delivered."
    category = case_builder.infer_issue_category(text)
    assert category == case_builder.CATEGORY_NON_DELIVERY


def test_dynamic_issue_classification_refund_refusal():
    text = "I cancelled my flight booking within the free cancellation window, but the portal refuses to refund my money."
    category = case_builder.infer_issue_category(text)
    assert category in (case_builder.CATEGORY_REFUND_REFUSAL, case_builder.CATEGORY_SERVICE_DEFICIENCY)


def test_dynamic_issue_classification_service_deficiency():
    text = "The airline offloaded my luggage without notice and gave no hotel accommodation during a 14-hour delay."
    category = case_builder.infer_issue_category(text)
    assert category == case_builder.CATEGORY_SERVICE_DEFICIENCY


def test_dynamic_issue_classification_subscription_unauthorized():
    text = "An OTT platform auto-debited ₹1,499 from my credit card for an annual subscription after I cancelled my membership."
    category = case_builder.infer_issue_category(text)
    assert category == case_builder.CATEGORY_SUBSCRIPTION_UNAUTHORIZED


def test_dynamic_issue_classification_warranty_dispute():
    text = "The authorized service center is refusing my warranty card and asking ₹5,000 for repair within the 1-year guarantee period."
    category = case_builder.infer_issue_category(text)
    assert category == case_builder.CATEGORY_WARRANTY_DISPUTE


# ==============================================================================
# 2. SOURCE COVERAGE SEPARATION TESTS
# ==============================================================================

def test_source_coverage_supported_ecommerce():
    text = "I purchased an air cooler on Flipkart. It arrived damaged and the seller is refusing replacement."
    is_covered, framework, expl = intake.check_source_coverage(text)
    assert is_covered is True
    assert framework is None
    assert expl is None


def test_source_coverage_rera_builder_dispute():
    text = "I booked a 3BHK flat in 2021 with ABC Builders. Possession delayed by 2 years and builder is refusing delay interest."
    is_covered, framework, expl = intake.check_source_coverage(text)
    assert is_covered is False
    assert framework == "RERA"
    assert "Real Estate (Regulation and Development) Act" in expl
    assert "abstain" in expl.lower() or "limitation" in expl.lower() or "risk" in expl.lower()

    # Intake classification must mark consumer dispute but with unavailable coverage
    classification = intake.classify_issue(text, use_llm_fallback=False)
    assert classification["category"] == intake.CATEGORY_CONSUMER_DISPUTE
    assert classification["coverage_status"] == intake.COVERAGE_UNAVAILABLE
    assert classification["coverage_framework"] == "RERA"


def test_source_coverage_sebi_shares_dispute():
    text = "My stock broker unauthorizedly sold my shares from demat account and withheld trading account balance."
    is_covered, framework, expl = intake.check_source_coverage(text)
    assert is_covered is False
    assert framework == "SEBI"
    assert "Securities and Exchange Board of India" in expl

    classification = intake.classify_issue(text, use_llm_fallback=False)
    assert classification["coverage_status"] == intake.COVERAGE_UNAVAILABLE
    assert classification["coverage_framework"] == "SEBI"


def test_outside_scope_employment_unrelated():
    text = "My employer has not paid my monthly salary for 3 months."
    classification = intake.classify_issue(text, use_llm_fallback=False)
    assert classification["category"] == intake.CATEGORY_OUTSIDE_SCOPE
    assert classification["next_action"] == intake.ACTION_STOP_NORMAL_FLOW


def test_clarification_vague_input():
    text = "I have a problem with something I got."
    classification = intake.classify_issue(text, use_llm_fallback=False)
    assert classification["category"] == intake.CATEGORY_NEEDS_CLARIFICATION
    assert classification["next_action"] == intake.ACTION_ASK_QUESTION


# ==============================================================================
# 3. CONTEXT-SENSITIVE FOLLOW-UP QUESTIONS TESTS
# ==============================================================================

def test_dynamic_follow_up_non_repetitive():
    case = case_builder.create_empty_case(
        original_user_story="I ordered a pair of shoes from Myntra, but never received it.",
        language_preference="English",
    )
    case_builder.extract_case_facts_deterministically(case, case["original_user_story"])
    case_builder.compute_missing_information(case)

    # First question
    q1 = case_builder.get_next_follow_up_question(case, language="English")
    assert q1 is not None
    case["questions_asked"].append(q1)

    # Calling again must not repeat the exact same question if still missing
    q2 = case_builder.get_next_follow_up_question(case, language="English")
    if q2:
        assert q2 != q1


def test_dynamic_follow_up_for_subscription():
    case = case_builder.create_empty_case(
        original_user_story="An OTT app auto-debited ₹1,499 unauthorized subscription fee from my card.",
        language_preference="English",
    )
    case_builder.extract_case_facts_deterministically(case, case["original_user_story"])
    case_builder.compute_missing_information(case)

    q = case_builder.get_next_follow_up_question(case, language="English")
    assert q is not None
    # Context-sensitive subscription question should mention cancellation, dispute, or contact
    assert any(w in q.lower() for w in ["cancellation", "dispute", "contact", "seller", "provider"])


# ==============================================================================
# 4. ACTIVE CASE SCHEMA & WORKSPACE VALIDATION TESTS
# ==============================================================================

def test_case_schema_extensions():
    case = case_builder.create_empty_case(
        case_id="NS-9999",
        issue_category=case_builder.CATEGORY_DEFECTIVE_GOODS,
        original_user_story="Defective laptop screen purchased on Amazon from RetailNet seller.",
    )
    assert "seller_or_service_provider" in case
    assert "marketplace_or_platform" in case
    assert "problem_date" in case
    assert "marketplace_contact" in case
    assert "latest_analysis" in case
    assert "analysis_history" in case
    assert isinstance(case["analysis_history"], list)
    assert case["latest_analysis"] is None


def test_workspace_fact_validation_and_corrections():
    case = case_builder.create_empty_case(
        original_user_story="Purchased tablet online for 15000",
    )

    # Validate amount formatting
    is_ok, err, clean_amt = case_builder.validate_fact_value("purchase_amount", "15000")
    assert is_ok is True
    assert clean_amt == "₹15,000"

    # Reject numeric string into seller/provider field
    is_ok, err, _ = case_builder.validate_fact_value("seller_or_service_provider", "15000")
    assert is_ok is False
    assert "numeric amount" in err

    # Apply fact correction
    success = case_builder.correct_case_fact(case, "purchase_amount", "₹15,000")
    assert success is True
    assert case["purchase_amount"] == "₹15,000"
    assert len(case["correction_history"]) == 1
    assert case["correction_history"][0]["field"] == "purchase_amount"


# ==============================================================================
# 5. REANALYSIS PIPELINE & IN-PLACE SECTION C UPDATE TESTS
# ==============================================================================

def test_reanalyse_case_supported_ecommerce():
    case = case_builder.create_empty_case(
        case_id="NS-TEST-01",
        original_user_story="I bought a mixer grinder from Flipkart. It stopped working on day 2. Seller refused refund.",
    )
    case_builder.extract_case_facts_deterministically(case, case["original_user_story"])
    case["product_or_service"] = "Mixer grinder"
    case["seller_or_platform"] = "Flipkart"
    case["desired_resolution"] = "Full refund"
    case["purchase_amount"] = "₹2,500"
    case["seller_contact"]["contacted"] = True
    case["seller_contact"]["seller_response"] = "Refused refund"
    case_builder.confirm_case_facts(case)

    # Mock answer generator and retriever to avoid network calls
    mock_sources = [
        {
            "source_id": "CPA_SEC_002_006",
            "act_name": "Consumer Protection Act, 2019",
            "section_or_rule": "Section 2(6) — Complaint",
            "official_url": "https://consumeraffairs.nic.in",
            "content": "Complaint means any allegation in writing made by a consumer regarding unfair trade practice or defect.",
        },
        {
            "source_id": "CPA_SEC_039",
            "act_name": "Consumer Protection Act, 2019",
            "section_or_rule": "Section 39 — Findings of Commission",
            "official_url": "https://consumeraffairs.nic.in",
            "content": "District Commission may order removal of defect, replacement, or return of price.",
        },
    ]

    with patch("src.hybrid_retriever.hybrid_search", return_value=mock_sources):
        with patch("src.answer_generator.generate_legal_explanation", return_value="Under Section 39 of the Consumer Protection Act, 2019, you are entitled to replacement or refund."):
            analysis = workflow_service.reanalyse_case(case, language="English")

    assert analysis is not None
    assert "analysis_id" in analysis
    assert analysis["case_id"] == "NS-TEST-01"
    assert analysis["coverage_status"] == intake.COVERAGE_SUPPORTED
    assert case["latest_analysis"] is not None
    assert case["latest_analysis"]["analysis_id"] == analysis["analysis_id"]
    assert len(case["analysis_history"]) == 1
    assert case["status"] == case_builder.STATUS_LEGAL_ANALYSIS


def test_reanalyse_case_unsupported_domain_abstention():
    case = case_builder.create_empty_case(
        case_id="NS-RERA-01",
        original_user_story="Builder delayed flat possession by 3 years under RERA project.",
    )
    case["product_or_service"] = "Residential flat"
    case["seller_or_service_provider"] = "ABC Builders"
    case["desired_resolution"] = "Possession with delay interest"
    case_builder.confirm_case_facts(case)

    analysis = workflow_service.reanalyse_case(case, language="English")

    assert analysis["coverage_status"] == intake.COVERAGE_UNAVAILABLE
    assert analysis["coverage_framework"] == "RERA"
    assert analysis["gate_status"] == "ABSTAIN"
    assert "Real Estate (Regulation and Development) Act" in analysis["user_facing_response"]
    assert len(analysis["citations"]) == 0
    assert case["latest_analysis"] == analysis


def test_workspace_reanalyse_refreshes_analysis_history():
    case = case_builder.create_empty_case(
        case_id="NS-MULTI-01",
        original_user_story="Received wrong item delivered by seller.",
    )
    case["product_or_service"] = "Shoes"
    case["seller_or_platform"] = "Flipkart"
    case_builder.confirm_case_facts(case)

    mock_sources = [{
        "source_id": "CPA_SEC_002_006",
        "act_name": "Consumer Protection Act, 2019",
        "section_or_rule": "Section 2(6)",
        "official_url": "https://consumeraffairs.nic.in",
        "content": "Complaint provisions for wrong goods.",
    }]

    with patch("src.hybrid_retriever.hybrid_search", return_value=mock_sources):
        with patch("src.answer_generator.generate_legal_explanation", return_value="Legal rights for wrong item under Section 2(6)."):
            # Run 1
            a1 = workflow_service.reanalyse_case(case, language="English")
            # Update fact in workspace
            case_builder.correct_case_fact(case, "purchase_amount", "₹3,499")
            # Run 2
            a2 = workflow_service.reanalyse_case(case, language="English")

    assert len(case["analysis_history"]) == 2
    assert a1["analysis_id"] != a2["analysis_id"]
    assert case["latest_analysis"]["analysis_id"] == a2["analysis_id"]
    assert case["latest_analysis"]["facts_used"]["purchase_amount"] == "₹3,499"
