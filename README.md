# ⚖️ Nyaya Saathi — AI Consumer Dispute Assistant for India

> **A practical, guided legal-assistance assistant designed for ordinary consumers in India.**

---

## 📌 1. Project Overview

**Nyaya Saathi** is an AI-powered assistant designed to help everyday consumers across India articulate, organize, and resolve consumer disputes under the **Consumer Protection Act, 2019 (CPA 2019)** and related rules (such as the Consumer Protection (E-Commerce) Rules, 2020).

Consumer grievances—such as damaged goods, delayed refunds, defective products, undelivered orders, or deficient services—often leave consumers overwhelmed by formal legal procedures. Nyaya Saathi bridges this gap by:
1. Identifying whether an inquiry is an Indian consumer dispute before providing assistance.
2. Clarifying ambiguous or vague statements with targeted questions.
3. Escalating emergencies, immediate safety concerns, or physical threats to human helplines (112).
4. Courteously stopping matters that fall outside consumer jurisdiction (e.g., tenancy, employment, family law).

---

## 🚀 2. Current Status: Intelligent Dynamic Legal Companion & Cloud Deployment Ready

Nyaya Saathi is an intelligent consumer-dispute companion built for Kuku's AI Generalist Assignment (Problem 2: Build an AI Lawyer).

The project is fully prepared for **Streamlit Community Cloud** (100% free hosting) with:
- **Zero-Cloud-Cost Architecture**: Runs on free Streamlit Cloud containers with persistent ChromaDB (14MB prebuilt).
- **Multi-User Isolation**: Every browser session has independent, sandboxed `st.session_state`.
- **Memory & Resource Budgeting**: Lazy-loading and Streamlit `@st.cache_resource` for the multilingual E5 embedding model (~470MB) shared safely across sessions within the ~1GB RAM limit.
- **Abuse & Rate Protections**: Capped at 2,500 chars/submission and 40 turns/session with automatic duplicate debounce.
- **Step-by-Step Deployment Guide**: See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for 1-click deployment instructions to Streamlit Community Cloud.

### 📌 Core System Capabilities
1. **Intelligent Scope Classification**: Four outcomes (`LIKELY_CONSUMER_DISPUTE`, `NEEDS_CLARIFICATION`, `OUTSIDE_SCOPE`, `URGENT_ESCALATION`) with strict safety priority.
2. **Dynamic Fact Extraction & Review**: Category-aware structured fact extraction with confidence ratings, provenance tracking, and interactive inline correction.
3. **Statutory Legal Knowledge Base**: 141 CPA 2019 sections, 36 E-Commerce Rules (2020), 4 General Rules (2020), 1 E-Commerce Amendment (2021), and e-Jagriti procedural filing manual.
4. **Hybrid Search Engine**: Reciprocal Rank Fusion ($k=60$) combining dense Multilingual E5 embeddings and BM25Okapi lexical retrieval with 5-date temporal gating.
5. **Grounded Legal Companion**: Conversational legal analysis, actionable next steps, consumer commission hierarchy, limitation period advisories, and official portal citations.
6. **Safety & Abstention Engine**: Automatic escalation for physical harm/accidents (112), out-of-scope redirection (RERA, Labour, Family, Criminal), and explicit abstention when facts lack legal support.

### 📌 Authoritative Blueprint Step Alignment
To maintain strict compliance with the authoritative Nyaya Saathi Project Blueprint:
- **Step 12**: Category-Aware Follow-up Question Logic (Implemented in `src/case_builder.py` & `src/intake.py`).
- **Step 13**: Structured Case Builder & Active Grievance Memory (Implemented in `src/case_builder.py` & `app.py`).
- **Step 16**: Keyword Retrieval (Our semantic, BM25, and hybrid retrieval implementations already exceed the original Step 16 retrieval specification). Dynamic RAG Context Assembly is an upcoming integration layer, not the original Blueprint Step 16.
- **Step 17**: Source-Grounded Legal Explanation (Upcoming).
- **Step 18**: Citation Verification & Checking (Upcoming).
- **Step 19**: Safety & Escalation Guardrails (Implemented in `src/safety.py`).

---

### 🧠 2.1 How Active Grievance Memory & Intake Work

1. **Active Grievance Memory (`st.session_state.active_case`)**:
   - When a user submits an initial grievance verified as `LIKELY_CONSUMER_DISPUTE`, a structured case object is generated with a unique Case ID (e.g., `NS-0001-2609`).
   - The user's exact initial text is recorded in `original_user_story` and is **permanently immutable**.
   - The case tracks product/service, seller/platform, purchase amount, seller communication status, timeline events, and evidence items.

