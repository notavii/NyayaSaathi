"""Automated Streamlit AppTest for Phase 3 Scope Classification.

Verifies the live interactive behavior of the four classification outcomes in Streamlit:
1. LIKELY_CONSUMER_DISPUTE -> Displays scope confirmation.
2. NEEDS_CLARIFICATION -> Displays clarifying question.
3. OUTSIDE_SCOPE -> Displays outside scope explanation and pauses workflow.
4. URGENT_ESCALATION -> Displays emergency 112 notice and pauses workflow.
5. Reset button -> Unpauses workflow and resets conversation.
"""

from unittest.mock import patch
from streamlit.testing.v1 import AppTest


def test_app_scope_classification_outcomes():
    print(">>> 1. Initializing AppTest...")
    with patch("src.gemini_service.generate_response", return_value="Mocked AI guidance for testing."):
        at = AppTest.from_file("../app.py", default_timeout=30)
        at.run()
        assert not at.exception, f"App crashed on startup: {at.exception}"

    # Scenario 1: URGENT_ESCALATION
    print(">>> 2. Testing URGENT_ESCALATION in UI...")
    urgent_input = "Someone is threatening to physically harm me."
    at.text_area[0].input(urgent_input).run()
    submit_btn = [b for b in at.button if "Submit" in b.label][0]
    submit_btn.click().run()

    assert at.session_state.current_scope == "URGENT_ESCALATION"
    assert at.session_state.workflow_paused is True
    messages = at.session_state.messages
    assert len(messages) == 2
    assert "112" in messages[1]["text"]
    assert "URGENT ESCALATION" in messages[1]["text"]
    print("PASS: Urgent escalation triggered emergency notice and paused workflow.")

    # Reset before next scenario
    print(">>> 3. Testing Reset button...")
    reset_btn = [b for b in at.button if "Reset" in b.label][0]
    reset_btn.click().run()
    assert len(at.session_state.messages) == 0
    assert at.session_state.workflow_paused is False
    print("PASS: Reset button cleared state.")

    # Scenario 2: OUTSIDE_SCOPE
    print(">>> 4. Testing OUTSIDE_SCOPE in UI...")
    outside_input = "My employer has not paid my salary for two months."
    at.text_area[0].input(outside_input).run()
    submit_btn = [b for b in at.button if "Submit" in b.label][0]
    submit_btn.click().run()

    assert at.session_state.current_scope == "OUTSIDE_SCOPE"
    assert at.session_state.workflow_paused is True
    messages = at.session_state.messages
    assert len(messages) == 2
    assert "OUTSIDE CONSUMER DISPUTE SCOPE" in messages[1]["text"]
    print("PASS: Outside scope triggered polite rejection and paused workflow.")

    # Reset
    reset_btn = [b for b in at.button if "Reset" in b.label][0]
    reset_btn.click().run()

    # Scenario 3: NEEDS_CLARIFICATION
    print(">>> 5. Testing NEEDS_CLARIFICATION in UI...")
    vague_input = "I need legal help."
    at.text_area[0].input(vague_input).run()
    submit_btn = [b for b in at.button if "Submit" in b.label][0]
    submit_btn.click().run()

    assert at.session_state.current_scope == "NEEDS_CLARIFICATION"
    assert at.session_state.workflow_paused is False
    messages = at.session_state.messages
    assert len(messages) == 2
    assert "Clarification Needed" in messages[1]["text"]
    print("PASS: Vague statement prompted clarifying question without pausing.")

    # Scenario 4: User clarifies in turn 2 -> LIKELY_CONSUMER_DISPUTE
    print(">>> 6. Testing Clarification resolution in Turn 2...")
    clarification_input = "Yes, I purchased a TV online from an electronics store and it arrived cracked."
    at.text_area[0].input(clarification_input).run()
    submit_btn = [b for b in at.button if "Submit" in b.label][0]
    submit_btn.click().run()

    assert at.session_state.current_scope == "LIKELY_CONSUMER_DISPUTE"
    assert at.session_state.workflow_paused is False
    messages = at.session_state.messages
    assert len(messages) == 4
    assert "Scope Confirmation" in messages[3]["text"]
    print("PASS: Clarification resolved to LIKELY_CONSUMER_DISPUTE.")

    print("\nALL PHASE 3 APP UI TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_app_scope_classification_outcomes()
