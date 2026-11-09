"""
Keyword Expansion Module for Nyaya Saathi.

Blueprint Phase 4B: Controlled Bilingual Vocabulary for Lexical Legal Retrieval.
Translates consumer dispute complaints in Hindi (Devanagari), Hinglish (Latin),
and informal English into canonical statutory English search terms, bridging the
linguistic gap to the statutory corpus without calling external LLM APIs.

Guarantees:
1. Controlled vocabulary: Every mapped term corresponds strictly to statutory consumer concepts.
2. Zero fabrication: If a query has no recognized consumer phrases, no fake legal terms are invented.
3. Separation of provenance: Expanded English search terms are tracked separately from original query.
4. Pure offline execution: Zero Gemini or external network API calls.
5. High precision for consumer disputes: Covers defective goods, refunds, non-delivery, seller refusals,
   service deficiencies, unfair trade practices, consumer eligibility, and e-Jagriti filing.
"""

import re
import unicodedata
from typing import Any, Dict, List, Set, Tuple

# Devanagari Unicode Block range: U+0900 to U+097F
DEVANAGARI_REGEX = re.compile(r"[\u0900-\u097F]")

# Common Hinglish grammatical and lexical markers
HINGLISH_MARKERS = {
    "hai", "hain", "ho", "nahi", "nahin", "mila", "mili", "mile", "raha",
    "rahe", "rahi", "hua", "hue", "hui", "kare", "karein", "karna", "kar",
    "diya", "diye", "dene", "utha", "uthaya", "bheja", "bheji", "paise",
    "rupaye", "wapas", "kharab", "toota", "tooti", "dukaan", "dukaandar",
    "pe", "se", "ko", "aur", "bhi", "kya", "kaise", "mera", "meri", "mere",
    "aap", "tum", "mujhe", "unhone", "unka", "wala", "wali", "wale", "bahut",
    "lekin", "par", "ke", "ki", "ka"
}

