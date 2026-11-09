"""
Safety, Escalation, and Explicit Abstention Module for Nyaya Saathi.

Blueprint Step 19: Safety, Escalation, and Explicit Abstention.

Provides a multi-tier, deterministic safety and abstention firewall:
1. Turn-by-Turn Safety Evaluation (evaluated on every turn: initial, follow-ups, edits).
2. Five Core Safety Classifications:
   - URGENT_ESCALATION (immediate danger, physical threat, fire, smoking, electric shock -> 112)
   - HIGH_RISK_LEGAL_REVIEW (court notice, summons, limitation expiry, severe injury, criminal coercion)
   - OUTSIDE_SCOPE (tenancy, employment, matrimonial, property, coding, relationship)
   - NEEDS_CLARIFICATION (vague, ambiguous, or unrecognizable inquiries)
   - NORMAL_CONSUMER_DISPUTE (ordinary Indian consumer grievance workflow)
3. Explicit Abstention Engine:
   - Abstains when official legal sources are absent or insufficient.
   - Abstains when citations fail verification or claims lack textual support.
   - Enforces future-effective gating (G.S.R. 789(E) commencement on 2027-01-01).
   - Enforces provisional treatment of unconfirmed case facts.
4. Final Answer Safety Gate:
   - Evaluates generated answers and citation checker reports before delivery to user.
   - Blocks unsafe claims and prevents guaranteed outcome promises.
"""

from datetime import date, datetime
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from src import citation_checker
from src import safety

logger = logging.getLogger("safety_guard")

# ---------------------------------------------------------------------------
# Classification & Risk Constants
# ---------------------------------------------------------------------------

CATEGORY_URGENT_ESCALATION = "URGENT_ESCALATION"
CATEGORY_HIGH_RISK_LEGAL_REVIEW = "HIGH_RISK_LEGAL_REVIEW"
CATEGORY_OUTSIDE_SCOPE = "OUTSIDE_SCOPE"
CATEGORY_NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
CATEGORY_NORMAL_CONSUMER_DISPUTE = "NORMAL_CONSUMER_DISPUTE"

RISK_CRITICAL = "CRITICAL"
RISK_HIGH = "HIGH"
RISK_MEDIUM = "MEDIUM"
RISK_LOW = "LOW"

# Gate Statuses
GATE_PASSED = "PASSED"
GATE_ABSTENTION_REQUIRED = "ABSTENTION_REQUIRED"
GATE_UNSAFE_BLOCKED = "UNSAFE_BLOCKED"

# Official Emergency and Consumer Helplines in India
EMERGENCY_NUMBER_INDIA = "112"
NCH_HELPLINE_NUMBER = "1915"
CYBER_CRIME_NUMBER = "1930"

# Standard Explicit Abstention Statement (Blueprint Step 19 Part E)
STANDARD_ABSTENTION_STATEMENT = (
    "The available legal sources in Nyaya Saathi are insufficient to verify this point. "
    "I don't want to give you an unsupported legal answer."
)

# ---------------------------------------------------------------------------
# High-Risk Legal Review Patterns (Part C.2)
# ---------------------------------------------------------------------------

HIGH_RISK_LEGAL_PATTERNS = {
    "court_notice_or_summons": [
        r"\b(court\s+notice|summons|warrant|subpoena|court\s+hearing|matter\s+is\s+in\s+court)\b",
        r"\b(notice\s+from\s+advocate|advocate\s+notice|legal\s+notice\s+received|vakil\s+ka\s+notice)\b",
        r"\b(appear\s+before\s+(court|commission|magistrate)|bailable|non-bailable)\b",
        r"\b(court\s+ka\s+notice|peshi|adalat|court\s+order)\b",
    ],
    "limitation_or_deadline": [
        r"\b(limitation\s+(period|deadline|issue|date)?|time[\s-]bar(red)?|last\s+day\s+to\s+file)\b",
        r"\b(deadline\s+(is|approaching|expir(ing|ed)?)|last\s+date\s+to\s+respond)\b",
        r"\b(appeal\s+period|statutory\s+deadline|statutory\s+period|limitation\s+issue)\b",
        r"\b(appeal\s+within\s+\d+\s+days|\d+\s+days?\s+(appeal|deadline|limitation|notice\s+period|to\s+(appeal|file|respond)))\b",
        r"\b(within\s+\d+\s+days?\s+to\s+(appeal|respond|file))\b",
        r"\b(aakhri\s+tareekh|samay\s+seema\s+samapt|samay\s+seema)\b",
    ],
    "severe_physical_injury": [
        r"\b(permanent\s+disability|severe\s+burn\s+injury|hospitali[zs]ed\s+due\s+to\s+defect)\b",
        r"\b(fatal(ity)?|death\s+caused\s+by|loss\s+of\s+limb|severe\s+electric\s+shock\s+injury)\b",
        r"\b(icu|intensive\s+care|deep\s+burns|fractured\s+skull)\b",
    ],
    "criminal_conduct_or_threats": [
        r"\b(extortion|blackmail|fraud\s+syndicate|threatened\s+physical\s+violence)\b",
        r"\b(seller\s+threatened\s+my\s+life|goons\s+sent|threatened\s+family|kidnap)\b",
        r"\b(jaan\s+se\s+marne\s+ki\s+dhamki|hafta\s+vasooli|gundey)\b",
    ],
    "multiple_proceedings": [
        r"\b(high\s+court\s+writ|writ\s+petition|nclt|insolvency\s+proceedings|fir\s+already\s+filed)\b",
        r"\b(police\s+case\s+pending|civil\s+suit\s+pending|arbitration\s+clause\s+invoked)\b",
    ],
    "complex_transitional_law": [
        r"\b(transitional\s+application|retrospective\s+applicability|pre-commencement\s+transaction)\b",
        r"\b(repealed\s+1986\s+act\s+vs\s+2019\s+act|amendment\s+retrospective|is\s+the\s+amendment\s+retrospective)\b",
        r"\b(retrospective|retrospectively|commencement\s+date|transitional\s+law|transitional\s+provision)\b",
    ],
}

# General non-consumer domain extra patterns (coding, relationship advice)
EXTRA_OUTSIDE_SCOPE_PATTERNS = {
    "coding_software": [
        r"\b(write\s+(a\s+)?python\s+code|binary\s+search|react\s+component|debug\s+this\s+code|javascript\s+function|sql\s+query\s+to\s+join)\b",
        r"\b(html\s+css|docker\s+compose|git\s+commit|machine\s+learning\s+model|api\s+endpoint)\b",
    ],
    "relationship_personal": [
        r"\b(how\s+do\s+i\s+talk\s+to\s+my\s+(boyfriend|girlfriend|crush|husband|wife))\b",
        r"\b(breakup\s+advice|dating\s+advice|love\s+problem|friend\s+stopped\s+talking)\b",
    ],
    "general_academic": [
        r"\b(who\s+wrote\s+hamlet|solve\s+this\s+calculus|capital\s+of\s+france|photosynthesis\s+equation)\b",
    ],
}

# ---------------------------------------------------------------------------
# Specific Urgent Threat Patterns (Smoking, Fire, Electric Shock, Immediate Danger)
# ---------------------------------------------------------------------------

