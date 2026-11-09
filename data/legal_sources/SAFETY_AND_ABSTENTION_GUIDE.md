# Nyaya Saathi — Safety, Escalation, and Explicit Abstention Guide
**Authoritative Cross-Cutting Safety Architecture Specification**
*Aligned with NYAYASAATHI.txt Blueprint | Version 1.1.0 | November 2026*

---

## 1. Executive Summary & Authoritative Blueprint Alignment

Nyaya Saathi is an AI-powered legal companion designed to help ordinary citizens in India understand consumer disputes, organize grievance facts, verify official statutory provisions, and prepare structured complaints.

In accordance with the authoritative project blueprint (**`NYAYASAATHI.txt`**), the project step sequence is:
- **Step 17**: Create the Citation Validator (`src/citation_checker.py`)
- **Step 18**: Create an Abstention Mechanism (`src/abstention.py`)
- **Step 19**: Create the Case Data Structure (`src/case_builder.py`)
- **Step 20**: Implement Session Memory
- **Step 21**: Implement Fact Extraction
- **Step 22**: Implement Follow-Up Questions
- **Step 23**: Implement Case Timeline
- **Step 24**: Implement Evidence Inventory
- **Steps 25–27**: Legal Companion Agent and Workflow
- **Steps 28–29**: Voice Input (Hindi and English)
- **Steps 30–34**: Complaint Structure, DOCX, PDF, and Download Buttons
- **Steps 35–36**: Main UI and Streamlit Application (`app.py`)
- **Steps 37–40**: Optional Adversarial Agent (Practice Mode)
- **Steps 41–44**: Testing and Validation
- **Step 45**: Privacy and Security
- **Step 46**: Complete System Flow
- **Steps 47–48**: Running the Application and Initial Demo
- **Steps 49–51**: Deliverables and Final Expected Result

The safety guard (`src/safety_guard.py`) operates as a **cross-cutting safety and escalation firewall** that envelopes every conversation turn and guards the final answer delivery gate. It does not replace the numbering of Step 19 (Case Data Structure).

The safety architecture guarantees that:
1. Every user turn is evaluated against a strict 5-tier safety hierarchy before any legal intake or generation occurs.
2. Immediate physical safety threats (appliance fires, sparks, electric shocks, physical violence) supersede all commercial workflows and guide users directly to **112**.
3. Situations demanding formal advocacy (court notices, summons, impending statutory deadlines, multi-forum proceedings) trigger structured warnings advising professional legal consultation.
4. If official legal sources are missing, unretrieved, contradictory, or fail citation validation, Nyaya Saathi executes **explicit abstention** using the exact standard statement.
5. All legal answers pass through an independent **Final Answer Safety Gate** that **blocks** prohibited outcome guarantees ("guarantee", "definitely win", "100% refund") and strictly forbids false credibility claims such as "Legally Verified".

---

## 2. Five Structured Safety Classifications & Deterministic Precedence

On **every user turn** (initial problem submission, guided intake answers, fact corrections, or clarification responses), Nyaya Saathi runs `evaluate_turn_safety()` from `src/safety_guard.py`. The evaluation follows strict deterministic precedence:

```
[User Turn Input]
       │
       ▼
[Tier 1: URGENT_ESCALATION] ───────────────► Immediate 112 Safety Guidance & Pause
       │ (No match)
       ▼
[Tier 2: HIGH_RISK_LEGAL_REVIEW] ──────────► Advocate Consultation Guidance & Pause
       │ (No match)
       ▼
[Tier 3: OUTSIDE_SCOPE] ───────────────────► Domain Redirect & Pause
       │ (No match)
       ▼
[Tier 4: NEEDS_CLARIFICATION] ─────────────► Single Clarifying Question (Initial Only)
       │ (No match or active case ongoing)
       ▼
[Tier 5: NORMAL_CONSUMER_DISPUTE] ─────────► Structured Intake / Grounded Generation
```

### Classification Specifications

| Classification | Priority | Description | Required System Action |
| :--- | :--- | :--- | :--- |
| `URGENT_ESCALATION` | 1 (Highest) | Immediate appliance hazard (smoke, sparks, fire, electric shock), physical violence, threats to life, medical emergencies. | Halts case workflow immediately. Delivers prioritized physical safety instructions directing the user to dial **112**. Forbids legal jargon or seller-related questions. |
| `HIGH_RISK_LEGAL_REVIEW` | 2 | Formal court summons, legal notice with impending hearing, limitation/appeal expiry (<30 days), severe injury/hospitalization, criminal extortion, multiple court proceedings (High Court, NCLT, FIR), or complex transitional law. | Halts automated intake/drafting. Directs the consumer to preserve evidence and consult a qualified advocate or the District Legal Services Authority (DLSA). |
| `OUTSIDE_SCOPE` | 3 | Tenancy, employment/unpaid wages, matrimonial/divorce, property/inheritance, criminal complaints, traffic fines, coding/software queries, or personal dating/relationship advice. | Explains why the matter falls outside Indian consumer protection law. Provides appropriate alternate forums (Rent Controller, Labour Court, Family Court, Cyber Crime Helpline 1930). |
| `NEEDS_CLARIFICATION` | 4 | Extremely vague or generic initial messages without mention of product, service, platform, or seller problem (e.g., "I need legal help with a problem"). | Prompts a single, focused clarifying question asking for the product/service and seller issue. **Exemption**: Does NOT flag short answers (e.g., "₹15,000", "Amazon") when an active case is answering guided follow-ups. |
| `NORMAL_CONSUMER_DISPUTE` | 5 | Ordinary Indian consumer grievances (defective goods, delayed delivery, refund refusal, deficiency in service, misleading advertisements). | Allows normal structured case builder extraction, guided follow-up question flow, and source-grounded legal answer generation. |

