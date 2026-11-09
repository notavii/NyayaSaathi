"""Safety, Boundaries & Escalation Module for Nyaya Saathi.

Provides pattern detection for:
1. Urgent high-risk situations (immediate danger, physical harm, emergency).
2. Out-of-scope legal domains (tenancy, employment, matrimonial, criminal).
3. Emergency contact recommendations (112, 1930, 1915 in India).
"""

import re
from typing import List, Tuple, Optional

# Official Emergency and Consumer Helplines in India
EMERGENCY_CONTACTS = {
    "national_emergency": "112 (National Emergency Number - Police, Fire, Ambulance)",
    "women_helpline": "181 (Women Helpline) / 1091 (Women in Distress)",
    "cyber_crime": "1930 (Cyber Crime Reporting Helpline / cybercrime.gov.in)",
    "consumer_helpline": "1915 (National Consumer Helpline - NCH / consumerhelpline.gov.in)",
}

# Regex patterns for urgent escalation (Highest priority - life, safety, physical threat)
URGENT_PATTERNS = [
    # Physical danger, assault, threats
    r"\b(threaten(ed|ing)?|attack(ed)?|kill(ed|ing)?|murder|assault(ed)?|beat(en|ing)?)\b",
    r"\b(physical(ly)?\s+harm|bodily\s+harm|stab(bed)?|shoot(ing)?|gun|knife|weapon)\b",
    r"\b(dhamki|jaan\s+se\s+maar|maar\s+peet|hamla|chot|khatra)\b",
    # Severe bodily injury, medical emergency, poisoning
    r"\b(severe(ly)?\s+injur(ed|y)|serious\s+injur(ed|y)|burn(s|ed|t)?\s+injur(y|ies))\b",
    r"\b(bleed(ing)?|hospital(ized|ised)?|fracture|electric\s+shock|electrocuted)\b",
    r"\b(poison(ed|ing)?|toxic\s+reaction|exploded|burst\s+and\s+injur(ed|y))\b",
    # Imminent danger / police emergency
    r"\b(immediate(ly)?\s+danger|life\s+threat(ening)?|emergency\s+help|call\s+police)\b",
    r"\b(suicid(e|al)|self[\s-]harm)\b",
]

# Regex patterns for clearly outside-scope legal domains
OUTSIDE_SCOPE_PATTERNS = {
    "tenancy": [
        r"\b(landlord|tenant|tenancy|security\s+deposit|house\s+rent|rent(al)?\s+agreement|evict(ion|ed)?|room\s+owner|flat\s+owner)\b",
        r"\b(makaan\s+maalik|kirayedar|kiraya|security\s+deposit\s+makaan)\b",
    ],
    "employment": [
        r"\b(employer|employee|salary|unpaid\s+wages|boss|hr\s+department|resignation|fired|terminate(d)?\s+from\s+job|provident\s+fund|pf\s+claim|gratuity|workplace\s+harassment)\b",
        r"\b(naukri|vetan|tanqua|tanakhwah|owner\s+salary)\b",
    ],
    "matrimonial_family": [
        r"\b(divorce|talaq|talaaq|husband|wife|custody\s+of\s+child|alimony|maintenance\s+case|matrimonial|in-laws|dowry|domestic\s+violence|498a)\b",
        r"\b(pati|patni|sasural|dahej)\b",
    ],
    "property_inheritance": [
        r"\b(ancestral\s+property|land\s+dispute|partition\s+suit|property\s+dispute|inheritance|will\s+contest|registry|patta|khata|encroachment|boundary\s+wall)\b",
        r"\b(sampatti\s+vivad|zameen|batwara|vasiyat)\b",
    ],
    "personal_dispute": [
        r"\b(borrow(ed)?\s+money|lent\s+money|personal\s+loan|friend\s+borrowed|roommate|neighbour|neighbor|personal\s+dispute)\b",
    ],
    "criminal_traffic": [
        r"\b(arrest(ed)?|bail\s+application|fir\s+quash(ing)?|police\s+station|traffic\s+challan|rto\s+fine|jail|extortion|bribe|corruption)\b",
        r"\b(hack(ing)?|steal(ing)?|stolen|card\s+data|cyber\s+attack|commit\s+fraud)\b",
    ],
}

