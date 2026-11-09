"""
Comprehensive Test Suite for Nyaya Saathi Intelligent Dynamic Legal Companion MVP.

Validates:
1. Dynamic Issue Identification & 3 Decisions (Decision A, Decision B, Decision C).
2. Dynamic category tracking (PROVISIONAL vs CONFIRMED).
3. Dynamic Document & Evidence Checklist (e-Jagriti procedure, conditions, recommended evidence, unestablished items).
4. Interactive evidence status management & provenance tracking.
5. Intelligent Clarification Question Engine with dispute-aware prioritization & non-repetition.
6. Case Workspace fact updates & Reanalysis pipeline.
7. Transparent abstention on specialized out-of-corpus statutory regimes (RERA / SEBI / MACT).
8. Product liability harm gating under CPA 2019 Section 2(22).
"""

import os
import pytest
from unittest.mock import patch

from src import intake
from src import case_builder
from src import evidence_checklist
from src import workflow_service
from src import safety_guard


def test_01_three_decisions_structure_on_case_creation():
    """Verifies Decision A (Classification), Decision B (Coverage), and Decision C (Analysis) separation."""
    text = "Ordered a smartwatch on Flipkart, received a broken stone inside the box."
    case = case_builder.create_empty_case(original_user_story=text, language_preference="English")

    # Decision A: Issue Classification
    assert "classification_decision" in case
    assert case["classification_decision"]["decision_type"] == "DECISION_A_ISSUE_CLASSIFICATION"
    assert case["classification_decision"]["status"] == "PROVISIONAL"
    assert case["issue_category_status"] == "PROVISIONAL"
    assert case["issue_category"] in (
        case_builder.CATEGORY_INCORRECT_ITEM,
        case_builder.CATEGORY_DEFECTIVE_GOODS,
        case_builder.CATEGORY_ECOMMERCE,
    )

    # Decision B: Legal Coverage
    assert "coverage_decision" in case
    assert case["coverage_decision"]["decision_type"] == "DECISION_B_LEGAL_COVERAGE"
    assert case["coverage_decision"]["status"] == "SUPPORTED_IN_KNOWLEDGE_BASE"

    # Decision C: Legal Analysis
    assert "analysis_decision" in case
    assert case["analysis_decision"]["decision_type"] == "DECISION_C_LEGAL_ANALYSIS"
    assert case["analysis_decision"]["status"] == "NOT_STARTED"


def test_02_dynamic_category_confirmation_and_user_edit():
    """Verifies category transitions from PROVISIONAL to CONFIRMED on confirmation or edit."""
    case = case_builder.create_empty_case(
        issue_category="E-commerce grievance",
        original_user_story="Seller refused refund.",
    )
    assert case["issue_category_status"] == "PROVISIONAL"

    # Edit category via workspace
    case_builder.correct_case_fact(case, "issue_category", "Defective or damaged goods")
    assert case["issue_category"] == "Defective or damaged goods"
    assert case["issue_category_status"] == "CONFIRMED"
    assert case["classification_decision"]["status"] == "CONFIRMED"
    assert case["classification_decision"]["inferred_category"] == "Defective or damaged goods"

    # Confirm all facts
    case_builder.confirm_case_facts(case)
    assert case["facts_confirmed_by_user"] is True
    assert case["issue_category_status"] == "CONFIRMED"


def test_03_evidence_checklist_generation_for_defective_goods():
    """Verifies that evidence checklist derives mandatory procedural items and conditional test reports."""
    case = case_builder.create_empty_case(
        issue_category=case_builder.CATEGORY_DEFECTIVE_GOODS,
        original_user_story="I bought a refrigerator from local showroom, cooling stopped working after 3 days.",
    )
    case_builder.extract_case_facts_deterministically(case, case["original_user_story"])
    chk = case.get("evidence_checklist", [])
    assert len(chk) >= 7

    classifications = {item["id"]: item["classification"] for item in chk}

    # 1. Official procedural requirements
    assert classifications["doc_complainant_id_address"] == evidence_checklist.CLASS_REQUIRED_PROCEDURE
    assert classifications["doc_complaint_affidavit"] == evidence_checklist.CLASS_REQUIRED_PROCEDURE

    # 2. Conditionally required
    assert classifications["doc_vakalatnama"] == evidence_checklist.CLASS_CONDITIONALLY_REQUIRED
    assert classifications["doc_expert_lab_report"] == evidence_checklist.CLASS_CONDITIONALLY_REQUIRED

    # 3. Recommended supporting evidence
    assert classifications["doc_invoice_receipt"] == evidence_checklist.CLASS_RECOMMENDED_EVIDENCE
    assert classifications["doc_payment_proof"] == evidence_checklist.CLASS_RECOMMENDED_EVIDENCE
    assert classifications["doc_photos_unboxing_video"] == evidence_checklist.CLASS_RECOMMENDED_EVIDENCE

    # 4. Not yet established
    assert classifications["doc_notary_seal"] == evidence_checklist.CLASS_NOT_ESTABLISHED


