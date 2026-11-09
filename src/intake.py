"""User Intake & Scope Classification Module for Nyaya Saathi.

Implements the Issue Scope Classifier (Phase 3) following the
authoritative Project Blueprint and Beginner Build Guide.

Classifies incoming descriptions into four mutually exclusive outcomes:
1. URGENT_ESCALATION (Immediate safety concern / bodily harm / threat)
2. OUTSIDE_SCOPE (Clearly unrelated to Indian consumer protection law)
3. NEEDS_CLARIFICATION (Vague, ambiguous, or lacking transaction context)
4. LIKELY_CONSUMER_DISPUTE (Involves consumer transaction for goods or services)

URGENT_ESCALATION takes strict precedence over all other categories.
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple

from src import config
from src import safety
from src import gemini_service
from src import case_builder

get_next_follow_up_question = case_builder.get_next_follow_up_question

# Permitted Classification Categories
CATEGORY_CONSUMER_DISPUTE = "LIKELY_CONSUMER_DISPUTE"
CATEGORY_NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
CATEGORY_OUTSIDE_SCOPE = "OUTSIDE_SCOPE"
CATEGORY_URGENT_ESCALATION = "URGENT_ESCALATION"

# Legal Knowledge Base Coverage Status
COVERAGE_SUPPORTED = "SUPPORTED_IN_KNOWLEDGE_BASE"
COVERAGE_UNAVAILABLE = "SOURCE_COVERAGE_UNAVAILABLE"

VALID_CATEGORIES = {
    CATEGORY_CONSUMER_DISPUTE,
    CATEGORY_NEEDS_CLARIFICATION,
    CATEGORY_OUTSIDE_SCOPE,
    CATEGORY_URGENT_ESCALATION,
}

# Permitted Actions
ACTION_PROCEED = "PROCEED"
ACTION_ASK_QUESTION = "ASK_QUESTION"
ACTION_STOP_NORMAL_FLOW = "STOP_NORMAL_FLOW"
ACTION_ESCALATE = "ESCALATE"


def check_source_coverage(text: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Checks whether a consumer grievance is within Nyaya Saathi's official legal knowledge base
    (Consumer Protection Act 2019, E-Commerce Rules 2020, e-Jagriti filing system).

    If the matter is a consumer transaction governed by a specialized regulatory framework
    not yet indexed in our legal corpus (e.g. RERA real estate builder disputes, TRAI telecom regulations,
    SEBI securities/shares, MACT motor vehicle accident compensation), this function identifies
    the limitation so the assistant can acknowledge the consumer nature while transparently abstaining
    rather than fabricating statutory provisions.

    Returns:
        (is_covered: bool, regulatory_framework: Optional[str], explanation: Optional[str])
    """
    if not text:
        return True, None, None

    text_lower = text.lower()

    # 1. Real estate builder / flat possession delays (RERA)
    if re.search(r"\b(flat|apartment|plot|house|villa|property)\b.*?\b(possession|builder|allotment|rera)\b|\b(builder|developer|promoter)\b.*?\b(delay|possession|handover|rera|allotment|interest)\b|\brera\b", text_lower):
        return False, "RERA", (
            "This matter concerns a real estate allotment or builder possession dispute. While home-buyers are recognized as consumers under the Consumer Protection Act, "
            "the specialized regulatory framework and primary redressal mechanism is under the Real Estate (Regulation and Development) Act, 2016 (RERA). "
            "Nyaya Saathi's current official legal corpus is focused on the Consumer Protection Act 2019, E-Commerce Rules 2020, and e-Jagriti online filing. "
            "Because specialized RERA regulations are not yet indexed in our verified legal knowledge base, Nyaya Saathi cannot provide statutory section citations "
            "for builder-allottee proceedings without risking inaccurate legal information. You may consider approaching your State RERA Authority or filing a consumer complaint on e-Jagriti."
        )

    # 2. Stock market / securities / mutual funds / crypto (SEBI)
    if re.search(r"\b(stock\s+broker|demat|shares|securities|mutual\s+fund|crypto\w*|trading\s+account|sebi\b|portfolio\s+manager)\b", text_lower):
        return False, "SEBI", (
            "This matter concerns financial securities, shares, or broker trading accounts. While retail investors have consumer protections, "
            "these operations are governed primarily by the Securities and Exchange Board of India (SEBI) and SEBI SCORES redressal portal. "
            "Specialized SEBI statutory regulations are not currently part of Nyaya Saathi's verified official knowledge base. "
            "We transparently abstain from citing investment regulations. You may lodge a complaint on SEBI SCORES (scores.sebi.gov.in)."
        )

    # 3. Motor accident claims (MACT)
    if re.search(r"\b(motor\s+accident|road\s+accident\s+claim|hit\s+and\s+run|mact\b|third\s+party\s+accident\s+insurance)\b", text_lower):
        return False, "MACT", (
            "Motor vehicle accident compensation claims are handled by Motor Accident Claims Tribunals (MACT) under the Motor Vehicles Act, 1988, "
            "rather than Consumer Commissions. Nyaya Saathi does not have MACT statutory materials in its knowledge base."
        )

    return True, None, None

