"""Gemini API Service Module.

Isolates all communication with the Google Gemini API using the official
google-genai Python SDK. Implements robust error handling without exposing
credentials or raw stack traces.
"""

import json
from typing import Any, Dict, Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError

from src import config


class GeminiServiceError(Exception):
    """Base exception for Gemini service errors."""
    pass


class GeminiConfigurationError(GeminiServiceError):
    """Raised when API key or required configuration is missing or invalid."""
    pass


class GeminiAPIError(GeminiServiceError):
    """Raised when an API call fails due to network, quota, or service errors."""
    pass


def get_genai_client(api_key: Optional[str] = None) -> genai.Client:
    """Create and return an authenticated Google GenAI client.

    Args:
        api_key: Optional API key. If not provided, reads from src.config.

    Raises:
        GeminiConfigurationError: If no valid API key is found.
    """
    key = api_key or config.get_api_key()
    if not key:
        raise GeminiConfigurationError(
            "Gemini API key is not configured. Please add your GEMINI_API_KEY "
            "to .streamlit/secrets.toml or set the GEMINI_API_KEY environment variable."
        )

    try:
        return genai.Client(api_key=key)
    except Exception as e:
        raise GeminiConfigurationError(f"Failed to initialize GenAI client: {str(e)}")


def generate_response(
    user_content: str,
    system_instruction: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.3,
    max_output_tokens: int = 1500,
) -> str:
    """Generate a response from the Gemini model using the official SDK.

    Args:
        user_content: The text prompt or message from the user.
        system_instruction: Base instruction defining persona and constraints.
        api_key: Optional API key override.
        model_name: Optional model override (defaults to configured model).
        temperature: Sampling temperature (0.0 to 1.0, lower for factual consistency).
        max_output_tokens: Maximum tokens in the generated response.

    Returns:
        The generated response string.

    Raises:
        GeminiConfigurationError: If configuration or credentials are missing/invalid.
        GeminiAPIError: If the API call fails or returns an empty response.
    """
    cleaned_input = user_content.strip() if user_content else ""
    if not cleaned_input:
        raise ValueError("User content cannot be empty.")

    client = get_genai_client(api_key=api_key)
    target_model = model_name or config.get_model_name()

    # Build Generation Configuration using the official SDK types
    config_params = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    if system_instruction:
        config_params["system_instruction"] = system_instruction

    gen_config = types.GenerateContentConfig(**config_params)

    try:
        response = client.models.generate_content(
            model=target_model,
            contents=cleaned_input,
            config=gen_config,
        )

        if not response or not hasattr(response, "text") or not response.text:
            raise GeminiAPIError(
                "Gemini returned an empty response. The model may have filtered "
                "the request or encountered an internal issue."
            )

        return response.text.strip()

    except APIError as e:
        # Categorize known API error scenarios
        err_msg = str(e)
        code = getattr(e, "code", None)

        if code in (401, 403) or "API_KEY_INVALID" in err_msg or "PERMISSION_DENIED" in err_msg:
            raise GeminiConfigurationError(
                "The configured Gemini API key is invalid or lacks necessary permissions. "
                "Please check your key in Google AI Studio."
            )
        elif code == 429 or "RESOURCE_EXHAUSTED" in err_msg:
            raise GeminiAPIError(
                "Gemini API rate limit or quota exceeded. Please wait a moment before trying again."
            )
        else:
            raise GeminiAPIError(
                f"Gemini API communication failed (Status {code or 'unknown'}): {err_msg}"
            )
    except GeminiServiceError:
        raise
    except Exception as e:
        # Mask any sensitive details in generic exceptions
        raise GeminiAPIError(
            f"An unexpected error occurred while communicating with Gemini: {type(e).__name__} - {str(e)}"
        )