SMOKING_FIRE_PATTERNS = [
    r"\b(smok(ing|e)|burning\s+smell|fire|caught\s+fire|flames|spark(ing|s)?)\b",
    r"\b(exploded|burst|blast|shock(ing)?|electric\s+shock|current\s+mar\s+raha\s+hai)\b",
    r"(धुआं|धुआँ|धुएं|धुआ|आग\s+लग|जल\s+रहा|करंट|बिजली\s+का\s+झटका)",
    r"\b(dhuen?|aag\s+lag\s+gayi|jal\s+raha|dhuan)\b",
]


def detect_smoking_or_fire_hazard(text: str) -> Tuple[bool, Optional[str]]:
    """Detects immediate physical hazards such as appliance smoking, sparks, or fire."""
    clean = text.strip()
    for pat in SMOKING_FIRE_PATTERNS:
        m = re.search(pat, clean, re.IGNORECASE)
        if m:
            matched = m.group(0)
            return True, f"Detected active appliance hazard / fire danger indicator: '{matched}'"
    return False, None


AMBIGUOUS_INITIAL_PATTERNS = [
    r"\b(i\s+need\s+legal\s+help|need\s+legal\s+help|need\s+help\s+with\s+a\s+problem|have\s+a\s+(legal\s+)?problem|some\s+problem|cheat(ed)?\s+me)\b",
    r"\b(mujhe\s+legal\s+madad|madad\s+chahiye|kuch\s+problem\s+hai)\b",
    r"^(help|legal\s+advice|problem|advice|consumer\s+help)$",
]

SUBSTANTIVE_CONSUMER_KEYWORDS = [
    "phone", "mobile", "laptop", "tv", "refrigerator", "fridge", "car", "bike", "flight",
    "ticket", "hotel", "amazon", "flipkart", "seller", "order", "delivery", "delivered",
    "refund", "warranty", "defective", "broken", "package", "service", "appliance", "course",
    "bill", "invoice", "payment", "rupees", "rs", "inr", "crore", "lakh"
]


def is_vague_initial_turn(text: str) -> Tuple[bool, Optional[str]]:
    """Detects vague or ambiguous user inquiries on initial turns."""
    is_vague, reason = safety.is_text_vague_or_insufficient(text)
    if is_vague:
        return True, reason
    clean = text.lower().strip()
    has_substantive = any(k in clean for k in SUBSTANTIVE_CONSUMER_KEYWORDS)
    if not has_substantive:
        for pat in AMBIGUOUS_INITIAL_PATTERNS:
            m = re.search(pat, clean)
            if m:
                return True, f"Ambiguous generic inquiry lacking product/transaction facts ('{m.group(0)}')"
    return False, None


def detect_high_risk_legal_review(text: str) -> Tuple[bool, List[str], Optional[str]]:
    """
    Detects situations requiring professional advocate / legal counsel review:
    - Court notice, summons, subpoenas
    - Imminent limitation / statutory appeal deadlines
    - Severe personal physical injury
    - Criminal coercion or physical threats
    - Multiple active court proceedings / insolvency
    - Complex transitional statutory applicability
    """
    clean = text.lower().strip()
    reason_codes = []
    reasons = []

    for category, patterns in HIGH_RISK_LEGAL_PATTERNS.items():
        for pat in patterns:
            m = re.search(pat, clean, re.IGNORECASE)
            if m:
                matched = m.group(0)
                code = f"HIGH_RISK_{category.upper()}"
                if code not in reason_codes:
                    reason_codes.append(code)
                    reasons.append(f"{category.replace('_', ' ').title()} ('{matched}')")

    if reason_codes:
        summary_reason = f"Identified matter requiring qualified legal professional review: {'; '.join(reasons)}."
        return True, reason_codes, summary_reason

    return False, [], None


def detect_extended_outside_scope(text: str) -> Tuple[bool, str, Optional[str]]:
    """Checks for non-consumer queries including coding, general academia, and relationship advice."""
    clean = text.lower().strip()
    for domain, patterns in EXTRA_OUTSIDE_SCOPE_PATTERNS.items():
        for pat in patterns:
            m = re.search(pat, clean, re.IGNORECASE)
            if m:
                matched = m.group(0)
                readable = domain.replace("_", " ").title()
                reason = f"Query appears to be a general {readable} question ('{matched}'), not an Indian consumer dispute."
                return True, f"OUTSIDE_SCOPE_{domain.upper()}", reason

    return False, "", None


# ---------------------------------------------------------------------------
# Turn-Level Safety Evaluator (Part B & C & D)
# ---------------------------------------------------------------------------

