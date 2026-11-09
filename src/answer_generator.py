"""
Source-Grounded Legal Answer Generation Module for Nyaya Saathi.

Blueprint Step 17: Source-Grounded Legal Answer Generation using Gemini.

Synthesizes user case facts with officially retrieved legal passages using Gemini.
Operates under strict source-grounding safeguards:
1. Exclusive Authority: Gemini may only use supplied source passages for specific legal claims.
2. Zero Hallucination: Never invent acts, sections, limitation periods, fees, deadlines, or outcomes.
3. Explicit Abstention: If retrieved sources do not cover the inquiry, states:
   "The available legal sources in Nyaya Saathi are insufficient to verify this point."
4. Empty Retrieval Safeguard: If retrieval is empty, returns an insufficient-source response directly
   from Python without calling Gemini.
5. Fact Separation: Clearly distinguishes allegations, user-provided facts, user-confirmed facts,
   and official legal text.
6. Confirmation Gate: If case['facts_confirmed_by_user'] is False, marks response as provisional.
7. Temporal Awareness: Respects 5-date gating (G.S.R. 789(E) commencement on 2027-01-01) and flags
   transitional disputes as 'NEEDS_LEGAL_REVIEW'.
8. Review Status Disclosure: Discloses 'REQUIRES_LEGAL_REVIEW' on unverified source passages.
9. Strict Output Validation: Enforces structured JSON schema and validates source ID provenance in Python.
"""

from datetime import date, datetime
import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Union

from src import config
from src import gemini_service
from src.hybrid_retriever import (
    DateGatingResult,
    TEMPORAL_CURRENTLY_IN_FORCE,
    TEMPORAL_FUTURE_EFFECTIVE,
    TEMPORAL_NEEDS_LEGAL_REVIEW,
    TEMPORAL_NOT_APPLICABLE_PRE_COMMENCEMENT,
    VALID_TEMPORAL_STATUSES,
)

logger = logging.getLogger("answer_generator")

# Response Statuses
STATUS_SOURCE_GROUNDED = "SOURCE_GROUNDED_INFORMATION"
STATUS_UNCONFIRMED_PROVISIONAL = "UNCONFIRMED_FACTS_PROVISIONAL"
STATUS_INSUFFICIENT_SOURCES = "INSUFFICIENT_SOURCES"
STATUS_ERROR_FALLBACK = "GENERATION_ERROR_FALLBACK"

INSUFFICIENT_SOURCES_STATEMENT = "The available legal sources in Nyaya Saathi are insufficient to verify this point."

# Standard System Instruction for Source-Grounded Legal Explanations
SYSTEM_INSTRUCTION_LEGAL_EXPLANATION = """You are Nyaya Saathi, an informational consumer-dispute assistant for India.
You are not an advocate and do not represent the user.
Your job is to explain supplied official legal passages in plain language.
The supplied legal passages are your EXCLUSIVE authority for specific legal claims.
Never supplement them with invented provisions or remembered legal references from your training data.
Clearly distinguish allegations, user-provided facts, confirmed facts, and legal source material.
Do not guarantee remedies, refunds, or legal outcomes.
If the supplied sources do not support or address a specific question or point, you MUST explicitly state:
"The available legal sources in Nyaya Saathi are insufficient to verify this point."
If the matter is complex, urgent, transitional, or uncertain, recommend appropriate professional review.
Respect the user's selected language (English, Hindi/Hinglish, or Hindi).
Preserve official Act names, rule titles, gazette references, and statutory section numbers exactly as written in the sources.

STATUTORY INTERPRETATION & ACCURACY RULES:
1. PRODUCT LIABILITY EXCLUSION (CPA 2019 SECTION 2(22)): Under Section 2(22), "harm" in relation to a product liability action explicitly excludes damage to the product itself or commercial/economic loss. When a product itself is damaged, broken, or defective without causing personal injury, illness, death, or damage to other property, you MUST NOT advise or recommend a product liability action under Sections 82–87. Instead, frame it as an ordinary consumer dispute for "defect" under Section 2(10) with conditional remedies under Section 39(1) (removal of defect, replacement, refund of price paid, or compensation).
2. E-COMMERCE RULES ATTRIBUTION:
   - Rule 5(3)(c): Marketplace e-commerce entity's obligation to display terms regarding return, refund, exchange, warranty, and grievance mechanism on its platform.
   - Rule 6(3): Seller's obligation not to refuse return or refund if goods delivered are defective, deficient, spurious, or delivered late (subject to force majeure proviso for late delivery).
   - Rule 6(5)(g): Seller's obligation to provide the marketplace entity with the terms and conditions regarding return, refund, exchange, and delivery for display on the platform.
3. DEFECT DEFINITION (CPA 2019 SECTION 2(10)): Accurately state that defect means any fault, imperfection or shortcoming in quality, quantity, potency, purity or standard required by law or contract or claimed by the trader.
4. CONDITIONAL REMEDIES (SECTION 39(1)): Remedies under Section 39(1) are conditional orders issued by the Consumer Commission against the opposite party after finding a defect; do not assert them as automatic unconditional entitlements from the marketplace without process.
5. PROCEDURAL GUIDANCE & VAKALATNAMA: e-Jagriti (e-jagriti.gov.in) is procedural portal guidance, not a statutory Act. A Vakalatnama is required ONLY if the consumer is represented by an advocate/lawyer; it is NOT required if the consumer files or appears in person.
6. CLAIMS STRUCTURE: Provide a "claims" list where each claim has its own specific citation, authority, and official URL. Every claim must stand on its own citation.

You MUST output ONLY a valid, parseable JSON object matching the requested schema. Do not output any markdown text outside the JSON object."""