def extract_case_facts_with_llm(
    case: Dict[str, Any],
    user_message: str,
    pending_question: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extracts structured consumer case facts using Gemini (Blueprint Step 13 / Part F).
    Guards strictly against hallucinations, legal advice, or overwriting existing facts.
    Falls back gracefully to deterministic rule-based extraction on any failure.
    """
    from src import case_builder

    cleaned_msg = user_message.strip()
    if not cleaned_msg:
        return case

    # Fallback helper
    def _fallback():
        return case_builder.extract_case_facts_deterministically(
            case=case,
            user_message=cleaned_msg,
            pending_question=pending_question,
        )

    if not config.is_api_configured():
        return _fallback()

    system_instruction = (
        "You are the Case Fact Extractor for Nyaya Saathi, an Indian consumer dispute assistant.\n"
        "Your task is to extract factual details from the consumer's latest message.\n"
        "STRICT GUARDRAILS:\n"
        "1. Extract ONLY facts explicitly stated by the consumer. Never invent, assume, or hallucinate dates, amounts, platforms, or seller responses.\n"
        "2. Do NOT provide legal advice, legal citations, or legal conclusions.\n"
        "3. If the user explicitly says they do not know or do not remember a detail, list that field in 'unknown_fields'.\n"
        "4. Return ONLY a valid JSON object matching the requested schema.\n\n"
        "Output JSON Schema:\n"
        "{\n"
        '  "product_or_service": string or null,\n'
        '  "seller_or_platform": string or null,\n'
        '  "purchase_amount": string or null,\n'
        '  "purchase_date": string or null,\n'
        '  "delivery_date": string or null,\n'
        '  "problem_description": string or null,\n'
        '  "desired_resolution": string or null,\n'
        '  "seller_contact": {\n'
        '    "contacted": boolean or null,\n'
        '    "contact_method": string or null,\n'
        '    "seller_response": string or null,\n'
        '    "contact_date": string or null\n'
        "  },\n"
        '  "new_events": [{"event": "description", "date": "date or Not provided"}],\n'
        '  "new_evidence": [{"item": "label", "description": "details"}],\n'
        '  "unknown_fields": ["field_name"]\n'
        "}"
    )

    prompt = (
        f"Pending question asked to user: {pending_question or 'None'}\n"
        f"User response: \"{cleaned_msg}\"\n"
        f"Current known facts: Product='{case.get('product_or_service')}', "
        f"Platform='{case.get('seller_or_platform')}', "
        f"Amount='{case.get('purchase_amount')}'"
    )

    try:
        raw_json = generate_response(
            user_content=prompt,
            system_instruction=system_instruction,
            temperature=0.0,
            max_output_tokens=600,
        )

        clean_str = raw_json.strip()
        if clean_str.startswith("```json"):
            clean_str = clean_str[7:]
        elif clean_str.startswith("```"):
            clean_str = clean_str[3:]
        if clean_str.endswith("```"):
            clean_str = clean_str[:-3]
        clean_str = clean_str.strip()

        data = json.loads(clean_str)

        mid = f"MSG_{len(case.get('conversation_history', [])) + 1:03d}"

        # Apply extracted facts
        for field in ["product_or_service", "seller_or_platform", "purchase_amount", "purchase_date", "delivery_date", "problem_description", "desired_resolution"]:
            val = data.get(field)
            if val and isinstance(val, str) and val.strip():
                case_builder.update_case_fact(case, field, val.strip(), source="GEMINI_EXTRACTED", message_id=mid)

        # Seller contact
        sc = data.get("seller_contact")
        if isinstance(sc, dict):
            if sc.get("contacted") is not None:
                case["seller_contact"]["contacted"] = sc["contacted"]
            if sc.get("contact_method"):
                case["seller_contact"]["contact_method"] = sc["contact_method"]
            if sc.get("seller_response"):
                case["seller_contact"]["seller_response"] = sc["seller_response"]
            if sc.get("contact_date"):
                case["seller_contact"]["contact_date"] = sc["contact_date"]

        # Events
        for ev in data.get("new_events", []):
            if isinstance(ev, dict) and ev.get("event"):
                case_builder.add_event(case, ev["event"], event_date=ev.get("date"), source="GEMINI_EXTRACTED", message_id=mid)

        # Evidence
        for evi in data.get("new_evidence", []):
            if isinstance(evi, dict) and evi.get("item"):
                case_builder.add_evidence(case, evi["item"], description=evi.get("description"), source="GEMINI_EXTRACTED", message_id=mid)

        # Unknown fields
        for unk in data.get("unknown_fields", []):
            if isinstance(unk, str):
                case_builder.mark_as_unknown(case, unk)

        case_builder.compute_missing_information(case)
        return case

    except Exception:
        # Graceful fallback to deterministic extraction
        return _fallback()