# Consumer Dispute Keyword / Pattern Groups
CONSUMER_GOODS_PATTERNS = [
    r"\b(phone|mobile|smartphone|iphone|android|laptop|macbook|computer|pc|tablet|ipad)\b",
    r"\b(tv|television|fridge|refrigerator|washing\s+machine|ac|air\s+conditioner|cooler|cooler\s+fan|microwave|oven)\b",
    r"\b(headphone|earphone|earbuds|smartwatch|watch|camera|speaker|gadget|charger|battery)\b",
    r"\b(clothing|clothes|dress|shirt|shoes|footwear|furniture|sofa|bed|mattress)\b",
    r"\b(car|bike|two[\s-]wheeler|motorcycle|scooter|vehicle|tyre|spare\s+part)\b",
    r"\b(item|product|goods|package|parcel|merchandise|device|appliance|equipment|samaan)\b",
]

CONSUMER_TRANSACTION_PATTERNS = [
    r"\b(purchas(e|ed|ing)?|bought|buy(ing)?|order(ed|ing)?|book(ed|ing)?)\b",
    r"\b(refund|refunded|refunding|reimburse(ment)?|money\s+back)\b",
    r"\b(replace(d|ment|ing)?|return(ed|ing)?|exchange(d)?)\b",
    r"\b(deliver(ed|y|ing)?|shipped|shipping|courier|dispatch(ed)?)\b",
    r"\b(undelivered|non[\s-]delivery|not\s+delivered|delayed\s+delivery|wrong\s+(item|product|order))\b",
    r"\b(defect(ive)?|damag(ed)?|crack(ed)?|broken|fault(y)?|not\s+working|stop(ped)?\s+working)\b",
    r"\b(seller|merchant|vendor|retailer|dealer|shop(keeper)?|store|showroom|manufacturer)\b",
    r"\b(amazon|flipkart|myntra|meesho|swiggy|zomato|tata\s+cliq|jiomart|nykaa|e[\s-]commerce)\b",
    r"\b(warranty|guarantee|invoice|bill(ing)?|receipt|cash\s+memo|payment|paid)\b",
    r"\b(refus(e|ed|ing)?\s+to\s+(refund|replace|return|deliver|fix|repair))\b",
    r"\b(service\s+deficiency|deficiency\s+in\s+service|misleading\s+advertisement|unfair\s+trade)\b",
    # Hindi/Hinglish consumer terms
    r"\b(kharida|khareeda|kharid|manga(ya)?|samaan|order\s+kiya)\b",
    r"\b(paise\s+wapas|wapas\s+nahi|toota\s+hua|kharab\s+nikla|galat\s+samaan)\b",
]

CONSUMER_SERVICE_PATTERNS = [
    r"\b(flight|airline|air\s+ticket|hotel|resort|booking|travel\s+agency|train\s+ticket|bus\s+ticket)\b",
    r"\b(broadband|wifi|internet\s+service|telecom|sim\s+card|mobile\s+recharge|dth)\b",
    r"\b(courier\s+service|dry\s+cleaning|laundry|repair\s+service|service\s+center)\b",
    r"\b(bank\s+charges|locker\s+charges|insurance\s+claim\s+refusal)\b",
    r"\b(stock\s+broker|demat|trading\s+account|shares|mutual\s+fund)\b",
    r"\b(builder|flat\s+booking|possession|real\s+estate\s+developer|housing\s+society)\b",
]


def _match_any(patterns: List[str], text: str) -> bool:
    """Check if any regex in patterns matches the text."""
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def get_default_clarifying_question(language: str = "English") -> str:
    """Return a single, concise clarifying question based on language preference."""
    is_hindi = language.lower() in ("hindi", "hinglish", "hindi/hinglish")
    if is_hindi:
        return "कृपया स्पष्ट करें: क्या यह समस्या किसी उत्पाद (product) या सेवा (service) से जुड़ी है जो आपने किसी विक्रेता या कंपनी से खरीदी थी?"
    return "Could you please clarify: Did this issue involve a product or service you purchased from a company or seller?"