2. **How Follow-up Answers Update the Same Case**:
   - When `st.session_state.active_case` exists, subsequent submissions are recognized as follow-up answers to the active case.
   - The system **bypasses the initial scope classifier**, ensuring that brief follow-up replies (e.g., "I ordered it from Amazon", "It cost ₹45,000", "The seller is not answering my calls") are ingested into the existing case without re-triggering scope classification.
   - Facts are extracted deterministically and updated with source provenance in `fact_sources`.
   - The next targeted question is generated dynamically until all core facts are known or marked unknown, at which point the case advances to `FACTS_REVIEW`.

3. **How to Start a New Grievance (`➕ New Grievance`)**:
   - Clicking `➕ New Grievance` clears the active case, clears conversation history, resets scope classification state, and presents a clean slate.
   - When the user enters their next grievance, a completely new unique Case ID is generated.
   - None of the previous grievance's facts, seller details, amounts, or conversation history carry over.

4. **What Happens When the User Resets (`🔄 Reset`)**:
   - Clicking `🔄 Reset` clears `messages`, sets `active_case = None`, clears `current_scope`, and unpauses any workflow pause.
   - The application returns to its initial clean state.

5. **Safety Signal Priority During Follow-up**:
   - Urgent safety detection (`detect_urgent_safety_signals()`) executes on **every** user message, even during multi-turn follow-ups.
   - If an emergency or bodily harm signal appears mid-intake (e.g., "The device exploded and burned my hand"), the assistant immediately pauses normal workflow and surfaces emergency 112 assistance.


---

## 🛠️ 3. Technology Stack