# Regex patterns for vague/insufficient statements needing clarification
VAGUE_PATTERNS = [
    r"^(i\s+need\s+legal\s+help|legal\s+help|need\s+help|help\s+me|help)$",
    r"^(i\s+have\s+a\s+(legal\s+)?problem|i\s+have\s+an\s+issue|some\s+problem)$",
    r"^(a\s+company\s+is\s+troubling\s+me|company\s+problem|cheat(ed)?\s+me)$",
    r"^(i\s+lost\s+my\s+money|lost\s+money|money\s+issue|someone\s+took\s+my\s+money)$",
    r"^(someone\s+is\s+not\s+returning\s+my\s+money|return\s+my\s+money|want\s+my\s+money\s+back)$",
    r"^(i\s+need\s+help\s+with\s+a\s+complaint|want\s+to\s+file\s+a\s+complaint|complaint)$",
    r"^(mujhe\s+legal\s+madad\s+chahiye|madad\s+chahiye|kuch\s+pareshani\s+hai|paise\s+doob\s+gaye)$",
]


def detect_urgent_safety_signals(text: str) -> Tuple[bool, List[str], Optional[str]]:
    """Detect if text contains urgent safety or emergency signals.

    Returns:
        (is_urgent, safety_flags, reason)
    """
    clean_text = text.lower().strip()
    flags = []

    for pattern in URGENT_PATTERNS:
        match = re.search(pattern, clean_text, re.IGNORECASE)
        if match:
            matched_phrase = match.group(0)
            if any(k in clean_text for k in ["kill", "murder", "threat", "harm", "weapon", "dhamki", "suicid"]):
                flags.append("IMMEDIATE_DANGER")
            if any(k in clean_text for k in ["injur", "burn", "bleed", "hospital", "poison", "chot"]):
                flags.append("PHYSICAL_HARM")
            if not flags:
                flags.append("URGENT_EMERGENCY")

            reason = f"Detected urgent high-risk indicator ('{matched_phrase}') requiring immediate human or emergency assistance."
            return True, list(set(flags)), reason

    return False, [], None