def classify_issue_deterministically(
    user_message: str,
    language: str = "English",
) -> Optional[Dict[str, Any]]:
    """Fast, deterministic rule-based scope classification (Layer 1).

    Returns a classification dictionary if high confidence, or None if ambiguous.
    """
    clean_text = user_message.strip()

    # 1. PRIORITY 1: URGENT ESCALATION (Strict precedence over all others)
    is_urgent, safety_flags, urgent_reason = safety.detect_urgent_safety_signals(clean_text)
    if is_urgent:
        return {
            "category": CATEGORY_URGENT_ESCALATION,
            "confidence": "high",
            "reason": urgent_reason,
            "next_action": ACTION_ESCALATE,
            "clarifying_question": None,
            "safety_flags": safety_flags,
        }

    # 2. PRIORITY 2: OUTSIDE SCOPE DOMAINS (Clearly non-consumer matters)
    is_outside, domain, outside_reason = safety.detect_outside_scope_domain(clean_text)
    if is_outside:
        return {
            "category": CATEGORY_OUTSIDE_SCOPE,
            "confidence": "high",
            "reason": outside_reason,
            "next_action": ACTION_STOP_NORMAL_FLOW,
            "clarifying_question": None,
            "safety_flags": [],
        }

    # 3. PRIORITY 3: VAGUENESS / INSUFFICIENT INFO
    is_vague, vague_reason = safety.is_text_vague_or_insufficient(clean_text)
    if is_vague:
        return {
            "category": CATEGORY_NEEDS_CLARIFICATION,
            "confidence": "high",
            "reason": vague_reason or "The description is too vague to determine whether it is a consumer dispute.",
            "next_action": ACTION_ASK_QUESTION,
            "clarifying_question": get_default_clarifying_question(language),
            "safety_flags": [],
        }

    # 4. PRIORITY 4: CLEAR CONSUMER DISPUTE INDICATORS
    has_goods = _match_any(CONSUMER_GOODS_PATTERNS, clean_text)
    has_transaction = _match_any(CONSUMER_TRANSACTION_PATTERNS, clean_text)
    has_service = _match_any(CONSUMER_SERVICE_PATTERNS, clean_text)

    if (has_goods and has_transaction) or has_service or (has_transaction and "refund" in clean_text.lower()) or (has_transaction and "order" in clean_text.lower()):
        return {
            "category": CATEGORY_CONSUMER_DISPUTE,
            "confidence": "high",
            "reason": "The description clearly concerns a consumer transaction involving products, delivery, refunds, or services.",
            "next_action": ACTION_PROCEED,
            "clarifying_question": None,
            "safety_flags": [],
        }

    if has_goods or has_transaction:
        return {
            "category": CATEGORY_CONSUMER_DISPUTE,
            "confidence": "high",
            "reason": "The issue involves consumer goods or retail transaction elements.",
            "next_action": ACTION_PROCEED,
            "clarifying_question": None,
            "safety_flags": [],
        }

    # Ambiguous - not caught by high-confidence rules
    return None


def classify_issue_with_gemini(
    user_message: str,
    language: str = "English",
) -> Dict[str, Any]:
    """Call Gemini for structured issue classification when rules are ambiguous (Layer 2)."""
    system_instruction = (
        "You are the Issue Scope Classifier for Nyaya Saathi, an Indian consumer dispute assistant. "
        "Classify the user's issue into EXACTLY ONE of the following four categories:\n"
        "1. URGENT_ESCALATION: Immediate physical danger, threats, violence, serious physical injury, emergency.\n"
        "2. OUTSIDE_SCOPE: Landlord-tenant/rent, employment/salary, family/divorce, property partition, criminal matters.\n"
        "3. NEEDS_CLARIFICATION: Vague, ambiguous statements lacking concrete transaction details.\n"
        "4. LIKELY_CONSUMER_DISPUTE: Issues involving purchased goods, defective products, delayed/missing refunds, online delivery, e-commerce, or service deficiency.\n\n"
        "CRITICAL RULE: If there is any serious physical injury or threat, classify as URGENT_ESCALATION regardless of whether a purchase occurred.\n"
        "Respond with ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "category": "LIKELY_CONSUMER_DISPUTE" | "NEEDS_CLARIFICATION" | "OUTSIDE_SCOPE" | "URGENT_ESCALATION",\n'
        '  "confidence": "high" | "medium" | "low",\n'
        '  "reason": "Brief explanation",\n'
        '  "next_action": "PROCEED" | "ASK_QUESTION" | "STOP_NORMAL_FLOW" | "ESCALATE",\n'
        '  "clarifying_question": null or "One short question if NEEDS_CLARIFICATION"\n'
        "}"
    )

    try:
        raw_response = gemini_service.generate_response(
            user_content=f"Classify this user statement:\n\"{user_message}\"",
            system_instruction=system_instruction,
            temperature=0.1,
            max_output_tokens=300,
        )

        # Parse JSON from response (handling potential markdown fences)
        clean_json_str = raw_response.strip()
        if clean_json_str.startswith("```json"):
            clean_json_str = clean_json_str[7:]
        elif clean_json_str.startswith("```"):
            clean_json_str = clean_json_str[3:]
        if clean_json_str.endswith("```"):
            clean_json_str = clean_json_str[:-3]
        clean_json_str = clean_json_str.strip()

        parsed = json.loads(clean_json_str)

        category = parsed.get("category", "").strip()
        if category in VALID_CATEGORIES:
            next_action = parsed.get("next_action")
            if not next_action:
                action_map = {
                    CATEGORY_CONSUMER_DISPUTE: ACTION_PROCEED,
                    CATEGORY_NEEDS_CLARIFICATION: ACTION_ASK_QUESTION,
                    CATEGORY_OUTSIDE_SCOPE: ACTION_STOP_NORMAL_FLOW,
                    CATEGORY_URGENT_ESCALATION: ACTION_ESCALATE,
                }
                next_action = action_map.get(category, ACTION_ASK_QUESTION)

            return {
                "category": category,
                "confidence": parsed.get("confidence", "medium"),
                "reason": parsed.get("reason", "Classified via AI semantic evaluation."),
                "next_action": next_action,
                "clarifying_question": parsed.get("clarifying_question") if category == CATEGORY_NEEDS_CLARIFICATION else None,
                "safety_flags": ["LLM_FLAGGED"] if category == CATEGORY_URGENT_ESCALATION else [],
            }
    except Exception:
        # On model failure or parsing error, fallback safely without assuming in-scope
        pass

    # Safe fallback when ambiguous and LLM fails
    return {
        "category": CATEGORY_NEEDS_CLARIFICATION,
        "confidence": "low",
        "reason": "The description could not be definitively classified. Further clarification is needed.",
        "next_action": ACTION_ASK_QUESTION,
        "clarifying_question": get_default_clarifying_question(language),
        "safety_flags": [],
    }