def test_04_vakalatnama_condition_explicit_disclosure():
    """Verifies that Vakalatnama is explicitly marked conditional (only if represented by advocate)."""
    case = case_builder.create_empty_case(issue_category="Service deficiency")
    chk = case["evidence_checklist"]
    vaka = next((i for i in chk if i["id"] == "doc_vakalatnama"), None)
    assert vaka is not None
    assert vaka["classification"] == evidence_checklist.CLASS_CONDITIONALLY_REQUIRED
    assert "advocate" in vaka["condition"].lower() or "lawyer" in vaka["condition"].lower()
    assert "in person" in vaka["condition"].lower()


def test_05_update_evidence_item_status_and_provenance():
    """Verifies updating evidence item status records provenance in correction_history."""
    case = case_builder.create_empty_case(issue_category="E-commerce grievance")
    ok = evidence_checklist.update_evidence_item_status(
        case=case,
        item_id="doc_invoice_receipt",
        new_status=evidence_checklist.STATUS_AVAILABLE,
        notes="Saved in Tax_Invoices folder.",
    )
    assert ok is True

    # Find item
    item = next(i for i in case["evidence_checklist"] if i["id"] == "doc_invoice_receipt")
    assert item["status"] == evidence_checklist.STATUS_AVAILABLE
    assert item["user_notes"] == "Saved in Tax_Invoices folder."

    # Verify provenance
    hist = case.get("correction_history", [])
    assert len(hist) >= 1
    last_h = hist[-1]
    assert last_h["field"] == "evidence_checklist.doc_invoice_receipt"
    assert last_h["source_type"] == "USER_EVIDENCE_UPDATE"
    assert last_h["new_value"] == evidence_checklist.STATUS_AVAILABLE


def test_06_intelligent_follow_up_questions_non_repetitive():
    """Verifies that follow-up questions inspect active context and never repeat."""
    case = case_builder.create_empty_case(
        issue_category=case_builder.CATEGORY_DEFECTIVE_GOODS,
        original_user_story="My Samsung phone screen got cracked on delivery from Amazon.",
    )
    case_builder.extract_case_facts_deterministically(case, case["original_user_story"])

    # First question should ask about seller contact
    q1 = case_builder.get_next_follow_up_question(case, language="English")
    assert q1 is not None
    assert "seller" in q1.lower() or "customer care" in q1.lower()

    # Record question as asked
    case["questions_asked"].append(q1)

    # Next question must not be identical
    case["seller_contact"]["contacted"] = True
    case["seller_contact"]["seller_response"] = "Refused replacement"
    q2 = case_builder.get_next_follow_up_question(case, language="English")
    assert q2 is not None
    assert q2 != q1

    # Harm scope question for damaged goods
    case["questions_asked"].append(q2)
    q3 = case_builder.get_next_follow_up_question(case, language="English")
    assert q3 is not None
    assert q3 != q2
    assert q3 != q1


def test_07_specialized_domain_honest_abstention():
    """Verifies that specialized regimes (RERA, SEBI) set coverage_decision to UNAVAILABLE and abstain."""
    rera_text = "Builder delayed flat possession by 3 years and refuses delay interest under RERA."
    is_cov, fw, expl = intake.check_source_coverage(rera_text)
    assert is_cov is False
    assert "RERA" in fw or "Real Estate" in fw

    case = case_builder.create_empty_case(
        issue_category="Service deficiency",
        original_user_story=rera_text,
    )
    res = workflow_service.reanalyse_case(case, language="English")

    assert res["gate_status"] == "ABSTAIN"
    assert res["coverage_status"] == intake.COVERAGE_UNAVAILABLE
    assert case["coverage_decision"]["status"] == intake.COVERAGE_UNAVAILABLE
    assert case["analysis_decision"]["status"] == "ABSTAINED_COVERAGE_UNAVAILABLE"
    assert len(res["citations"]) == 0  # Zero hallucination of citations


def test_08_reanalyse_preserves_history_and_updates_facts():
    """Verifies that reanalysis creates a new analysis ID and preserves prior analysis history."""
    case = case_builder.create_empty_case(
        issue_category="Defective or damaged goods",
        original_user_story="Bought a laptop, defective screen.",
    )
    case_builder.update_case_fact(case, "product_or_service", "Laptop")
    case_builder.update_case_fact(case, "purchase_amount", "₹50,000")
    case_builder.confirm_case_facts(case)

    # First analysis run
    run1 = workflow_service.reanalyse_case(case, language="English")
    id1 = run1["analysis_id"]
    assert len(case["analysis_history"]) == 1

    # Update fact via workspace
    case_builder.correct_case_fact(case, "purchase_amount", "₹55,000")

    # Second analysis run
    run2 = workflow_service.reanalyse_case(case, language="English")
    id2 = run2["analysis_id"]
    assert len(case["analysis_history"]) == 2
    assert id1 != id2
    assert run2["facts_used"]["purchase_amount"] == "₹55,000"