# Controlled Dispute Term Mappings
# Maps semantic concepts to authoritative statutory search terms and multilingual trigger patterns
CONTROLLED_VOCABULARY: List[Dict[str, Any]] = [
    {
        "concept": "DAMAGED_OR_DEFECTIVE_GOODS",
        "english_terms": ["defective goods", "defect", "damaged goods", "product liability"],
        "hindi_patterns": [
            "टूटा हुआ सामान", "टूटा हुआ", "खराब मोबाइल", "खराब सामान", "खराब प्रोडक्ट",
            "खराब वस्तु", "दोषपूर्ण सामान", "दोषपूर्ण वस्तु", "टूटी हुई", "खराबी",
            "सामान टूटा", "डैमेज सामान", "टूटा फूटा"
        ],
        "hinglish_patterns": [
            "product damaged hai", "product damaged", "item damaged", "damaged item",
            "damaged product", "damaged piece", "damaged phone", "damaged laptop",
            "kharab mobile", "kharab product", "kharab item", "kharab samaan",
            "kharab saman", "toota hua samaan", "toota hua saman", "toota hua product",
            "toota hua item", "toota hua", "defective phone", "defective product",
            "defective item", "defective goods", "defect hai", "faulty product"
        ],
        "english_patterns": [
            "damaged", "physically damaged", "defective goods", "defect in goods",
            "motherboard defect", "manufacturing defect", "faulty product", "broken goods"
        ],
    },
    {
        "concept": "REFUND_NOT_RECEIVED",
        "english_terms": ["refund", "repayment", "return of consideration"],
        "hindi_patterns": [
            "पैसे वापस नहीं मिले", "पैसे वापस नहीं", "पैसे वापस", "रिफंड नहीं मिला",
            "रिफंड नहीं आया", "रिफंड", "रुपये वापस", "पैसे लौटाने", "पैसे नहीं लौटा रहे",
            "पैसा वापस", "रिफंड रिजेक्ट", "पैसे कब मिलेंगे", "रकम वापस",
            "पैसे वापस करने से मना"
        ],
        "hinglish_patterns": [
            "refund nahi mil raha", "refund nahi mila", "refund nahi aaya",
            "paise wapas nahi mile", "paise wapas nahi", "paise wapas",
            "paise wapas chahiye", "refund not received", "money return nahi hua",
            "refund request reject", "paise nahi lautaye", "refund decline",
            "paisa wapas", "refund wapas", "refund delay"
        ],
        "english_patterns": [
            "refund not received", "not refunded", "has not refunded",
            "refused to refund", "refuse refund", "delay in refund", "refund of money"
        ],
    },
    {
        "concept": "NON_DELIVERY_OR_DELAY",
        "english_terms": ["non-delivery", "delivery", "goods"],
        "hindi_patterns": [
            "सामान नहीं मिला", "डिलीवरी नहीं हुई", "ऑर्डर नहीं मिला", "ऑर्डर नहीं आया",
            "पार्सल नहीं मिला", "डिलीवरी लेट", "सामान नहीं भेजा", "पैकेज नहीं मिला"
        ],
        "hinglish_patterns": [
            "order deliver nahi hua", "order nahi aaya", "order nahi mila",
            "delivery nahi hui", "item nahi mila", "parcel nahi mila",
            "package deliver nahi hua", "samaan nahi mila", "saman nahi mila",
            "package nahi aaya", "delivery delayed", "not delivered"
        ],
        "english_patterns": [
            "never delivered", "not delivered", "non-delivery", "undelivered package",
            "delivery delay", "failed to deliver"
        ],
    },
    {
        "concept": "SELLER_REFUSING_REPLACEMENT",
        "english_terms": ["seller", "replacement", "defect", "refund"],
        "hindi_patterns": [
            "दुकानदार मना कर रहा है", "बदलने से मना", "रिप्लेसमेंट नहीं कर रहे",
            "रिप्लेसमेंट रिजेक्ट", "वापस लेने से मना", "दुकानदार बदल नहीं रहा",
            "सेलर मना कर रहा है", "फोन नहीं उठा रहा", "कॉल नहीं उठा रहा"
        ],
        "hinglish_patterns": [
            "seller call nahi utha raha", "seller phone nahi utha raha",
            "replacement reject kar diya", "seller refusing replacement",
            "replacement nahi de rahe", "replacement nahi mil raha",
            "return request cancel kar di", "return request cancel",
            "return request reject", "badalne se mana kar raha hai",
            "seller mana kar raha hai", "exchange nahi kar raha",
            "seller replace nahi kar raha"
        ],
        "english_patterns": [
            "refuses to replace", "refusing to replace", "refusing replacement",
            "replacement refused", "no-return policy", "refusing to accept the return",
            "refused replacement"
        ],
    },
    {
        "concept": "SERVICE_DEFICIENCY",
        "english_terms": ["deficiency in service", "service deficiency", "deficient"],
        "hindi_patterns": [
            "सेवा में कमी", "खराब सेवा", "सर्विस नहीं दी", "काम नहीं किया",
            "कनेक्शन काट दिया", "सर्विस नहीं मिली", "घटिया सर्विस"
        ],
        "hinglish_patterns": [
            "service achhi nahi hai", "service nahi mili", "service deficiency",
            "kaam nahi kiya", "connection kaat diya", "service provide nahi ki",
            "ghatiya service", "bad service", "poor service"
        ],
        "english_patterns": [
            "service deficiency", "deficiency of service", "deficiency in service",
            "disconnected my connection", "refused to restore", "service failure"
        ],
    },
    {
        "concept": "WRONG_PRODUCT_OR_MISREPRESENTATION",
        "english_terms": ["incorrect goods", "misrepresentation", "wrong product"],
        "hindi_patterns": [
            "गलत सामान भेज दिया", "गलत सामान", "नकली सामान", "गलत प्रोडक्ट",
            "गलत मॉडल", "नकली प्रोडक्ट भेज दिया"
        ],
        "hinglish_patterns": [
            "wrong product deliver hua", "wrong item bheja", "nakli product bheja",
            "galat item deliver hua", "galat product bheja", "wrong model deliver hua",
            "fake product bheja", "duplicate item"
        ],
        "english_patterns": [
            "wrong product", "wrong model", "wrong item delivered", "fake product",
            "incorrect goods"
        ],
    },
    {
        "concept": "UNFAIR_TRADE_PRACTICE",
        "english_terms": ["unfair trade practice", "misleading advertisement", "overcharging"],
        "hindi_patterns": [
            "अनुचित व्यापार", "भ्रामक विज्ञापन", "एमआरपी से ज्यादा", "धोखाधड़ी",
            "छिपे हुए शुल्क", "ज्यादा पैसे लिए", "गलत प्रचार"
        ],
        "hinglish_patterns": [
            "unfair trade practice", "misleading ad", "mrp se zyada charge kiya",
            "extra charge liya", "hidden charges", "dhokhadhadi", "fraud advertisement"
        ],
        "english_patterns": [
            "unfair trade practice", "misleading advertisement", "fake advertisement",
            "misleading ads", "deceptive practice"
        ],
    },
    {
        "concept": "COMPLAINT_ELIGIBILITY",
        "english_terms": ["consumer", "commercial purpose", "complaint", "complainant"],
        "hindi_patterns": [
            "उपभोक्ता कौन है", "उपभोक्ता की परिभाषा", "शिकायत कौन कर सकता है"
        ],
        "hinglish_patterns": [
            "consumer kaun hai", "complaint kaun kar sakta hai"
        ],
        "english_patterns": [
            "eligible to be considered a consumer", "who is a consumer",
            "definition of consumer", "consumer eligibility", "who can file a complaint"
        ],
    },
    {
        "concept": "COMPLAINT_FILING_OR_COMMISSION",
        "english_terms": ["consumer complaint", "district commission", "e-jagriti", "filing of complaint"],
        "hindi_patterns": [
            "शिकायत कैसे करें", "उपभोक्ता फोरम में शिकायत", "उपभोक्ता आयोग",
            "कंज्यूमर कोर्ट", "केस कैसे करें", "ई-जागृति पर शिकायत",
            "उपभोक्ता फोरम", "फोरम में केस"
        ],
        "hinglish_patterns": [
            "complaint kaise file kare", "consumer court me complaint",
            "consumer forum me case", "case kaise kare", "e-jagriti complaint",
            "consumer court me case", "forum me complaint"
        ],
        "english_patterns": [
            "how to file complaint", "register and file a consumer complaint",
            "e-jagriti portal", "pecuniary jurisdiction", "district consumer commission"
        ],
    },
]