def detect_outside_scope_domain(text: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Detect if text clearly belongs to an outside legal domain (tenancy, employment, family, etc.).

    Returns:
        (is_outside, domain_name, reason)
    """
    clean_text = text.lower().strip()

    for domain, patterns in OUTSIDE_SCOPE_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE)
            if match:
                matched_term = match.group(0)
                readable_domain = domain.replace("_", " ").title()
                reason = (
                    f"The description appears to concern a {readable_domain} matter ('{matched_term}'), "
                    "which is not a consumer dispute under Indian consumer protection law."
                )
                return True, domain, reason

    return False, None, None


def is_text_vague_or_insufficient(text: str) -> Tuple[bool, Optional[str]]:
    """Detect if input is too brief or ambiguous to identify the dispute type.

    Returns:
        (is_vague, reason)
    """
    clean_text = text.lower().strip()
    # Strip surrounding punctuation for pattern matching
    stripped_punct = re.sub(r"^[^\w]+|[^\w]+$", "", clean_text)

    # Empty or whitespace
    if not clean_text:
        return True, "No description provided."

    # Direct match with known vague phrases
    for pattern in VAGUE_PATTERNS:
        if re.search(pattern, stripped_punct, re.IGNORECASE):
            return True, f"The message ('{text}') is too general to determine if a consumer transaction is involved."

    # General phrase checks: 'someone is not returning' or 'lost my money' without seller/goods
    has_vague_money_phrase = bool(re.search(r"\b(someone\s+(took|has|is\s+not\s+returning)\s+.*money|lost\s+my\s+money|not\s+returning\s+(it|my\s+money)|troubling\s+me)\b", stripped_punct, re.IGNORECASE))
    if has_vague_money_phrase and not any(
        kw in stripped_punct for kw in ["seller", "merchant", "store", "product", "item", "order", "delivered", "laptop", "phone", "airline", "flight", "kharida"]
    ):
        return True, "The description mentions financial loss or trouble, but lacks details about the merchant, product, or service."

    # Extremely short message without concrete transaction words (under 4 words)
    words = [w for w in re.split(r"\s+", clean_text) if w]
    if len(words) <= 3 and not any(
        kw in clean_text for kw in ["phone", "order", "product", "laptop", "refund", "delivered", "seller", "damaged", "samaan", "kharida"]
    ):
        return True, "The description is too short to provide sufficient factual context."

    return False, None


def get_urgent_escalation_message(language: str = "English", safety_flags: Optional[List[str]] = None) -> str:
    """Generate a prominent, supportive emergency escalation message."""
    is_hindi = language.lower() in ("hindi", "hinglish", "hindi/hinglish")
    flags = safety_flags or []
    is_cyber = "CYBER_FRAUD" in flags or any("cyber" in f.lower() for f in flags)

    if is_hindi:
        msg = (
            "🚨 **तत्काल सहायता चेतावनी (Emergency Notice):**\n\n"
            "आपकी दी गई जानकारी में तत्काल खतरे, गंभीर चोट या सुरक्षा जोखिम का संकेत मिला है। "
            "न्याय साथी (Nyaya Saathi) एक सूचनात्मक कानूनी प्रोटोटाइप है और आपातकालीन सेवा नहीं दे सकता।\n\n"
            "**तत्काल निम्नलिखित आपातकालीन सेवाओं से संपर्क करें:**\n"
            "- **राष्ट्रीय आपातकालीन नंबर:** `112` (पुलिस, एम्बुलेंस, फायर ब्रिगेड)\n"
            "- **महिला हेल्पलाइन:** `181` / `1091`\n"
        )
        if is_cyber:
            msg += "- **साइबर वित्तीय धोखाधड़ी हेल्पलाइन:** `1930` (cybercrime.gov.in)\n"
        msg += "\nकृपया तुरंत किसी चिकित्सक, पुलिस या अधिकृत आपातकालीन सेवा से संपर्क करें।"
        return msg

    msg = (
        "🚨 **URGENT ESCALATION NOTICE:**\n\n"
        "Your message indicates an urgent safety concern, physical harm, or high-risk situation. "
        "Nyaya Saathi is an informational software prototype and cannot provide emergency help or legal representation.\n\n"
        "**Please seek immediate assistance through official emergency channels in India:**\n"
        "- **National Emergency Helpline:** **112** (Police, Ambulance, Fire)\n"
        "- **Women's Helpline:** **181** / **1091**\n"
    )
    if is_cyber:
        msg += "- **National Cyber Crime Helpline:** **1930** (cybercrime.gov.in)\n"
    msg += "\nIf you or someone else is in immediate danger or requires urgent medical attention, please call emergency services (112) right away."
    return msg


def get_outside_scope_message(reason: str, language: str = "English") -> str:
    """Generate an accurate explanation that the matter is outside consumer scope with appropriate legal aid routing."""
    is_hindi = language.lower() in ("hindi", "hinglish", "hindi/hinglish")
    is_cyber = bool(re.search(r"\b(cyber|hack|online\s+fraud|upi\s+fraud|bank\s+fraud|phishing)\b", reason, re.IGNORECASE))

    if is_hindi:
        msg = (
            "ℹ️ **विषय क्षेत्र से बाहर (Outside Scope Notice):**\n\n"
            f"{reason}\n\n"
            "न्याय साथी (Nyaya Saathi) केवल **भारतीय उपभोक्ता संरक्षण कानून (Consumer Protection Act, 2019)** "
            "से जुड़े मामलों (जैसे खराब सामान, रिफंड न मिलना, ई-कॉमर्स अनुचित व्यापार व्यवहार, सेवा में कमी) के लिए बनाया गया प्रोटोटाइप है।\n\n"
            "किरायेदारी, नौकरी/वेतन, पारिवारिक विवाद, संपत्ति विभाजन या सामान्य आपराधिक मामलों के लिए कृपया किसी योग्य अधिवक्ता (Advocate) से परामर्श लें।\n\n"
            "यदि आप निःशुल्क विधिक सेवा के पात्र हैं, तो आप विधिक सेवा प्राधिकरण अधिनियम, 1987 के तहत पात्रता और अधिकार क्षेत्र के अनुसार "
            "उपयुक्त तालुक विधिक सेवा समिति (TLSC), जिला विधिक सेवा प्राधिकरण (DLSA) या राज्य विधिक सेवा प्राधिकरण (SLSA) से संपर्क कर सकते हैं।"
        )
        if is_cyber:
            msg += "\n\nवित्तीय साइबर धोखाधड़ी की रिपोर्ट करने के लिए आप राष्ट्रीय साइबर अपराध रिपोर्टिंग पोर्टल (cybercrime.gov.in) या हेल्पलाइन **1930** पर संपर्क कर सकते हैं।"
        return msg

    msg = (
        "ℹ️ **OUTSIDE CONSUMER DISPUTE SCOPE:**\n\n"
        f"{reason}\n\n"
        "**Nyaya Saathi is designed exclusively for Indian consumer disputes** under the "
        "Consumer Protection Act, 2019 (such as defective products, delayed refunds, e-commerce grievances, and deficiency in services).\n\n"
        "It does not cover landlord-tenant disputes, employment or salary claims, family/matrimonial matters, "
        "property partitions, or general criminal cases. For these matters, please consult a qualified advocate.\n\n"
        "If you qualify for free legal services, you may approach the appropriate Taluk Legal Services Committee (TLSC), "
        "District Legal Services Authority (DLSA), or State Legal Services Authority (SLSA) under the Legal Services Authorities Act, 1987, "
        "subject to applicable statutory eligibility criteria and jurisdiction."
    )
    if is_cyber:
        msg += "\n\nFor reporting online financial cyber fraud, you may contact the National Cyber Crime Reporting Portal (cybercrime.gov.in) or call Helpline **1930**."
    return msg
