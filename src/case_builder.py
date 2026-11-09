"""
Structured Case Builder & Active Grievance Context Module for Nyaya Saathi.

Blueprint Steps 12 & 13:
- Fixed, validated case schema conforming to Project Blueprint Part C.
- Fact origin and provenance tracking ("USER_STATEMENT", message_id, confirmed).
- Permanent preservation of original grievance story.
- Event timeline and evidence inventory management.
- Fact corrections with audit history.
- Deterministic extraction and Gemini-assisted case extraction.
- Category-aware guided follow-up question logic (Step 12).
- Dynamic missing information calculation and status lifecycle.
"""

from datetime import datetime, date
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

# Case Statuses (Blueprint Conversation Lifecycle)
STATUS_INTAKE = "INTAKE"
STATUS_NEW_GRIEVANCE = "NEW_GRIEVANCE"
STATUS_SCOPE_CHECK = "SCOPE_CHECK"
STATUS_FACTS_REVIEW = "FACTS_REVIEW"
STATUS_FACTS_CONFIRMED = "FACTS_CONFIRMED"
STATUS_FACTS_CONFIRMED_WITH_GAPS = "FACTS_CONFIRMED_WITH_GAPS"
STATUS_LEGAL_ANALYSIS = "LEGAL_ANALYSIS"
STATUS_WAITING_FOR_USER = "WAITING_FOR_USER"
STATUS_READY_FOR_DRAFT = "READY_FOR_DRAFT"

VALID_CASE_STATUSES = {
    STATUS_INTAKE,
    STATUS_NEW_GRIEVANCE,
    STATUS_SCOPE_CHECK,
    STATUS_FACTS_REVIEW,
    STATUS_FACTS_CONFIRMED,
    STATUS_FACTS_CONFIRMED_WITH_GAPS,
    STATUS_LEGAL_ANALYSIS,
    STATUS_WAITING_FOR_USER,
    STATUS_READY_FOR_DRAFT,
}

# Standard Category Constants
CATEGORY_INCORRECT_ITEM = "Incorrect item delivered / Wrong product received"
CATEGORY_DEFECTIVE_GOODS = "Defective or damaged goods"
CATEGORY_NON_DELIVERY = "Non-delivery or wrong delivery"
CATEGORY_REFUND_REFUSAL = "Refund or replacement refusal"
CATEGORY_ECOMMERCE = "E-commerce grievance"
CATEGORY_SERVICE_DEFICIENCY = "Service deficiency"
CATEGORY_MISLEADING_REP = "Misleading representation"
CATEGORY_SUBSCRIPTION_UNAUTHORIZED = "Subscription / Unauthorized charges"
CATEGORY_UNFAIR_TRADE = "Unfair trade practice"
CATEGORY_WARRANTY_DISPUTE = "Warranty dispute"

# Standard Case ID Counter (Session-safe generator)
_case_counter = 0


def generate_case_id() -> str:
    """Generates a human-readable, unique case identifier (e.g. NS-0001)."""
    global _case_counter
    _case_counter += 1
    timestamp_suffix = datetime.now().strftime("%y%m%d-%H%M%S")
    return f"NS-{_case_counter:04d}-{timestamp_suffix[-4:]}"


def infer_issue_category(text: str, current_category: Optional[str] = None) -> str:
    """
    Infers the most accurate consumer dispute category from user text.
    Ensures wrong item delivery is NOT categorized as defective/damaged goods
    unless explicit physical damage is reported.
    Supports a flexible taxonomy covering various consumer dispute domains.
    """
    if not text or not text.strip():
        return current_category or CATEGORY_ECOMMERCE

    text_lower = text.strip().lower()
    has_damage = bool(re.search(r"\b(defect\w*|faulty|malfunction\w*|damag\w*|broken|cracked|shattered|kharab|toota|leak\w*|dent\w*)\b", text_lower))
    has_wrong_item = (
        bool(
            re.search(
                r"\b(wrong\s+(?:item|product|goods|order|delivery|parcel|package)|"
                r"incorrect\s+(?:item|product|goods|order|delivery)|"
                r"different\s+(?:item|product|samaan)|"
                r"ordered\s+.*?\s+(?:received|delivered|got)|"
                r"(?:received|delivered|got)\s+.*?\s+instead|"
                r"galat\s+samaan)\b",
                text_lower,
            )
        )
        or ("wrong" in text_lower and any(w in text_lower for w in ["item", "delivered", "delivery", "product", "received", "order"]))
    ) and not bool(re.search(r"\b(not\s+delivered|never\s+delivered|undelivered|non[\s-]delivery|stuck\s+in\s+transit)\b", text_lower))

    # Priority rule: Wrong item without physical damage is CATEGORY_INCORRECT_ITEM
    if has_wrong_item and not has_damage:
        return CATEGORY_INCORRECT_ITEM

    if current_category and current_category not in ("", "I am not sure"):
        if current_category == CATEGORY_DEFECTIVE_GOODS and has_wrong_item and not has_damage:
            return CATEGORY_INCORRECT_ITEM
        return current_category

    # Explicit domain checks
    if re.search(r"\b(subscription|recurring|auto[\s-]debit|auto[\s-]renew|unauthorized\s+charge|membership\s+fee|ott\s+plan)\b", text_lower):
        return CATEGORY_SUBSCRIPTION_UNAUTHORIZED

    if re.search(r"\b(warranty|guarantee\s+card|free\s+repair\s+denied|warranty\s+void|claim\s+rejected)\b", text_lower):
        return CATEGORY_WARRANTY_DISPUTE

    if re.search(r"\b(flight|airline|hotel|telecom|broadband|service\s+deficiency|service\s+center|hospital|dry\s+clean\w*|gym|booking)\b", text_lower):
        return CATEGORY_SERVICE_DEFICIENCY

    if has_damage:
        return CATEGORY_DEFECTIVE_GOODS
    if has_wrong_item:
        return CATEGORY_INCORRECT_ITEM
    if re.search(r"\b(not\s+delivered|never\s+delivered|delayed?\s*(?:delivery|order|package|parcel|shipment)|delay\w*\s+in\s+delivery|undelivered|transit|courier\s+lost|parcel\s+missing)\b", text_lower):
        return CATEGORY_NON_DELIVERY
    if re.search(r"\b(warranty|guarantee\s+card|free\s+repair\s+denied|warranty\s+void|claim\s+rejected)\b", text_lower):
        return CATEGORY_WARRANTY_DISPUTE
    if re.search(r"\b(misleading|false\s+promise|fake\s+discount|wrong\s+specs|fake\s+review)\b", text_lower):
        return CATEGORY_MISLEADING_REP
    if re.search(r"\b(unfair\s+trade|mrp\s+overcharg\w*|forced\s+bundling|hidden\s+charge)\b", text_lower):
        return CATEGORY_UNFAIR_TRADE
    if re.search(r"\b(refund|replace\w*|money\s+back)\b", text_lower):
        return CATEGORY_REFUND_REFUSAL

    return current_category or CATEGORY_ECOMMERCE


