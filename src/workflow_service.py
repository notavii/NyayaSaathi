"""
Conversation Workflow Service for Nyaya Saathi.

Manages post-confirmation transitions, legal companion response generation,
and turn routing between intake, fact review, legal analysis, and user follow-up questions.

Pipeline:
active_case_context
→ hybrid_retriever
→ answer_generator
→ citation_checker
→ abstention
→ final_safety_gate
→ user-facing response
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from src import abstention
from src import answer_generator
from src import case_builder
from src import citation_checker
from src import hybrid_retriever
from src import intake
from src import safety_guard

logger = logging.getLogger("workflow_service")


# Three-state product liability harm constants
HARM_PRODUCT_DAMAGE_ONLY = safety_guard.HARM_PRODUCT_DAMAGE_ONLY
HARM_OTHER_REPORTED = safety_guard.HARM_OTHER_REPORTED
HARM_SCOPE_UNKNOWN = safety_guard.HARM_SCOPE_UNKNOWN
classify_harm_scope = safety_guard.classify_harm_scope


def is_harm_limited_to_product(case: Optional[Dict[str, Any]], query: str = "") -> bool:
    """
    Evaluates whether harm is strictly limited to the product itself under CPA 2019 Section 2(22).
    Delegates to safety_guard.classify_harm_scope to maintain three-state classification:
    PRODUCT_DAMAGE_ONLY_CONFIRMED, OTHER_HARM_REPORTED, and HARM_SCOPE_UNKNOWN.
    Returns True when harm is confined to the product itself or unclarified, excluding product liability.
    """
    scope = safety_guard.classify_harm_scope(case, query)
    return scope != safety_guard.HARM_OTHER_REPORTED


def format_missing_information_summary(case: Dict[str, Any], language: str = "English") -> List[str]:
    """Returns human-readable labels for missing information fields."""
    is_hindi = language.lower() in ("hindi", "hinglish", "hindi/hinglish")
    missing_items = []

    if not case.get("product_or_service"):
        missing_items.append("उत्पाद का नाम / मॉडल (Product ordered / received)" if is_hindi else "Product ordered / Product received")
    if not case.get("purchase_amount"):
        missing_items.append("भुगतान की गई राशि (Purchase amount)" if is_hindi else "Amount paid (INR)")
    if not case.get("purchase_date") and not case.get("delivery_date"):
        missing_items.append("ऑर्डर या डिलीवरी की तारीख (Order or delivery date)" if is_hindi else "Order or purchase date")
    sc = case.get("seller_contact", {})
    if not sc.get("seller_response"):
        missing_items.append("विक्रेता का लिखित जवाब (Seller / platform formal response)" if is_hindi else "Seller / platform formal response")
    if not case.get("evidence"):
        missing_items.append("उपलब्ध सबूत जैसे इनवॉइस, फोटो (Evidence available)" if is_hindi else "Available evidence (invoice, package photos)")

    return missing_items


def reanalyse_case(
    case: Dict[str, Any],
    language: str = "English",
) -> Dict[str, Any]:
    """
    Executes a comprehensive, fact-driven legal reanalysis for the active case record.
    1. Evaluates official knowledge base source coverage (e.g. CPA 2019 vs specialized RERA/TRAI/SEBI).
    2. Builds search query from active facts (product, platform, category, problem, resolution).
    3. Evaluates Section 2(22) harm boundary to prevent misapplying product liability.
    4. Executes hybrid retrieval (semantic + BM25 via RRF).
    5. Synthesizes legal explanation via Gemini.
    6. Verifies statutory citations and applies final safety gate.
    7. Appends full analysis record to case["analysis_history"] and updates case["latest_analysis"].

    Returns:
        analysis_record: Dict[str, Any]
    """
    cid = case.get("case_id", "NS-0000")
    now_iso = datetime.now().isoformat()
    analysis_count = len(case.get("analysis_history", [])) + 1
    analysis_id = f"ANL-{cid}-{analysis_count:02d}-{datetime.now().strftime('%H%M%S')}"

    facts_used = {
        "issue_category": case.get("issue_category"),
        "product_or_service": case.get("product_or_service"),
        "seller_or_platform": case.get("seller_or_platform"),
        "seller_or_service_provider": case.get("seller_or_service_provider"),
        "marketplace_or_platform": case.get("marketplace_or_platform"),
        "purchase_amount": case.get("purchase_amount"),
        "purchase_date": case.get("purchase_date"),
        "delivery_date": case.get("delivery_date"),
        "problem_date": case.get("problem_date"),
        "desired_resolution": case.get("desired_resolution"),
        "seller_contact": dict(case.get("seller_contact", {})),
        "marketplace_contact": dict(case.get("marketplace_contact", {})),
    }

    # Step A: Evaluate source coverage
    dispute_text = case.get("original_user_story", "")
    is_covered, framework, coverage_expl = intake.check_source_coverage(dispute_text)

    # Refresh dynamic evidence checklist
    try:
        from src import evidence_checklist
        case["evidence_checklist"] = evidence_checklist.generate_case_evidence_checklist(case)
    except Exception as exc:
        logger.warning(f"Could not refresh evidence checklist during reanalysis: {exc}")

    if not is_covered:
        analysis_record = {
            "analysis_id": analysis_id,
            "case_id": cid,
            "timestamp": now_iso,
            "facts_used": facts_used,
            "retrieved_source_ids": [],
            "citations": [],
            "validation_status": "ABSTAINED_COVERAGE_UNAVAILABLE",
            "gate_status": "ABSTAIN",
            "coverage_status": intake.COVERAGE_UNAVAILABLE,
            "coverage_framework": framework,
            "user_facing_response": coverage_expl,
            "structured_answer": {
                "understanding_of_your_problem": dispute_text,
                "what_the_source_says": coverage_expl,
                "how_it_may_relate_to_your_problem": "Governed by a specialized statutory framework not currently indexed in Nyaya Saathi.",
                "possible_next_steps": ["Approach the competent specialized authority or regulatory portal."],
                "limitations_and_uncertainties": ["Statutory source coverage is unavailable for this specialized domain in Nyaya Saathi."],
            },
            "raw_answer": coverage_expl,
        }
        case.setdefault("analysis_history", []).append(analysis_record)
        case["latest_analysis"] = analysis_record
        case["status"] = case_builder.STATUS_LEGAL_ANALYSIS
        case["coverage_decision"] = {
            "status": intake.COVERAGE_UNAVAILABLE,
            "framework": framework,
            "decision_type": "DECISION_B_LEGAL_COVERAGE",
        }
        case["analysis_decision"] = {
            "status": "ABSTAINED_COVERAGE_UNAVAILABLE",
            "analysis_id": analysis_id,
            "decision_type": "DECISION_C_LEGAL_ANALYSIS",
            "timestamp": now_iso,
        }
        return analysis_record

    # Step B: Build query from active case facts
    platform = case.get("seller_or_platform") or case.get("marketplace_or_platform") or ""
    category = case.get("issue_category", "")
    product = case.get("product_or_service") or ""
    resolution = case.get("desired_resolution") or ""
    search_query = f"{category} {platform} {product} {dispute_text} {resolution}".strip()

    # Step C: Evaluate harm scope
    harm_product_only = is_harm_limited_to_product(case, search_query)

    # Step D: Hybrid Retrieval
    try:
        retrieved_sources = hybrid_retriever.hybrid_search(
            query=search_query,
            top_k=5,
            include_procedural=True,
            exclude_product_liability=harm_product_only,
        )
    except Exception as e:
        logger.error(f"Error in hybrid retrieval during reanalysis: {e}")
        retrieved_sources = []

    # Step E: Answer generation
    try:
        gen_answer = answer_generator.generate_legal_explanation(
            user_question=f"What are my legal rights and next steps for: {dispute_text}",
            confirmed_case=case,
            retrieved_sources=retrieved_sources,
            language=language,
        )

        val_report = citation_checker.validate_legal_answer(
            gen_answer,
            retrieved_sources=retrieved_sources,
        )

        gate_decision = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_report,
            case=case,
            retrieved_sources=retrieved_sources,
            language=language,
        )

        explanation_body = gate_decision["user_facing_response"]
        citations = val_report.get("citations", [])
        val_status = val_report.get("status")
        gate_status = gate_decision.get("gate_status")

    except Exception as exc:
        logger.error(f"Error in answer generation during reanalysis: {exc}")
        is_hindi = language.lower() in ("hindi", "hinglish", "hindi/hinglish")
        if is_hindi:
            explanation_body = (
                "⚠️ कानूनी विश्लेषण तैयार करते समय एक तकनीकी समस्या आई। आपके तथ्य सुरक्षित हैं। "
                "कृपया राष्ट्रीय उपभोक्ता हेल्पलाइन 1915 पर संपर्क करें अथवा कुछ देर बाद पुनः प्रयास करें।"
            )
        else:
            explanation_body = (
                "⚠️ A technical error occurred while preparing the legal explanation. Your case facts are safe. "
                "You may contact the National Consumer Helpline at 1915 (consumerhelpline.gov.in) or try asking your question again."
            )
        citations = []
        val_status = "ERROR"
        gate_status = "ERROR"
        gen_answer = explanation_body

    retrieved_ids = [s.get("source_id") or s.get("id") for s in retrieved_sources if isinstance(s, dict)]
    structured_ans = gate_decision.get("safe_structured_answer", {}) if "gate_decision" in locals() and isinstance(gate_decision, dict) else (gen_answer if isinstance(gen_answer, dict) else {})
    analysis_record = {
        "analysis_id": analysis_id,
        "case_id": cid,
        "timestamp": now_iso,
        "facts_used": facts_used,
        "retrieved_source_ids": retrieved_ids,
        "citations": citations,
        "validation_status": val_status,
        "gate_status": gate_status,
        "coverage_status": intake.COVERAGE_SUPPORTED,
        "coverage_framework": "CPA_2019_ECOMMERCE",
        "user_facing_response": explanation_body,
        "structured_answer": structured_ans,
        "raw_answer": gen_answer,
    }

    case.setdefault("analysis_history", []).append(analysis_record)
    case["latest_analysis"] = analysis_record
    case["status"] = case_builder.STATUS_LEGAL_ANALYSIS
    case["coverage_decision"] = {
        "status": intake.COVERAGE_SUPPORTED,
        "framework": "Consumer Protection Act, 2019 & E-Commerce Rules, 2020",
        "decision_type": "DECISION_B_LEGAL_COVERAGE",
    }
    case["analysis_decision"] = {
        "status": "COMPLETED",
        "analysis_id": analysis_id,
        "gate_status": gate_status,
        "decision_type": "DECISION_C_LEGAL_ANALYSIS",
        "timestamp": now_iso,
    }
    return analysis_record


def generate_post_confirmation_response(
    case: Dict[str, Any],
    language: str = "English",
) -> str:
    """
    Generates the initial legal companion response immediately following fact confirmation.
    Transitions workflow from FACTS_CONFIRMED/FACTS_CONFIRMED_WITH_GAPS to LEGAL_ANALYSIS.
    Delegates to reanalyse_case to maintain a unified source of truth in case['latest_analysis'].
    """
    is_hindi = language.lower() in ("hindi", "hinglish", "hindi/hinglish")
    missing_gaps = format_missing_information_summary(case, language=language)

    # Perform full reanalysis pipeline
    analysis = reanalyse_case(case, language=language)
    explanation_body = analysis["user_facing_response"]

    # Header acknowledgement
    if missing_gaps:
        if is_hindi:
            ack = (
                "✅ **तथ्य सहेज लिए गए हैं (Facts Saved):** आपके द्वारा समीक्षा किए गए तथ्य दर्ज कर लिए गए हैं। "
                "हालाँकि कुछ महत्वपूर्ण विवरण अभी भी शेष हैं। आधिकारिक स्रोतों के आधार पर सामान्य अगले कदम नीचे दिए गए हैं:\n\n"
            )
        else:
            ack = (
                "✅ **Facts Saved:** Your reviewed facts have been saved. Some details are still missing. "
                "Nyaya Saathi can explain the general next steps using the available official sources, while we collect the remaining information:\n\n"
            )
    else:
        if is_hindi:
            ack = (
                "✅ **तथ्य प्रमाणित (Facts Confirmed):** आपके मामले के सभी मुख्य विवरण सफलतापूर्वक प्रमाणित कर लिए गए हैं। "
                "आधिकारिक कानूनी प्रावधानों के आधार पर विश्लेषण नीचे प्रस्तुत है:\n\n"
            )
        else:
            ack = (
                "✅ **Facts Confirmed:** All core facts in your case record have been verified. "
                "Here is the source-grounded legal information based on verified official provisions:\n\n"
            )

    # Follow-up missing question (At most 1-2 focused questions)
    gap_prompt = ""
    if missing_gaps:
        top_missing = missing_gaps[:2]
        if is_hindi:
            gap_prompt = (
                f"\n\n👉 **अपेक्षित जानकारी:** सटीक कानूनी उपाय और फोरम क्षेत्राधिकार निर्धारित करने के लिए, "
                f"कृपया बताएं: **{', '.join(top_missing)}**"
            )
        else:
            gap_prompt = (
                f"\n\n👉 **Pending Information:** To help evaluate jurisdiction and specific remedies, "
                f"could you please share: **{', '.join(top_missing)}**?"
            )

    # Update case status
    case["status"] = case_builder.STATUS_LEGAL_ANALYSIS

    return ack + explanation_body + gap_prompt


def process_case_turn(
    case: Dict[str, Any],
    user_message: str,
    language: str = "English",
) -> str:
    """
    Processes subsequent user inquiries or new facts for an active case.
    Ensures confirmed cases are routed into legal retrieval and NOT bounced back to fact review.
    """
    clean_msg = user_message.strip()
    is_hindi = language.lower() in ("hindi", "hinglish", "hindi/hinglish")

    # 1. Evaluate Turn Safety
    turn_safety = safety_guard.evaluate_turn_safety(
        user_message=clean_msg,
        active_case=case,
        conversation_history=case.get("conversation_history", []),
        language=language,
    )
    if turn_safety["classification"] in (
        safety_guard.CATEGORY_URGENT_ESCALATION,
        safety_guard.CATEGORY_HIGH_RISK_LEGAL_REVIEW,
        safety_guard.CATEGORY_OUTSIDE_SCOPE,
    ):
        return turn_safety["user_message"]

    # 2. Extract any newly provided facts from user message (e.g. amounts, evidence, dates)
    prev_amount = case.get("purchase_amount")
    prev_prod = case.get("product_or_service")
    prev_evidence_count = len(case.get("evidence", []))

    case_builder.extract_case_facts_deterministically(case, clean_msg)
    case_builder.compute_missing_information(case)

    # Check what was updated
    fact_update_notes = []
    if not prev_amount and case.get("purchase_amount"):
        fact_update_notes.append(f"Purchase Amount: {case['purchase_amount']}")
    if not prev_prod and case.get("product_or_service"):
        fact_update_notes.append(f"Product: {case['product_or_service']}")
    if len(case.get("evidence", [])) > prev_evidence_count:
        new_ev = case["evidence"][-1]
        fact_update_notes.append(f"Evidence: {new_ev.get('item')}")

    # 3. Formulate Search Query
    # Contextualize query with active case details
    platform = case.get("seller_or_platform", "")
    prod = case.get("product_or_service", "")
    cat = case.get("issue_category", "")
    orig = case.get("original_user_story", "")

    harm_product_only = is_harm_limited_to_product(case, clean_msg)

    proc_keywords = ["procedure", "how to file", "file complaint", "step to file", "e-jagriti", "process to file", "complaint filing", "complaint portal"]
    is_procedural_query = any(k in clean_msg.lower() for k in proc_keywords)
    if is_procedural_query:
        query = f"e-jagriti online complaint filing procedure consumer commission Section 35 {clean_msg}"
    else:
        query = f"{clean_msg} {platform} {prod} {cat} {orig}".strip()

    # 4. Retrieve official legal passages and generate explanation
    try:
        try:
            retrieved_sources = hybrid_retriever.hybrid_search(
                query=query,
                top_k=5,
                include_procedural=True,
                exclude_product_liability=harm_product_only,
            )
        except Exception as e:
            logger.error(f"Error in hybrid retrieval: {e}")
            retrieved_sources = []

        # 5. Generate source-grounded legal explanation
        gen_answer = answer_generator.generate_legal_explanation(
            user_question=clean_msg,
            confirmed_case=case,
            retrieved_sources=retrieved_sources,
            language=language,
        )

        # 6. Validate Citations
        val_report = citation_checker.validate_legal_answer(
            gen_answer,
            retrieved_sources=retrieved_sources,
        )

        # 7. Final Safety Gate
        gate_decision = safety_guard.evaluate_final_answer_safety_gate(
            generated_answer=gen_answer,
            validation_report=val_report,
            case=case,
            retrieved_sources=retrieved_sources,
            turn_safety_decision=turn_safety,
            language=language,
        )

        user_facing = gate_decision["user_facing_response"]
        
        # Update latest_analysis with turn output
        case["latest_analysis"] = {
            "analysis_id": f"TURN-{case.get('case_id', 'NS-0000')}-{len(case.get('analysis_history', [])) + 1:02d}",
            "case_id": case.get("case_id"),
            "timestamp": datetime.now().isoformat(),
            "facts_used": {
                "product_or_service": case.get("product_or_service"),
                "seller_or_platform": case.get("seller_or_platform"),
                "purchase_amount": case.get("purchase_amount"),
                "desired_resolution": case.get("desired_resolution"),
            },
            "retrieved_source_ids": [s.get("source_id") or s.get("id") for s in retrieved_sources if isinstance(s, dict)],
            "citations": val_report.get("citations", []),
            "validation_status": val_report.get("status"),
            "gate_status": gate_decision.get("gate_status"),
            "coverage_status": intake.COVERAGE_SUPPORTED,
            "coverage_framework": "CPA_2019_ECOMMERCE",
            "user_facing_response": user_facing,
            "raw_answer": gen_answer,
        }
    except Exception as exc:
        logger.error(f"Error processing case turn: {exc}")
        if is_hindi:
            user_facing = (
                "⚠️ कानूनी जानकारी प्राप्त करते समय एक अप्रत्याशित समस्या आई। आपके केस के तथ्य सुरक्षित हैं। "
                "कृपया राष्ट्रीय उपभोक्ता हेल्पलाइन 1915 पर संपर्क करें अथवा अपना प्रश्न पुनः पूछें।"
            )
        else:
            user_facing = (
                "⚠️ An unexpected error occurred while processing your legal query. Your case facts are safe. "
                "You may contact the National Consumer Helpline at 1915 (consumerhelpline.gov.in) or ask your question again."
            )

    # Prepend fact update acknowledgement if facts were added
    if fact_update_notes:
        if is_hindi:
            update_header = f"📝 **तथ्य अपडेट किया गया:** {', '.join(fact_update_notes)} को आपके केस रिकॉर्ड में जोड़ दिया गया है।\n\n"
        else:
            update_header = f"📝 **Case Record Updated:** Added {', '.join(fact_update_notes)} to your active case facts.\n\n"
        user_facing = update_header + user_facing

    # Check if case status should remain in LEGAL_ANALYSIS / WAITING_FOR_USER
    case["status"] = case_builder.STATUS_WAITING_FOR_USER

    return user_facing
