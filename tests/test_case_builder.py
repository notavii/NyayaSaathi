"""
Automated Test Suite for Blueprint Steps 12 & 13:
- Step 12: Category-Aware Guided Follow-up Question Logic
- Step 13: Structured Case Builder & Active Grievance Context

Verifies:
1. Strict schema conformity and immutability of original grievance story.
2. Fact provenance and audit history tracking.
3. Event timeline and evidence inventory management.
4. Deterministic fact extraction (amounts, platforms, seller contact, remedies).
5. Exact Part D Missing Product multi-turn dialogue.
6. Execution of all 20 synthetic case management test cases.
7. Streamlit interactive multi-turn AppTest verification.
"""

import json
import os
from unittest.mock import patch
import pytest

from src import case_builder
from src import intake
from src import safety


def test_case_schema_conformance():
    """Verifies that create_empty_case initializes every required blueprint field."""
    case = case_builder.create_empty_case(
        issue_category="E-commerce grievance",
        original_user_story="I ordered a phone and it never arrived.",
        language_preference="English",
    )

    expected_keys = [
        "case_id",
        "status",
        "issue_category",
        "original_user_story",
        "language_preference",
        "state",
        "district",
        "product_or_service",
        "seller_or_platform",
        "purchase_amount",
        "purchase_currency",
        "purchase_date",
        "delivery_date",
        "expected_delivery_date",
        "problem_description",
        "desired_resolution",
        "seller_contact",
        "events",
        "evidence",
        "missing_information",
        "unknown_information",
        "safety_flags",
        "source_ids",
        "pending_question",
        "questions_asked",
        "conversation_history",
        "fact_sources",
        "correction_history",
        "facts_confirmed_by_user",
        "created_at",
        "updated_at",
    ]

    for key in expected_keys:
        assert key in case, f"Required field '{key}' missing from case schema"

    assert case["status"] == case_builder.STATUS_INTAKE
    assert case["purchase_currency"] == "INR"
    assert case["facts_confirmed_by_user"] is False
    assert case["original_user_story"] == "I ordered a phone and it never arrived."
    assert isinstance(case["seller_contact"], dict)
    assert case["seller_contact"]["contacted"] is None
    assert case["seller_contact"]["seller_response"] is None


def test_fact_provenance_and_update():
    """Verifies update_case_fact tracks source provenance and updates missing information."""
    case = case_builder.create_empty_case()
    case["missing_information"] = ["product_or_service", "purchase_amount"]

    updated = case_builder.update_case_fact(
        case=case,
        field="product_or_service",
        value="air conditioner",
        source="USER_STATEMENT",
        message_id="MSG_001",
    )

    assert updated is True
    assert case["product_or_service"] == "air conditioner"
    assert "product_or_service" not in case["missing_information"]
    assert "product_or_service" in case["fact_sources"]
    assert case["fact_sources"]["product_or_service"]["source"] == "USER_STATEMENT"
    assert case["fact_sources"]["product_or_service"]["message_id"] == "MSG_001"


def test_fact_correction_and_story_immutability():
    """Verifies that user corrections maintain an audit log and original story is immutable."""
    case = case_builder.create_empty_case(original_user_story="Original grievance description.")
    case_builder.update_case_fact(case, "purchase_amount", "₹8,000")

    # Correct purchase amount
    success = case_builder.correct_case_fact(
        case=case,
        field="purchase_amount",
        new_value="₹9,500",
        message_id="MSG_003",
    )
    assert success is True
    assert case["purchase_amount"] == "₹9,500"
    assert len(case["correction_history"]) == 1
    assert case["correction_history"][0]["old_value"] == "₹8,000"
    assert case["correction_history"][0]["new_value"] == "₹9,500"

    # Attempt to alter original_user_story must be rejected
    story_alter = case_builder.correct_case_fact(
        case=case,
        field="original_user_story",
        new_value="Manipulated grievance description.",
    )
    assert story_alter is False
    assert case["original_user_story"] == "Original grievance description."


def test_mark_as_unknown_and_timeline_events():
    """Verifies marking facts unknown and adding timeline events without duplicates."""
    case = case_builder.create_empty_case()
    case["missing_information"] = ["purchase_date"]

    case_builder.mark_as_unknown(case, "purchase_date")
    assert "purchase_date" in case["unknown_information"]
    assert "purchase_date" not in case["missing_information"]

    # Events addition
    case_builder.add_event(case, "Order placed", event_date="2026-10-01")
    case_builder.add_event(case, "Order placed", event_date="2026-10-01")  # Duplicate
    assert len(case["events"]) == 1

    # Evidence addition
    case_builder.add_evidence(case, "Tax Invoice", description="Invoice dated 2026-10-01")
    case_builder.add_evidence(case, "Tax Invoice")  # Duplicate
    assert len(case["evidence"]) == 1


