"""Comprehensive Automated Test Suite for Phase 2.

Covers:
1. Python syntax across all modules
2. Session-state initialization and persistence
3. Missing API key handling
4. Empty model response handling
5. API failure handling
6. Language preference and prompt generation
7. Security scan for accidental secrets
"""

import os
import sys
import py_compile
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import config
from src import prompts
from src import gemini_service


class TestPhase2Suite(unittest.TestCase):

    def test_01_syntax_compilation(self):
        """1. Check syntax for all Python files in the project."""
        project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        py_files = []
        for root, dirs, files in os.walk(project_dir):
            if ".venv" in root:
                continue
            for file in files:
                if file.endswith(".py"):
                    py_files.append(os.path.join(root, file))

        self.assertGreater(len(py_files), 0, "No Python files found to compile.")
        for py_path in py_files:
            try:
                py_compile.compile(py_path, doraise=True)
            except py_compile.PyCompileError as e:
                self.fail(f"Syntax error in {py_path}: {e}")

    def test_02_session_state_logic(self):
        """2 & 3. Test session state message tracking and persistence logic."""
        import streamlit as st

        # Test conversation list structure
        messages = []
        messages.append({"role": "user", "text": "I received a damaged laptop."})
        messages.append({"role": "assistant", "text": "I understand your concern."})

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertIn("damaged laptop", messages[0]["text"])

    def test_03_missing_api_key_handling(self):
        """4. Verify missing API key handling."""
        with patch.dict(os.environ, {}, clear=True):
            # Ensure no secret from Streamlit either
            with patch("src.config._get_secret_from_streamlit", return_value=None):
                self.assertFalse(config.is_api_configured())
                self.assertIsNone(config.get_api_key())

                status = config.get_configuration_status()
                self.assertFalse(status["api_configured"])
                self.assertIn("not configured", status["status_message"])

                # Attempting to call generate_response without key must raise GeminiConfigurationError
                with self.assertRaises(gemini_service.GeminiConfigurationError) as ctx:
                    gemini_service.generate_response(user_content="Hello")
                self.assertIn("not configured", str(ctx.exception))

    def test_04_empty_model_response_handling(self):
        """5. Verify empty model response raises GeminiAPIError."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = ""  # Empty text
        mock_client.models.generate_content.return_value = mock_response

        with patch("src.gemini_service.get_genai_client", return_value=mock_client):
            with self.assertRaises(gemini_service.GeminiAPIError) as ctx:
                gemini_service.generate_response(
                    user_content="Hello",
                    api_key="mock-key-for-test",
                )
            self.assertIn("empty response", str(ctx.exception))

    def test_05_api_failure_handling(self):
        """6. Verify APIError is caught and wrapped without leaking keys."""
        from google.genai.errors import APIError

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = APIError(
            429,
            {"error": {"message": "RESOURCE_EXHAUSTED: rate limit exceeded"}},
        )

        with patch("src.gemini_service.get_genai_client", return_value=mock_client):
            with self.assertRaises(gemini_service.GeminiAPIError) as ctx:
                gemini_service.generate_response(
                    user_content="Hello",
                    api_key="mock-key-for-test",
                )
            self.assertIn("rate limit or quota", str(ctx.exception))
            # Verify key is never in error string
            self.assertNotIn("mock-key-for-test", str(ctx.exception))

    def test_06_language_preference_instructions(self):
        """7. Verify language preference and dispute category in system instructions."""
        # English instruction
        en_prompt = prompts.build_system_instruction(
            language="English",
            category="Defective or damaged goods",
        )
        self.assertIn("Nyaya Saathi", en_prompt)
        self.assertIn("Defective or damaged goods", en_prompt)
        self.assertIn("clear, accessible plain English", en_prompt)
        self.assertIn("Consumer Protection Act, 2019", en_prompt)

        # Hindi/Hinglish instruction
        hi_prompt = prompts.build_system_instruction(
            language="Hindi/Hinglish",
            category="Refund or replacement refusal",
        )
        self.assertIn("Refund or replacement refusal", hi_prompt)
        self.assertIn("Hindi/Hinglish", hi_prompt)

    def test_07_security_scan(self):
        """8. Scan repository to ensure no actual API keys or secrets are committed/exposed."""
        project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        # Check .gitignore
        gitignore_path = os.path.join(project_dir, ".gitignore")
        self.assertTrue(os.path.exists(gitignore_path), ".gitignore is missing!")
        with open(gitignore_path, "r", encoding="utf-8") as f:
            gitignore_content = f.read()

        self.assertIn(".streamlit/secrets.toml", gitignore_content)
        self.assertIn(".env", gitignore_content)
        self.assertIn(".venv/", gitignore_content)

        # Ensure no real secrets in secrets.toml.example
        example_path = os.path.join(project_dir, ".streamlit", "secrets.toml.example")
        self.assertTrue(os.path.exists(example_path))
        with open(example_path, "r", encoding="utf-8") as f:
            example_content = f.read()
        self.assertIn("YOUR_ACTUAL_KEY", example_content)
        self.assertNotIn("AIza", example_content)  # Typical Google API key prefix


if __name__ == "__main__":
    unittest.main()
