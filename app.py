"""Nyaya Saathi — AI Consumer Dispute Assistant for India.

Authoritative Specification: Project Blueprint & Beginner Build Guide.
- Dynamic Legal Companion & Conversational Issue Resolution
- Section A: Conversation & Intake
- Section B: Case Fact Review & Provenance Audit
- Section C: Case Analysis & Suggested Next Steps (Immediately below Facts Panel)
- Right-Side Persistent Case Workspace (70/30 split, Editable Facts, Update & Reanalyse)
"""

from datetime import datetime
import streamlit as st

from src import config
from src import prompts
from src import safety
from src import intake
from src import case_builder
from src import gemini_service
from src import safety_guard
from src import abstention
from src import workflow_service

# Configure Streamlit page layout to wide for 70/30 desktop split
st.set_page_config(
    page_title="Nyaya Saathi — Consumer Dispute Assistant",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for clean, professional legal-tech appearance
st.markdown(
    """
    <style>
    /* Clean typography & header styling */
    .main-header {
        text-align: center;
        padding-top: 0.5rem;
        padding-bottom: 0.5rem;
    }
    .main-title {
        color: #1a365d;
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
        letter-spacing: -0.02em;
    }
    .sub-title {
        color: #4a5568;
        font-size: 1.05rem;
        line-height: 1.5;
        margin-bottom: 1rem;
    }
    .scope-badge-in-scope {
        background-color: #ebf8ff;
        border-left: 4px solid #3182ce;
        padding: 0.6rem 0.9rem;
        border-radius: 4px;
        margin-bottom: 0.75rem;
        font-size: 0.88rem;
        color: #2b6cb0;
    }
    .case-card {
        background-color: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    .workspace-container {
        background-color: #f8fafc;
        border: 1px solid #cbd5e0;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
    }
    .analysis-container {
        background-color: #f0fdf4;
        border: 1px solid #86efac;
        border-radius: 8px;
        padding: 1.25rem;
        margin-top: 1.25rem;
        margin-bottom: 1.25rem;
    }
    .footer-section {
        margin-top: 3.5rem;
        padding-top: 1.25rem;
        border-top: 1px solid #e2e8f0;
        text-align: center;
        color: #718096;
        font-size: 0.82rem;
        line-height: 1.6;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# Application Limits for Public Deployment (Abuse & Resource Protection)
MAX_INPUT_CHARS = 2500
MAX_SESSION_TURNS = 40


def init_session_state():
    """Initialize conversation history, classification tracking, and active case in session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_scope" not in st.session_state:
        st.session_state.current_scope = None
    if "workflow_paused" not in st.session_state:
        st.session_state.workflow_paused = False
    if "active_case" not in st.session_state:
        st.session_state.active_case = None
    if "input_key_counter" not in st.session_state:
        st.session_state.input_key_counter = 0
    if "session_turn_count" not in st.session_state:
        st.session_state.session_turn_count = 0


def reset_conversation():
    """Clear conversation history, reset classification, and clear active case with complete isolation."""
    st.session_state.messages = []
    st.session_state.current_scope = None
    st.session_state.workflow_paused = False
    st.session_state.active_case = None
    st.session_state.session_turn_count = 0
    st.session_state.input_key_counter = st.session_state.get("input_key_counter", 0) + 1


def main():
    init_session_state()

    # ---------------------------------------------------------
    # A. HEADER
    # ---------------------------------------------------------
    st.markdown(
        """
        <div class="main-header">
            <h1 class="main-title">⚖️ Nyaya Saathi</h1>
            <p style="font-weight: 600; color: #2b6cb0; margin-bottom: 0.5rem; font-size: 1.15rem;">
                Consumer Dispute Assistant
            </p>
            <p class="sub-title">
                Explain your consumer problem in ordinary language. Nyaya Saathi helps organise your facts,
                understand relevant official information and prepare a draft you can review.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---------------------------------------------------------
    # B. IMPORTANT DISCLAIMER
    # ---------------------------------------------------------
    st.warning(
        "⚠️ **Important Disclaimer:** Nyaya Saathi is an AI-powered informational and drafting prototype. "
        "It is not a lawyer, does not provide emergency assistance and does not guarantee legal outcomes. "
        "Please use fictional information in this demonstration."
    )

    # ---------------------------------------------------------
    # C. TOP CONTROLS (Category, Language, Reset)
    # ---------------------------------------------------------
    st.write("---")

    col1, col2, col3 = st.columns([4, 3, 3])

    with col1:
        category_options = [
            "Defective or damaged goods",
            "Refund or replacement refusal",
            "Non-delivery or wrong delivery",
            "E-commerce grievance",
            "Service deficiency",
            "Misleading representation",
            "I am not sure",
        ]
        selected_category = st.selectbox(
            "Select problem category:",
            options=category_options,
            index=0,
            help="Choose the category that best matches your dispute. If unsure, select 'I am not sure'.",
        )

    with col2:
        language_options = [
            "English",
            "Hindi/Hinglish",
        ]
        selected_language = st.selectbox(
            "Language preference:",
            options=language_options,
            index=0,
            help="Nyaya Saathi will respond in your chosen language while keeping legal citations standard.",
        )

    with col3:
        st.write("")  # Alignment spacing
        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            if st.button("🔄 Reset", help="Clear conversation history and start fresh"):
                reset_conversation()
                st.rerun()
        with btn_c2:
            if st.button("➕ New Grievance", help="Start a new grievance case"):
                reset_conversation()
                st.rerun()

    # Developer notice if Gemini API key not configured
    api_configured = config.is_api_configured()
    if not api_configured:
        st.info(
            "ℹ️ **Setup Notice:** Gemini API key is not yet configured. "
            "To enable live AI conversational reasoning, configure `GEMINI_API_KEY` in Streamlit Cloud "
            "**App Settings → Secrets** (or in `.streamlit/secrets.toml` for local development)."
        )

    # ---------------------------------------------------------
    # MAIN LAYOUT: 70% Left (Conversation & Analysis) / 30% Right (Case Workspace)
    # ---------------------------------------------------------
    col_main, col_workspace = st.columns([7, 3])

    # =========================================================
    # LEFT COLUMN (70%): SECTIONS A, B, AND C
    # =========================================================
    with col_main:
        active_case = st.session_state.active_case

        # ---------------------------------------------------------
        # SECTION A: CONVERSATION & INTAKE
        # ---------------------------------------------------------
        if active_case:
            status = active_case.get("status", case_builder.STATUS_INTAKE)
            cid = active_case.get("case_id", "N/A")
            st.info(f"📂 **Active Case:** `{cid}` | **Status:** `{status}` | **Category:** `{active_case.get('issue_category', selected_category)}`")

        if st.session_state.messages:
            st.markdown("### Conversation History")
            for message in st.session_state.messages:
                role = message.get("role", "user")
                avatar = "👤" if role == "user" else "⚖️"
                with st.chat_message(role, avatar=avatar):
                    st.markdown(message.get("text", ""))
            st.write("---")

        input_placeholder = "Example: I purchased a mobile phone online. It arrived with a damaged screen. I contacted the seller, but they refused to replace it."
        if active_case:
            pending_q = active_case.get("pending_question")
            if pending_q:
                input_placeholder = f"Your answer to: {pending_q[:80]}..."
            elif active_case.get("status") == case_builder.STATUS_FACTS_REVIEW:
                input_placeholder = "All main facts collected. You may add extra details or review the facts panel below..."
        elif st.session_state.current_scope == intake.CATEGORY_NEEDS_CLARIFICATION:
            st.info("💬 **Clarification Needed:** Please provide additional details to help Nyaya Saathi confirm if your issue is a consumer dispute.")
            input_placeholder = "Example: Yes, I purchased it from an online marketplace and paid via credit card..."
        elif st.session_state.workflow_paused:
            st.error(
                "⛔ **Assistance Paused:** The previous message was determined to be an emergency or outside consumer dispute scope. "
                "To submit a different inquiry, please click '🔄 Reset' or '➕ New Grievance' above."
            )

        st.markdown("### Describe your consumer issue / Provide answer")
        problem_description = st.text_area(
            label="Enter details",
            height=140,
            placeholder=input_placeholder,
            help="Please describe what happened or answer the guided follow-up question.",
            key=f"problem_input_{st.session_state.input_key_counter}",
            disabled=st.session_state.workflow_paused,
        )

        scope_display = st.session_state.current_scope or "Not Evaluated"
        st.caption(
            f"ℹ️ *Active Model:* `{config.get_model_name()}` | "
            f"*Status:* {'🟢 Connected' if api_configured else '🟡 Setup Required'} | "
            f"*Scope Status:* `{scope_display}`"
        )

        btn_label = "Submit Answer" if (active_case and active_case.get("pending_question")) else "Submit My Problem"
        submitted = st.button(btn_label, type="primary", use_container_width=True, disabled=st.session_state.workflow_paused)

        if submitted:
            cleaned_text = problem_description.strip()

            if not cleaned_text:
                st.error("❌ **Description Required:** Please enter your response before submitting.")
            elif len(cleaned_text) > MAX_INPUT_CHARS:
                st.warning(
                    f"⚠️ **Input Limit Exceeded:** Your response is {len(cleaned_text):,} characters. "
                    f"Please keep your description under {MAX_INPUT_CHARS:,} characters so Nyaya Saathi can process it accurately."
                )
            elif st.session_state.get("session_turn_count", 0) >= MAX_SESSION_TURNS:
                st.error(
                    "⚠️ **Session Request Limit Reached:** You have reached the maximum interaction turns (40) for this session. "
                    "Please click [➕ New Chat] in the right workspace to start a fresh inquiry, or contact the National Consumer Helpline at 1915."
                )
            elif (
                st.session_state.messages
                and st.session_state.messages[-1].get("role") == "user"
                and st.session_state.messages[-1].get("text") == cleaned_text
            ):
                st.info("ℹ️ Your message has already been received. Please wait while the analysis completes.")
            else:
                st.session_state.session_turn_count = st.session_state.get("session_turn_count", 0) + 1
                # 1. EVALUATE TURN SAFETY
                safety_eval = safety_guard.evaluate_turn_safety(
                    user_message=cleaned_text,
                    active_case=st.session_state.active_case,
                    conversation_history=st.session_state.messages,
                    language=selected_language,
                )
                cat = safety_eval["classification"]

                if cat == safety_guard.CATEGORY_URGENT_ESCALATION:
                    st.session_state.workflow_paused = True
                    st.session_state.current_scope = intake.CATEGORY_URGENT_ESCALATION
                    st.session_state.messages.append({"role": "user", "text": cleaned_text})
                    st.session_state.messages.append({"role": "assistant", "text": safety_eval["user_message"]})
                    st.session_state.input_key_counter += 1
                    st.rerun()

                elif cat == safety_guard.CATEGORY_HIGH_RISK_LEGAL_REVIEW:
                    st.session_state.workflow_paused = True
                    st.session_state.current_scope = safety_guard.CATEGORY_HIGH_RISK_LEGAL_REVIEW
                    st.session_state.messages.append({"role": "user", "text": cleaned_text})
                    st.session_state.messages.append({"role": "assistant", "text": safety_eval["user_message"]})
                    st.session_state.input_key_counter += 1
                    st.rerun()

                elif cat == safety_guard.CATEGORY_OUTSIDE_SCOPE:
                    st.session_state.workflow_paused = True
                    st.session_state.current_scope = intake.CATEGORY_OUTSIDE_SCOPE
                    st.session_state.messages.append({"role": "user", "text": cleaned_text})
                    st.session_state.messages.append({"role": "assistant", "text": safety_eval["user_message"]})
                    st.session_state.input_key_counter += 1
                    st.rerun()

                elif cat == safety_guard.CATEGORY_NEEDS_CLARIFICATION and st.session_state.active_case is None:
                    st.session_state.workflow_paused = False
                    st.session_state.current_scope = intake.CATEGORY_NEEDS_CLARIFICATION
                    st.session_state.messages.append({"role": "user", "text": cleaned_text})
                    st.session_state.messages.append({"role": "assistant", "text": safety_eval["user_message"]})
                    st.session_state.input_key_counter += 1
                    st.rerun()

                # 2. ACTIVE CASE FOLLOW-UP INGESTION
                if st.session_state.active_case is not None and not st.session_state.workflow_paused:
                    case = st.session_state.active_case
                    st.session_state.messages.append({"role": "user", "text": cleaned_text})
                    case["conversation_history"].append({"role": "user", "text": cleaned_text})

                    # If already confirmed -> process inquiry or new facts via legal companion
                    if case.get("facts_confirmed_by_user"):
                        with st.spinner("Analyzing your inquiry and official legal sources..."):
                            reply_text = workflow_service.process_case_turn(
                                case=case,
                                user_message=cleaned_text,
                                language=selected_language,
                            )
                        st.session_state.messages.append({"role": "assistant", "text": reply_text})
                        case["conversation_history"].append({"role": "assistant", "text": reply_text})
                        st.session_state.input_key_counter += 1
                        st.rerun()

                    # Otherwise continue guided intake
                    pending_q = case.get("pending_question")
                    case_builder.extract_case_facts_deterministically(case, cleaned_text, pending_question=pending_q)

                    if api_configured:
                        try:
                            gemini_service.extract_case_facts_with_llm(case, cleaned_text, pending_question=pending_q)
                        except Exception:
                            pass

                    case_builder.compute_missing_information(case)
                    next_q = case_builder.get_next_follow_up_question(case, language=selected_language)

                    is_hindi = selected_language.lower() in ("hindi", "hinglish", "hindi/hinglish")

                    if next_q:
                        case["pending_question"] = next_q
                        case["questions_asked"].append(next_q)
                        reply_text = f"👉 **{next_q}**"
                    else:
                        case["pending_question"] = None
                        case["status"] = case_builder.STATUS_FACTS_REVIEW
                        if is_hindi:
                            reply_text = (
                                "📋 **तथ्य समीक्षा (Facts Review):** आपके मामले के सभी मुख्य तथ्य एकत्र कर लिए गए हैं। "
                                "कृपया नीचे दिए गए **तथ्य समीक्षा पैनल** में विवरणों की जांच करें और 'पुष्टि करें (Confirm Facts)' पर क्लिक करें।"
                            )
                        else:
                            reply_text = (
                                "📋 **Facts Review:** Thank you. All core facts have been organized into your structured case. "
                                "Please review the extracted facts in the **Review Panel** below and click **Confirm Facts** to finalize."
                            )

                    st.session_state.messages.append({"role": "assistant", "text": reply_text})
                    case["conversation_history"].append({"role": "assistant", "text": reply_text})
                    st.session_state.input_key_counter += 1
                    st.rerun()

                # 3. INITIAL GRIEVANCE SUBMISSION
                else:
                    with st.spinner("Checking issue scope and knowledge base coverage..."):
                        classification = intake.classify_issue(
                            user_message=cleaned_text,
                            conversation_context=st.session_state.messages,
                            language=selected_language,
                            use_llm_fallback=True,
                        )

                    category = classification.get("category")
                    st.session_state.current_scope = category

                    st.session_state.messages.append({
                        "role": "user",
                        "text": cleaned_text,
                    })

                    if category == intake.CATEGORY_URGENT_ESCALATION:
                        st.session_state.workflow_paused = True
                        urgent_msg = safety.get_urgent_escalation_message(
                            language=selected_language,
                            safety_flags=classification.get("safety_flags"),
                        )
                        st.session_state.messages.append({"role": "assistant", "text": urgent_msg})
                        st.session_state.input_key_counter += 1
                        st.rerun()

                    elif category == intake.CATEGORY_OUTSIDE_SCOPE:
                        st.session_state.workflow_paused = True
                        outside_msg = safety.get_outside_scope_message(
                            reason=classification.get("reason", "This matter is outside Indian consumer protection law."),
                            language=selected_language,
                        )
                        st.session_state.messages.append({"role": "assistant", "text": outside_msg})
                        st.session_state.input_key_counter += 1
                        st.rerun()

                    elif category == intake.CATEGORY_NEEDS_CLARIFICATION:
                        st.session_state.workflow_paused = False
                        clarifying_q = classification.get("clarifying_question") or intake.get_default_clarifying_question(selected_language)
                        is_hindi = selected_language.lower() in ("hindi", "hinglish", "hindi/hinglish")
                        if is_hindi:
                            clarification_text = (
                                "ℹ️ **विवरण की आवश्यकता (Clarification Needed):**\n\n"
                                "आपकी समस्या को सही ढंग से समझने के लिए, कृपया निम्नलिखित प्रश्न का उत्तर दें:\n\n"
                                f"👉 **{clarifying_q}**"
                            )
                        else:
                            clarification_text = (
                                "ℹ️ **Clarification Needed:**\n\n"
                                "To verify whether your issue falls under consumer dispute assistance, could you please clarify:\n\n"
                                f"👉 **{clarifying_q}**"
                            )
                        st.session_state.messages.append({"role": "assistant", "text": clarification_text})
                        st.session_state.input_key_counter += 1
                        st.rerun()

                    else:
                        # Case A / Case B: Consumer dispute
                        st.session_state.workflow_paused = False

                        new_case = case_builder.create_empty_case(
                            issue_category=selected_category,
                            original_user_story=cleaned_text,
                            language_preference=selected_language,
                        )
                        new_case["conversation_history"].append({"role": "user", "text": cleaned_text})

                        case_builder.extract_case_facts_deterministically(new_case, cleaned_text)
                        if api_configured:
                            try:
                                gemini_service.extract_case_facts_with_llm(new_case, cleaned_text)
                            except Exception:
                                pass

                        case_builder.compute_missing_information(new_case)
                        first_q = case_builder.get_next_follow_up_question(new_case, language=selected_language)

                        if first_q:
                            new_case["pending_question"] = first_q
                            new_case["questions_asked"].append(first_q)

                        st.session_state.active_case = new_case

                        is_hindi = selected_language.lower() in ("hindi", "hinglish", "hindi/hinglish")
                        cov_status = classification.get("coverage_status", intake.COVERAGE_SUPPORTED)

                        if is_hindi:
                            scope_confirmation = (
                                f"✅ **Scope Confirmation:** आपकी शिकायत भारतीय उपभोक्ता संरक्षण कानून के कार्यक्षेत्र में आती प्रतीत होती है। "
                                f"(केस आईडी: `{new_case['case_id']}`)\n\n"
                            )
                            if cov_status == intake.COVERAGE_UNAVAILABLE:
                                scope_confirmation += (
                                    f"⚠️ *नोट:* यह विषय एक विशेष नियामक क्षेत्र ({classification.get('coverage_framework')}) से संबंधित है। "
                                    "न्याय साथी उपलब्ध सामान्य कानूनी सिद्धांतों पर मार्गदर्शन देगा।\n\n"
                                )
                            question_prompt = f"👉 **{first_q}**" if first_q else "कृपया नीचे दिए गए तथ्य समीक्षा पैनल में अपने मामले की जांच करें।"
                        else:
                            scope_confirmation = (
                                f"✅ **Scope Confirmation:** Your issue appears to concern a consumer transaction under Indian consumer protection law. "
                                f"(Case ID: `{new_case['case_id']}`)\n\n"
                            )
                            if cov_status == intake.COVERAGE_UNAVAILABLE:
                                scope_confirmation += (
                                    f"⚠️ *Knowledge Base Note:* This matter involves a specialized regulatory framework ({classification.get('coverage_framework')}). "
                                    "Nyaya Saathi will provide guidance under core consumer principles while transparently abstaining from citing unindexed regulations.\n\n"
                                )
                            question_prompt = f"👉 **{first_q}**" if first_q else "Please review your case facts in the panel below."

                        full_response = scope_confirmation + question_prompt
                        st.session_state.messages.append({"role": "assistant", "text": full_response})
                        new_case["conversation_history"].append({"role": "assistant", "text": full_response})
                        st.session_state.input_key_counter += 1
                        st.rerun()

        # ---------------------------------------------------------
        # SECTION B: REVIEW YOUR CASE FACTS (Blueprint Step 13)
        # ---------------------------------------------------------
        if st.session_state.active_case is not None:
            case = st.session_state.active_case
            st.write("---")
            with st.expander(f"📋 Review Your Case Facts ({case['case_id']})", expanded=True):
                status = case.get("status", case_builder.STATUS_INTAKE)
                status_color = "🟢" if status == case_builder.STATUS_FACTS_CONFIRMED else "🟡" if status == case_builder.STATUS_FACTS_REVIEW else "🔵"
                st.markdown(f"#### Case Record: `{case['case_id']}` | Status: {status_color} **{status}**")

                if case.get("facts_confirmed_by_user"):
                    missing = case.get("missing_information", [])
                    has_gaps = (
                        bool(missing)
                        or not case.get("purchase_amount")
                        or not case.get("product_or_service")
                        or not case.get("seller_or_platform")
                        or not case.get("desired_resolution")
                        or not (case.get("purchase_date") or case.get("delivery_date"))
                        or not case.get("evidence")
                        or not case.get("seller_contact", {}).get("seller_response")
                    )
                    if has_gaps:
                        st.success(
                            "✅ **Facts Confirmed:** Your reviewed facts have been confirmed. "
                            "Some information is still missing. You can continue the conversation and add the remaining details."
                        )
                    else:
                        st.success("✅ **Facts Confirmed:** All core case details have been verified and confirmed.")

                # Immutable Original Story
                st.text_area(
                    "Original Grievance Story (Permanent & Immutable)",
                    value=case.get("original_user_story", ""),
                    height=70,
                    disabled=True,
                    help="Your original statement is preserved permanently and cannot be overwritten.",
                )

                # Core Facts Grid
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    st.markdown(f"**Product / Service:** {case.get('product_or_service') or '_Not yet specified_'}")
                    seller_display = case.get("seller_or_service_provider") or case.get("seller_or_platform") or "_Not yet specified_"
                    market_display = case.get("marketplace_or_platform") or "_Not specified_"
                    st.markdown(f"**Seller / Service Provider:** {seller_display}")
                    st.markdown(f"**Marketplace / Platform:** {market_display}")
                    st.markdown(f"**Purchase Amount:** {case.get('purchase_amount') or '_Not yet specified_'}")
                with col_f2:
                    sc = case.get("seller_contact", {})
                    contacted_str = "Yes" if sc.get("contacted") is True else "No" if sc.get("contacted") is False else "_Not yet recorded_"
                    st.markdown(f"**Seller Contacted:** {contacted_str}")
                    st.markdown(f"**Seller Response:** {sc.get('seller_response') or '_N/A_'}")
                    mc = case.get("marketplace_contact", {})
                    m_contacted_str = "Yes" if mc.get("contacted") is True else "No" if mc.get("contacted") is False else "_Not recorded_"
                    st.markdown(f"**Marketplace Contacted:** {m_contacted_str}")
                    st.markdown(f"**Marketplace Response:** {mc.get('marketplace_response') or '_N/A_'}")

                st.markdown(f"**Desired Resolution:** {case.get('desired_resolution') or '_Not yet specified_'}")

                # Timeline Events
                events = case.get("events", [])
                if events:
                    st.markdown("##### 📅 Event Timeline")
                    for idx, ev in enumerate(events, 1):
                        st.markdown(f"- **Event {idx}:** {ev.get('event')} *(Date: {ev.get('date', 'Not specified')})*")

                # Evidence Inventory
                evidence = case.get("evidence", [])
                if evidence:
                    st.markdown("##### 📎 Evidence Inventory")
                    for ev_item in evidence:
                        st.markdown(f"- **{ev_item.get('item')}:** {ev_item.get('description', '')}")

                # Missing Information Display
                missing_fields = []
                if not case.get("product_or_service"):
                    missing_fields.append("Product ordered / Product received")
                if not case.get("purchase_amount"):
                    missing_fields.append("Amount paid")
                if not case.get("purchase_date") and not case.get("delivery_date"):
                    missing_fields.append("Order or purchase date")
                sc = case.get("seller_contact", {})
                if not sc.get("seller_response"):
                    missing_fields.append("Seller / platform formal response")
                if not case.get("desired_resolution"):
                    missing_fields.append("Whether replacement or refund was formally requested")
                if not case.get("evidence"):
                    missing_fields.append("Evidence available (invoice, package photos)")

                if missing_fields:
                    st.markdown("##### ⚠️ Pending Information Gaps")
                    st.info("The following details are still missing from your case record:\n" + "\n".join(f"- {f}" for f in missing_fields))

                # Fact Correction Controls
                st.markdown("##### ✏️ Make a Correction to Your Facts")
                field_labels = {
                    "purchase_amount": "Purchase Amount (e.g. ₹26,000)",
                    "product_or_service": "Product or Service Name",
                    "seller_or_platform": "Seller or E-Commerce Platform",
                    "desired_resolution": "Desired Resolution / Remedy",
                }
                cor_col1, cor_col2, cor_col3 = st.columns([3, 4, 2])
                with cor_col1:
                    field_to_correct = st.selectbox(
                        "Field to correct:",
                        options=["purchase_amount", "product_or_service", "seller_or_platform", "desired_resolution"],
                        format_func=lambda k: field_labels.get(k, k),
                        key="correct_field_select",
                    )
                with cor_col2:
                    new_fact_val = st.text_input(
                        "Correct value:",
                        key=f"correct_val_input_{field_to_correct}",
                        placeholder=f"Enter revised value for {field_to_correct}...",
                    )
                with cor_col3:
                    st.write("")
                    apply_clicked = st.button("Update Fact", key=f"btn_apply_correction_{field_to_correct}")

                current_val = case.get(field_to_correct) or "Not specified"
                if new_fact_val.strip():
                    is_valid, err_msg, cleaned_val = case_builder.validate_fact_value(field_to_correct, new_fact_val.strip())
                    if is_valid:
                        st.info(f"🔎 **Correction Preview:** You are changing **{field_labels.get(field_to_correct, field_to_correct)}** from `{current_val}` to **`{cleaned_val}`**.")
                    else:
                        st.warning(f"⚠️ {err_msg}")

                if apply_clicked:
                    if not new_fact_val.strip():
                        st.error("Please enter a new value before clicking Update.")
                    else:
                        is_valid, err_msg, cleaned_val = case_builder.validate_fact_value(field_to_correct, new_fact_val.strip())
                        if not is_valid:
                            st.error(f"Cannot update: {err_msg}")
                        else:
                            success = case_builder.correct_case_fact(case, field_to_correct, cleaned_val)
                            if success:
                                case_builder.compute_missing_information(case)
                                st.success(f"Updated {field_labels.get(field_to_correct, field_to_correct)} to '{cleaned_val}'!")
                                st.rerun()

                # Confirmation Button
                if not case.get("facts_confirmed_by_user"):
                    st.write("")
                    if st.button("✅ Confirm All Facts as Correct", type="primary", use_container_width=True, key="btn_confirm_facts"):
                        case_builder.confirm_case_facts(case)
                        with st.spinner("Analyzing your case and generating next steps..."):
                            post_conf_resp = workflow_service.generate_post_confirmation_response(case, language=selected_language)
                        
                        is_hi = selected_language.lower() in ("hindi", "hinglish", "hindi/hinglish")
                        notif_text = (
                            "✅ **तथ्य प्रमाणित एवं कानूनी विश्लेषण अद्यतन:** आपके द्वारा समीक्षा किए गए तथ्यों को दर्ज कर लिया गया है। "
                            "विस्तृत कानूनी विश्लेषण, लागू धाराएं तथा आवश्यक दस्तावेजों की सूची नीचे समर्पित अनुभागों में तैयार है।"
                            if is_hi else
                            "✅ **Facts Confirmed & Analysis Updated:** Your structured case facts have been confirmed. "
                            "Your source-grounded legal explanation, applicable laws, realistic options, and dynamic evidence checklist are available in the dedicated sections below."
                        )
                        st.session_state.messages.append({"role": "assistant", "text": notif_text})
                        case["conversation_history"].append({"role": "assistant", "text": notif_text})
                        st.success("Facts confirmed successfully!")
                        st.rerun()

            # ---------------------------------------------------------
            # SECTION 3: CASE ANALYSIS & SUGGESTED NEXT STEPS (Part 5)
            # (Placed immediately below Section B in col_main)
            # ---------------------------------------------------------
            latest_analysis = case.get("latest_analysis")
            if latest_analysis or case.get("facts_confirmed_by_user"):
                st.write("---")
                st.markdown("### ⚖️ Case Analysis & Suggested Next Steps")
                if not latest_analysis and case.get("facts_confirmed_by_user"):
                    with st.spinner("Refreshing case analysis..."):
                        latest_analysis = workflow_service.reanalyse_case(case, language=selected_language)

                if latest_analysis:
                    cov_status = latest_analysis.get("coverage_status", intake.COVERAGE_SUPPORTED)
                    if cov_status == intake.COVERAGE_SUPPORTED:
                        cov_badge = "🟢 In-Scope & Verified (CPA 2019 / E-Commerce Rules)"
                    else:
                        cov_badge = f"🟡 Specialized Domain: {latest_analysis.get('coverage_framework', 'Statutory Limitation')} (Abstention Active)"

                    anl_id = latest_analysis.get("analysis_id", "ANL-CURRENT")
                    anl_time = latest_analysis.get("timestamp", "")[:19].replace("T", " ")
                    st.caption(f"**Analysis Reference:** `{anl_id}` | **Framework:** {cov_badge} | **Generated:** {anl_time}")

                    # Render the 8 distinct analytical components (Part 5.2)
                    struct_ans = latest_analysis.get("structured_answer", {})
                    user_facing_raw = latest_analysis.get("user_facing_response", "")

                    # 1. Case Understanding
                    st.markdown("#### 📌 Case Understanding")
                    prob_desc = struct_ans.get("understanding_of_your_problem") or case.get("problem_description") or case.get("original_user_story")
                    st.markdown(f"> *{prob_desc}*")

                    # 2. Relevant Legal Provisions
                    st.markdown("#### ⚖️ Relevant Legal Provisions")
                    what_says = struct_ans.get("what_the_source_says")
                    if what_says:
                        st.markdown(what_says)
                    else:
                        st.markdown("Under official provisions of the **Consumer Protection Act, 2019** and the **Consumer Protection (E-Commerce) Rules, 2020**, consumers possess protected statutory rights against defective goods, deficiency in service, and unfair refusal of returns or refunds.")

                    # 3. How They Relate to Your Case
                    st.markdown("#### 🔍 How They Relate to Your Case")
                    how_relates = struct_ans.get("how_it_may_relate_to_your_problem")
                    if how_relates:
                        st.markdown(how_relates)
                    else:
                        st.markdown(f"The reported grievance concerns **{case.get('product_or_service', 'the purchased item')}** from **{case.get('seller_or_platform', 'the seller')}**. The obligations of the seller and marketplace apply regarding grievance redressal and replacement/refund remedies.")

                    # 4. Your Possible Options
                    st.markdown("#### 💡 Your Possible Options")
                    st.markdown(
                        "- **1. Direct Merchant & Platform Grievance Escalation:** File a formal written complaint with the platform's designated Grievance Officer under Rule 4(4) / 5(3)(c) of the E-Commerce Rules, 2020 (statutory 48-hour acknowledgment, 1-month resolution).\n"
                        "- **2. National Consumer Helpline (NCH):** Register a formal pre-litigation grievance at **1915** or via `consumerhelpline.gov.in` (DOCA / convergence partner mediation).\n"
                        "- **3. Formal Consumer Commission Filing (e-Jagriti):** If internal escalation fails, file an online consumer complaint under **Section 35 of CPA 2019** before the District Consumer Disputes Redressal Commission via `e-jagriti.gov.in`."
                    )

                    # 5. Practical Next Steps
                    st.markdown("#### 🚀 Practical Next Steps")
                    next_steps = struct_ans.get("possible_next_steps", [])
                    if next_steps:
                        for ns in next_steps:
                            st.markdown(f"- {ns}")
                    else:
                        st.markdown(
                            "- Preserve your tax invoice, purchase confirmation, and bank debit record.\n"
                            "- Maintain unboxing photographs or video showing product defect/damage.\n"
                            "- Keep records of all written communications and seller rejection notices.\n"
                            "- Lodge a grievance on the National Consumer Helpline portal (1915)."
                        )

                    # 6. Documents and Evidence to Gather (Summary)
                    st.markdown("#### 📋 Documents and Evidence to Gather")
                    st.info("A comprehensive, case-specific evidence checklist is generated below in **Section 5** with official procedural and statutory requirements.")

                    # 7. Information Still Required
                    missing_info = struct_ans.get("missing_information") or case.get("missing_information", [])
                    if missing_info:
                        st.markdown("#### ❓ Information Still Required")
                        for mi in missing_info[:3]:
                            st.markdown(f"- {mi}")

                    # 8. Limitations and Professional Review
                    st.markdown("#### ⚠️ Limitations and Professional Review")
                    limitations = struct_ans.get("limitations_and_uncertainties", [])
                    if limitations:
                        for lim in limitations:
                            st.caption(f"- {lim}")
                    else:
                        st.caption(
                            "- Informational guidance only; does not substitute for qualified legal advice from an advocate.\n"
                            "- Remedies under CPA 2019 Section 39(1) are subject to Commission findings and formal proceedings."
                        )

                # ---------------------------------------------------------
                # SECTION 4: RELEVANT LAWS AND CITATIONS (Part 5)
                # ---------------------------------------------------------
                citations = latest_analysis.get("citations", [])
                if citations:
                    st.write("---")
                    st.markdown("### 📜 Relevant Laws and Citations")
                    for cit in citations:
                        act = cit.get("act_name", "Consumer Protection Act, 2019")
                        sec = cit.get("section_or_rule", "Statutory Provision")
                        url = cit.get("official_url", "https://consumeraffairs.nic.in")
                        authority = cit.get("issuing_authority", "Ministry of Consumer Affairs, Food and Public Distribution")
                        excerpt = cit.get("excerpt", "")
                        with st.container():
                            st.markdown(f"**{act} — {sec}**")
                            st.markdown(f"- **Issuing Authority:** {authority}  \n- **Official Gazette Link:** [{url}]({url})")
                            if excerpt:
                                st.caption(f"> *\"{excerpt}\"*")
                            st.write("")

                # ---------------------------------------------------------
                # SECTION 5: DOCUMENTS AND EVIDENCE TO GATHER (Part 4 & 5)
                # ---------------------------------------------------------
                st.write("---")
                st.markdown("### 📋 Documents and Evidence to Gather")
                st.markdown(
                    "Before filing a formal consumer grievance or approaching a Consumer Commission, "
                    "gather the following documents. Items are classified by official procedural and statutory authority:"
                )

                checklist = case.get("evidence_checklist", [])
                if not checklist:
                    from src import evidence_checklist
                    checklist = evidence_checklist.generate_case_evidence_checklist(case)
                    case["evidence_checklist"] = checklist

                # Table display of evidence checklist
                class_icons = {
                    "REQUIRED_OFFICIAL_PROCEDURE": "📌 Required by Official Procedure",
                    "CONDITIONALLY_REQUIRED": "⚖️ Conditionally Required",
                    "RECOMMENDED_EVIDENCE": "📄 Recommended Supporting Evidence",
                    "NOT_YET_ESTABLISHED": "🔍 Not Yet Established",
                }
                status_icons = {
                    "Available": "🟢 Available",
                    "To be collected": "🟡 To be collected",
                    "Missing": "🔴 Missing",
                    "Not applicable": "⚪ Not applicable",
                }

                for item in checklist:
                    c_badge = class_icons.get(item.get("classification"), item.get("classification_label", "Evidence"))
                    s_badge = status_icons.get(item.get("status"), item.get("status", "To be collected"))
                    with st.expander(f"{item['name']} | {s_badge} | {c_badge}", expanded=False):
                        st.markdown(f"**Classification:** `{c_badge}`")
                        if item.get("condition"):
                            st.markdown(f"**Condition / Rule:** {item['condition']}")
                        st.markdown(f"**Relevance:** {item.get('relevance')}")
                        st.markdown(f"**Official Source:** [{item.get('source')}]({item.get('source_url', 'https://consumeraffairs.nic.in')})")
                        st.markdown(f"**Current Status:** **{s_badge}**")
                        if item.get("user_notes"):
                            st.caption(f"**User Notes:** {item['user_notes']}")

                # ---------------------------------------------------------
                # SECTION 6: REMAINING QUESTIONS / SUGGESTED NEXT ACTIONS (Part 5)
                # ---------------------------------------------------------
                st.write("---")
                st.markdown("### ❓ Remaining Questions / Suggested Next Actions")
                pending_q = case.get("pending_question")
                if pending_q:
                    st.warning(f"👉 **Pending Clarification:** {pending_q}\n\n*You can answer this question in the conversation area above to refine your case.*")
                else:
                    st.success("✅ **Core Facts Gathered:** All initial facts have been documented. You can now download and review your evidence checklist.")

                st.markdown(
                    "**Recommended Next Step:**\n"
                    "1. Mark available documents in the right-side **Evidence Checklist**.\n"
                    "2. Click **[ 🔄 Reanalyse ]** in the Case Workspace if you update any facts.\n"
                    "3. If unresolved by seller, call **National Consumer Helpline at 1915** or visit `e-jagriti.gov.in`."
                )

    # =========================================================
    # RIGHT COLUMN (30%): CASE WORKSPACE (Part 6)
    # =========================================================
    with col_workspace:
        # 1. [ ➕ New Chat ] button at top of workspace (Order Item 1)
        if st.button("➕ New Chat", use_container_width=True, type="secondary", help="Start a completely isolated new chat and clear case"):
            reset_conversation()
            st.rerun()

        st.markdown("---")
        case = st.session_state.active_case

        if not case:
            st.markdown("### 📁 Case Workspace")
            st.info(
                "**No active case record.**\n\n"
                "Submit your consumer dispute in the conversation area to automatically create your case, "
                "extract facts, track communication, and inspect legal analysis here."
            )
        else:
            cid = case.get("case_id", "NS-0000")
            status = case.get("status", case_builder.STATUS_INTAKE)
            st.markdown(f"### 📁 Case Workspace: `{cid}`")
            status_color = "🟢" if case.get("facts_confirmed_by_user") else "🟡"
            cat_status = case.get("issue_category_status", "PROVISIONAL")
            st.caption(f"Status: {status_color} **{status}** | Classification: **[{cat_status}]**")

            # 3. Dynamic Issue Category (Order Item 3)
            st.markdown("##### 🏷️ Issue Category")
            ws_category = st.text_input(
                "Dispute Category",
                value=case.get("issue_category", ""),
                key="ws_input_category",
                help="Dynamically inferred consumer dispute category. You may edit this to refine your case.",
            )

            # 4. Editable Case Details (Order Item 4)
            st.markdown("##### 📝 Case Details")
            ws_product = st.text_input(
                "Product or Service",
                value=case.get("product_or_service") or "",
                key="ws_input_product",
                placeholder="e.g. Mobile phone, Air cooler",
            )
            ws_seller = st.text_input(
                "Seller / Service Provider",
                value=case.get("seller_or_service_provider") or case.get("seller_or_platform") or "",
                key="ws_input_seller",
                placeholder="e.g. Retailer or provider name",
            )
            ws_marketplace = st.text_input(
                "Marketplace / Platform",
                value=case.get("marketplace_or_platform") or "",
                key="ws_input_marketplace",
                placeholder="e.g. Amazon, Flipkart, Myntra",
            )
            ws_amount = st.text_input(
                "Purchase Amount (INR)",
                value=str(case.get("purchase_amount") or ""),
                key="ws_input_amount",
                placeholder="e.g. ₹26,000 or 26000",
            )

            ws_col_d1, ws_col_d2 = st.columns(2)
            with ws_col_d1:
                ws_pdate = st.text_input(
                    "Purchase Date",
                    value=case.get("purchase_date") or "",
                    key="ws_input_pdate",
                    placeholder="DD/MM/YYYY",
                )
            with ws_col_d2:
                ws_ddate = st.text_input(
                    "Problem / Delivery Date",
                    value=case.get("delivery_date") or case.get("problem_date") or "",
                    key="ws_input_ddate",
                    placeholder="DD/MM/YYYY",
                )

            sc = case.get("seller_contact", {})
            seller_opts = ["Not sure / Not specified", "Yes", "No"]
            curr_s_idx = 1 if sc.get("contacted") is True else 2 if sc.get("contacted") is False else 0
            ws_scontact = st.selectbox(
                "Seller Contacted?",
                options=seller_opts,
                index=curr_s_idx,
                key="ws_select_scontact",
            )
            ws_sresp = st.text_input(
                "Seller Response",
                value=sc.get("seller_response") or "",
                key="ws_input_sresp",
                placeholder="e.g. Denied replacement / No response",
            )

            mc = case.get("marketplace_contact", {})
            curr_m_idx = 1 if mc.get("contacted") is True else 2 if mc.get("contacted") is False else 0
            ws_mcontact = st.selectbox(
                "Marketplace Contacted?",
                options=seller_opts,
                index=curr_m_idx,
                key="ws_select_mcontact",
            )
            ws_mresp = st.text_input(
                "Marketplace Response",
                value=mc.get("marketplace_response") or "",
                key="ws_input_mresp",
                placeholder="e.g. Refused escalation / Asked to contact seller",
            )

            ws_resolution = st.text_input(
                "Desired Resolution",
                value=case.get("desired_resolution") or "",
                key="ws_input_resolution",
                placeholder="e.g. Full refund, Replacement",
            )

            # 5. Evidence Checklist (Order Item 5)
            st.markdown("##### 📎 Evidence Checklist")
            from src import evidence_checklist
            ws_checklist = case.get("evidence_checklist", [])
            if not ws_checklist:
                ws_checklist = evidence_checklist.generate_case_evidence_checklist(case)
                case["evidence_checklist"] = ws_checklist

            ev_status_updates = {}
            ev_note_updates = {}
            with st.expander(f"Track Evidence ({len(ws_checklist)} items)", expanded=False):
                stat_choices = [
                    evidence_checklist.STATUS_TO_COLLECT,
                    evidence_checklist.STATUS_AVAILABLE,
                    evidence_checklist.STATUS_MISSING,
                    evidence_checklist.STATUS_NOT_APPLICABLE,
                ]
                for ev_it in ws_checklist:
                    item_id = ev_it["id"]
                    curr_st = ev_it.get("status", evidence_checklist.STATUS_TO_COLLECT)
                    curr_st_idx = stat_choices.index(curr_st) if curr_st in stat_choices else 0
                    st.caption(f"**{ev_it['name']}**")
                    chosen_stat = st.selectbox(
                        f"Status for {item_id}",
                        options=stat_choices,
                        index=curr_st_idx,
                        key=f"ws_ev_sel_{item_id}",
                    )
                    chosen_note = st.text_input(
                        f"Notes for {item_id}",
                        value=ev_it.get("user_notes", ""),
                        placeholder="e.g. Saved in downloads / bill received",
                        key=f"ws_ev_nt_{item_id}",
                    )
                    ev_status_updates[item_id] = chosen_stat
                    ev_note_updates[item_id] = chosen_note
                    st.write("")

            st.write("")

            # 6. Update and Reanalyse buttons side by side (Order Item 6)
            col_btn_u, col_btn_r = st.columns(2)
            btn_workspace_update = col_btn_u.button("💾 Update", use_container_width=True, help="Save changes to case facts and evidence")
            btn_workspace_reanalyse = col_btn_r.button("🔄 Reanalyse", use_container_width=True, type="primary", help="Save changes and re-run legal analysis")

            if btn_workspace_update or btn_workspace_reanalyse:
                updates_applied = 0

                # Update Category
                if ws_category.strip() and ws_category.strip() != case.get("issue_category"):
                    case_builder.correct_case_fact(case, "issue_category", ws_category.strip())
                    case["issue_category_status"] = "CONFIRMED"
                    updates_applied += 1

                # Update Product
                if ws_product.strip() and ws_product.strip() != (case.get("product_or_service") or ""):
                    is_ok, _, clean_p = case_builder.validate_fact_value("product_or_service", ws_product.strip())
                    if is_ok:
                        case_builder.correct_case_fact(case, "product_or_service", clean_p)
                        updates_applied += 1

                # Update Seller
                if ws_seller.strip() and ws_seller.strip() != (case.get("seller_or_service_provider") or ""):
                    is_ok, _, clean_s = case_builder.validate_fact_value("seller_or_service_provider", ws_seller.strip())
                    if is_ok:
                        case_builder.correct_case_fact(case, "seller_or_service_provider", clean_s)
                        case["seller_or_platform"] = clean_s
                        updates_applied += 1

                # Update Marketplace
                if ws_marketplace.strip() and ws_marketplace.strip() != (case.get("marketplace_or_platform") or ""):
                    is_ok, _, clean_m = case_builder.validate_fact_value("marketplace_or_platform", ws_marketplace.strip())
                    if is_ok:
                        case_builder.correct_case_fact(case, "marketplace_or_platform", clean_m)
                        updates_applied += 1

                # Update Amount
                if ws_amount.strip() and ws_amount.strip() != str(case.get("purchase_amount") or ""):
                    is_ok, _, clean_a = case_builder.validate_fact_value("purchase_amount", ws_amount.strip())
                    if is_ok:
                        case_builder.correct_case_fact(case, "purchase_amount", clean_a)
                        updates_applied += 1

                # Update Dates
                if ws_pdate.strip() and ws_pdate.strip() != (case.get("purchase_date") or ""):
                    case_builder.update_case_fact(case, "purchase_date", ws_pdate.strip(), source="USER_CORRECTION")
                    updates_applied += 1
                if ws_ddate.strip() and ws_ddate.strip() != (case.get("delivery_date") or ""):
                    case_builder.update_case_fact(case, "delivery_date", ws_ddate.strip(), source="USER_CORRECTION")
                    case["problem_date"] = ws_ddate.strip()
                    updates_applied += 1

                # Update Seller Contact
                s_contacted = True if ws_scontact == "Yes" else False if ws_scontact == "No" else None
                if s_contacted != case["seller_contact"].get("contacted"):
                    case["seller_contact"]["contacted"] = s_contacted
                    updates_applied += 1
                if ws_sresp.strip() != (case["seller_contact"].get("seller_response") or ""):
                    case["seller_contact"]["seller_response"] = ws_sresp.strip()
                    updates_applied += 1

                # Update Marketplace Contact
                m_contacted = True if ws_mcontact == "Yes" else False if ws_mcontact == "No" else None
                if m_contacted != case["marketplace_contact"].get("contacted"):
                    case["marketplace_contact"]["contacted"] = m_contacted
                    updates_applied += 1
                if ws_mresp.strip() != (case["marketplace_contact"].get("marketplace_response") or ""):
                    case["marketplace_contact"]["marketplace_response"] = ws_mresp.strip()
                    updates_applied += 1

                # Update Desired Resolution
                if ws_resolution.strip() and ws_resolution.strip() != (case.get("desired_resolution") or ""):
                    is_ok, _, clean_r = case_builder.validate_fact_value("desired_resolution", ws_resolution.strip())
                    if is_ok:
                        case_builder.correct_case_fact(case, "desired_resolution", clean_r)
                        updates_applied += 1

                # Update Evidence Checklist items
                for it_id, stat_val in ev_status_updates.items():
                    note_val = ev_note_updates.get(it_id, "")
                    for ev_item in case.get("evidence_checklist", []):
                        if ev_item.get("id") == it_id:
                            if ev_item.get("status") != stat_val or ev_item.get("user_notes") != note_val:
                                evidence_checklist.update_evidence_item_status(case, it_id, stat_val, note_val)
                                updates_applied += 1

                case_builder.compute_missing_information(case)

                if btn_workspace_reanalyse:
                    with st.spinner("Reanalysing case with updated workspace facts..."):
                        analysis_res = workflow_service.reanalyse_case(case, language=selected_language)
                    st.success("✅ Case reanalysed! Updated legal analysis in Sections 3, 4, 5 below.")
                    st.rerun()
                else:
                    st.success(f"✅ Case workspace updated ({updates_applied} fields updated)!")
                    st.rerun()

            # 7. Case Activity / Audit Summary (Order Item 7)
            st.markdown("---")
            st.markdown("##### 📊 Case Activity")
            c_hist = len(case.get("correction_history", []))
            a_hist = len(case.get("analysis_history", []))
            ev_cnt = len(case.get("evidence", []))
            ev_chk = len([e for e in case.get("evidence_checklist", []) if e.get("status") == "Available"])
            evn_cnt = len(case.get("events", []))
            st.markdown(
                f"- **Facts Revisions:** {c_hist}\n"
                f"- **Analysis Runs:** {a_hist}\n"
                f"- **Available Evidence:** {ev_chk} verified\n"
                f"- **Timeline Events:** {evn_cnt}"
            )

    # ---------------------------------------------------------
    # G. FULL-WIDTH FOOTER
    # ---------------------------------------------------------
    st.markdown(
        """
        <div class="footer-section">
            <p><strong>Nyaya Saathi Prototype</strong> | Conversational Legal Companion & Case Workspace</p>
            <p>
                <strong>Informational Use Only:</strong> This prototype is built for educational, research, and technical evaluation purposes.
                It does not constitute formal legal advice, representation, or advocacy.
            </p>
            <p style="color: #c53030;">
                ⚠️ <strong>Fictional Data Notice:</strong> Do not submit real personal, banking, or sensitive confidential information.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
