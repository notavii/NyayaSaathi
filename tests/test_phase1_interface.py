"""Automated test script for Streamlit Interface and Session State."""

import sys
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


def test_app():
    with patch("src.gemini_service.generate_response", return_value="Sample consumer assistance guidance."):
        print(">>> 1. Loading app with AppTest.from_file...")
        import os
        app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
        at = AppTest.from_file(app_path, default_timeout=30)
        at.run()
        assert not at.exception, f"App crashed on startup: {at.exception}"
        print("PASS: App loaded successfully with no exceptions.")

    # Check title / header
    print(">>> 2. Verifying Title & Header...")
    markdowns = [m.value for m in at.markdown]
    header_found = any("Nyaya Saathi" in m for m in markdowns)
    assert header_found, "Header does not contain 'Nyaya Saathi'"
    print("PASS: Header found.")

    # Check disclaimer
    print(">>> 3. Verifying Disclaimer...")
    warnings = [w.value for w in at.warning]
    assert any("Important Disclaimer" in w for w in warnings), "Disclaimer warning not found"
    assert any("fictional information" in w for w in warnings), "Fictional data disclaimer not found"
    print("PASS: Disclaimer verified.")

    # Check category dropdown
    print(">>> 4. Verifying Category dropdown...")
    expected_categories = [
        "Defective or damaged goods",
        "Refund or replacement refusal",
        "Non-delivery or wrong delivery",
        "E-commerce grievance",
        "Service deficiency",
        "Misleading representation",
        "I am not sure",
    ]
    assert at.selectbox[0].options == expected_categories, f"Category options mismatch: {at.selectbox[0].options}"
    print("PASS: Category dropdown has all 7 expected options.")

    # Check language selector
    print(">>> 5. Verifying Language selector...")
    expected_languages = ["English", "Hindi/Hinglish"]
    assert at.selectbox[1].options == expected_languages, f"Language options mismatch: {at.selectbox[1].options}"
    print("PASS: Language selector has English and Hindi/Hinglish.")

    # Check validation on empty submit
    print(">>> 6. Verifying empty description rejection...")
    at.text_area[0].input("").run()
    submit_btn = [b for b in at.button if "Submit" in b.label][0]
    submit_btn.click().run()
    assert len(at.error) > 0, "Expected error on empty submission, but none was displayed."
    assert "Description Required" in at.error[0].value
    print("PASS: Empty description was properly rejected with an error message.")

    # Check valid submission & session state preservation
    print(">>> 7. Verifying valid submission & session state...")
    sample_problem = "I purchased an air cooler online. It arrived with a broken fan, and the merchant refuses to refund."
    at.selectbox[0].select("Refund or replacement refusal").run()
    at.selectbox[1].select("English").run()
    at.text_area[0].input(sample_problem).run()
    submit_btn = [b for b in at.button if "Submit" in b.label][0]
    submit_btn.click().run()

    # Verify session state messages
    messages = at.session_state.get("messages", [])
    assert len(messages) >= 2, f"Expected user and assistant messages in session state, got {len(messages)}"
    assert messages[0]["role"] == "user"
    assert messages[0]["text"] == sample_problem
    assert messages[1]["role"] == "assistant"
    print("PASS: User message and assistant response preserved in session state.")

    # Check Reset button clears session state
    print(">>> 8. Verifying Reset button...")
    reset_btn = [b for b in at.button if "Reset" in b.label][0]
    reset_btn.click().run()
    messages_after_reset = at.session_state.get("messages", [])
    assert len(messages_after_reset) == 0, "Reset button failed to clear messages."
    print("PASS: Reset button properly clears conversation history.")

    print("\nALL INTERFACE & SESSION STATE TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_app()