def contains_devanagari(text: str) -> bool:
    """Checks whether the text contains Devanagari script characters."""
    if not text:
        return False
    return bool(DEVANAGARI_REGEX.search(text))


def detect_query_language(text: str) -> str:
    """
    Detects whether the query is in Devanagari Hindi ('hi'),
    Hinglish ('hinglish'), or English ('en').
    """
    if not text or not text.strip():
        return "en"

    # 1. Pure or mixed Devanagari script
    if contains_devanagari(text):
        return "hi"

    # 2. Check for Hinglish lexical markers in Latin script
    lowered = text.lower()
    words = set(re.findall(r"\b[a-z]+\b", lowered))
    hinglish_matches = words.intersection(HINGLISH_MARKERS)

    if len(hinglish_matches) >= 1:
        return "hinglish"

    return "en"


def expand_query_terms(query: str) -> Tuple[List[str], List[str], str]:
    """
    Analyzes an incoming user dispute query and returns:
    1. expanded_terms: Canonical English legal terms mapped from recognized patterns.
    2. matched_keywords: The trigger phrases that matched in the query.
    3. detected_language: 'hi', 'hinglish', or 'en'.

    If no trigger phrases match, returns ([], [], detected_language) without fabricating terms.
    """
    if not query or not isinstance(query, str) or not query.strip():
        return [], [], "en"

    normalized_query = unicodedata.normalize("NFKC", query).lower()
    lang = detect_query_language(normalized_query)

    expanded_terms: List[str] = []
    matched_keywords: List[str] = []
    seen_terms: Set[str] = set()

    for entry in CONTROLLED_VOCABULARY:
        patterns: List[str] = []
        if lang == "hi":
            patterns.extend(entry["hindi_patterns"])
            patterns.extend(entry.get("hinglish_patterns", []))
        elif lang == "hinglish":
            patterns.extend(entry.get("hinglish_patterns", []))
            patterns.extend(entry.get("english_patterns", []))
        else:
            # English query: check domain-specific english patterns
            patterns.extend(entry.get("english_patterns", []))

        concept_matched = False
        for pattern in patterns:
            norm_pattern = unicodedata.normalize("NFKC", pattern).lower()
            if norm_pattern in normalized_query:
                matched_keywords.append(pattern)
                concept_matched = True

        if concept_matched:
            for term in entry["english_terms"]:
                if term not in seen_terms:
                    seen_terms.add(term)
                    expanded_terms.append(term)

    return expanded_terms, matched_keywords, lang