def evaluate_turn_safety(
    user_message: str,
    active_case: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    language: str = "English",
) -> Dict[str, Any]:
    """
    Evaluates safety on EVERY user turn (initial message, follow-up, edits, fact confirmation).
    Operates strictly under deterministic precedence.

    Returns structured decision dictionary matching Part H specification:
    - classification
    - risk_level
    - reason_codes
    - requires_human_review
    - requires_immediate_action
    - allow_normal_legal_generation
    - abstention_required
    - user_message
    - developer_notes
    """
    clean_text = (user_message or "").strip()
    is_hindi = language.lower() in ("hindi", "hinglish", "hindi/hinglish")

    # 1. IMMEDIATE URGENT PHYSICAL THREAT / FIRE / SMOKING CHECK (Highest Priority)
    # Check appliance fire / smoking / explosion hazard
    has_fire_hazard, fire_reason = detect_smoking_or_fire_hazard(clean_text)
    is_urgent_general, safety_flags, urgent_reason = safety.detect_urgent_safety_signals(clean_text)

    # Distinguish ordinary delay from emergency:
    # "my refund is delayed 45 days" or "seller refused refund" must NOT be treated as an emergency
    is_refund_only = bool(re.search(r"\b(refund|return|money\s+back|replacement)\b", clean_text.lower())) and not any(
        k in clean_text.lower() for k in ["kill", "murder", "threat", "fire", "smoke", "burn", "shock", "blood", "bleed", "hospital", "poison", "chot", "jaan"]
    )

    # Distinguish legal notices/court threats from physical violence emergencies
    is_legal_threat_only = bool(
        re.search(
            r"\b(legal\s+notice|court\s+proceeding|court\s+notice|lawsuit|summons|advocate\s+notice|defamation\s+notice)\b",
            clean_text,
            re.IGNORECASE,
        )
    ) and not any(
        k in clean_text.lower()
        for k in ["kill", "murder", "physic", "assault", "beat", "weapon", "knife", "gun", "fire", "smoke", "burn", "shock", "blood", "poison", "chot", "jaan", "suicid"]
    )

    if (has_fire_hazard or is_urgent_general) and not is_refund_only and not is_legal_threat_only:
        reason_codes = []
        if has_fire_hazard:
            reason_codes.append("URGENT_FIRE_HAZARD")
        if "IMMEDIATE_DANGER" in safety_flags or any(k in clean_text.lower() for k in ["threat", "kill", "murder", "weapon"]):
            reason_codes.append("URGENT_PHYSICAL_THREAT")
        if "PHYSICAL_HARM" in safety_flags or any(k in clean_text.lower() for k in ["bleed", "hospital", "poison", "injur"]):
            reason_codes.append("URGENT_MEDICAL_EMERGENCY")
        if not reason_codes:
            reason_codes.append("URGENT_SAFETY_HAZARD")

        # Compose immediate user guidance: Safety instruction FIRST, Call 112, No legal jargon
        if is_hindi:
            user_msg = (
                "🚨 **तत्काल सहायता निर्देश (Immediate Emergency Notice):**\n\n"
                "**कृपया तुरंत अपनी सुरक्षा सुनिश्चित करें। आपातकालीन स्थिति में तुरंत 112 डायल करें।**\n\n"
                "- यदि किसी उपकरण से धुआं, आग या चिंगारी निकल रही है, तो तुरंत मुख्य बिजली स्विच (Main Switch) बंद करें और उपकरण से दूर हटें।\n"
                "- यदि कोई शारीरिक खतरा या चिकित्सा आपातकाल है, तो **112 (राष्ट्रीय आपातकालीन नंबर)** पर कॉल करें।\n\n"
                "न्याय साथी (Nyaya Saathi) एक सूचनात्मक सॉफ्टवेयर प्रोटोटाइप है और आपातकालीन प्रतिक्रिया सेवा नहीं है। "
                "पहले अपनी और दूसरों की शारीरिक सुरक्षा सुनिश्चित करें।"
            )
        else:
            user_msg = (
                "🚨 **URGENT ESCALATION / IMMEDIATE SAFETY NOTICE:**\n\n"
                "**Please ensure your immediate safety first. For any emergency in India, call 112 immediately.**\n\n"
                "- If an electrical appliance is smoking, sparking, or on fire, safely disconnect power at the main switch if safe to do so, and move away.\n"
                "- If you or anyone else faces a physical threat, serious injury, or medical emergency, call **112 (National Emergency Helpline)** immediately.\n\n"
                "Nyaya Saathi is an informational software prototype and cannot provide emergency response. "
                "Do not wait for legal advice when immediate physical safety is at risk."
            )

        return {
            "classification": CATEGORY_URGENT_ESCALATION,
            "risk_level": RISK_CRITICAL,
            "reason_codes": reason_codes,
            "requires_human_review": True,
            "requires_immediate_action": True,
            "allow_normal_legal_generation": False,
            "abstention_required": True,
            "user_message": user_msg,
            "developer_notes": f"Triggered URGENT_ESCALATION on turn: {fire_reason or urgent_reason}",
        }

    # 2. HIGH RISK LEGAL REVIEW CHECK (Court notices, deadlines, serious injury, threats, criminal)
    is_high_risk, risk_codes, risk_summary = detect_high_risk_legal_review(clean_text)
    if is_high_risk:
        if is_hindi:
            user_msg = (
                "⚠️ **विधिक समीक्षा चेतावनी (Legal Professional Review Required):**\n\n"
                f"{risk_summary}\n\n"
                "इस मामले में अदालती नोटिस, समय-सीमा (Limitation Deadline), या गंभीर विधिक परिणाम शामिल हैं। "
                "न्याय साथी एक स्वचालित प्रोटोटाइप है और किसी अधिवक्ता (Advocate) का स्थान नहीं ले सकता।\n\n"
                "**सुझावित कदम:**\n"
                "1. अपने खरीद बिल, सभी लिखित पत्राचार और प्राप्त नोटिस की मूल प्रति सुरक्षित रखें।\n"
                "2. समय-सीमा समाप्त होने से पूर्व किसी योग्य उपभोक्ता अधिवक्ता से परामर्श लें। यदि आप निःशुल्क विधिक सहायता के पात्र हैं, तो आप उपयुक्त तालुक विधिक सेवा समिति (TLSC), जिला विधिक सेवा प्राधिकरण (DLSA) या राज्य विधिक सेवा प्राधिकरण (SLSA) से संपर्क कर सकते हैं।"
            )
        else:
            user_msg = (
                "⚠️ **LEGAL PROFESSIONAL REVIEW REQUIRED:**\n\n"
                f"{risk_summary}\n\n"
                "This situation involves formal court proceedings, impending statutory deadlines, or complex legal risks. "
                "Nyaya Saathi provides informational drafting assistance only and cannot represent you or provide definitive legal opinions.\n\n"
                "**Recommended Action:**\n"
                "1. Preserve all purchase invoices, receipts, written communications, and notices received.\n"
                "2. Consult a qualified consumer advocate promptly to protect your legal remedies before statutory limitation periods or procedural deadlines expire. If you qualify for free legal aid, you may approach the appropriate Taluk Legal Services Committee (TLSC), District Legal Services Authority (DLSA), or State Legal Services Authority (SLSA) under the Legal Services Authorities Act, 1987, subject to applicable statutory eligibility criteria and jurisdiction."
            )

        return {
            "classification": CATEGORY_HIGH_RISK_LEGAL_REVIEW,
            "risk_level": RISK_HIGH,
            "reason_codes": risk_codes,
            "requires_human_review": True,
            "requires_immediate_action": False,
            "allow_normal_legal_generation": False,
            "abstention_required": True,
            "user_message": user_msg,
            "developer_notes": f"Triggered HIGH_RISK_LEGAL_REVIEW on turn: {risk_summary}",
        }

    # 3. OUTSIDE SCOPE CHECK (Tenancy, employment, matrimonial, property, coding, relationship)
    is_outside_core, domain_name, outside_reason = safety.detect_outside_scope_domain(clean_text)
    is_outside_ext, ext_code, ext_reason = detect_extended_outside_scope(clean_text)

    if is_outside_core or is_outside_ext:
        code = ext_code if is_outside_ext else f"OUTSIDE_SCOPE_{domain_name.upper()}"
        reason = ext_reason if is_outside_ext else outside_reason
        user_msg = safety.get_outside_scope_message(reason=reason, language=language)

        return {
            "classification": CATEGORY_OUTSIDE_SCOPE,
            "risk_level": RISK_LOW,
            "reason_codes": [code],
            "requires_human_review": False,
            "requires_immediate_action": False,
            "allow_normal_legal_generation": False,
            "abstention_required": True,
            "user_message": user_msg,
            "developer_notes": f"Triggered OUTSIDE_SCOPE on turn: {reason}",
        }

    # 4. NEEDS CLARIFICATION CHECK
    # Crucial check: If user is actively answering a follow-up in an existing case,
    # e.g., "₹15,000", "Amazon", "I contacted them by phone", do NOT classify as vague!
    has_active_context = active_case is not None and bool(active_case.get("pending_question") or active_case.get("product_or_service"))

    if not has_active_context:
        is_vague, vague_reason = is_vague_initial_turn(clean_text)
        if is_vague:
            if is_hindi:
                user_msg = (
                    "ℹ️ **अधिक जानकारी की आवश्यकता है (Clarification Needed):**\n\n"
                    "आपकी दी गई जानकारी से यह स्पष्ट नहीं हो रहा है कि यह किस उत्पाद, सेवा या व्यापारी से संबंधित उपभोक्ता विवाद है।\n\n"
                    "👉 **कृपया बताएं: आपने क्या खरीदा या किस सेवा का उपयोग किया, और विक्रेता/कंपनी से क्या समस्या हुई?**"
                )
            else:
                user_msg = (
                    "ℹ️ **Clarification Needed:**\n\n"
                    "Your description is too brief or general to determine if an Indian consumer dispute is involved.\n\n"
                    "👉 **Could you please clarify: What product or service did you purchase, and what problem did you experience with the seller or platform?**"
                )

            return {
                "classification": CATEGORY_NEEDS_CLARIFICATION,
                "risk_level": RISK_LOW,
                "reason_codes": ["CLARIFICATION_VAGUE_QUERY"],
                "requires_human_review": False,
                "requires_immediate_action": False,
                "allow_normal_legal_generation": False,
                "abstention_required": False,
                "user_message": user_msg,
                "developer_notes": f"Triggered NEEDS_CLARIFICATION: {vague_reason}",
            }

    # 5. NORMAL CONSUMER DISPUTE (Safe to proceed)
    return {
        "classification": CATEGORY_NORMAL_CONSUMER_DISPUTE,
        "risk_level": RISK_LOW,
        "reason_codes": ["NORMAL_CONSUMER_GRIEVANCE"],
        "requires_human_review": False,
        "requires_immediate_action": False,
        "allow_normal_legal_generation": True,
        "abstention_required": False,
        "user_message": "",
        "developer_notes": "Input classified as ordinary consumer dispute. Permitted to continue case building and legal synthesis.",
    }


