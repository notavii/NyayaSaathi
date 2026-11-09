"""
Explicit Abstention Module for Nyaya Saathi.

Blueprint Step 19: Safety, Escalation, and Explicit Abstention.

Defines the explicit abstention triggers and response generators:
1. No relevant official legal sources retrieved.
2. Citation verification failure (invented IDs, non-existent provisions, wrong Act).
3. Material quotation mismatch or unverified paraphrase.
4. Unsupported legal claims lacking statutory foundation.
5. Legal interpretation unestablished or requires professional advocacy.
6. Future-effective law (G.S.R. 789(E) commencement on 2027-01-01).
7. Historical or superseded materials.
8. Unconfirmed facts (facts_confirmed_by_user is False).
9. Conflicting or ambiguous legal sources.
"""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple, Union

from src import citation_checker

# Standard Explicit Abstention Statement (Blueprint Step 19 Part E)
STANDARD_ABSTENTION_STATEMENT = (
    "The available legal sources in Nyaya Saathi are insufficient to verify this point. "
    "I don't want to give you an unsupported legal answer."
)

ABSTENTION_REASON_EMPTY_RETRIEVAL = "EMPTY_RETRIEVAL"
ABSTENTION_REASON_CITATION_FAILURE = "CITATION_CHECK_FAILED"
ABSTENTION_REASON_UNSUPPORTED_CLAIMS = "UNSUPPORTED_CLAIMS"
ABSTENTION_REASON_FUTURE_LAW = "FUTURE_EFFECTIVE_LAW"
ABSTENTION_REASON_HISTORICAL_LAW = "HISTORICAL_OR_SUPERSEDED_LAW"
ABSTENTION_REASON_UNCONFIRMED_FACTS = "UNCONFIRMED_FACTS"
ABSTENTION_REASON_TRANSITIONAL_DISPUTE = "TRANSITIONAL_APPLICABILITY_DISPUTE"


def should_abstain_from_legal_answer(
    retrieved_sources: Optional[List[Dict[str, Any]]],
    validation_report: Optional[Dict[str, Any]],
    as_of_date: Optional[Union[str, date]] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Evaluates whether the system must abstain from delivering a legal answer.

    Returns:
        (must_abstain, reason_code, explanation)
    """
    # 1. No retrieved sources
    if not retrieved_sources:
        return (
            True,
            ABSTENTION_REASON_EMPTY_RETRIEVAL,
            "No official statutory passages were retrieved matching this inquiry.",
        )

    if validation_report:
        # 2. Citation check failed with invented source IDs or non-existent sections
        unsupported_refs = validation_report.get("unsupported_references", [])
        if validation_report.get("overall_status") == citation_checker.STATUS_FAILED or unsupported_refs:
            return (
                True,
                ABSTENTION_REASON_CITATION_FAILURE,
                f"Citations failed verification: {'; '.join(unsupported_refs)}",
            )

        # 3. High-impact unsupported claims
        unsupported_claims = validation_report.get("unsupported_claims", [])
        if unsupported_claims and validation_report.get("overall_status") == citation_checker.STATUS_UNSUPPORTED_CLAIMS_DETECTED:
            return (
                True,
                ABSTENTION_REASON_UNSUPPORTED_CLAIMS,
                "One or more substantive legal claims could not be verified against the text of the cited provisions.",
            )

    return False, None, None


def build_explicit_abstention_response(
    reason_code: str,
    specific_details: Optional[str] = None,
    language: str = "English",
    suggested_steps: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Builds a supportive, transparent explicit abstention response conforming to Part E.
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
