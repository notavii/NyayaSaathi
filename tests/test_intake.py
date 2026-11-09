"""Automated Unit & Integration Test Suite for Issue Scope Classification (Phase 3).

Verifies:
1. All 22 synthetic test cases from test_cases.json match expected outcomes.
2. URGENT_ESCALATION takes strict priority over normal consumer disputes.
3. Multi-turn clarification flows correctly resolve ambiguous initial inputs.
4. Model/API failures gracefully fallback to NEEDS_CLARIFICATION without false in-scope assumptions.
5. Hindi and Hinglish inputs are properly classified.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import intake
from src import safety
from src import gemini_service


class TestIssueScopeClassifier(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        test_cases_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "data", "test_cases", "test_cases.json")
        )
        with open(test_cases_path, "r", encoding="utf-8") as f:
            cls.test_cases = json.load(f)

    def test_01_synthetic_test_cases_catalog(self):
        """1. Verify all 22 synthetic test cases from test_cases.json."""
        for case in self.test_cases:
            case_id = case.get("id")
            user_msg = case.get("user_message")
            expected_cat = case.get("expected_category")
            expected_act = case.get("expected_action")
            lang = case.get("language", "English")

            result = intake.classify_issue(user_msg, language=lang, use_llm_fallback=False)

            self.assertEqual(
                result["category"],
                expected_cat,
                f"Failed on {case_id}: '{user_msg}'. Expected {expected_cat}, got {result['category']}. Reason: {result.get('reason')}",
            )
            self.assertEqual(
                result["next_action"],
                expected_act,
                f"Action mismatch on {case_id}: Expected {expected_act}, got {result['next_action']}",
            )

    def test_02_urgent_escalation_precedence(self):
        """2. Verify URGENT_ESCALATION takes precedence over consumer goods purchase."""
        # Mentions buying a product AND serious bodily injury
        urgent_consumer_msg = "I bought a microwave online and when I plugged it in, it exploded causing severe burns on my hand and face."
        result = intake.classify_issue(urgent_consumer_msg, use_llm_fallback=False)

        self.assertEqual(result["category"], intake.CATEGORY_URGENT_ESCALATION)
        self.assertEqual(result["next_action"], intake.ACTION_ESCALATE)
        self.assertIn("PHYSICAL_HARM", result["safety_flags"])

        # Physical threat overrides any business context
        threat_msg = "The seller came to my house with weapons and threatened to kill me if I ask for a refund."
        threat_result = intake.classify_issue(threat_msg, use_llm_fallback=False)
        self.assertEqual(threat_result["category"], intake.CATEGORY_URGENT_ESCALATION)
        self.assertIn("IMMEDIATE_DANGER", threat_result["safety_flags"])

    def test_03_multi_turn_clarification_flow(self):
        """3. Verify multi-turn clarification turns ambiguous issues into concrete outcomes."""
        # Turn 1: Vague initial input
        vague_msg = "Someone took my money and is not returning it."
        turn1_result = intake.classify_issue(vague_msg, use_llm_fallback=False)
        self.assertEqual(turn1_result["category"], intake.CATEGORY_NEEDS_CLARIFICATION)
        self.assertEqual(turn1_result["next_action"], intake.ACTION_ASK_QUESTION)

        # Context setup
        context = [
            {"role": "user", "text": vague_msg},
            {"role": "assistant", "text": turn1_result["clarifying_question"]},
        ]

        # Turn 2A: User clarifies it was a retail order
        clarified_consumer = "I paid for a smartphone on a merchant website, but they cancelled the order and kept the money."
        turn2_consumer_result = intake.classify_issue(
            clarified_consumer, conversation_context=context, use_llm_fallback=False
        )
        self.assertEqual(turn2_consumer_result["category"], intake.CATEGORY_CONSUMER_DISPUTE)
        self.assertEqual(turn2_consumer_result["next_action"], intake.ACTION_PROCEED)

        # Turn 2B: User clarifies it was a personal loan / roommate
        clarified_outside = "My roommate borrowed money for his personal rent and has now blocked my calls."
        turn2_outside_result = intake.classify_issue(
            clarified_outside, conversation_context=context, use_llm_fallback=False
        )
        self.assertEqual(turn2_outside_result["category"], intake.CATEGORY_OUTSIDE_SCOPE)
        self.assertEqual(turn2_outside_result["next_action"], intake.ACTION_STOP_NORMAL_FLOW)

    def test_04_gemini_fallback_and_api_failure_handling(self):
        """4. Verify LLM classification and graceful fallback when API fails."""
        ambiguous_text = "The service provider charged an extra hidden maintenance fee on the invoice."

        # Case A: LLM returns valid JSON
        mock_llm_json = json.dumps({
            "category": "LIKELY_CONSUMER_DISPUTE",
            "confidence": "high",
            "reason": "Hidden fees on a service bill represent a potential unfair trade practice.",
            "next_action": "PROCEED",
            "clarifying_question": None,
        })
        with patch("src.gemini_service.generate_response", return_value=mock_llm_json):
            with patch("src.config.is_api_configured", return_value=True):
                result = intake.classify_issue(ambiguous_text, use_llm_fallback=True)
                self.assertEqual(result["category"], intake.CATEGORY_CONSUMER_DISPUTE)
                self.assertEqual(result["next_action"], intake.ACTION_PROCEED)

        # Case B: LLM fails with an exception -> MUST NOT assume in-scope, must fallback to NEEDS_CLARIFICATION
        with patch("src.gemini_service.generate_response", side_effect=Exception("API connection timeout")):
            with patch("src.config.is_api_configured", return_value=True):
                fallback_result = intake.classify_issue_with_gemini(ambiguous_text)
                self.assertEqual(fallback_result["category"], intake.CATEGORY_NEEDS_CLARIFICATION)
                self.assertEqual(fallback_result["next_action"], intake.ACTION_ASK_QUESTION)

    def test_05_bilingual_clarifying_questions(self):
        """5. Verify clarifying questions are generated in appropriate language."""
        en_q = intake.get_default_clarifying_question("English")
        self.assertIn("product or service", en_q)

        hi_q = intake.get_default_clarifying_question("Hindi/Hinglish")
        self.assertIn("उत्पाद (product)", hi_q)

    def test_06_safety_message_generators(self):
        """6. Verify urgent escalation and outside scope message content."""
        urgent_msg_en = safety.get_urgent_escalation_message("English")
        self.assertIn("112", urgent_msg_en)
        self.assertIn("URGENT ESCALATION", urgent_msg_en)

        urgent_msg_hi = safety.get_urgent_escalation_message("Hindi/Hinglish")
        self.assertIn("112", urgent_msg_hi)
        self.assertIn("तत्काल सहायता", urgent_msg_hi)

        outside_msg = safety.get_outside_scope_message("This concerns tenancy rent.", "English")
        self.assertIn("Consumer Protection Act, 2019", outside_msg)
        self.assertIn("OUTSIDE CONSUMER DISPUTE SCOPE", outside_msg)


if __name__ == "__main__":
    unittest.main()