---

## 3. Tier 1: Immediate Urgent Escalation Triggers & Protocols

### Urgent Hazard Triggers
1. **Appliance & Electrical Hazards**:
   - Appliance smoking, sparks, fire, explosion, burning odor.
   - Electric shock or live current from consumer goods (e.g., water heater, refrigerator, mixer grinder).
   - Regex patterns explicitly account for English, Hinglish, and Devanagari Hindi (e.g., `धुआं`, `आग lag`, `जल raha`, `करंट`, `बिजली का झटका`).
2. **Physical Harm & Emergency**:
   - Physical assault by delivery personnel or seller representatives.
   - Severe bodily injury, deep burns, poisoning, hospitalization.
   - Direct threats to life or family safety.

### Urgent Response Rules
- **Safety First**: The response must prioritize life and physical safety before any other topic.
- **Emergency Helpline 112**: Prominently display **112** (National Emergency Number for Police, Fire, and Ambulance).
- **Zero Legal Jargon**: Never quote statutory sections (e.g., Section 83 CPA) or mention legal rights while an active physical danger exists.
- **Zero Seller Inquiries**: Never ask the user follow-up commercial questions such as "Did you contact Amazon?" or "What was the purchase price?".
- **Workflow Pause**: Set `st.session_state.workflow_paused = True` to halt automated processing until the user resets or starts a new grievance.

---

## 4. Tier 2: High-Risk Legal Review Triggers & Advocate Referral

Nyaya Saathi is an educational and drafting prototype. It must never attempt to replace qualified legal counsel when formal proceedings or legal peril exist.

### High-Risk Triggers
1. **Formal Court Summons / Notice**:
   - "I received a summons from the District Commission."
   - "The seller served me an advocate notice threatening defamation."
2. **Impending Statutory Expiry / Limitation Issues**:
   - Explicit limitation deadlines, statutory appeal windows, or notice response periods (e.g. 10, 29, 30, 45, or 90 days).
   - Limitation questions under Section 69 (2 years from cause of action) or Section 41/51 appeal timeframes.
   - **Crucial Rule**: The system does NOT calculate unverified legal deadlines or apply an arbitrary 30-day numerical threshold. Any explicit limitation or deadline issue triggers cautious advocate review.
3. **Severe Personal Injury / Product Liability**:
   - Permanent disability, skull fracture, ICU admission from defective products.
4. **Multiple Concurrent Proceedings**:
   - Simultaneous proceedings in High Court, NCLT (insolvency), or criminal police FIR.
5. **Complex Transitional Statutory Applicability**:
   - Questions regarding retrospective application of amendments or transactions spanning the transition between the 1986 Act and the 2019 Act.

### System Response
- Transparently advises that formal judicial representation is required.
- Details the specific risk factors detected.
- Advises preservation of all primary evidence (invoices, emails, packaging, notices).
- Recommends prompt consultation with a qualified advocate. Explains that consumers who qualify for free legal services may approach the appropriate Taluk Legal Services Committee (TLSC), District Legal Services Authority (DLSA), or State Legal Services Authority (SLSA) under the Legal Services Authorities Act, 1987, subject to statutory eligibility and jurisdiction. Does not claim DLSA provides "binding statutory advice".

---

## 5. Explicit Legal Abstention Engine (`src/abstention.py`)

When legal answer generation is requested, the system evaluates deterministic prerequisites. If any criterion fails, the system executes **explicit abstention** instead of returning ungrounded or speculative legal advice.

### Mandatory Standard Abstention Statement
> *"The available legal sources in Nyaya Saathi are insufficient to verify this point. I don't want to give you an unsupported legal answer."*

### Explicit Abstention Triggers
1. **Zero Retrieved Legal Sources**:
   - Hybrid retrieval returns an empty source list.
   - Action: Abstains with `ABSTAIN_NO_RETRIEVED_SOURCES`.
2. **Unretrieved Statutory Grounding**:
   - An answer refers to a statutory provision that exists in law but was not retrieved into the active retrieval context.
   - Action: Abstains with `ABSTAIN_UNRETRIEVED_SOURCE`.