# ---------------------------------------------------------------------------
# Explicit Abstention Engine (Part E)
# ---------------------------------------------------------------------------

def build_explicit_abstention_response(
    reason_code: str,
    specific_details: Optional[str] = None,
    language: str = "English",
    suggested_steps: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Builds a supportive, clear explicit abstention response conforming to Part E.
    Explains honestly what could not be verified and why, without confusing generic errors.
    """
    is_hindi = language.lower() in ("hindi", "hinglish", "hindi/hinglish")

    if is_hindi:
        heading = "ℹ️ **स्पष्ट अस्वीकरण व विधिक सीमा (Legal Abstention Notice):**"
        base_statement = (
            "न्याय साथी के कानूनी डेटाबेस में इस विशिष्ट बिंदु को सत्यापित करने के लिए आधिकारिक कानूनी स्रोत अपर्याप्त हैं। "
            "हम आपको कोई असमर्थित या अधूरा कानूनी उत्तर नहीं देना चाहते।"
        )
        default_steps = [
            "अपनी खरीद रसीद, इनवॉइस और भुगतान विवरण सुरक्षित रखें।",
            "राष्ट्रीय उपभोक्ता हेल्पलाइन (NCH) 1915 या consumerhelpline.gov.in पर संपर्क करें।",
            "विशिष्ट कानूनी सलाह के लिए किसी योग्य अधिवक्ता से परामर्श लें।",
        ]
    else:
        heading = "ℹ️ **EXPLICIT LEGAL ABSTENTION NOTICE:**"
        base_statement = STANDARD_ABSTENTION_STATEMENT
        default_steps = [
            "Preserve your purchase invoice, receipt, and payment transaction details.",
            "Contact the National Consumer Helpline at 1915 or visit consumerhelpline.gov.in.",
            "Consult a qualified legal practitioner for formal legal advice on your specific matter.",
        ]

    steps = suggested_steps or default_steps
    detail_str = f"\n\n**Reason:** {specific_details}" if specific_details else ""

    message_text = f"{heading}\n\n{base_statement}{detail_str}\n\n**Recommended Next Steps:**\n" + "\n".join(f"- {s}" for s in steps)

    return {
        "response_status": "EXPLICIT_ABSTENTION",
        "abstention_reason_code": reason_code,
        "language": language,
        "what_the_source_says": base_statement,
        "how_it_may_relate_to_your_problem": specific_details or "No verified statutory rule could be established for this question.",
        "possible_next_steps": steps,
        "limitations_and_uncertainties": [
            base_statement,
            "This software prototype provides informational assistance only and does not provide formal legal advice or representation.",
        ],
        "needs_professional_review": True,
        "user_facing_message": message_text,
    }


# ---------------------------------------------------------------------------
# Final Answer Safety Gate (Part F)
# ---------------------------------------------------------------------------

PROHIBITED_OUTCOME_PHRASES = [
    r"\b(definitely\s+win|guaranteed?\s+to\s+win)\b",
    r"\b(guarantee(d)?\s+refund|100%\s+refund|100%\s+entitled)\b",
    r"\b(entitled\s+to\s+immediate\s+refund|seller\s+is\s+strictly\s+required\s+to\s+pay\s+immediately)\b",
    r"\b(legally\s+verified|certified\s+legal\s+opinion)\b",
]


# Three-State Product Liability Harm Classification Constants
HARM_PRODUCT_DAMAGE_ONLY = "PRODUCT_DAMAGE_ONLY_CONFIRMED"
HARM_OTHER_REPORTED = "OTHER_HARM_REPORTED"
HARM_SCOPE_UNKNOWN = "HARM_SCOPE_UNKNOWN"


def classify_harm_scope(case: Optional[Dict[str, Any]], query: str = "") -> str:
    """
    Classifies harm scope into one of three explicit states:
    1. OTHER_HARM_REPORTED: External personal injury, medical care, fatality, or damage to other property reported.
    2. PRODUCT_DAMAGE_ONLY_CONFIRMED: Confirmed that harm is strictly confined to the purchased product itself.
    3. HARM_SCOPE_UNKNOWN: Damaged or defective product reported, but whether external injury or other harm occurred is unconfirmed.
    """
    texts = [query]
    if case:
        texts.append(str(case.get("original_user_story", "")))
        texts.append(str(case.get("product_or_service", "")))
        texts.append(str(case.get("issue_category", "")))
        for msg in case.get("conversation_history", []):
            if isinstance(msg, dict):
                texts.append(str(msg.get("content", "")))

    combined = " ".join(t for t in texts if t).lower()

    # 1. Check for external injury, burn, explosion, or other property damage
    external_harm_patterns = [
        r"\b(personal\s+injury|bodily\s+injury|physical\s+injury|hospital(ised|ized)?|doctor|medical\s+bill)\b",
        r"\b(fracture|cut\s+finger|burn(ed|t)?\s+injury|burn(ed|t)?\s+skin|burns?\s+on\s+hand|loss\s+of\s+limb|death|fatal)\b",
        r"\b(electric\s+shock|current\s+mar\s+raha|fire|burn(ed|t)?|exploded?|blast)\b",
        r"\b(damaged?\s+(my\s+)?(other|house|room|property|furniture|table|bed|laptop|desk|clothes|floor|wall))\b",
    ]
    for pat in external_harm_patterns:
        if re.search(pat, combined):
            return HARM_OTHER_REPORTED

    # 2. Check for explicit confirmation that damage is limited to product only
    explicit_product_only_patterns = [
        r"\b(only\s+(?:the\s+)?(product|item|mobile|phone|goods?)\s+(?:is|was)?\s*damaged)\b",
        r"\b(no\s+(?:bodily\s+|personal\s+|other\s+)?injury|no\s+other\s+damage|no\s+one\s+hurt)\b",
        r"\b(sirf\s+(?:mobile|phone|samaan)\s+(?:kharab|toota)\s+hai|koi\s+chot\s+nahi\s+lagi)\b",
        r"\b(damage\s+(?:is\s+)?limited\s+to\s+product|product\s+damage\s+only)\b",
    ]
    for pat in explicit_product_only_patterns:
        if re.search(pat, combined):
            return HARM_PRODUCT_DAMAGE_ONLY

    # 3. If facts have been formally confirmed by user and no external harm reported
    if case and case.get("facts_confirmed_by_user"):
        return HARM_PRODUCT_DAMAGE_ONLY

    # 4. If product is damaged/defective but unconfirmed and harm scope not clarified
    has_damage_or_defect = bool(re.search(r"\b(damag\w*|defect\w*|broken|cracked|kharab|toota|faulty)\b", combined))
    if has_damage_or_defect:
        return HARM_SCOPE_UNKNOWN

    # Default for non-damage consumer disputes (e.g. non-delivery, refund refusal)
    return HARM_PRODUCT_DAMAGE_ONLY


def _is_harm_limited_to_product(case: Optional[Dict[str, Any]], text: str = "") -> bool:
    """
    Evaluates whether harm is strictly limited to the product itself under CPA 2019 Section 2(22).
    Returns True when harm is confined to the product itself or harm scope is unclarified (excluding product liability).
    """
    scope = classify_harm_scope(case, text)
    return scope in (HARM_PRODUCT_DAMAGE_ONLY, HARM_SCOPE_UNKNOWN)


def _attempt_safe_claim_filtering(
    generated_answer: Dict[str, Any],
    validation_report: Dict[str, Any],
    retrieved_sources: List[Dict[str, Any]],
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Attempts to salvage valid supported claims by removing unverified/unsupported claims.
    Re-validates the filtered answer. Returns (filtered_answer, new_val_report) if supported
    claims remain, or None if no supported claims exist.
    """
    claims = validation_report.get("claims", [])
    if not claims:
        claims = generated_answer.get("claims", [])

    if not claims:
        return None

    unsupported_statuses = {
        citation_checker.SUPPORT_NOT_ESTABLISHED,
        citation_checker.UNSUPPORTED_NO_CITATION,
        citation_checker.REFERENCE_NOT_FOUND,
        citation_checker.TITLE_MISMATCH,
        citation_checker.DOCUMENT_MISMATCH,
        citation_checker.SOURCE_NOT_RETRIEVED,
        citation_checker.QUOTE_MISMATCH,
    }

    supported_claims = [
        c for c in claims
        if c.get("support_status") not in unsupported_statuses and (c.get("source_ids") or c.get("cited_provision"))
    ]

    unsupported_claims = [
        c for c in claims
        if c.get("support_status") in unsupported_statuses or not (c.get("source_ids") or c.get("cited_provision"))
    ]

    if not supported_claims:
        return None

    # Construct filtered answer
    filtered_answer = dict(generated_answer)
    filtered_answer["claims"] = supported_claims

    # Filter text in what_the_source_says and how_it_may_relate_to_your_problem
    what_says = filtered_answer.get("what_the_source_says", "")
    how_relates = filtered_answer.get("how_it_may_relate_to_your_problem", "")
    for uc in unsupported_claims:
        ctxt = uc.get("claim_text", "").strip()
        if ctxt:
            what_says = what_says.replace(ctxt, "").strip()
            how_relates = how_relates.replace(ctxt, "").strip()

    filtered_answer["what_the_source_says"] = what_says
    filtered_answer["how_it_may_relate_to_your_problem"] = how_relates

    # Collect source IDs from supported claims
    used_sids = set()
    for sc in supported_claims:
        for sid in sc.get("source_ids", []):
            used_sids.add(sid)
    filtered_answer["source_ids_used"] = list(used_sids)

    # Disclose omitted unverified points
    limits = list(filtered_answer.get("limitations_and_uncertainties", []))
    omitted_notice = (
        "FILTERED UNVERIFIED CLAIMS: One or more material statements were omitted because "
        "they could not be verified against official statutory passages."
    )
    if omitted_notice not in limits:
        limits.append(omitted_notice)
    filtered_answer["limitations_and_uncertainties"] = limits

    # Re-validate citations
    new_report = citation_checker.validate_legal_answer(filtered_answer, retrieved_sources=retrieved_sources)
    return filtered_answer, new_report


def _format_user_facing_explanation_with_citations(
    safe_answer: Dict[str, Any],
    validation_report: Dict[str, Any],
    retrieved_sources: List[Dict[str, Any]],
    existing_limits: List[str],
    language: str,
) -> str:
    """Formats plain-language explanation with claim-level citations and official URLs."""
    is_hindi = language.lower() in ("hindi", "hinglish", "hindi/hinglish")
    what_says = safe_answer.get("what_the_source_says", "").strip()
    how_relates = safe_answer.get("how_it_may_relate_to_your_problem", "").strip()

    citations = validation_report.get("citations") or safe_answer.get("relevant_official_sources") or retrieved_sources or []

    # Map chunks/citations by sid and provision for claim matching
    citation_pool = []
    for c in citations:
        sid = c.get("chunk_id") or c.get("source_id") or c.get("embedding_record_id") or ""
        doc_title = c.get("document_title", "Official Legal Source")
        doc_type = c.get("document_type", "ACT")
        prov_num = str(c.get("provision_number", "")).strip()
        prov_type = c.get("provision_type", "Section" if doc_type == "ACT" else "Rule")
        prov_heading = c.get("provision_heading", "")

        source_url = c.get("source_url")
        if not source_url and "CPA_2019" in str(c.get("document_id", "") or c.get("source_id", "")):
            source_url = "https://consumeraffairs.gov.in/public/upload/files/CP%20Act%202019_1732700731.pdf"
        elif not source_url and "ECOMMERCE" in str(c.get("document_id", "") or c.get("source_id", "")):
            source_url = "https://consumeraffairs.gov.in/public/upload/files/E%20commerce%20rules_1732703966.pdf"
        elif not source_url:
            source_url = "https://consumeraffairs.gov.in/"

        authority = c.get("issuing_authority") or "Ministry of Consumer Affairs, Food and Public Distribution, Government of India"
        excerpt = c.get("exact_original_text") or c.get("text") or c.get("source_text_summary") or ""
        if excerpt and len(excerpt) > 240:
            excerpt = excerpt[:237] + "..."

        is_procedural = (
            doc_type == "PROCEDURAL_GUIDE" or
            "EJAGRITI" in str(c.get("document_id", "")).upper() or
            "e-jagriti" in doc_title.lower() or
            "e-jagriti" in str(sid).lower()
        )

        citation_pool.append({
            "source_id": sid,
            "document_title": doc_title,
            "document_type": doc_type,
            "provision_number": prov_num,
            "provision_type": prov_type,
            "provision_heading": prov_heading,
            "source_url": source_url,
            "authority": authority,
            "excerpt": excerpt,
            "is_procedural": is_procedural,
        })

    # Filter supported claims from validation report / answer
    raw_claims = validation_report.get("claims") or safe_answer.get("claims") or []
    unsupported_statuses = {
        citation_checker.SUPPORT_NOT_ESTABLISHED,
        citation_checker.UNSUPPORTED_NO_CITATION,
        citation_checker.REFERENCE_NOT_FOUND,
        citation_checker.TITLE_MISMATCH,
        citation_checker.DOCUMENT_MISMATCH,
        citation_checker.SOURCE_NOT_RETRIEVED,
        citation_checker.QUOTE_MISMATCH,
    }
    supported_claims = [
        c for c in raw_claims
        if c.get("support_status") not in unsupported_statuses
        and (c.get("source_ids") or c.get("referenced_provision") or c.get("cited_provision"))
    ]

    # Defense-in-depth: scrub any unverified/unsupported claim text from narrative sections
    for uc in raw_claims:
        if uc.get("support_status") in unsupported_statuses:
            ctxt = uc.get("claim_text", "").strip()
            if ctxt:
                what_says = what_says.replace(ctxt, "").strip()
                how_relates = how_relates.replace(ctxt, "").strip()

    claim_sections = []
    seen_claim_keys = set()

    if supported_claims:
        for idx, clm in enumerate(supported_claims, 1):
            c_text = clm.get("claim_text", "").strip()
            c_prov = clm.get("referenced_provision") or clm.get("cited_provision") or ""
            c_sids = clm.get("source_ids") or []
            if isinstance(c_sids, str):
                c_sids = [c_sids]

            # Determine label (Prioritize specific remedies like Section 39 before broad defect keywords)
            combined_label_text = (c_prov + " " + c_text).lower()
            if "39" in combined_label_text or "replace" in combined_label_text or "refund" in combined_label_text or "वापसी" in combined_label_text or "बदलना" in combined_label_text:
                label = "प्रतिस्थापन या धनवापसी का उपाय (Possible replacement or refund remedy)" if is_hindi else "Possible replacement or refund remedy"
            elif "2(10)" in combined_label_text or "defect" in combined_label_text or "खराबी" in combined_label_text or "दोष" in combined_label_text:
                label = "दोष की परिभाषा (Definition of defect)" if is_hindi else "Definition of defect"
            elif "35" in combined_label_text or "e-jagriti" in combined_label_text or "filing" in combined_label_text or "दाखिल" in combined_label_text:
                label = "ई-जागृति ऑनलाइन शिकायत प्रक्रिया (E-Jagriti online filing procedure)" if is_hindi else "E-Jagriti online complaint filing procedure"
            elif "rule" in combined_label_text or "e-commerce" in combined_label_text or "ई-कॉमर्स" in combined_label_text:
                label = "ई-कॉमर्स नियम अनुपालन (E-Commerce Rules compliance)" if is_hindi else "E-Commerce Rules compliance"
            elif "2(47)" in combined_label_text or "unfair" in combined_label_text or "अनुचित" in combined_label_text:
                label = "अनुचित व्यापार व्यवहार निषेध (Unfair trade practice prohibition)" if is_hindi else "Unfair trade practice prohibition"
            elif "2(11)" in combined_label_text or "deficiency" in combined_label_text:
                label = "सेवा में कमी की परिभाषा (Definition of service deficiency)" if is_hindi else "Definition of service deficiency"
            else:
                prov_label = c_prov.strip() if c_prov else "Official Legal Provision"
                label = f"कानूनी प्रावधान ({prov_label})" if is_hindi else f"Statutory Provision ({prov_label})"

            # Find matching citations for this claim
            matched_cites = []
            for cp in citation_pool:
                cp_sid = cp["source_id"]
                cp_pnum = cp["provision_number"]
                if cp_sid in c_sids:
                    matched_cites.append(cp)
                elif c_prov and (c_prov.lower() in cp_pnum.lower() or cp_pnum.lower() in c_prov.lower()):
                    matched_cites.append(cp)

            if not matched_cites and citation_pool:
                # Fallback to first available citation matching provision pattern
                if "2(10)" in combined_label_text:
                    matched_cites = [cp for cp in citation_pool if "2(10)" in cp["provision_number"] or "2(10)" in cp["source_id"]]
                elif "39" in combined_label_text:
                    matched_cites = [cp for cp in citation_pool if "39" in cp["provision_number"] or "39" in cp["source_id"]]

            if not matched_cites and citation_pool:
                matched_cites = [citation_pool[0]]

            # Format the claim block
            claim_header = f"### {'दावा' if is_hindi else 'Claim'} {idx} — {label}"
            blocks = [claim_header]

            for mc in matched_cites:
                ckey = f"{mc['document_title']}_{mc['provision_number']}_{idx}"
                if ckey in seen_claim_keys:
                    continue
                seen_claim_keys.add(ckey)

                if mc["is_procedural"]:
                    portal_url = "https://e-jagriti.gov.in/"
                    if is_hindi:
                        b = (
                            f"- 🌐 **{mc['document_title']}**\n"
                            f"  - **स्रोत प्रकार:** PROCEDURAL_GUIDANCE (प्रक्रियात्मक मार्गदर्शन)\n"
                            f"  - **आधिकारिक पोर्टल:** [{portal_url}]({portal_url})\n"
                            f"  - **वकालतनामा नियम:** वकालतनामा केवल तभी आवश्यक है जब वकील/अधिवक्ता के माध्यम से आवेदन कर रहे हों।"
                        )
                    else:
                        b = (
                            f"- 🌐 **{mc['document_title']}**\n"
                            f"  - **Source Type:** PROCEDURAL_GUIDANCE\n"
                            f"  - **Official Portal:** [{portal_url}]({portal_url})\n"
                            f"  - **Vakalatnama Requirement:** Required ONLY if represented by an advocate/lawyer; NOT required when appearing in person."
                        )
                else:
                    prov_str = f"{mc['provision_type']} {mc['provision_number']}".strip() if mc["provision_number"] else ""
                    if "39" in mc["provision_number"] and ("39(1)(b)" in c_text or "39(1)(c)" in c_text or "39(1)(b)" in c_prov or "39(1)(c)" in c_prov):
                        prov_str = "Section 39(1)(b) and Section 39(1)(c)"
                    elif mc["provision_heading"] and prov_str:
                        prov_str = f"{prov_str} ({mc['provision_heading']})"

                    title_str = f"📜 **{mc['document_title']}**"
                    if prov_str:
                        title_str += f", {prov_str}"

                    if is_hindi:
                        b = (
                            f"- {title_str}\n"
                            f"  - **जारीकर्ता प्राधिकारी:** {mc['authority']}\n"
                            f"  - **आधिकारिक स्रोत:** [{mc['source_url']}]({mc['source_url']})"
                        )
                        if mc["excerpt"]:
                            b += f'\n  - **कानूनी उद्धरण:** "{mc["excerpt"]}"'
                    else:
                        b = (
                            f"- {title_str}\n"
                            f"  - **Issuing Authority:** {mc['authority']}\n"
                            f"  - **Official Source Link:** [{mc['source_url']}]({mc['source_url']})"
                        )
                        if mc["excerpt"]:
                            b += f'\n  - **Statutory Excerpt:** "{mc["excerpt"]}"'
                blocks.append(b)

            claim_sections.append("\n".join(blocks))

    # If no structured claims were processed, fall back to pooled citations
    if not claim_sections:
        seen_sources = set()
        for idx, cp in enumerate(citation_pool, 1):
            prov_str = f"{cp['provision_type']} {cp['provision_number']}".strip() if cp["provision_number"] else "General Provision"
            dedup_key = f"{cp['document_title']}_{cp['provision_number']}".strip()
            if dedup_key in seen_sources:
                continue
            seen_sources.add(dedup_key)

            title_str = f"📜 **{cp['document_title']}**"
            if prov_str:
                title_str += f", {prov_str}"

            if cp["is_procedural"]:
                portal_url = "https://e-jagriti.gov.in/"
                b = (
                    f"### {'संदर्भ' if is_hindi else 'Reference'} {idx} — {cp['document_title']}\n"
                    f"- 🌐 **{cp['document_title']}**\n"
                    f"  - **Official Portal:** [{portal_url}]({portal_url})"
                )
            else:
                b = (
                    f"### {'संदर्भ' if is_hindi else 'Reference'} {idx} — {prov_str}\n"
                    f"- {title_str}\n"
                    f"  - **Issuing Authority:** {cp['authority']}\n"
                    f"  - **Official Source Link:** [{cp['source_url']}]({cp['source_url']})"
                )
                if cp["excerpt"]:
                    b += f'\n  - **Statutory Excerpt:** "{cp["excerpt"]}"'
            claim_sections.append(b)

    citations_section = "\n\n".join(claim_sections)

    if is_hindi:
        parts = []
        if what_says:
            parts.append(f"📖 **कानूनी जानकारी (Source-Grounded Explanation):**\n\n{what_says}")
        if how_relates:
            parts.append(f"🔍 **यह आपके मामले से कैसे संबंधित हो सकता है:**\n\n{how_relates}")
        if citations_section:
            parts.append(f"📚 **आधिकारिक कानूनी संदर्भ और स्रोत (Official Statutory Citations & Sources):**\n\n{citations_section}")
        if existing_limits:
            parts.append(f"⚠️ **महत्वपूर्ण सीमाएं एवं अस्वीकरण (Statutory Limitations & Disclaimers):**\n" + "\n".join(f"- {l}" for l in existing_limits))
        return "\n\n".join(parts)
    else:
        parts = []
        if what_says:
            parts.append(f"📖 **Official Legal Information:**\n\n{what_says}")
        if how_relates:
            parts.append(f"🔍 **How This May Relate to Your Case:**\n\n{how_relates}")
        if citations_section:
            parts.append(f"📚 **Official Statutory Citations & Sources:**\n\n{citations_section}")
        if existing_limits:
            parts.append(f"⚠️ **Statutory Limitations & Disclaimers:**\n" + "\n".join(f"- {l}" for l in existing_limits))
        return "\n\n".join(parts)


def evaluate_final_answer_safety_gate(
    generated_answer: Dict[str, Any],
    validation_report: Dict[str, Any],
    case: Optional[Dict[str, Any]] = None,
    retrieved_sources: Optional[List[Dict[str, Any]]] = None,
    turn_safety_decision: Optional[Dict[str, Any]] = None,
    language: str = "English",
) -> Dict[str, Any]:
    """
    Evaluates generated answer and citation verification report against the 10 Safety Gate criteria (Part F).
    Guarantees unsafe, hallucinated, or ungrounded claims are never exposed to the user.

    Returns:
    - gate_status: PASSED | ABSTENTION_REQUIRED | UNSAFE_BLOCKED
    - allow_delivery: bool
    - user_facing_response: str
    - safe_structured_answer: Optional[Dict[str, Any]]
    - gate_reason_codes: List[str]
    - limitations_and_disclaimers: List[str]
    - developer_notes: str
    """
    gate_reason_codes: List[str] = []
    limitations: List[str] = []
    developer_notes: List[str] = []

    # 1. Gate Check 1: Turn Safety Decision Precedence
    if turn_safety_decision and not turn_safety_decision.get("allow_normal_legal_generation", True):
        classification = turn_safety_decision.get("classification")
        user_msg = turn_safety_decision.get("user_message", "")
        return {
            "gate_status": GATE_UNSAFE_BLOCKED,
            "allow_delivery": False,
            "user_facing_response": user_msg,
            "safe_structured_answer": None,
            "gate_reason_codes": turn_safety_decision.get("reason_codes", ["TURN_SAFETY_BLOCKED"]),
            "limitations_and_disclaimers": ["Answer blocked because turn was classified as unsafe/out-of-scope."],
            "developer_notes": f"Gate blocked output due to turn classification: {classification}",
        }

    # 2. Gate Check 2: Empty Retrieval Result Check
    sources = retrieved_sources or []
    if not sources:
        gate_reason_codes.append("ABSTENTION_EMPTY_RETRIEVAL")
        abstain_resp = build_explicit_abstention_response(
            reason_code="EMPTY_RETRIEVAL",
            specific_details="No official statutory passages were retrieved matching this inquiry.",
            language=language,
        )
        return {
            "gate_status": GATE_ABSTENTION_REQUIRED,
            "allow_delivery": True,
            "user_facing_response": abstain_resp["user_facing_message"],
            "safe_structured_answer": abstain_resp,
            "gate_reason_codes": gate_reason_codes,
            "limitations_and_disclaimers": [STANDARD_ABSTENTION_STATEMENT],
            "developer_notes": "Abstained directly because retrieved_sources is empty.",
        }

    # 3. Gate Check 3: Citation Verification Report Integrity
    unsupported_refs = validation_report.get("unsupported_references", [])
    unsupported_claims = validation_report.get("unsupported_claims", [])
    overall_val_status = validation_report.get("overall_status")

    if overall_val_status == citation_checker.STATUS_FAILED or unsupported_refs:
        gate_reason_codes.append("GATE_BLOCKED_UNSUPPORTED_REFERENCES")
        developer_notes.append(f"Citation verification failed with invalid references: {unsupported_refs}")

        # Suppress the unsafe answer completely and return safe abstention
        abstain_resp = build_explicit_abstention_response(
            reason_code="CITATION_CHECK_FAILED",
            specific_details="One or more cited legal provisions or source references could not be verified in official statutory text.",
            language=language,
        )
        return {
            "gate_status": GATE_UNSAFE_BLOCKED,
            "allow_delivery": False,
            "user_facing_response": abstain_resp["user_facing_message"],
            "safe_structured_answer": abstain_resp,
            "gate_reason_codes": gate_reason_codes,
            "limitations_and_disclaimers": [
                "One or more citations failed deterministic verification.",
                STANDARD_ABSTENTION_STATEMENT,
            ],
            "developer_notes": f"Blocked output because citation verification failed: {unsupported_refs}",
        }

    # 4. Gate Check 4: Prohibited Outcome Guarantees (Must BLOCK, never silently scrub)
    combined_answer_text = (
        str(generated_answer.get("what_the_source_says", "")) + " " +
        str(generated_answer.get("how_it_may_relate_to_your_problem", ""))
    )
    for forbidden_pat in PROHIBITED_OUTCOME_PHRASES:
        m = re.search(forbidden_pat, combined_answer_text, re.IGNORECASE)
        if m:
            matched_phrase = m.group(0)
            gate_reason_codes.append("PROHIBITED_OUTCOME_PROMISE")
            developer_notes.append(f"Detected prohibited outcome phrase: '{matched_phrase}'")

            abstain_resp = build_explicit_abstention_response(
                reason_code="PROHIBITED_OUTCOME_PROMISE",
                specific_details=(
                    "The generated legal response contained an ungrounded outcome guarantee or entitlement claim. "
                    "Nyaya Saathi policy strictly forbids automated legal outcome guarantees."
                ),
                language=language,
            )
            return {
                "gate_status": GATE_UNSAFE_BLOCKED,
                "allow_delivery": False,
                "user_facing_response": abstain_resp["user_facing_message"],
                "safe_structured_answer": abstain_resp,
                "gate_reason_codes": gate_reason_codes,
                "limitations_and_disclaimers": [
                    "Output blocked due to prohibited outcome assertion.",
                    STANDARD_ABSTENTION_STATEMENT,
                ],
                "developer_notes": f"Blocked output because prohibited outcome guarantee was detected: '{matched_phrase}'",
            }

    # Gate Check 3B: Unsupported Claims Filtering or Blocking
    if overall_val_status == citation_checker.STATUS_UNSUPPORTED_CLAIMS_DETECTED or unsupported_claims:
        filtered_result = _attempt_safe_claim_filtering(
            generated_answer=generated_answer,
            validation_report=validation_report,
            retrieved_sources=sources,
        )
        if filtered_result is not None:
            safe_gen_answer, validation_report = filtered_result
            generated_answer = safe_gen_answer
            gate_reason_codes.append("SAFE_CLAIM_FILTERING_APPLIED")
            developer_notes.append("Unsupported claims safely filtered; re-validated supported claims.")
        else:
            gate_reason_codes.append("GATE_BLOCKED_UNSUPPORTED_CLAIMS")
            abstain_resp = build_explicit_abstention_response(
                reason_code="UNSUPPORTED_CLAIMS",
                specific_details="One or more material claims could not be substantiated by official statutory sources, and no verified claims remained.",
                language=language,
            )
            return {
                "gate_status": GATE_UNSAFE_BLOCKED,
                "allow_delivery": False,
                "user_facing_response": abstain_resp["user_facing_message"],
                "safe_structured_answer": abstain_resp,
                "gate_reason_codes": gate_reason_codes,
                "limitations_and_disclaimers": [
                    "One or more material claims lacked official statutory support.",
                    STANDARD_ABSTENTION_STATEMENT,
                ],
                "developer_notes": "Blocked output because all material claims lacked official statutory support.",
            }

    # 4B. Gate Check 4B: Product Liability Exclusion under CPA 2019 Section 2(22)
    harm_scope = classify_harm_scope(case, combined_answer_text)
    if harm_scope != HARM_OTHER_REPORTED:
        has_pl = any(
            c.get("provision_number") in ("82", "83", "84", "85", "86", "87") or "product liability" in str(c.get("provision_heading", "")).lower()
            for c in validation_report.get("citations", [])
        ) or "product liability" in combined_answer_text.lower()
        if has_pl:
            gate_reason_codes.append("PRODUCT_LIABILITY_EXCLUDED_SECTION_2_22")
            developer_notes.append("Product liability action excluded under CPA 2019 Section 2(22) because harm is limited to product itself or unclarified.")
            limitations.append(
                "NOTE ON PRODUCT LIABILITY: Under Section 2(22) of the Consumer Protection Act, 2019, 'harm' excludes damage to the product itself. The remedy is sought as an ordinary defect complaint under Sections 34–39."
            )
        if harm_scope == HARM_SCOPE_UNKNOWN:
            gate_reason_codes.append("HARM_SCOPE_UNKNOWN")
            developer_notes.append("Harm scope is unknown/unclarified; distinguishing product-only remedies from product liability.")
            limitations.append(
                "HARM SCOPE: Whether any injury or damage to other property occurred has not been confirmed. Ordinary defect remedies apply under Sections 34–39."
            )

    # 5. Gate Check 5: Future-Effective Law (G.S.R. 789(E))
    has_future_amendment = any(
        "CP_ECOMMERCE_AMENDMENT_2026" in str(c.get("document_id") or c.get("source_id", ""))
        for c in validation_report.get("citations", [])
    )
    if has_future_amendment:
        if date.today() < citation_checker.GSR_789_EFFECTIVE_DATE:
            gate_reason_codes.append("TEMPORAL_FUTURE_EFFECTIVE_NOTICE")
            limitations.append(
                f"NOTICE ON COMMENCEMENT: The Consumer Protection (E-Commerce) (Amendment) Rules, 2026 (G.S.R. 789(E)) "
                f"commence on {citation_checker.GSR_789_EFFECTIVE_DATE} and are not currently operative."
            )

    # 6. Gate Check 6: Unconfirmed Case Facts
    is_confirmed = False
    if case:
        is_confirmed = bool(case.get("facts_confirmed_by_user", False))

    if not is_confirmed:
        gate_reason_codes.append("UNCONFIRMED_FACTS_PROVISIONAL")
        limitations.append(
            "PROVISIONAL EXPLANATION: Case facts have not yet been formally reviewed and confirmed by the consumer. "
            "This informational summary is preliminary."
        )

    # 7. Gate Check 7: Legal Review Status Transparency (Never "Legally Verified")
    any_requires_review = any(
        c.get("legal_review_status") == citation_checker.REQUIRES_LEGAL_REVIEW
        for c in validation_report.get("citations", [])
    ) or validation_report.get("requires_professional_review", False)

    if any_requires_review:
        gate_reason_codes.append("REQUIRES_LEGAL_REVIEW")
        limitations.append(
            "One or more retrieved source passages have not undergone human legal review. Consult a qualified advocate for formal advice."
        )

    # Sanitize and prepare delivery payload
    safe_answer = citation_checker.produce_safe_validated_answer(generated_answer, validation_report)

    # Append gate limitations
    existing_limits = list(safe_answer.get("limitations_and_uncertainties", []))
    for lim in limitations:
        if lim not in existing_limits:
            existing_limits.append(lim)
    safe_answer["limitations_and_uncertainties"] = existing_limits

    # Build friendly user-facing text with claim-level citations and official source links
    user_facing = _format_user_facing_explanation_with_citations(
        safe_answer=safe_answer,
        validation_report=validation_report,
        retrieved_sources=sources,
        existing_limits=existing_limits,
        language=language,
    )

    return {
        "gate_status": GATE_PASSED,
        "allow_delivery": True,
        "user_facing_response": user_facing,
        "safe_structured_answer": safe_answer,
        "gate_reason_codes": gate_reason_codes,
        "limitations_and_disclaimers": existing_limits,
        "developer_notes": f"Safety gate PASSED. Codes: {gate_reason_codes}. DevNotes: {'; '.join(developer_notes)}",
    }