def _format_case_facts_summary(confirmed_case: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Extracts and separates user-provided allegations, confirmed facts, and missing info."""
    if not confirmed_case:
        return {
            "facts_provided": [],
            "facts_confirmed": [],
            "missing_info": ["Complete case details not yet gathered."],
            "is_confirmed": False,
            "story": "",
        }

    is_confirmed = bool(confirmed_case.get("facts_confirmed_by_user", False))
    story = confirmed_case.get("original_user_story", "")

    provided: List[str] = []
    confirmed: List[str] = []

    if confirmed_case.get("product_or_service"):
        provided.append(f"Product / Service: {confirmed_case['product_or_service']}")
    if confirmed_case.get("seller_or_platform"):
        provided.append(f"Seller / Platform: {confirmed_case['seller_or_platform']}")
    if confirmed_case.get("purchase_amount"):
        provided.append(f"Purchase Amount: {confirmed_case['purchase_amount']}")
    if confirmed_case.get("desired_resolution"):
        provided.append(f"Desired Remedy: {confirmed_case['desired_resolution']}")

    sc = confirmed_case.get("seller_contact", {})
    if sc.get("contacted") is True:
        method = sc.get("contact_method") or "Unspecified method"
        resp = sc.get("seller_response") or "Unspecified response"
        provided.append(f"Seller Contact: Contacted via {method}; Response: {resp}")
    elif sc.get("contacted") is False:
        provided.append("Seller Contact: Not yet contacted")

    for ev in confirmed_case.get("events", []):
        provided.append(f"Event: {ev.get('event')} (Date: {ev.get('date', 'Not specified')})")

    for evi in confirmed_case.get("evidence", []):
        provided.append(f"Evidence Available: {evi.get('item')} ({evi.get('description', '')})")

    if is_confirmed:
        confirmed = list(provided)

    missing = list(confirmed_case.get("missing_information", []))

    return {
        "facts_provided": provided,
        "facts_confirmed": confirmed,
        "missing_info": missing,
        "is_confirmed": is_confirmed,
        "story": story,
    }


def _build_insufficient_sources_response(
    user_question: str,
    language: str,
    facts_summary: Dict[str, Any],
    temporal_status: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Generates a safe fallback response directly in Python when retrieval is empty or insufficient."""
    is_hindi = language.lower() in ("hindi", "hinglish", "hindi/hinglish")

    explanation = INSUFFICIENT_SOURCES_STATEMENT
    if reason:
        explanation = f"{INSUFFICIENT_SOURCES_STATEMENT} ({reason})"

    understanding = user_question.strip() if user_question else "Inquiry regarding consumer dispute."

    if is_hindi:
        how_it_relates = "न्याय साथी के कानूनी डेटाबेस में इस विशिष्ट प्रश्न से संबंधित कोई आधिकारिक कानूनी प्रावधान प्राप्त नहीं हुआ है।"
        next_steps = [
            "खरीद की रसीद / इनवॉइस और भुगतान का प्रमाण सुरक्षित रखें।",
            "राष्ट्रीय उपभोक्ता हेल्पलाइन (NCH) 1915 या consumerhelpline.gov.in पर संपर्क करने पर विचार करें।",
            "विशिष्ट कानूनी सलाह के लिए किसी योग्य अधिवक्ता से परामर्श लें।",
        ]
        limitations = [
            "उपलब्ध आधिकारिक स्रोतों में इस प्रश्न के लिए आवश्यक विशिष्ट कानूनी प्रावधान शामिल नहीं हैं।",
            "यह जानकारी केवल शैक्षिक व सूचनात्मक उद्देश्य के लिए है और इसे कानूनी सलाह नहीं माना जाना चाहिए।",
        ]
    else:
        how_it_relates = "No matching official legal provisions were retrieved from the Nyaya Saathi knowledge base for this specific inquiry."
        next_steps = [
            "Preserve your tax invoice, purchase receipt, and payment proof.",
            "Consider contacting the National Consumer Helpline at 1915 or visiting consumerhelpline.gov.in.",
            "Consult a qualified legal practitioner for formal legal advice on your specific matter.",
        ]
        limitations = [
            "No matching verified statutory sources were retrieved for this specific inquiry.",
            "This prototype provides informational assistance only and does not constitute formal legal advice or representation.",
        ]

    return {
        "response_status": STATUS_INSUFFICIENT_SOURCES,
        "language": language,
        "understanding_of_your_problem": understanding,
        "facts_provided_by_you": facts_summary["facts_provided"],
        "facts_confirmed_by_you": facts_summary["facts_confirmed"],
        "relevant_official_sources": [],
        "what_the_source_says": explanation,
        "how_it_may_relate_to_your_problem": how_it_relates,
        "missing_information": facts_summary["missing_info"],
        "possible_next_steps": next_steps,
        "limitations_and_uncertainties": limitations,
        "needs_professional_review": True,
        "temporal_applicability_status": temporal_status,
        "source_ids_used": [],
        "unsupported_claims_detected": [],
    }


def _prepare_prompt_payload(
    user_question: str,
    facts_summary: Dict[str, Any],
    retrieved_sources: List[Dict[str, Any]],
    language: str,
    temporal_status: str,
) -> str:
    """Prepares structured, strict prompt payload containing only supplied passages."""
    sources_text_blocks = []
    for idx, s in enumerate(retrieved_sources, start=1):
        sid = s.get("chunk_id") or s.get("embedding_record_id") or f"SRC_{idx:02d}"
        doc_title = s.get("document_title", "Official Legal Source")
        prov_ref = f"{s.get('provision_type', '')} {s.get('provision_number', '')}".strip()
        if s.get("provision_heading"):
            prov_ref += f" ({s.get('provision_heading')})"
        review_stat = s.get("legal_review_status", "REQUIRES_LEGAL_REVIEW")
        temp_stat = s.get("temporal_applicability_status", "CURRENTLY_IN_FORCE")
        eff_from = s.get("effective_from") or "Currently operative"
        gazette = s.get("gazette_reference") or "N/A"
        raw_text = s.get("exact_original_text") or s.get("text", "")

        block = (
            f"--- SOURCE #{idx} ---\n"
            f"Source ID: {sid}\n"
            f"Document Title: {doc_title}\n"
            f"Provision Reference: {prov_ref or 'General Provision'}\n"
            f"Legal Review Status: {review_stat}\n"
            f"Temporal Status: {temp_stat} (Effective: {eff_from})\n"
            f"Gazette Reference: {gazette}\n"
            f"Official Statutory Text:\n\"\"\"{raw_text.strip()}\"\"\"\n"
        )
        sources_text_blocks.append(block)

    formatted_sources = "\n".join(sources_text_blocks)

    facts_section = (
        f"FACTS CONFIRMED BY USER: {'YES (User has confirmed these facts)' if facts_summary['is_confirmed'] else 'NO (Unconfirmed - Preliminary/Provisional)'}\n"
        f"User Original Statement: \"{facts_summary['story'] or user_question}\"\n"
        f"User Extracted Facts:\n" + ("\n".join(f"- {f}" for f in facts_summary['facts_provided']) if facts_summary['facts_provided'] else "- None specified yet.") + "\n"
        f"Missing Information:\n" + ("\n".join(f"- {m}" for m in facts_summary['missing_info']) if facts_summary['missing_info'] else "- None identified.")
    )

    temporal_instructions = (
        f"TEMPORAL APPLICABILITY STATUS: {temporal_status}\n"
        "Note on Temporal Rules: If the Consumer Protection (E-Commerce) (Amendment) Rules, 2026 (G.S.R. 789(E)) are retrieved, "
        "they commence on 1 January 2027 and are NOT currently in force before that date. "
        "If status is 'NEEDS_LEGAL_REVIEW', explicitly disclose that transitional application to pre-commencement transactions "
        "with ongoing post-commencement disputes is legally unresolved and requires formal legal advice."
    )

    schema_guide = """{
  "response_status": "SOURCE_GROUNDED_INFORMATION" | "UNCONFIRMED_FACTS_PROVISIONAL" | "INSUFFICIENT_SOURCES",
  "language": "English" | "Hindi/Hinglish" | "Hindi",
  "understanding_of_your_problem": "Brief plain-language summary describing the user's issue (treat allegations as user assertions, e.g. 'You allege that...')",
  "facts_provided_by_you": ["List of facts provided in conversation"],
  "facts_confirmed_by_you": ["List of facts explicitly confirmed by user, or empty if unconfirmed"],
  "claims": [
    {
      "claim_id": "CLM_001",
      "claim_text": "Plain language legal assertion supported by the cited source",
      "source_ids": ["Exact Source ID"],
      "cited_provision": "e.g. Consumer Protection Act, 2019, Section 2(10)",
      "issuing_authority": "Ministry of Consumer Affairs, Food and Public Distribution",
      "source_url": "Official URL from source",
      "statutory_excerpt": "Relevant short excerpt from the source text"
    }
  ],
  "relevant_official_sources": [
    {
      "source_id": "Exact Source ID from above",
      "document_title": "Official Title",
      "provision_reference": "Section / Rule reference",
      "source_text_summary": "1-2 sentence plain-language summary of what this provision says",
      "source_url": "URL if present",
      "pdf_page_start": null,
      "pdf_page_end": null,
      "legal_review_status": "Status from source"
    }
  ],
  "what_the_source_says": "Plain language explanation of what the retrieved official legal texts state. Cite only provisions present in the sources above.",
  "how_it_may_relate_to_your_problem": "Objective explanation of how these provisions may relate to the problem without guaranteeing liability, refund, or outcome.",
  "missing_information": ["Important missing facts needed to understand the legal position"],
  "possible_next_steps": ["2-4 practical, cautious steps (e.g. preserve invoice, save communication, contact NCH 1915, consult advocate)"],
  "limitations_and_uncertainties": ["Statutory limitations, unconfirmed facts disclaimers, or pending legal review disclosures"],
  "needs_professional_review": true | false,
  "temporal_applicability_status": "Status string matching input",
  "source_ids_used": ["List of Source IDs actually used"]
}"""

    prompt = (
        f"USER INQUIRY:\n\"{user_question}\"\n\n"
        f"SELECTED LANGUAGE: {language}\n\n"
        f"CASE FACTS SUMMARY:\n{facts_section}\n\n"
        f"{temporal_instructions}\n\n"
        f"EXCLUSIVE RETRIEVED LEGAL SOURCES (Use ONLY these sources):\n"
        f"{formatted_sources}\n\n"
        f"CRITICAL INSTRUCTIONS:\n"
        f"1. Explain only what is supported by the supplied sources. If sources do not support the query, set 'what_the_source_says' to: '{INSUFFICIENT_SOURCES_STATEMENT}'.\n"
        f"2. Never invent Act names, sections, deadlines, limitation periods, or court decisions.\n"
        f"3. If facts are not confirmed, set 'response_status' to 'UNCONFIRMED_FACTS_PROVISIONAL' and disclose in limitations that facts are provisional.\n"
        f"4. If any source has legal_review_status 'REQUIRES_LEGAL_REVIEW', set 'needs_professional_review' to true and disclose pending review in limitations.\n"
        f"5. Product Liability Gating: Under CPA 2019 Section 2(22), if damage is to the product itself, DO NOT cite product liability (Sections 82-87). Cite defect (Section 2(10)) and remedies (Section 39(1)).\n"
        f"6. E-Commerce Rules: Correctly attribute Rule 5(3)(c) to marketplace platform, Rule 6(3) to seller (with force majeure proviso), Rule 6(5)(g) to seller providing terms to marketplace.\n"
        f"7. e-Jagriti & Vakalatnama: e-Jagriti is PROCEDURAL_GUIDANCE. Vakalatnama is required ONLY if represented by an advocate, NOT in person.\n"
        f"8. Each claim in 'claims' must cite only the source ID that textually supports it.\n"
        f"9. Output ONLY a valid JSON object matching this schema:\n{schema_guide}"
    )

    return prompt


def _validate_and_sanitize_response(
    raw_response: str,
    retrieved_sources: List[Dict[str, Any]],
    facts_summary: Dict[str, Any],
    temporal_status: str,
    language: str,
    user_question: str,
) -> Dict[str, Any]:
    """Parses, validates, and sanitizes Gemini JSON output against strict grounding constraints."""
    # 1. Clean markdown code fences if present
    clean_str = raw_response.strip()
    if clean_str.startswith("```json"):
        clean_str = clean_str[7:]
    elif clean_str.startswith("```"):
        clean_str = clean_str[3:]
    if clean_str.endswith("```"):
        clean_str = clean_str[:-3]
    clean_str = clean_str.strip()

    try:
        data = json.loads(clean_str)
    except Exception as e:
        logger.error(f"Failed to parse Gemini legal explanation JSON: {e}")
        return _build_insufficient_sources_response(
            user_question=user_question,
            language=language,
            facts_summary=facts_summary,
            temporal_status=temporal_status,
            reason="Model output could not be parsed into valid structured format.",
        )

    if not isinstance(data, dict):
        return _build_insufficient_sources_response(
            user_question=user_question,
            language=language,
            facts_summary=facts_summary,
            temporal_status=temporal_status,
            reason="Model output format invalid.",
        )

    # 2. Collect valid source IDs from retrieved sources
    valid_source_ids: Set[str] = set()
    source_review_map: Dict[str, str] = {}
    for s in retrieved_sources:
        sid = s.get("chunk_id") or s.get("embedding_record_id")
        if sid:
            valid_source_ids.add(sid)
            source_review_map[sid] = s.get("legal_review_status", "REQUIRES_LEGAL_REVIEW")

    # 3. Sanitize and verify source_ids_used
    raw_used = data.get("source_ids_used", [])
    valid_used: List[str] = []
    unsupported_claims: List[str] = []

    if isinstance(raw_used, list):
        for sid in raw_used:
            if isinstance(sid, str) and sid in valid_source_ids:
                if sid not in valid_used:
                    valid_used.append(sid)
            else:
                unsupported_claims.append(f"Model cited unsupplied or unknown source ID: {sid}")

    data["source_ids_used"] = valid_used
    data["unsupported_claims_detected"] = unsupported_claims

    # 4. Check facts confirmation gate
    if not facts_summary["is_confirmed"]:
        data["response_status"] = STATUS_UNCONFIRMED_PROVISIONAL
        data["facts_confirmed_by_you"] = []
        # Ensure limitations discloses unconfirmed facts
        limits = data.get("limitations_and_uncertainties", [])
        disclaimer = "Case facts have not yet been formally reviewed and confirmed by the consumer. This legal explanation is preliminary and provisional only."
        if disclaimer not in limits:
            limits.append(disclaimer)
        data["limitations_and_uncertainties"] = limits
    else:
        if data.get("response_status") not in (STATUS_SOURCE_GROUNDED, STATUS_INSUFFICIENT_SOURCES):
            data["response_status"] = STATUS_SOURCE_GROUNDED
        data["facts_confirmed_by_you"] = facts_summary["facts_confirmed"]

    # 5. Check Legal Review Status of sources used
    any_requires_review = any(
        source_review_map.get(sid) == "REQUIRES_LEGAL_REVIEW"
        for sid in valid_used
    )
    if any_requires_review or temporal_status == TEMPORAL_NEEDS_LEGAL_REVIEW:
        data["needs_professional_review"] = True
        limits = data.get("limitations_and_uncertainties", [])
        if any_requires_review:
            rev_notice = "One or more retrieved source passages have not undergone formal human legal review and are provided for informational research purposes only."
            if rev_notice not in limits:
                limits.append(rev_notice)
        if temporal_status == TEMPORAL_NEEDS_LEGAL_REVIEW:
            temp_notice = "This dispute involves a pre-commencement transaction with continuing post-commencement events under G.S.R. 789(E). Transitional applicability is legally unsettled and requires formal advocate review."
            if temp_notice not in limits:
                limits.append(temp_notice)
        data["limitations_and_uncertainties"] = limits

    # 6. Ensure default lists & types
    data["facts_provided_by_you"] = facts_summary["facts_provided"]
    data["missing_information"] = data.get("missing_information") or facts_summary["missing_info"]
    data["temporal_applicability_status"] = temporal_status
    data["language"] = language

    if not isinstance(data.get("possible_next_steps"), list) or not data["possible_next_steps"]:
        data["possible_next_steps"] = [
            "Preserve your purchase invoice, receipt, and payment transaction details.",
            "Maintain records of all written communications and seller responses.",
            "Contact the National Consumer Helpline at 1915 (consumerhelpline.gov.in) for procedural guidance.",
        ]

    if not isinstance(data.get("limitations_and_uncertainties"), list):
        data["limitations_and_uncertainties"] = []

    # 7. Disallow guaranteed outcomes or promises
    what_says = str(data.get("what_the_source_says", ""))
    how_relates = str(data.get("how_it_may_relate_to_your_problem", ""))
    for forbidden in ["guarantee", "guaranteed", "definitely win", "100% refund", "entitled to immediate refund"]:
        if forbidden in what_says.lower() or forbidden in how_relates.lower():
            data["unsupported_claims_detected"].append(f"Model generated overly definitive outcome phrase: '{forbidden}'")
            # Replace definitive assertion with neutral phrasing
            data["how_it_may_relate_to_your_problem"] = how_relates.replace(forbidden, "may potentially seek")

    # 8. Sanitize and validate claims array
    claims = data.get("claims")
    sanitized_claims = []
    if isinstance(claims, list):
        for idx, clm in enumerate(claims, start=1):
            if not isinstance(clm, dict):
                continue
            cid = clm.get("claim_id") or f"CLM_{idx:03d}"
            ctxt = str(clm.get("claim_text", "")).strip()
            sids = [s for s in clm.get("source_ids", []) if s in valid_source_ids]
            if not sids and clm.get("source_ids"):
                unsupported_claims.append(f"Claim {cid} cited unverified source ID: {clm.get('source_ids')}")
            sanitized_claims.append({
                "claim_id": cid,
                "claim_text": ctxt,
                "source_ids": sids,
                "cited_provision": clm.get("cited_provision", ""),
                "issuing_authority": clm.get("issuing_authority", ""),
                "source_url": clm.get("source_url", ""),
                "statutory_excerpt": clm.get("statutory_excerpt", ""),
            })
    data["claims"] = sanitized_claims

    # 9. Gating on Product Liability under CPA 2019 Section 2(22)
    story_text = (facts_summary.get("story", "") + " " + user_question).lower()
    has_injury_or_ext_damage = bool(re.search(
        r"\b(injury|injured|burn|hospital|doctor|death|fatal|shock\s+injury|damaged\s+(my\s+)?(house|car|bed|room|property))\b",
        story_text
    ))
    if not has_injury_or_ext_damage:
        if "product liability action" in what_says.lower() or "section 83" in what_says.lower() or "section 84" in what_says.lower():
            limits = data.get("limitations_and_uncertainties", [])
            sec22_notice = (
                "NOTE ON PRODUCT LIABILITY: Under Section 2(22) of the Consumer Protection Act, 2019, 'harm' "
                "excludes damage to the product itself or economic loss. Therefore, ordinary defect remedies (repair, "
                "replacement, refund) are pursued under Sections 34–39 rather than product liability."
            )
            if sec22_notice not in limits:
                limits.append(sec22_notice)
            data["limitations_and_uncertainties"] = limits

    # 10. Vakalatnama clarification: only if represented by an advocate
    if "vakalatnama" in what_says.lower() or "vakalatnama" in how_relates.lower():
        vaka_notice = "A Vakalatnama is required only if the consumer is represented by an advocate/lawyer; it is not required when filing or appearing in person."
        limits = data.get("limitations_and_uncertainties", [])
        if not any("vakalatnama" in lim.lower() for lim in limits):
            limits.append(vaka_notice)
        data["limitations_and_uncertainties"] = limits

    return data


def generate_legal_explanation(
    user_question: str,
    confirmed_case: Optional[Dict[str, Any]] = None,
    retrieved_sources: Optional[List[Dict[str, Any]]] = None,
    language: str = "English",
    temporal_context: Optional[Union[str, DateGatingResult, Dict[str, Any]]] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.0,
) -> Dict[str, Any]:
    """
    Synthesizes official legal passages into a source-grounded explanation using Gemini.

    Blueprint Step 17 Core Implementation.

    Args:
        user_question: The consumer grievance or question text.
        confirmed_case: Optional structured case dictionary from case_builder.
        retrieved_sources: List of legal chunk/record dictionaries returned by hybrid_search.
        language: Preferred output language ('English', 'Hindi/Hinglish', 'Hindi').
        temporal_context: Temporal gating string, DateGatingResult, or metadata dict.
        api_key: Optional Gemini API key override.
        model_name: Optional Gemini model override (defaults to gemini-3.1-flash-lite).
        temperature: Sampling temperature (default 0.0 for deterministic factual consistency).

    Returns:
        Structured legal explanation dictionary conforming strictly to the Blueprint schema.
    """
    clean_question = (user_question or "").strip()
    sources = retrieved_sources if isinstance(retrieved_sources, list) else []

    # 1. Resolve temporal applicability status
    if isinstance(temporal_context, DateGatingResult):
        temporal_status = temporal_context.temporal_status
    elif isinstance(temporal_context, dict):
        temporal_status = temporal_context.get("temporal_applicability_status") or temporal_context.get("temporal_status", TEMPORAL_CURRENTLY_IN_FORCE)
    elif isinstance(temporal_context, str) and temporal_context in VALID_TEMPORAL_STATUSES:
        temporal_status = temporal_context
    elif sources and sources[0].get("temporal_applicability_status"):
        temporal_status = sources[0]["temporal_applicability_status"]
    else:
        temporal_status = TEMPORAL_CURRENTLY_IN_FORCE

    # 2. Extract and summarize case facts
    facts_summary = _format_case_facts_summary(confirmed_case)

    # 3. SAFEGUARD: Empty Retrieval Handling (Zero LLM calls)
    if not sources:
        logger.info("Empty retrieved_sources supplied to generate_legal_explanation. Returning Python-generated abstention.")
        return _build_insufficient_sources_response(
            user_question=clean_question,
            language=language,
            facts_summary=facts_summary,
            temporal_status=temporal_status,
            reason="No official legal passages were retrieved for this query.",
        )

    # 4. Check API configuration
    if not config.is_api_configured() and not api_key:
        logger.warning("Gemini API key is not configured. Returning safe offline insufficient-sources response.")
        return _build_insufficient_sources_response(
            user_question=clean_question,
            language=language,
            facts_summary=facts_summary,
            temporal_status=temporal_status,
            reason="Gemini API is not configured.",
        )

    # 5. Build strict, grounded prompt
    prompt = _prepare_prompt_payload(
        user_question=clean_question,
        facts_summary=facts_summary,
        retrieved_sources=sources,
        language=language,
        temporal_status=temporal_status,
    )

    # 6. Invoke Gemini with strict system instructions and temperature 0.0
    try:
        raw_response = gemini_service.generate_response(
            user_content=prompt,
            system_instruction=SYSTEM_INSTRUCTION_LEGAL_EXPLANATION,
            api_key=api_key,
            model_name=model_name or config.get_model_name(),
            temperature=temperature,
            max_output_tokens=1800,
        )

        return _validate_and_sanitize_response(
            raw_response=raw_response,
            retrieved_sources=sources,
            facts_summary=facts_summary,
            temporal_status=temporal_status,
            language=language,
            user_question=clean_question,
        )

    except Exception as e:
        logger.error(f"Error calling Gemini in generate_legal_explanation: {e}")
        return _build_insufficient_sources_response(
            user_question=clean_question,
            language=language,
            facts_summary=facts_summary,
            temporal_status=temporal_status,
            reason=f"AI explanation service error: {type(e).__name__}",
        )