3. **Citation Validation Failure**:
   - One or more cited provisions fail deterministic validation against canonical legal chunks (`legal_chunks.json` or `embedding_records.json`).
   - Action: Blocks answer delivery with `ABSTAIN_CITATION_CHECK_FAILED`.
4. **Unsupported Legal Claims**:
   - Generated claims lack verifiable textual overlap against the exact text of retrieved official sources.
   - Action: Suppresses unsupported claims or abstains with `ABSTAIN_UNSUPPORTED_LEGAL_CLAIM`.
5. **Future-Effective Law Presented as Operative**:
   - G.S.R. 789(E) (E-Commerce Amendment Rules, 2026) has an official commencement date of **2027-01-01**.
   - If referenced prior to 2027-01-01, the system issues a mandatory non-operative commencement notice.
6. **Historical or Superseded Law**:
   - Chunks from `historical_reference_chunks.json` (such as Consumer Protection Act, 1986) are strictly barred from being presented as governing current disputes.
   - Action: Abstains with `ABSTAIN_HISTORICAL_SUPERSEDED_SOURCE`.
7. **Unconfirmed Case Facts**:
   - If `case.facts_confirmed_by_user` is False, the answer is flagged with a prominent **Provisional Notice**, preventing definitive conclusions based on unverified allegations.

---

## 6. Final Answer Safety Gate (`evaluate_final_answer_safety_gate`)

The Final Answer Safety Gate is an independent firewall that inspects every generated legal response and its corresponding citation validation report before delivery to the user interface.

```
[Generated Legal Answer] ──┐
                          ▼
[Validation Report] ────► [Final Answer Safety Gate]
                                  │
          ┌───────────────────────┴───────────────────────┐
          ▼                                               ▼
[Blocked / Prohibited]                          [Sanitized Delivery]
- Fails Citation Check                          - Prohibited phrases scrubbed
- Prohibited Claims                             - Disclaimers attached
- Returns Abstention Response                   - Delivers to Streamlit UI
```

### Prohibited Outcome Guarantees Blocked (Not Scrubbed)
The gate strictly blocks delivery if an answer contains material outcome guarantees:
- `"will definitely win"` / `"guarantee 100% refund"`
- `"100% guaranteed"` / `"certain victory"`
- Any claim that compensation or refund is automatic or guaranteed by law.
- **Strict Policy**: Prohibited phrases are NEVER silently rewritten or replaced with alternative legal wording. The entire response is blocked, suppressed from the UI, and replaced with an explicit abstention response explaining that automated systems cannot provide guaranteed legal remedies.

### Prohibition of "Legally Verified" Badges
- Textual support from retrieved sources verifies that a sentence reflects official text (`SUPPORTED_BY_PASSAGE`).
- It **does not** constitute legal certification or attorney review.
- The UI and API are strictly prohibited from rendering badges, pills, or text containing `"Legally Verified"`.
- When sources with `REQUIRES_LEGAL_REVIEW` are used, an explicit advocate review disclaimer is appended.

---

## 7. Multi-Turn Safety Pipeline & Grievance Continuity

### Turn-by-Turn Execution
Safety checks are not restricted to the initial submission. The safety evaluation executes on every turn:
1. **Initial Grievance**: Checks for emergency, out-of-scope, or vague initial inputs.
2. **Guided Follow-up Answers**: Evaluates answers while exempting valid short inputs (e.g., "₹45,000", "Amazon") from vague classification.
3. **Mid-Conversation Escalation**: If a user initially reports a defective phone but later reports `"The battery is smoking and burning!"`, the system immediately pauses normal intake and switches to `URGENT_ESCALATION`.
4. **Follow-up Threat Detection**: If a seller threatens court proceedings mid-conversation, the system immediately switches to `HIGH_RISK_LEGAL_REVIEW`.

### "+ New Grievance" Isolation
Clicking `+ New Grievance` or `🔄 Reset`:
- Generates a fresh, independent case record (`NS-XXXX`).
- Clears all session messages, active grievance context, and pause flags.
- **Never inherits risk flags or paused states** from previous grievances.

---

## 8. Technical Boundaries & Known Limitations

1. **Informational Software Prototype Only**: Nyaya Saathi is designed for research, educational, and drafting demonstration under the Consumer Protection Act, 2019. It is not an attorney and does not form an attorney-client relationship.
2. **Emergency Disclaimer**: Nyaya Saathi has no direct dispatch integration with police, fire, or ambulance services. Users facing active threats must call **112**.
3. **Statutory Cutoff & Commencement**: Statutory sources are current as of November 2026. Amendments with future commencement dates (e.g., G.S.R. 789(E) commencing 2027-01-01) are handled through explicit temporal applicability notices.
4. **Deterministic Gate Priority**: Deterministic safety rules and exact-match citation verification strictly override generative LLM outputs.

---
*End of Safety, Escalation, and Explicit Abstention Guide.*