- **Language:** Python 3.11 / 3.12
- **Web Interface:** [Streamlit](https://streamlit.io/)
- **AI Runtime:** Google Gemini API (`google-genai` SDK v3.0.0, Model: `gemini-3.1-flash-lite`)
- **Embeddings & Vector Search:** `sentence-transformers` (`intfloat/multilingual-e5-small`), `chromadb`
- **Lexical Search:** `rank-bm25` (v0.2.2)
- **Testing:** `pytest` (v9.2.0) and Python standard library `unittest`
- **Document Handling:** `pymupdf` (PDF extraction), `pypdf`, `python-docx`
- **Environment Management:** Python standard `venv` and `python-dotenv`

> **Architectural Guardrail:** Nyaya Saathi does **not** use LangChain, LangGraph, or external vector databases. It maintains a clean, transparent, deterministic architecture.

---

## 📂 4. Project Directory Structure

```text
NyayaSaathi/
│
├── app.py                             # Main Streamlit web application with Issue Scope Classifier
├── requirements.txt                   # Python project dependencies (streamlit, google-genai, etc.)
├── README.md                          # Beginner-friendly setup and project documentation
├── .gitignore                         # Excludes venvs, caches, secrets, and private documents
│
├── .streamlit/
│   ├── secrets.toml.example           # Template for local Gemini API configuration
│   └── secrets.toml                   # (Local only - Git ignored) Your actual Gemini API key
│
├── src/                               # Application source modules
│   ├── __init__.py                    # Package initializer
│   ├── config.py                      # Central secrets and model configuration manager
│   ├── prompts.py                     # 16-point base system instructions & prompt builder
│   ├── safety.py                      # Safety patterns, emergency helplines & domain detection
│   ├── intake.py                      # Issue Scope Classifier (4 outcomes, deterministic + LLM fallback)
│   ├── gemini_service.py              # Official Google GenAI SDK client wrapper & error handler
│   ├── embeddings.py                  # Multilingual E5 embeddings (384 dim, 512 max tokens, E5 prefixes)
│   ├── vector_store.py                # ChromaDB persistent vector store manager (3 collections)
│   ├── legal_retriever.py             # Multilingual E5 semantic retrieval engine (Phase 4A)
│   ├── keyword_expansion.py           # Controlled bilingual Hindi/Hinglish vocabulary (Phase 4B)
│   ├── bm25_retriever.py              # BM25Okapi lexical retrieval engine (Phase 4B)
│   ├── hybrid_retriever.py            # Reciprocal Rank Fusion hybrid retrieval engine (Phase 4C)
│   ├── case_builder.py                # Structured Case Builder, active grievance memory & guided intake (Steps 12 & 13)
│   ├── answer_generator.py            # Grounded legal guidance synthesizer (Upcoming)
│   ├── citation_checker.py            # Official citation verification engine (Upcoming)
│   └── document_export.py             # Word (.docx) & text draft generator (Upcoming)
│
├── scripts/
│   ├── build_vector_index.py          # Idempotent ChromaDB vector index build & audit script
│   ├── test_semantic_retrieval.py     # Developer semantic retrieval CLI & benchmark runner (Phase 4A)
│   ├── test_bm25_retrieval.py         # Developer BM25 retrieval CLI & benchmark runner (Phase 4B)
│   └── test_hybrid_retrieval.py       # Developer Hybrid retrieval CLI & benchmark runner (Phase 4C)
│
├── data/                              # Knowledge bases and test suites
│   ├── legal_sources/
│   │   ├── originals/                 # Original official source PDFs/notifications
│   │   ├── extracted/                 # Cleaned, extracted text versions
│   │   ├── chroma_db/                 # (Local only - Git ignored) ChromaDB persistent vector database (3 collections)
│   │   ├── source_catalog.json        # Metadata catalog of official legal sources
│   │   ├── legal_chunks.json          # Canonical, citeable legal knowledge chunks (206 chunks)
│   │   ├── embedding_records.json     # Derived non-truncated legal embedding records (251 records)
│   │   ├── historical_reference_chunks.json # Historical 2015 educational chunks (74 chunks)
│   │   ├── vector_index_manifest.json # Vector index metadata, counts, hash & configuration manifest (v1.1.0)
│   │   └── VECTOR_INDEX_AUDIT.md      # Full source reconciliation & discrepancy resolution report
│   │
│   └── test_cases/
│       ├── test_cases.json            # 22 synthetic test cases for scope classification
│       ├── semantic_retrieval_cases.json # 20 synthetic test cases for semantic retrieval evaluation
│       └── case_management_cases.json # 20 synthetic end-to-end multi-turn intake scenarios (Steps 12 & 13)
│
├── generated_documents/               # Output folder for user-generated drafts (.docx/.txt)
│
└── tests/                             # Automated test suite (203 passing tests)
    ├── test_case_builder.py           # Unit, integration & AppTest suite for Steps 12 & 13 (15 tests)
    ├── test_hybrid_retriever.py       # RRF hybrid retrieval & temporal gating tests (39 tests)
    ├── test_bm25_retriever.py         # BM25 keyword retrieval, normalisation & segregation tests (30 tests)
    ├── test_retrieval.py              # Semantic retrieval, date filtering & collection routing tests (25 tests)
    ├── test_source_catalog.py         # Legal source catalog metadata verification tests (15 tests)
    ├── test_vector_store.py           # ChromaDB 3-collection segregation, persistence & manifest tests (15 tests)
    ├── test_chunking.py               # Legal chunking and metadata preservation tests (14 tests)
    ├── test_keyword_expansion.py      # Controlled bilingual vocabulary & language detection tests (12 tests)
    ├── test_embeddings.py             # Multilingual E5 embedding, prefix, 512-token & child tests (12 tests)
    ├── test_document_loader.py        # PDF text extraction and boundary tests (10 tests)
    ├── test_phase2_suite.py           # Unit tests for config, prompts, mocks & error handling (7 tests)
    ├── test_intake.py                 # Unit & integration tests for all 4 scope outcomes & safety (6 tests)
    ├── test_phase1_interface.py       # Streamlit UI & session state baseline tests (1 test)
    ├── test_phase3_app.py             # Live interactive Streamlit AppTest for classification UI (1 test)
    └── test_citations.py              # Citation verification tests (1 test)
```

---

## 💻 5. Running the Application & Tests (Windows PowerShell)

### Step 5.1: Navigate to the Project

```powershell
cd c:\Users\91995\Desktop\kuku\project\NyayaSaathi
```

### Step 5.2: Run the Automated Test Suite

Run the full automated test suite using `pytest`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

*(All 203 tests will pass cleanly with exit code 0)*

### Step 5.3: Test Semantic and BM25 Retrieval via Developer CLI

```powershell
# 1. Test BM25 Lexical Retrieval
.\.venv\Scripts\python.exe scripts\test_bm25_retrieval.py --query "Section 35 Consumer Protection Act"
.\.venv\Scripts\python.exe scripts\test_bm25_retrieval.py --query "दुकानदार पैसे वापस नहीं कर रहा है"
.\.venv\Scripts\python.exe scripts\test_bm25_retrieval.py --eval

# 2. Test Semantic Retrieval
.\.venv\Scripts\python.exe scripts\test_semantic_retrieval.py --query "I received a damaged laptop"
.\.venv\Scripts\python.exe scripts\test_semantic_retrieval.py --eval
```

### Step 5.3: Run the Developer Connectivity Check

Verify live Gemini API connectivity:

```powershell
.\.venv\Scripts\python.exe tests\test_gemini_connectivity.py
```

### Step 5.4: Launch the Streamlit Web Application

```powershell
streamlit run app.py
```

The web interface will open automatically in your browser at `http://localhost:8501`.

---

## ⚖️ Legal Disclaimer

Nyaya Saathi is an automated educational and drafting assistant. It is **not** a lawyer, does not provide legal representation, and cannot guarantee any dispute outcome. For formal disputes, always consult a qualified advocate or the **National Consumer Helpline (1915 / consumerhelpline.gov.in)**.