def create_empty_case(
    case_id: Optional[str] = None,
    issue_category: str = "",
    original_user_story: str = "",
    language_preference: str = "English",
) -> Dict[str, Any]:
    """
    Initializes a new structured case record strictly conforming to the Blueprint schema,
    extended with distinct seller vs marketplace tracking and analysis history.
    """
    cid = case_id or generate_case_id()
    now_iso = datetime.now().isoformat()
    resolved_category = infer_issue_category(original_user_story, issue_category)

    # Initialize empty case
    case_dict: Dict[str, Any] = {
        "case_id": cid,
        "status": STATUS_INTAKE,
        "issue_category": resolved_category,
        "issue_category_status": "PROVISIONAL",
        "original_user_story": original_user_story,
        "language_preference": language_preference,
        "state": None,
        "district": None,

        # Three Separate Decisions
        "classification_decision": {
            "inferred_category": resolved_category,
            "status": "PROVISIONAL",
            "decision_type": "DECISION_A_ISSUE_CLASSIFICATION",
        },
        "coverage_decision": {
            "status": "SUPPORTED_IN_KNOWLEDGE_BASE",
            "framework": "Consumer Protection Act, 2019 & E-Commerce Rules, 2020",
            "decision_type": "DECISION_B_LEGAL_COVERAGE",
        },
        "analysis_decision": {
            "status": "NOT_STARTED",
            "decision_type": "DECISION_C_LEGAL_ANALYSIS",
        },

        # Transaction & Product Details
        "product_or_service": None,
        "seller_or_platform": None,
        "seller_or_service_provider": None,
        "marketplace_or_platform": None,
        "purchase_amount": None,
        "purchase_currency": "INR",
        "purchase_date": None,
        "delivery_date": None,
        "problem_date": None,
        "expected_delivery_date": None,

        # Grievance Core
        "problem_description": None,
        "desired_resolution": None,

        # Seller & Marketplace Communication History
        "seller_contact": {
            "contacted": None,
            "contact_date": None,
            "contact_method": None,
            "seller_response": None,
        },
        "marketplace_contact": {
            "contacted": None,
            "contact_date": None,
            "contact_method": None,
            "marketplace_response": None,
        },

        # Chronology, Evidence & Document Checklist
        "events": [],
        "evidence": [],
        "evidence_checklist": [],
        "missing_information": [],
        "unknown_information": [],
        "safety_flags": [],
        "source_ids": [],

        # Intake Dialogue Tracking
        "pending_question": None,
        "questions_asked": [],
        "conversation_history": [],

        # Metadata & Provenance Tracking
        "fact_sources": {},
        "correction_history": [],
        "facts_confirmed_by_user": False,
        "latest_analysis": None,
        "analysis_history": [],
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    try:
        from src import evidence_checklist
        case_dict["evidence_checklist"] = evidence_checklist.generate_case_evidence_checklist(case_dict)
    except Exception as exc:
        logger.warning(f"Could not initialize evidence checklist: {exc}")

    return case_dict


def validate_fact_value(field: str, value: Any) -> Tuple[bool, Optional[str], Any]:
    """
    Validates and formats a fact value prior to updating or correcting a case record.
    Prevents cross-field contamination (e.g. monetary amounts entering platform fields).

    Returns:
        (is_valid: bool, error_message: Optional[str], cleaned_value: Any)
    """
    if value is None:
        return False, f"Value for '{field}' cannot be empty.", None

    val_str = str(value).strip()
    if not val_str:
        return False, f"Value for '{field}' cannot be empty.", None

    if field == "purchase_amount":
        # Strip currency symbols, commas, and formatting
        cleaned_num = re.sub(r"[₹\s,/-]|(?:rs\.?|inr|rupees)", "", val_str, flags=re.IGNORECASE).strip()
        try:
            amt_num = float(cleaned_num)
            if amt_num <= 0:
                return False, "Purchase amount must be a positive number greater than zero.", None
            if amt_num.is_integer():
                formatted_amt = f"₹{int(amt_num):,}"
            else:
                formatted_amt = f"₹{amt_num:,.2f}"
            return True, None, formatted_amt
        except (ValueError, TypeError):
            return False, f"Invalid monetary amount: '{val_str}'. Please enter a valid number (e.g. ₹26,000 or 26000).", None

    elif field in ("seller_or_platform", "seller_or_service_provider", "marketplace_or_platform"):
        # Disallow purely numeric input (e.g. user entered purchase amount into platform)
        cleaned_num = re.sub(r"[₹\s,/-]|(?:rs\.?|inr|rupees)", "", val_str, flags=re.IGNORECASE).strip()
        if cleaned_num.isdigit():
            return False, f"'{val_str}' is a numeric amount, not a valid seller, service provider, or platform name.", None
        if len(val_str) < 2:
            return False, "Name must be at least 2 characters.", None
        return True, None, val_str

    elif field in ("purchase_date", "delivery_date", "problem_date", "expected_delivery_date"):
        # Ensure date string is reasonable (at least 2 chars, not pure random digits without context)
        if len(val_str) < 2:
            return False, f"Date for '{field}' must be a valid date or time reference.", None
        return True, None, val_str

    elif field == "issue_category":
        if len(val_str) < 3:
            return False, "Issue category must be at least 3 characters.", None
        return True, None, val_str

    elif field == "product_or_service":
        cleaned_num = re.sub(r"[₹\s,/-]|(?:rs\.?|inr|rupees)", "", val_str, flags=re.IGNORECASE).strip()
        if cleaned_num.isdigit():
            return False, f"'{val_str}' is a numeric amount, not a valid product or service name.", None
        if len(val_str) < 2:
            return False, "Product or service name must be at least 2 characters.", None
        return True, None, val_str

    elif field == "desired_resolution":
        cleaned_num = re.sub(r"[₹\s,/-]|(?:rs\.?|inr|rupees)", "", val_str, flags=re.IGNORECASE).strip()
        if cleaned_num.isdigit():
            return False, f"'{val_str}' is a numeric amount, not a valid remedy request.", None
        if len(val_str) < 3:
            return False, "Desired resolution must be at least 3 characters.", None
        return True, None, val_str

    return True, None, val_str


def update_case_fact(
    case: Dict[str, Any],
    field: str,
    value: Any,
    source: str = "USER_STATEMENT",
    message_id: Optional[str] = None,
    overwrite: bool = True,
) -> bool:
    """Sets or updates a case fact while preserving its origin and provenance."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return False

    current_val = case.get(field)
    if current_val is not None and not overwrite:
        return False

    case[field] = value
    case["updated_at"] = datetime.now().isoformat()

    # Backwards-compatibility and cross-field sync
    if field == "seller_or_platform":
        if not case.get("seller_or_service_provider"):
            case["seller_or_service_provider"] = value
    elif field in ("seller_or_service_provider", "marketplace_or_platform"):
        if not case.get("seller_or_platform"):
            case["seller_or_platform"] = value

    if "fact_sources" not in case:
        case["fact_sources"] = {}

    source_type = "USER_STATEMENT"
    if source in ("USER_STATEMENT", "USER_CORRECTION", "DETERMINISTIC_EXTRACTION", "LLM_EXTRACTION"):
        source_type = source
    elif "CORRECTION" in source.upper():
        source_type = "USER_CORRECTION"
    elif "DETERMINISTIC" in source.upper() or "EXTRACTION" in source.upper():
        source_type = "DETERMINISTIC_EXTRACTION"

    case["fact_sources"][field] = {
        "field": field,
        "value": value,
        "source": source,
        "source_type": source_type,
        "message_id": message_id,
        "timestamp": datetime.now().isoformat(),
        "confirmed": False,
    }

    if "missing_information" in case and field in case["missing_information"]:
        case["missing_information"].remove(field)

    if "unknown_information" in case and field in case["unknown_information"]:
        case["unknown_information"].remove(field)

    return True


def correct_case_fact(
    case: Dict[str, Any],
    field: str,
    new_value: Any,
    source: str = "USER_CORRECTION",
    message_id: Optional[str] = None,
) -> bool:
    """Records a user correction to an existing case fact with validation and provenance audit."""
    if field == "original_user_story":
        return False

    is_valid, err_msg, cleaned_val = validate_fact_value(field, new_value)
    if not is_valid:
        return False

    old_value = case.get(field)
    case[field] = cleaned_val
    case["updated_at"] = datetime.now().isoformat()

    # Backwards-compatibility and cross-field sync
    if field == "seller_or_platform":
        if not case.get("seller_or_service_provider"):
            case["seller_or_service_provider"] = cleaned_val
    elif field in ("seller_or_service_provider", "marketplace_or_platform"):
        if not case.get("seller_or_platform"):
            case["seller_or_platform"] = cleaned_val
    elif field == "issue_category":
        case["issue_category_status"] = "CONFIRMED"
        if "classification_decision" in case and isinstance(case["classification_decision"], dict):
            case["classification_decision"]["status"] = "CONFIRMED"
            case["classification_decision"]["inferred_category"] = cleaned_val
        try:
            from src import evidence_checklist
            case["evidence_checklist"] = evidence_checklist.generate_case_evidence_checklist(case)
        except Exception:
            pass

    if "correction_history" not in case:
        case["correction_history"] = []

    case["correction_history"].append({
        "field": field,
        "old_value": old_value,
        "new_value": cleaned_val,
        "timestamp": datetime.now().isoformat(),
        "message_id": message_id,
    })

    if "fact_sources" not in case:
        case["fact_sources"] = {}

    case["fact_sources"][field] = {
        "field": field,
        "value": cleaned_val,
        "source": source,
        "source_type": "USER_CORRECTION",
        "message_id": message_id,
        "timestamp": datetime.now().isoformat(),
        "confirmed": True,
    }

    if "missing_information" in case and field in case["missing_information"]:
        case["missing_information"].remove(field)

    if "unknown_information" in case and field in case["unknown_information"]:
        case["unknown_information"].remove(field)

    return True


def mark_as_unknown(case: Dict[str, Any], field: str) -> None:
    """Records that the user explicitly indicated they do not know or lack this information."""
    if "unknown_information" not in case:
        case["unknown_information"] = []
    if field not in case["unknown_information"]:
        case["unknown_information"].append(field)

    if "missing_information" in case and field in case["missing_information"]:
        case["missing_information"].remove(field)

    case["updated_at"] = datetime.now().isoformat()


def add_event(
    case: Dict[str, Any],
    event: str,
    event_date: Optional[str] = None,
    source: str = "USER_STATEMENT",
    message_id: Optional[str] = None,
) -> None:
    """Adds a chronological event to the case timeline without duplicating existing events."""
    if not event or not event.strip():
        return

    cleaned_event = event.strip()
    if "events" not in case:
        case["events"] = []

    for existing in case["events"]:
        if existing.get("event", "").lower() == cleaned_event.lower():
            if event_date and not existing.get("date"):
                existing["date"] = event_date
            return

    case["events"].append({
        "event": cleaned_event,
        "date": event_date or "Not provided",
        "source": source,
        "message_id": message_id,
    })
    case["updated_at"] = datetime.now().isoformat()


def add_evidence(
    case: Dict[str, Any],
    item: str,
    description: Optional[str] = None,
    source: str = "USER_STATEMENT",
    message_id: Optional[str] = None,
) -> None:
    """Records an available piece of evidence into the case evidence inventory."""
    if not item or not item.strip():
        return

    cleaned_item = item.strip()
    if "evidence" not in case:
        case["evidence"] = []

    for existing in case["evidence"]:
        if existing.get("item", "").lower() == cleaned_item.lower():
            return

    case["evidence"].append({
        "item": cleaned_item,
        "description": description or cleaned_item,
        "source": source,
        "message_id": message_id,
    })
    case["updated_at"] = datetime.now().isoformat()


def confirm_case_facts(case: Dict[str, Any]) -> None:
    """Marks case facts as formally verified and confirmed by the consumer."""
    case["facts_confirmed_by_user"] = True
    case["issue_category_status"] = "CONFIRMED"
    if "classification_decision" in case and isinstance(case["classification_decision"], dict):
        case["classification_decision"]["status"] = "CONFIRMED"

    try:
        from src import evidence_checklist
        case["evidence_checklist"] = evidence_checklist.generate_case_evidence_checklist(case)
    except Exception as exc:
        logger.warning(f"Could not refresh evidence checklist on confirmation: {exc}")

    missing = compute_missing_information(case)
    # Check if important details remain unknown or missing
    has_gaps = bool(
        missing
        or not case.get("purchase_amount")
        or not case.get("product_or_service")
        or (not case.get("purchase_date") and not case.get("delivery_date"))
    )
    case["has_information_gaps"] = has_gaps
    case["status"] = STATUS_FACTS_CONFIRMED
    case["updated_at"] = datetime.now().isoformat()

    # Mark all currently extracted fact sources as confirmed
    if "fact_sources" in case:
        for field, meta in case["fact_sources"].items():
            if isinstance(meta, dict):
                meta["confirmed"] = True


def compute_missing_information(case: Dict[str, Any]) -> List[str]:
    """
    Computes which core facts are currently missing from the case.
    Considers fields marked as unknown as resolved.
    """
    missing = []
    unknown = set(case.get("unknown_information", []))

    # 1. Product/Service
    if not case.get("product_or_service") and "product_or_service" not in unknown:
        missing.append("product_or_service")

    # 2. Seller / Service Provider / Platform
    has_seller_info = bool(
        case.get("seller_or_platform")
        or case.get("seller_or_service_provider")
        or case.get("marketplace_or_platform")
    )
    if not has_seller_info and "seller_or_platform" not in unknown and "seller_or_service_provider" not in unknown:
        missing.append("seller_or_platform")

    # 3. Seller Contact
    sc = case.get("seller_contact", {})
    if sc.get("contacted") is None and "seller_contact" not in unknown:
        missing.append("seller_contact")
    elif sc.get("contacted") is True and not sc.get("seller_response") and "seller_response" not in unknown:
        missing.append("seller_response")

    # 4. Purchase Amount
    if not case.get("purchase_amount") and "purchase_amount" not in unknown:
        missing.append("purchase_amount")

    # 5. Desired Resolution
    if not case.get("desired_resolution") and "desired_resolution" not in unknown:
        missing.append("desired_resolution")

    case["missing_information"] = missing

    # Transition to FACTS_REVIEW when no missing facts remain
    if not missing and case.get("status") == STATUS_INTAKE:
        case["status"] = STATUS_FACTS_REVIEW

    return missing


def get_next_follow_up_question(
    case: Dict[str, Any],
    language: str = "English",
) -> Optional[str]:
    """
    Generates the next logical, category-aware intake question.
    Inspects full conversation history, current facts, and legal context.
    Prioritizes questions that materially affect the statutory analysis and legal route.
    """
    missing = compute_missing_information(case)
    is_hindi = language.lower() in ("hindi", "hinglish", "hindi/hinglish")

    # Aggregate all previously asked questions across questions_asked and conversation history
    asked = set(case.get("questions_asked", []))
    for msg in case.get("conversation_history", []):
        if isinstance(msg, dict) and msg.get("role") in ("assistant", "bot"):
            c = msg.get("text") or msg.get("content") or ""
            if c:
                asked.add(c.strip())

    category = case.get("issue_category", "")

    # Context A: Subscription / Unauthorized debit
    if category == CATEGORY_SUBSCRIPTION_UNAUTHORIZED:
        sub_q = "क्या आपने इस सब्सक्रिप्शन को रद्द करने का अनुरोध किया था, और क्या यह राशि आपकी सहमति के बिना काटी गई?" if is_hindi else "Did you request cancellation or dispute this recurring charge with the provider, and what was their response?"
        if sub_q not in asked and "seller_contact" in missing:
            return sub_q

    # Priority 1: Seller Contact
    if "seller_contact" in missing:
        if is_hindi:
            q = "क्या आपने इस समस्या के बारे में विक्रेता (seller) या प्लेटफॉर्म से संपर्क किया है, और उनका क्या जवाब था?"
        else:
            q = "Have you contacted the seller or customer care regarding this issue, and if so, what was their response?"

        if q not in asked:
            return q

    # Priority 2: Seller Response
    if "seller_response" in missing:
        if is_hindi:
            q = "विक्रेता या कस्टमर केयर ने संपर्क करने पर क्या प्रतिक्रिया दी (उदा. फोन नहीं उठाया, मना कर दिया, या समय मांगा)?"
        else:
            q = "What specific response or reason did the seller or customer care provide when you contacted them?"

        if q not in asked:
            return q

    # Priority 3: Product / Platform
    if "product_or_service" in missing or "seller_or_platform" in missing:
        if "product_or_service" in missing and "seller_or_platform" in missing:
            if is_hindi:
                q = "कृपया बताएं कि आपने कौन सा उत्पाद (product) या सेवा खरीदी थी और यह किस विक्रेता या प्लेटफॉर्म (उदा. Amazon, Flipkart, लोकल दुकान) से ली गई थी?"
            else:
                q = "Could you please share the specific product or service involved, and the name of the seller or platform (e.g., Amazon, Flipkart, local store)?"
        elif "product_or_service" in missing:
            if case.get("issue_category") == CATEGORY_INCORRECT_ITEM:
                if is_hindi:
                    q = "कृपया बताएं कि आपने वास्तव में कौन सा उत्पाद (product) ऑर्डर किया था और उसके बदले आपको कौन सा सामान डिलीवर हुआ?"
                else:
                    q = "Could you please specify which product you originally ordered and what item was actually delivered?"
            elif is_hindi:
                q = "कृपया उस उत्पाद (product) या सेवा का विशिष्ट नाम या मॉडल बताएं जिससे यह समस्या जुड़ी है।"
            else:
                q = "Could you please specify the exact product name, model, or service type involved?"
        else:
            if is_hindi:
                q = "आपने यह उत्पाद या सेवा किस विक्रेता, कंपनी या ई-कॉमर्स प्लेटफॉर्म से खरीदी थी?"
            else:
                q = "Which seller, company, or e-commerce platform did you purchase this product or service from?"

        if q not in asked:
            return q

    # Context B: Harm Scope / Bodily Injury check for Defective or Damaged Goods
    # Resolves Section 2(22) Product Liability gating vs Section 39(1) Defect
    if category == CATEGORY_DEFECTIVE_GOODS or "damage" in category.lower():
        harm_q = (
            "क्या यह क्षति केवल उत्पाद तक ही सीमित थी, या इसके कारण कोई शारीरिक चोट या किसी अन्य संपत्ति का नुकसान भी हुआ?"
            if is_hindi
            else "Was the damage strictly limited to the product itself, or did it cause any personal physical injury or damage to other property?"
        )
        if harm_q not in asked and not case.get("harm_scope_clarified"):
            # Only ask once if not already answered
            user_story = (case.get("original_user_story") or "").lower()
            if not any(k in user_story for k in ["injur", "burn", "hospital", "shock", "blood"]):
                return harm_q

    # Context C: Non-delivery order / delivery date inquiry
    if (category == CATEGORY_NON_DELIVERY or "delivery" in category.lower()) and not case.get("delivery_date") and not case.get("expected_delivery_date"):
        date_q = "इस ऑर्डर की अपेक्षित डिलीवरी तारीख (expected delivery date) या बुकिंग तारीख क्या थी?" if is_hindi else "What was the promised or expected delivery date for this order?"
        if date_q not in asked and "delivery_date" not in case.get("unknown_information", []):
            return date_q

    # Context D: Service Deficiency Duration & Docket Number
    if category == CATEGORY_SERVICE_DEFICIENCY:
        service_q = (
            "यह सेवा व्यवधान या कमी कितने समय से चल रही है, और क्या आपके पास कस्टमर सपोर्ट का कोई शिकायत या डॉकेट नंबर है?"
            if is_hindi
            else "How long has this service deficiency or disruption persisted, and do you have a complaint docket or ticket reference number?"
        )
        if service_q not in asked and not case.get("service_duration_clarified"):
            return service_q

    # Context E: Warranty Dispute & Service Center Denial
    if category == CATEGORY_WARRANTY_DISPUTE:
        warr_q = (
            "क्या अधिकृत सर्विस सेंटर ने उत्पाद का निरीक्षण किया, और वारंटी सेवा से इनकार करने का क्या कारण बताया गया?"
            if is_hindi
            else "Did the authorized service center inspect the product, and what specific reason did they provide for refusing warranty coverage?"
        )
        if warr_q not in asked and not case.get("warranty_denial_clarified"):
            return warr_q

    # Priority 4: Purchase Amount
    if "purchase_amount" in missing:
        if is_hindi:
            q = "इस उत्पाद या सेवा के लिए आपने लगभग कितनी राशि (रुपये में) का भुगतान किया था?"
        else:
            q = "What was the approximate purchase or transaction amount (in INR) paid for this item or service?"

        if q not in asked:
            return q

    # Priority 5: Desired Resolution
    if "desired_resolution" in missing:
        if is_hindi:
            q = "आप इस मामले में क्या समाधान चाहते हैं (जैसे पूरा रिफंड, नया सामान/रिप्लेसमेंट, मुफ्त मरम्मत, या हर्जाना)?"
        else:
            q = "What outcome or remedy are you seeking (e.g., full refund, product replacement, free repair, or compensation)?"

        if q not in asked:
            return q

    return None


def extract_case_facts_deterministically(
    case: Dict[str, Any],
    user_message: str,
    pending_question: Optional[str] = None,
    message_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Robust rule-based extractor that extracts concrete consumer facts from user answers.
    Ensures zero reliance on external LLM availability for basic intake continuity.
    """
    text = user_message.strip()
    text_lower = text.lower()
    mid = message_id or f"MSG_{len(case.get('conversation_history', [])) + 1:03d}"

    # 1. Check for explicit "I don't know" or "Not sure"
    if re.search(r"\b(don'?t\s+know|not\s+sure|no\s+idea|pata\s+nahi|yaad\s+nahi)\b.*?\b(amount|price|cost|paise|kharcha)\b|\b(amount|price|cost|paise|kharcha)\b.*?\b(don'?t\s+know|not\s+sure|no\s+idea|pata\s+nahi|yaad\s+nahi)\b", text_lower):
        mark_as_unknown(case, "purchase_amount")
    elif re.search(r"\b(i\s+don'?t\s+know|don'?t\s+remember|not\s+sure|no\s+idea|pata\s+nahi|yaad\s+nahi)\b", text_lower):
        if pending_question:
            pq_lower = pending_question.lower()
            if "date" in pq_lower:
                mark_as_unknown(case, "purchase_date")
            elif "amount" in pq_lower or "price" in pq_lower or "pay" in pq_lower or "राशि" in pq_lower:
                mark_as_unknown(case, "purchase_amount")
            elif "seller" in pq_lower or "platform" in pq_lower or "विक्रेता" in pq_lower:
                mark_as_unknown(case, "seller_or_platform")
            elif "tracking" in pq_lower or "order" in pq_lower:
                mark_as_unknown(case, "order_number")
            elif "contact" in pq_lower or "संपर्क" in pq_lower:
                mark_as_unknown(case, "seller_contact")

    # 2. Seller Contact extraction
    is_neg_contact = bool(re.search(
        r"^(?:no\b|nah\b)|(?:haven'?t|didn'?t|did\s+not|never|not\s+yet)\s+(?:contacted|called|reached|complained)\b|\b(nahi\s+kiya|baat\s+nahi\s+hui)\b",
        text_lower,
    ))
    has_seller_response_mention = bool(re.search(
        r"\b(not\s+receiving\s+calls?|not\s+answering|no\s+response|not\s+responding|unanswered|phone\s+not\s+pick|call\s+nahi\s+uthaya|switched\s+off|refus\w*|deni\w*|deny\w*|rejected|declined)\b",
        text_lower,
    ))
    is_pos_contact = bool(re.search(
        r"^(?:yes\b|yeah\b|yep\b|haan\b)|\b(call|calls|called|calling|phoned|emailed|complained|talked|baat\s+ki|call\s+kiya|mail\s+kiya)\b",
        text_lower,
    )) or has_seller_response_mention or ("contacted" in text_lower and not is_neg_contact)

    # Contradictory contact detection (e.g. user says both "never contacted" and "called them")
    has_contradiction = False
    if is_neg_contact and bool(re.search(r"\b(called|phoned|emailed|complained|talked|reached\s+out)\b", text_lower)):
        has_contradiction = True
    elif re.search(r"\b(never\s+contacted|did\s+not\s+contact)\b", text_lower) and re.search(r"\b(called|phoned|emailed)\b", text_lower):
        has_contradiction = True

    if has_contradiction:
        if "safety_flags" not in case:
            case["safety_flags"] = []
        if "CONTRADICTORY_CONTACT_METHOD" not in case["safety_flags"]:
            case["safety_flags"].append("CONTRADICTORY_CONTACT_METHOD")

    if is_neg_contact and not (text_lower.startswith("yes") or text_lower.startswith("haan")):
        case["seller_contact"]["contacted"] = False
        case["seller_contact"]["seller_response"] = "Not yet contacted"
        case["seller_contact"]["contact_method"] = "None"
        if "seller_contact" in case.get("missing_information", []):
            case["missing_information"].remove("seller_contact")
        if "seller_response" in case.get("missing_information", []):
            case["missing_information"].remove("seller_response")
    elif is_pos_contact:
        case["seller_contact"]["contacted"] = True
        if "seller_contact" in case.get("missing_information", []):
            case["missing_information"].remove("seller_contact")

        # Contact Method (Only attribute phone or email if explicitly stated)
        has_phone = bool(re.search(r"\b(call|calls|called|calling|phone|phoned|phoning|rang|telephon\w*)\b", text_lower))
        has_email = bool(re.search(r"\b(email\w*|e-mail\w*|mail|mailed|mailing|written)\b", text_lower))
        has_chat = bool(re.search(r"\b(chat|app|portal|website|customer\s+care)\b", text_lower))

        if has_phone:
            case["seller_contact"]["contact_method"] = "phone call"
        elif has_email:
            case["seller_contact"]["contact_method"] = "email"
        elif has_chat:
            case["seller_contact"]["contact_method"] = "in-app customer chat / portal"
        else:
            if not case["seller_contact"].get("contact_method") or case["seller_contact"].get("contact_method") == "None":
                case["seller_contact"]["contact_method"] = "Unknown"

        # Seller Response
        if re.search(r"\b(not\s+receiving\s+calls?|not\s+answering|no\s+response|not\s+responding|unanswered|phone\s+not\s+pick|call\s+nahi\s+uthaya|switched\s+off)\b", text_lower):
            case["seller_contact"]["seller_response"] = "Seller is not receiving calls / no response"
            if has_phone:
                add_event(case, "Seller contacted via phone; calls unanswered", source="USER_STATEMENT", message_id=mid)
            elif has_email:
                add_event(case, "Seller contacted via email; response not received", source="USER_STATEMENT", message_id=mid)
            elif has_chat:
                add_event(case, "Seller contacted via portal/chat; response not received", source="USER_STATEMENT", message_id=mid)
            else:
                add_event(case, "Seller contacted; response not received (method and date not provided)", source="USER_STATEMENT", message_id=mid)
            if "seller_response" in case.get("missing_information", []):
                case["missing_information"].remove("seller_response")
        elif re.search(r"\b(refus\w*|deni\w*|deny\w*|rejected|declined|mana\s+kar\s+diya)\b", text_lower):
            case["seller_contact"]["seller_response"] = "Seller refused assistance"
            add_event(case, "Seller contacted; assistance or refund refused", source="USER_STATEMENT", message_id=mid)
            if "seller_response" in case.get("missing_information", []):
                case["missing_information"].remove("seller_response")
        elif re.search(r"\b(promised|agreed|assurance|bola\s+ho\s+jayega)\b", text_lower):
            case["seller_contact"]["seller_response"] = "Seller promised resolution but delayed"
            add_event(case, "Seller contacted; promised resolution but not fulfilled", source="USER_STATEMENT", message_id=mid)
            if "seller_response" in case.get("missing_information", []):
                case["missing_information"].remove("seller_response")

    # 3. Currency / Purchase Amount extraction
    amount_match = re.search(r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d{2})?)|([\d,]+)\s*(?:rupees|rs\.?|inr|₹)", text, re.IGNORECASE)
    if amount_match:
        amt_str = amount_match.group(1) or amount_match.group(2)
        cleaned_amt = f"₹{amt_str.strip()}"
        update_case_fact(case, "purchase_amount", cleaned_amt, source="USER_STATEMENT", message_id=mid)

    # 4. Seller or Platform extraction
    platforms = [
        "Amazon", "Flipkart", "Myntra", "Meesho", "Swiggy", "Zomato", "Tata CliQ",
        "JioMart", "Nykaa", "Reliance Digital", "Croma", "Blinkit", "Zepto", "Samsung", "Dell",
        "MakeMyTrip", "Airtel", "Jio", "Vodafone", "Vi", "Uber", "Ola"
    ]
    for plat in platforms:
        if re.search(rf"\b{re.escape(plat)}\b", text, re.IGNORECASE):
            update_case_fact(case, "seller_or_platform", plat, source="USER_STATEMENT", message_id=mid)
            break

    if not case.get("seller_or_platform") and re.search(r"\b(airline|flight\s+booking)\b", text_lower):
        update_case_fact(case, "seller_or_platform", "Airline Service Provider", source="USER_STATEMENT", message_id=mid)

    # 5. Product or Service identification
    # A. Check for explicit ordered vs delivered item distinction
    ordered_received_match = re.search(
        r"ordered\s+([a-zA-Z0-9\s]+?)\s+(?:but|,|and)?\s*(?:received|got|delivered)\s+([a-zA-Z0-9\s]+?)(?:\.|$|,|\bfrom\b|\bvia\b|\bon\b)",
        text,
        re.IGNORECASE,
    )
    if ordered_received_match:
        p_ord = ordered_received_match.group(1).strip()
        p_rec = ordered_received_match.group(2).strip()
        p_ord_clean = re.sub(r"^(?:a|an|the)\s+", "", p_ord, flags=re.IGNORECASE).strip()
        p_rec_clean = re.sub(r"^(?:a|an|the)\s+", "", p_rec, flags=re.IGNORECASE).strip()
        if p_ord_clean and p_rec_clean and len(p_ord_clean) < 35 and len(p_rec_clean) < 35:
            case["product_ordered"] = p_ord_clean
            case["product_delivered"] = p_rec_clean
            combo_val = f"{p_ord_clean} (ordered) / {p_rec_clean} (delivered)"
            update_case_fact(case, "product_or_service", combo_val, source="USER_STATEMENT", message_id=mid)
            if "product_or_service" in case.get("missing_information", []):
                case["missing_information"].remove("product_or_service")

    # B. Match standard product types
    products = [
        ("mobile phone", [r"\b(mobile|phone|smartphone|iphone|android|oneplus|samsung)\b"]),
        ("air conditioner", [r"\b(ac|air\s+conditioner|split\s+ac)\b"]),
        ("laptop", [r"\b(laptop|macbook|dell|hp|lenovo)\b"]),
        ("refrigerator", [r"\b(refrigerator|fridge)\b"]),
        ("washing machine", [r"\b(washing\s+machine)\b"]),
        ("television", [r"\b(tv|television|led\s+tv|smart\s+tv)\b"]),
        ("air cooler", [r"\b(cooler|air\s+cooler)\b"]),
        ("flight ticket", [r"\b(flight\s+ticket|flight|airline|flight\s+booking)\b"]),
        ("broadband internet", [r"\b(broadband|wifi|internet\s+connection)\b"]),
        ("food delivery", [r"\b(dinner|lunch|meal|food|swiggy|zomato)\b"]),
        ("footwear / apparel", [r"\b(shoes|footwear|shirt|dress|clothing|clothes|jeans)\b"]),
    ]
    for prod_name, prod_pats in products:
        for p in prod_pats:
            if re.search(p, text_lower):
                update_case_fact(case, "product_or_service", prod_name, source="USER_STATEMENT", message_id=mid, overwrite=False)
                break

    # 6. Desired Resolution extraction (ensure distinct from seller refusal)
    is_answering_remedy_q = bool(pending_question and any(w in pending_question.lower() for w in ["outcome", "remedy", "seeking", "resolution", "समाधान", "चाहते"]))
    has_remedy_intent = bool(re.search(r"\b(want|seeking|require|requesting|demand|need|chahiye|claim|give\s+me|hope\s+for|desired)\b", text_lower))
    clean_remedy_text = re.sub(r"\b(refus\w*|deni\w*|did\s+not|didn'?t|never)\s+(?:to\s+)?(?:free\s+)?(?:refund|replace\w*|repair\w*|help)\b", "", text_lower)

    if has_remedy_intent or is_answering_remedy_q:
        if re.search(r"\b(compensation|damages|harzana|harjana)\b", clean_remedy_text):
            update_case_fact(case, "desired_resolution", "Refund and compensation for harassment/deficiency", source="USER_STATEMENT", message_id=mid)
        elif re.search(r"\b(refund|money\s+back|paise\s+wapas|reimburse|wapas)\b", clean_remedy_text):
            update_case_fact(case, "desired_resolution", "Full refund of purchase amount", source="USER_STATEMENT", message_id=mid)
        elif re.search(r"\b(replace|replacement|exchange|naya\s+samaan|new\s+piece)\b", clean_remedy_text):
            update_case_fact(case, "desired_resolution", "Replacement with non-defective product", source="USER_STATEMENT", message_id=mid)
        elif re.search(r"\b(repair|service|theek)\b", clean_remedy_text):
            update_case_fact(case, "desired_resolution", "Free repair under warranty", source="USER_STATEMENT", message_id=mid)
    elif not case.get("desired_resolution") and re.search(r"\b(?:denying|refusing|refused|denied)\s+to\s+(?:provide\s+)?(replace\s+or\s+refund|refund\s+or\s+replace)\b", text_lower):
        update_case_fact(case, "desired_resolution", "Replacement or full refund of purchase amount", source="USER_STATEMENT", message_id=mid)

    # 7. Evidence extraction
    evidence_types = [
        ("Invoice / Bill", r"\b(invoice|bill|receipt|cash\s+memo|tax\s+invoice)\b"),
        ("Photographs / Video", r"\b(photo|photos|photograph|picture|pic|video|recording)\b"),
        ("Payment Proof", r"\b(bank\s+statement|upi\s+transaction|payment\s+screenshot|credit\s+card\s+slip)\b"),
        ("Order / Delivery Tracking", r"\b(tracking\s+id|tracking\s+status|order\s+id|order\s+screenshot)\b"),
        ("Written Communication", r"\b(email\s+thread|chat\s+history|complaint\s+ticket|grievance\s+number)\b"),
    ]
    for ev_label, ev_pat in evidence_types:
        if re.search(ev_pat, text_lower):
            add_evidence(case, ev_label, description=f"Mentioned in user statement: '{text[:80]}'", source="USER_STATEMENT", message_id=mid)

    # 8. Timeline Event inference
    if "ordered" in text_lower or "kharida" in text_lower or "purchased" in text_lower or "bought" in text_lower:
        add_event(case, "Product purchased / order placed", source="USER_STATEMENT", message_id=mid)
    if "delivered" in text_lower or "received" in text_lower or "mil gaya" in text_lower:
        add_event(case, "Product delivered / received by consumer", source="USER_STATEMENT", message_id=mid)
    if "wrong item" in text_lower or "incorrect item" in text_lower or "galat samaan" in text_lower:
        add_event(case, "Incorrect / wrong item delivered", source="USER_STATEMENT", message_id=mid)
    if "stopped working" in text_lower or "defective" in text_lower or "damaged" in text_lower or "toot gaya" in text_lower:
        add_event(case, "Defect / damage observed", source="USER_STATEMENT", message_id=mid)

    # 9. Dynamic Issue Category Refinement
    refined_cat = infer_issue_category(text, case.get("issue_category"))
    if refined_cat and case.get("issue_category") != refined_cat:
        if case.get("issue_category") in (None, "", "Defective or damaged goods", "I am not sure") or refined_cat == CATEGORY_INCORRECT_ITEM:
            case["issue_category"] = refined_cat

    compute_missing_information(case)
    case["updated_at"] = datetime.now().isoformat()
    return case
