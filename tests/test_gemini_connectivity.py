"""Developer Connectivity Test for Google Gemini API.

Sends a harmless, non-legal question to verify API connectivity,
key reading, and model response generation using the official SDK.
Does NOT expose API keys or use sensitive dispute narratives.
"""

import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import config
from src import gemini_service

HARMLESS_PROMPT = "Explain what a consumer refund is in plain English in three sentences."


def run_connectivity_test():
    print("==================================================")
    print("NYAYA SAATHI — DEVELOPER GEMINI CONNECTIVITY TEST")
    print("==================================================")

    # 1. Check Configuration
    print("\n[Step 1] Checking API key configuration...")
    is_configured = config.is_api_configured()
    model_name = config.get_model_name()
    print(f"Target Model: {model_name}")

    if not is_configured:
        print("\n--------------------------------------------------")
        print("STATUS: ACTION REQUIRED")
        print("--------------------------------------------------")
        print("Gemini API key is not configured in .streamlit/secrets.toml")
        print("or environment variables.")
        print("\nAction required by developer:")
        print("1. Copy .streamlit/secrets.toml.example to .streamlit/secrets.toml")
        print("2. Set GEMINI_API_KEY = \"your-actual-api-key\"")
        print("3. Re-run this test script.")
        print("--------------------------------------------------")
        return "ACTION_REQUIRED"

    print("PASS: API key found (masked for security: '***...***').")

    # 2. Execute harmless test prompt
    print("\n[Step 2] Sending harmless connectivity prompt to Gemini...")
    print(f"Prompt: \"{HARMLESS_PROMPT}\"")

    try:
        response_text = gemini_service.generate_response(
            user_content=HARMLESS_PROMPT,
            system_instruction="You are a clear and concise educational assistant. Provide direct answers.",
            temperature=0.2,
            max_output_tokens=300,
        )

        print("\n[Step 3] Verifying response...")
        if not response_text or len(response_text.strip()) == 0:
            print("FAIL: Gemini returned an empty response.")
            return "FAIL"

        print("PASS: Gemini returned a valid response.\n")
        print("--- Response Preview ---")
        print(response_text)
        print("------------------------")
        print("\nSTATUS: PASS — Gemini API is reachable and responding normally.")
        return "PASS"

    except gemini_service.GeminiConfigurationError as cfg_err:
        print(f"\nFAIL: Configuration Error — {str(cfg_err)}")
        return "FAIL"
    except gemini_service.GeminiAPIError as api_err:
        print(f"\nFAIL: API Error — {str(api_err)}")
        return "FAIL"
    except Exception as ex:
        print(f"\nFAIL: Unexpected Error — {type(ex).__name__}: {str(ex)}")
        return "FAIL"


if __name__ == "__main__":
    result = run_connectivity_test()
    if result == "FAIL":
        sys.exit(1)