def test_confirm_case_facts_status_transition():
    """Verifies that confirming facts sets confirmed flag and status."""
    case = case_builder.create_empty_case()
    assert case["status"] == case_builder.STATUS_INTAKE

    case_builder.confirm_case_facts(case)
    assert case["facts_confirmed_by_user"] is True
    assert case["status"] == case_builder.STATUS_FACTS_CONFIRMED


def test_guided_follow_up_question_logic():
    """Verifies Step 12 category-aware guided questions and language handling."""
    case = case_builder.create_empty_case(issue_category="E-commerce grievance", language_preference="English")

    # Initially missing seller_contact
    q1 = case_builder.get_next_follow_up_question(case, language="English")
    assert q1 is not None
    assert "contacted the seller" in q1.lower()
    case["questions_asked"].append(q1)

    # Hindi question check
    q_hi = case_builder.get_next_follow_up_question(case, language="Hindi/Hinglish")
    assert q_hi is not None
    assert "विक्रेता" in q_hi

    # Simulate seller contacted, but no product/platform
    case["seller_contact"]["contacted"] = True
    case["seller_contact"]["seller_response"] = "Refused assistance"
    q2 = case_builder.get_next_follow_up_question(case, language="English")
    assert q2 is not None
    assert "product or service" in q2.lower()


def test_exact_part_d_missing_product_dialogue():
    """
    Verifies the exact Blueprint Part D Missing Product scenario:
    Turn 1: "I got missing product from e-commerce."
    Turn 2: "Yes, I contacted seller, but they are not receiving calls."
    """
    turn1_text = "I got missing product from e-commerce."

    # 1. Scope classification for initial turn
    classification = intake.classify_issue(turn1_text)
    assert classification["category"] == intake.CATEGORY_CONSUMER_DISPUTE

    # Initialize active case
    case = case_builder.create_empty_case(
        issue_category="E-commerce grievance",
        original_user_story=turn1_text,
    )
    case_builder.extract_case_facts_deterministically(case, turn1_text)

    # Bot generates guided question
    first_q = case_builder.get_next_follow_up_question(case, language="English")
    assert first_q is not None
    assert "contacted the seller" in first_q.lower()
    case["pending_question"] = first_q
    case["questions_asked"].append(first_q)

    # Turn 2: User answers follow-up
    turn2_text = "Yes, I contacted seller, but they are not receiving calls."

    # Ingest answer into active case WITHOUT restarting scope classification!
    case_builder.extract_case_facts_deterministically(
        case=case,
        user_message=turn2_text,
        pending_question=case["pending_question"],
    )

    # Verify exact extracted facts conforming to Part D specification
    assert case["seller_contact"]["contacted"] is True
    assert case["seller_contact"]["contact_method"] == "phone call"
    assert case["seller_contact"]["seller_response"] == "Seller is not receiving calls / no response"
    assert len(case["events"]) >= 1
    assert any("unanswered" in ev["event"].lower() for ev in case["events"])

    # Verify next follow-up question is asked
    next_q = case_builder.get_next_follow_up_question(case, language="English")
    assert next_q is not None
    assert next_q != first_q  # Does not repeat the same question!
    assert "product" in next_q.lower() or "amount" in next_q.lower()


