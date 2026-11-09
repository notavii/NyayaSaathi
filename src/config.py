"""Application Configuration Module.

Central configuration management for Nyaya Saathi.
Safely reads API keys and model parameters from Streamlit secrets
or environment variables without leaking credentials.
"""

import os
from typing import Optional

# Default supported production model for Gemini Developer API
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"

# Known placeholder values that should not be treated as valid API keys
PLACEHOLDER_KEYS = {
    "YOUR_ACTUAL_KEY",
    "your-gemini-api-key-here",
    "YOUR_API_KEY",
    "paste-your-key-here",
    "",
}


def _get_secret_from_streamlit(key: str) -> Optional[str]:
    """Safely attempt to read a key from Streamlit secrets without throwing exceptions."""
    try:
        import streamlit as st

        if hasattr(st, "secrets") and st.secrets:
            # 1. Direct key match (e.g. GEMINI_API_KEY = "...")
            if key in st.secrets:
                val = st.secrets[key]
                if isinstance(val, str) and val.strip():
                    return val.strip()

            # 2. Lowercase key match (e.g. gemini_api_key = "...")
            key_lower = key.lower()
            if key_lower in st.secrets:
                val = st.secrets[key_lower]
                if isinstance(val, str) and val.strip():
                    return val.strip()

            # 3. Check within common TOML sections (e.g. [general] or [secrets])
            for section in ("general", "secrets", "api"):
                if section in st.secrets and isinstance(st.secrets[section], dict):
                    sec = st.secrets[section]
                    if key in sec and isinstance(sec[key], str) and sec[key].strip():
                        return sec[key].strip()
                    if key_lower in sec and isinstance(sec[key_lower], str) and sec[key_lower].strip():
                        return sec[key_lower].strip()
    except Exception:
        # Streamlit secrets file might not exist or Streamlit is running in headless non-context mode
        pass
    return None


def get_api_key() -> Optional[str]:
    """Retrieve the Gemini API key from Streamlit secrets or environment variables.

    Returns:
        The valid API key string, or None if missing or placeholder.
    """
    # 1. Check Streamlit secrets first
    key = _get_secret_from_streamlit("GEMINI_API_KEY")

    # 2. Fall back to environment variables
    if not key:
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if key:
        key = key.strip()
        if key not in PLACEHOLDER_KEYS:
            return key

    return None


def get_model_name() -> str:
    """Retrieve the configured Gemini model identifier.

    Returns:
        The configured model name (e.g., 'gemini-2.5-flash').
    """
    # 1. Check Streamlit secrets
    model = _get_secret_from_streamlit("GEMINI_MODEL")

    # 2. Fall back to environment variable
    if not model:
        model = os.environ.get("GEMINI_MODEL")

    if model and model.strip():
        return model.strip()

    return DEFAULT_GEMINI_MODEL


def is_api_configured() -> bool:
    """Check whether a valid Gemini API key is configured.

    Returns:
        True if an API key is present and not a placeholder, False otherwise.
    """
    key = get_api_key()
    return bool(key)


def get_configuration_status() -> dict:
    """Return a sanitized summary of current configuration status.

    Never includes or reveals the actual API key.
    """
    configured = is_api_configured()
    model = get_model_name()

    return {
        "api_configured": configured,
        "model_name": model,
        "status_message": (
            f"Configured for model: {model}"
            if configured
            else "Gemini API key is not configured. Add GEMINI_API_KEY to .streamlit/secrets.toml."
        ),
    }