def classify_issue(
    user_message: str,
    conversation_context: Optional[List[Dict[str, str]]] = None,
    language: str = "English",
    use_llm_fallback: bool = True,
) -> Dict[str, Any]:
    """Main Issue Scope Classifier entry point for Nyaya Saathi.

    Evaluates user messages against Indian consumer law scope, safety boundaries,
    and multi-turn clarification context.

    Args:
        user_message: The text submitted by the user.
        conversation_context: Optional list of previous message dicts (role/text) for multi-turn clarification.
        language: User's preferred language ('English' or 'Hindi/Hinglish').
        use_llm_fallback: Whether to use Gemini if deterministic rules are ambiguous.

    Returns:
        Structured classification dictionary.
    """
    clean_message = (user_message or "").strip()
    if not clean_message:
        return {
            "category": CATEGORY_NEEDS_CLARIFICATION,
            "confidence": "high",
            "reason": "Empty description provided.",
            "next_action": ACTION_ASK_QUESTION,
            "clarifying_question": get_default_clarifying_question(language),
            "safety_flags": [],
        }

    # If this is a reply to a previous clarification, evaluate with context
    effective_text = clean_message
    if conversation_context and len(conversation_context) > 0:
        # Check if the last assistant message was a clarification question
        prev_user_msgs = [m.get("text", "") for m in conversation_context if m.get("role") == "user"]
        if prev_user_msgs:
            # Combine the initial problem and the clarification for holistic evaluation
            combined_context = f"{prev_user_msgs[-1]} Clarification: {clean_message}"
            effective_text = combined_context

    # 1. Deterministic Rule-Based Classification (Layer 1)
    result = classify_issue_deterministically(effective_text, language=language)

    # Also check raw clean_message deterministically if effective_text was combined
    if result is None and effective_text != clean_message:
        result = classify_issue_deterministically(clean_message, language=language)

    # 2. Gemini LLM Fallback (Layer 2) for genuinely ambiguous cases
    if result is None and use_llm_fallback and config.is_api_configured():
        result = classify_issue_with_gemini(effective_text, language=language)

    # 3. Default fallback when ambiguous and no LLM available
    if result is None:
        result = {
            "category": CATEGORY_NEEDS_CLARIFICATION,
            "confidence": "low",
            "reason": "The description requires additional context to verify if a consumer transaction is involved.",
            "next_action": ACTION_ASK_QUESTION,
            "clarifying_question": get_default_clarifying_question(language),
            "safety_flags": [],
        }

    # Annotate legal knowledge base source coverage
    if result.get("category") == CATEGORY_CONSUMER_DISPUTE:
        is_cov, framework, expl = check_source_coverage(effective_text)
        result["coverage_status"] = COVERAGE_SUPPORTED if is_cov else COVERAGE_UNAVAILABLE
        result["coverage_framework"] = framework
        result["coverage_explanation"] = expl
    else:
        result["coverage_status"] = COVERAGE_SUPPORTED
        result["coverage_framework"] = None
        result["coverage_explanation"] = None

    return result