def test_all_20_case_management_scenarios():
    """Executes and verifies all 20 scenarios from data/test_cases/case_management_cases.json."""
    cases_path = os.path.join(os.path.dirname(__file__), "..", "data", "test_cases", "case_management_cases.json")
    assert os.path.exists(cases_path), f"Test cases file missing: {cases_path}"

    with open(cases_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    test_cases = data["test_cases"]
    assert len(test_cases) == 20, f"Expected 20 test cases, found {len(test_cases)}"

    for tc in test_cases:
        t_id = tc["test_id"]
        lang = tc.get("language", "English")
        turns = tc["turns"]

        # Turn 1
        t1 = turns[0]
        t1_msg = t1["user_message"]
        classification = intake.classify_issue(t1_msg, language=lang)
        assert classification["category"] == t1["expected_scope"], f"Failed scope in {t_id} Turn 1"

        if t1["expected_scope"] != intake.CATEGORY_CONSUMER_DISPUTE:
            continue

        case = case_builder.create_empty_case(
            issue_category=tc.get("dispute_type", ""),
            original_user_story=t1_msg,
            language_preference=lang,
        )
        case_builder.extract_case_facts_deterministically(case, t1_msg)

        # Subsequent turns
        for turn_data in turns[1:]:
            msg = turn_data["user_message"]

            # Urgent check
            is_urgent, flags, reason = safety.detect_urgent_safety_signals(msg)
            if turn_data.get("expected_scope") == "URGENT_ESCALATION":
                assert is_urgent is True, f"Expected urgent escalation in {t_id}"
                break

            pending_q = case_builder.get_next_follow_up_question(case, language=lang)
            case_builder.extract_case_facts_deterministically(case, msg, pending_question=pending_q)

            if "expected_extracted_facts" in turn_data:
                expected = turn_data["expected_extracted_facts"]
                if "seller_contacted" in expected:
                    assert case["seller_contact"]["contacted"] == expected["seller_contacted"]
                if "contact_method" in expected:
                    assert case["seller_contact"]["contact_method"] == expected["contact_method"]
                if "seller_response" in expected:
                    assert case["seller_contact"]["seller_response"] == expected["seller_response"]
                if "product_or_service" in expected:
                    assert case["product_or_service"] == expected["product_or_service"]
                if "seller_or_platform" in expected:
                    assert case["seller_or_platform"] == expected["seller_or_platform"]
                if "purchase_amount" in expected:
                    assert case["purchase_amount"] == expected["purchase_amount"]
                if "desired_resolution" in expected:
                    assert case["desired_resolution"] == expected["desired_resolution"]

            if "expected_case_status" in turn_data:
                assert case["status"] == turn_data["expected_case_status"]

        # Check correction if specified
        if "correction_test" in tc:
            cor = tc["correction_test"]
            case_builder.correct_case_fact(case, cor["field"], cor["new_value"])
            assert case[cor["field"]] == cor["new_value"]

        # Check confirm lifecycle if specified
        if tc.get("confirm_lifecycle"):
            case_builder.confirm_case_facts(case)
            assert case["status"] == case_builder.STATUS_FACTS_CONFIRMED
            assert case["facts_confirmed_by_user"] is True


def test_streamlit_interactive_active_case_app():
    """Verifies interactive multi-turn session state in app.py using AppTest."""
    from streamlit.testing.v1 import AppTest

    app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
    with patch("src.gemini_service.generate_response", return_value="Mocked LLM"):
        at = AppTest.from_file(app_path, default_timeout=30)
        at.run()
        assert not at.exception

        # Turn 1: Initial Consumer Dispute Submission
        at.text_area[0].input("I got missing product from e-commerce.").run()
        submit_btn = [b for b in at.button if "Submit" in b.label][0]
        submit_btn.click().run()

        assert at.session_state.active_case is not None
        case = at.session_state.active_case
        assert case["original_user_story"] == "I got missing product from e-commerce."
        assert case["status"] == "INTAKE"
        assert len(at.session_state.messages) >= 2
        assert "Scope Confirmation" in at.session_state.messages[1]["text"]

        # Turn 2: Follow-up Answer
        at.text_area[0].input("Yes, I contacted seller, but they are not receiving calls.").run()
        submit_btn = [b for b in at.button if "Submit" in b.label][0]
        submit_btn.click().run()

        case_turn2 = at.session_state.active_case
        assert case_turn2["seller_contact"]["contacted"] is True
        assert case_turn2["seller_contact"]["seller_response"] == "Seller is not receiving calls / no response"

        # Turn 3: "+ New Grievance" Button resets active case
        new_grievance_btn = [b for b in at.button if "New Grievance" in b.label][0]
        new_grievance_btn.click().run()

        assert at.session_state.active_case is None
        assert len(at.session_state.messages) == 0


def test_part_a_exact_new_grievance_scenario():
    """
    Blueprint Acceptance Part A: Exact Multi-turn New Grievance Scenario.
    1. Start grievance: 'I ordered a laptop online, but it was never delivered.'
    2. Answer: 'I ordered it from Amazon.'
    3. Answer: 'It cost ₹45,000.'
    4. Answer: 'The seller is not answering my calls.'
    5. Click '+ New Grievance'.
    6. Submit: 'I received a defective mobile phone.'
    """
    from streamlit.testing.v1 import AppTest

    app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
    with patch("src.gemini_service.generate_response", return_value="Mocked LLM"):
        at = AppTest.from_file(app_path, default_timeout=30)
        at.run()
        assert not at.exception

        # 1. Start grievance
        at.text_area[0].input("I ordered a laptop online, but it was never delivered.").run()
        [b for b in at.button if "Submit" in b.label][0].click().run()
        case1 = at.session_state.active_case
        case1_id = case1["case_id"]
        assert case1_id is not None
        assert case1["product_or_service"] == "laptop"

        # 2. Answer: I ordered it from Amazon.
        at.text_area[0].input("I ordered it from Amazon.").run()
        [b for b in at.button if "Submit" in b.label][0].click().run()
        assert at.session_state.active_case["seller_or_platform"] == "Amazon"

        # 3. Answer: It cost ₹45,000.
        at.text_area[0].input("It cost ₹45,000.").run()
        [b for b in at.button if "Submit" in b.label][0].click().run()
        assert at.session_state.active_case["purchase_amount"] == "₹45,000"

        # 4. Answer: The seller is not answering my calls.
        at.text_area[0].input("The seller is not answering my calls.").run()
        [b for b in at.button if "Submit" in b.label][0].click().run()
        c1_contact = at.session_state.active_case["seller_contact"]
        assert c1_contact["contacted"] is True
        assert c1_contact["contact_method"] == "phone call"
        assert c1_contact["seller_response"] == "Seller is not receiving calls / no response"

        # 5. Click "+ New Grievance"
        new_grievance_btn = [b for b in at.button if "New Grievance" in b.label][0]
        new_grievance_btn.click().run()
        assert at.session_state.active_case is None
        assert len(at.session_state.messages) == 0

        # 6. Submit: I received a defective mobile phone.
        at.text_area[0].input("I received a defective mobile phone.").run()
        [b for b in at.button if "Submit" in b.label][0].click().run()

        case2 = at.session_state.active_case
        assert case2 is not None

        # Verify all Part A specifications
        # A new case ID is created
        assert case2["case_id"] != case1_id
        # Original grievance is the defective-mobile-phone complaint
        assert case2["original_user_story"] == "I received a defective mobile phone."
        # Previous product and seller are absent
        assert case2["product_or_service"] == "mobile phone"
        assert case2["seller_or_platform"] is None
        # Previous purchase amount is absent
        assert case2["purchase_amount"] is None
        # Previous contact history is absent
        assert case2["seller_contact"]["contacted"] is None
        assert case2["seller_contact"]["seller_response"] is None
        # Previous pending question is absent
        assert case2["pending_question"] is not None
        assert "laptop" not in case2["pending_question"].lower()
        # Previous conversation history is absent from active case
        assert len(case2["conversation_history"]) == 2
        assert "laptop" not in case2["conversation_history"][0]["text"]
        # Classifier started a fresh classification workflow
        assert at.session_state.current_scope == "LIKELY_CONSUMER_DISPUTE"


def test_reset_button_clears_active_case_and_messages():
    """Verifies that the Reset button clears all session state and active case."""
    from streamlit.testing.v1 import AppTest

    app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
    with patch("src.gemini_service.generate_response", return_value="Mocked LLM"):
        at = AppTest.from_file(app_path, default_timeout=30)
        at.run()

        # Submit an initial problem
        at.text_area[0].input("I purchased an air conditioner that does not work.").run()
        [b for b in at.button if "Submit" in b.label][0].click().run()
        assert at.session_state.active_case is not None
        assert len(at.session_state.messages) >= 2

        # Click Reset button
        reset_btn = [b for b in at.button if "Reset" in b.label][0]
        reset_btn.click().run()

        assert at.session_state.active_case is None
        assert len(at.session_state.messages) == 0
        assert at.session_state.current_scope is None
        assert at.session_state.workflow_paused is False


def test_session_state_safety_rerun_and_dropdown():
    """Verifies ordinary reruns and dropdown changes preserve active case."""
    from streamlit.testing.v1 import AppTest

    app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
    with patch("src.gemini_service.generate_response", return_value="Mocked LLM"):
        at = AppTest.from_file(app_path, default_timeout=30)
        at.run()

        # Start case
        at.text_area[0].input("I bought a defective television for Rs 20,000.").run()
        [b for b in at.button if "Submit" in b.label][0].click().run()
        case_id = at.session_state.active_case["case_id"]
        amt = at.session_state.active_case["purchase_amount"]

        # Ordinary rerun without submission
        at.run()
        assert at.session_state.active_case is not None
        assert at.session_state.active_case["case_id"] == case_id
        assert at.session_state.active_case["purchase_amount"] == amt

        # Dropdown change (language switch)
        at.selectbox[1].select("Hindi/Hinglish").run()
        assert at.session_state.active_case is not None
        assert at.session_state.active_case["case_id"] == case_id
        assert at.session_state.active_case["purchase_amount"] == amt


def test_urgent_safety_active_during_followup():
    """Verifies urgent bodily harm / safety signals trigger immediate escalation during follow-up."""
    from streamlit.testing.v1 import AppTest

    app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
    with patch("src.gemini_service.generate_response", return_value="Mocked LLM"):
        at = AppTest.from_file(app_path, default_timeout=30)
        at.run()

        # Turn 1: Normal consumer inquiry
        at.text_area[0].input("I bought an electric kettle online.").run()
        [b for b in at.button if "Submit" in b.label][0].click().run()
        assert at.session_state.active_case is not None
        assert at.session_state.workflow_paused is False

        # Turn 2: Urgent bodily harm statement in follow-up
        urgent_msg = "The kettle burst into fire, exploded and caused severe burns on my arm."
        at.text_area[0].input(urgent_msg).run()
        [b for b in at.button if "Submit" in b.label][0].click().run()

        assert at.session_state.current_scope == "URGENT_ESCALATION"
        assert at.session_state.workflow_paused is True
        latest_reply = at.session_state.messages[-1]["text"]
        assert "112" in latest_reply
        assert "URGENT ESCALATION" in latest_reply


def test_fact_integrity_provenance_and_dates():
    """Verifies date corrections, unknown date handling, provenance and confirmation."""
    case = case_builder.create_empty_case()

    # Provenance tracking
    case_builder.update_case_fact(case, "purchase_amount", "₹12,000", source="USER_STATEMENT", message_id="MSG_001")
    assert case["fact_sources"]["purchase_amount"]["source"] == "USER_STATEMENT"
    assert case["fact_sources"]["purchase_amount"]["message_id"] == "MSG_001"

    # Date correction with history
    case_builder.update_case_fact(case, "purchase_date", "2026-09-01", source="USER_STATEMENT", message_id="MSG_001")
    case_builder.correct_case_fact(case, "purchase_date", "2026-09-15", message_id="MSG_002")
    assert case["purchase_date"] == "2026-09-15"
    assert len(case["correction_history"]) == 1
    assert case["correction_history"][0]["field"] == "purchase_date"
    assert case["correction_history"][0]["old_value"] == "2026-09-01"
    assert case["correction_history"][0]["new_value"] == "2026-09-15"

    # Unknown date remains null
    case_builder.mark_as_unknown(case, "delivery_date")
    assert case["delivery_date"] is None
    assert "delivery_date" in case["unknown_information"]

    # Unconfirmed facts remain unconfirmed
    assert case["facts_confirmed_by_user"] is False
    assert case["status"] != case_builder.STATUS_FACTS_CONFIRMED


def test_part_d_ui_elements_and_review_panel():
    """
    Blueprint Acceptance Part D: UI elements visibility, Reset/New Grievance,
    and live Review Your Case Facts panel verification.
    """
    from streamlit.testing.v1 import AppTest

    app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
    with patch("src.gemini_service.generate_response", return_value="Mocked LLM"):
        at = AppTest.from_file(app_path, default_timeout=30)
        at.run()

        # 1. New Grievance button is visible
        new_btns = [b for b in at.button if "New Grievance" in b.label]
        assert len(new_btns) == 1, "New Grievance button not found"

        # Start Case 1
        at.text_area[0].input("I ordered a laptop online, but it was never delivered.").run()
        [b for b in at.button if "Submit" in b.label][0].click().run()
        case1_id = at.session_state.active_case["case_id"]

        # 2. Clicking New Grievance clears active case
        new_btns = [b for b in at.button if "New Grievance" in b.label]
        new_btns[0].click().run()
        assert at.session_state.active_case is None

        # 3. New conversation starts correctly
        at.text_area[0].input("I received a defective mobile phone.").run()
        [b for b in at.button if "Submit" in b.label][0].click().run()
        case2 = at.session_state.active_case
        assert case2 is not None

        # 4. New case ID generated
        case2_id = case2["case_id"]
        assert case2_id != case1_id

        # 5. Review Your Case Facts panel displays correct new information
        expanders = [e for e in at.expander if "Review Your Case Facts" in e.label]
        assert len(expanders) == 1
        assert case2_id in expanders[0].label
        story_tas = [t for t in at.text_area if "Original Grievance Story" in t.label]
        assert len(story_tas) == 1
        assert story_tas[0].value == "I received a defective mobile phone."


