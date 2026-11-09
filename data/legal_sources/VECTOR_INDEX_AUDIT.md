# VECTOR INDEX AUDIT REPORT
## Audit of Legal Sources, Canonical Chunks, and Vector Database Collections

**Project:** NYAYA SAATHI — AI Consumer Dispute Assistant for India  
**Date of Audit:** 2026-11-07  
**Scope:** Verification of `source_catalog.json`, `legal_chunks.json`, `historical_reference_chunks.json`, and ChromaDB Persistent Vector Database.

---

## 1. Executive Findings & Discrepancy Resolution

During the Phase 3C implementation, an apparent discrepancy was noted between earlier milestone reports (Phase 3B.1) and the summary figures reported in Phase 3C. A systematic audit was conducted comparing the canonical source JSON (`data/legal_sources/legal_chunks.json`), the catalogue (`data/legal_sources/source_catalog.json`), and the actual ChromaDB database entries (`data/legal_sources/chroma_db/`).

### Resolution Summary:
- **Canonical Dataset Integrity:** The canonical file `data/legal_sources/legal_chunks.json` has contained exactly **206 retrieval-eligible chunks** throughout both phases without modification.
- **ChromaDB Physical State:** ChromaDB contained exactly **204 records** in `nyaya_saathi_current_law` and **2 records** in `nyaya_saathi_future_law` (Total: 206 records). There were **0 missing chunk IDs**, **0 duplicate IDs**, and **0 unexpected records**.
- **Root Cause of Discrepancy:** The discrepancy originated solely from **clerical errors and narrative hallucination** in the prose of the Phase 3C markdown report. The physical database and JSON sources were completely consistent; however, the narrative summary presented fabricated sub-counts for rules documents and invented an entry for "Mediation Rules 2020: 4 rule chunks" to sum to 204.

---

## 2. Detailed Investigation of Reported Inconsistencies

### A. CPA 2019 Sections: 107 versus 106
- **Investigation:** The Consumer Protection Act, 2019 (Act No. 35 of 2019) contains 107 statutory sections (Sections 1 to 107).
- **Actual Record Count in `legal_chunks.json`:**
  - `SECTION` provision chunks: Exactly **107 chunks** (Sections 1 through 107, IDs: `CPA_2019_SECTION_1` to `CPA_2019_SECTION_107`).
  - `DEFINITION_CLAUSE` chunks: Exactly **47 chunks** (Clause (1) to Clause (47) of Section 2).
  - Total CPA 2019 Chunks: **154 chunks** (107 + 47).
- **Discrepancy Source:** The Phase 3C narrative report wrote `"106 section chunks + 47 definition clauses"`. This was an erroneous clerical typo that mistakenly subtracted Section 2 or miscounted 106 instead of 107. All 107 sections exist in the data and in ChromaDB.

### B. Consumer Protection (General) Rules, 2020: 5 versus 14
- **Investigation:** Official Notification G.S.R. 449(E) / G.S.R. 458(E) dated 15 July 2020 contains exactly **5 statutory rules**:
  1. Rule 1: Short title and commencement
  2. Rule 2: Definitions
  3. Rule 3: Public utility services to be establishments
  4. Rule 4: Certain activities to be exempt from unfair trade practice
  5. Rule 5: Manner of issuing invoice or bill or cash memo or receipt for goods sold or services rendered
- **Actual Count:** Exactly **5 chunks** (`CP_GENERAL_RULES_2020_RULE_1` through `RULE_5`).
- **Discrepancy Source:** The Phase 3C narrative report erroneously reported "14 rule chunks" for General Rules due to narrative transcription error.

### C. Consumer Protection (CDRC) Rules, 2020: 17 versus 14
- **Investigation:** Official Notification G.S.R. 448(E) / G.S.R. 459(E) dated 15 July 2020 contains **17 statutory rules** governing the appointment, qualifications, manner of deposit, and procedure of Consumer Commissions.
- **Actual Count:** Exactly **17 chunks** (`CP_CDRC_RULES_2020_RULE_1` through `RULE_17`).
- **Discrepancy Source:** The Phase 3C narrative report erroneously stated "14 rule chunks".

### D. Consumer Protection (E-Commerce) Rules, 2020: 8 versus 3
- **Investigation:** Official Notification G.S.R. 462(E) dated 23 July 2020 contains **8 statutory rules**:
  - Rule 1: Short title and commencement
  - Rule 2: Scope and Applicability
  - Rule 3: Definitions
  - Rule 4: Duties of e-commerce entities
  - Rule 5: Liabilities of marketplace e-commerce entities
  - Rule 6: Duties of sellers on marketplace
  - Rule 7: Duties and liabilities of inventory e-commerce entities
  - Rule 8: Contravention of rules
- **Actual Count:** Exactly **8 chunks** (`CP_ECOMMERCE_RULES_2020_RULE_1` through `RULE_8`).
- **Corrigendum:** 1 chunk (`CP_ECOMMERCE_CORRIGENDUM_2020_FULL_INSTRUMENT` under G.S.R. 468(E)).
- **Discrepancy Source:** The Phase 3C narrative report stated "3 rule chunks + G.S.R. 328(E) corrigendum", conflating rule counts and confusing the 2020 corrigendum G.S.R. 468(E) with the 2021 amendment G.S.R. 328(E).

### E. Consumer Protection (Jurisdiction of Commissions) Rules, 2021: 5 versus Not Listed
- **Investigation:** Official Notification G.S.R. 912(E) dated 30 December 2021 contains **5 statutory rules**:
  - Rule 1: Short title and commencement
  - Rule 2: Definitions
  - Rule 3: Jurisdiction of District Commission (up to Rs. 50 Lakhs)
  - Rule 4: Jurisdiction of State Commission (Rs. 50 Lakhs to Rs. 2 Crores)
  - Rule 5: Jurisdiction of National Commission (exceeding Rs. 2 Crores)
- **Actual Count:** Exactly **5 chunks** (`CP_JURISDICTION_RULES_2021_RULE_1` through `RULE_5`).
- **Discrepancy Source:** In the Phase 3C narrative summary, this entire document was accidentally omitted from the bulleted list in the text, even though all 5 chunks were correctly loaded and indexed in ChromaDB.

### F. Mediation Rules: Presence in Narrative vs Source Catalogue
- **Investigation:** The Phase 3C narrative report listed `"Mediation Rules 2020: 4 rule chunks"`.
- **Catalogue Verification:** `source_catalog.json` contains NO entry for "Mediation Rules 2020".
- **Source Data Verification:** `data/legal_sources/legal_chunks.json` contains NO chunks for "Mediation Rules 2020".
- **Legal Provenance:** Mediation in Indian consumer dispute resolution is established by **Chapter V of the Consumer Protection Act, 2019** (Sections 74–81) and Section 2(25). The Central Government published Consumer Protection (Mediation) Rules, 2020 separately in Gazette Notification G.S.R. 450(E), but that specific notification was not in the 7 primary statutory PDFs downloaded during Phase 3A.
- **Discrepancy Source:** The phrase `"Mediation Rules 2020: 4 rule chunks"` was entirely hallucinated in the narrative report to reconcile the math. No unauthorized mediation chunks were ever present in `legal_chunks.json` or ChromaDB.

---

## 3. Comprehensive Inventory: Source JSON vs ChromaDB (Pre-Migration)

| Document ID | Official Title | Document Type | Provision Types | Applicability Status | Canonical JSON Chunks | ChromaDB Records | Discrepancy |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| `CPA_2019` | The Consumer Protection Act, 2019 | `CENTRAL_ACT` | SECTION (107), DEFINITION_CLAUSE (47) | `CURRENTLY_IN_FORCE` | 154 | 154 | 0 (Exact Match) |
| `CP_GENERAL_RULES_2020` | Consumer Protection (General) Rules, 2020 | `RULES` | RULE (5) | `CURRENTLY_IN_FORCE` | 5 | 5 | 0 (Exact Match) |
| `CP_CDRC_RULES_2020` | Consumer Protection (CDRC) Rules, 2020 | `RULES` | RULE (17) | `CURRENTLY_IN_FORCE` | 17 | 17 | 0 (Exact Match) |
| `CP_ECOMMERCE_RULES_2020` | Consumer Protection (E-Commerce) Rules, 2020 | `RULES` | RULE (8) | `CURRENTLY_IN_FORCE` | 8 | 8 | 0 (Exact Match) |
| `CP_ECOMMERCE_CORRIGENDUM_2020` | Corrigendum to E-Commerce Rules (G.S.R. 468(E)) | `CORRIGENDUM` | CORRIGENDUM_ITEM (1) | `CURRENTLY_IN_FORCE` | 1 | 1 | 0 (Exact Match) |
| `CP_ECOMMERCE_AMENDMENT_2021` | E-Commerce Amendment Rules, 2021 (G.S.R. 328(E)) | `AMENDMENT_RULES` | AMENDMENT_ITEM (1) | `CURRENTLY_IN_FORCE` | 1 | 1 | 0 (Exact Match) |
| `CP_JURISDICTION_RULES_2021` | Jurisdiction of Commissions Rules, 2021 (G.S.R. 912(E)) | `RULES` | RULE (5) | `CURRENTLY_IN_FORCE` | 5 | 5 | 0 (Exact Match) |
| `EJAGRITI_FILING_GUIDE` | e-Jagriti Online Complaint Filing User Manual | `PROCEDURAL_GUIDE` | PROCEDURAL_GUIDANCE (13) | `CURRENTLY_IN_FORCE` | 13 | 13 | 0 (Exact Match) |
| `CP_ECOMMERCE_AMENDMENT_2026` | E-Commerce Amendment Rules, 2026 (G.S.R. 789(E)) | `AMENDMENT_RULES` | AMENDMENT_ITEM (2) | `FUTURE_EFFECTIVE` | 2 | 2 | 0 (Exact Match) |
| **TOTAL** | — | — | — | — | **206** | **206** | **0 (Perfect Match)** |

### Reconciliation Metrics:
- **A. Chunks in Source JSON (`legal_chunks.json`):** 206
- **B. Records in ChromaDB:** 206 (204 Current Law + 2 Future Law)
- **C. Unique Chunk IDs:** 206
- **D. Missing Chunk IDs in ChromaDB:** 0
- **E. Duplicate Chunk IDs:** 0
- **F. Unexpected Records in ChromaDB:** 0
- **G. Per-Document Chunk Matching:** 100% agreement across all 9 active instruments.

---

## 4. Redundancy & Granularity Analysis: Section 2 vs Definition Clauses

### The Redundancy Question:
In `legal_chunks.json`, Section 2 of CPA 2019 was extracted both as a monolithic section chunk (`CPA_2019_SECTION_2`, containing 24,526 characters and 5,785 tokens with prefix) and as 47 individual definition-clause chunks (`CPA_2019_SECTION_2_CLAUSE_1` to `CPA_2019_SECTION_2_CLAUSE_47`).

### Legal & Technical Analysis:
1. **Precision of Retrieval:** When a user queries a legal concept (e.g., *"What is an unfair contract?"* or *"Who qualifies as a consumer?"*), retrieving the specific definition clause (`CPA_2019_SECTION_2_CLAUSE_46` or `CLAUSE_7`) provides pinpoint relevance without polluting the LLM context with dozens of irrelevant definitions.
2. **Coverage of Section 2:** The monolithic `CPA_2019_SECTION_2` includes the introductory statutory formula:
   > *"2. In this Act, unless the context otherwise requires,—"*
   and then repeats all 47 definitions.
3. **Derived Embedding Record Architecture:**
   - For complete backward compatibility, traceability, and adherence to the Phase 3C.1 specification, `CPA_2019_SECTION_2` is segmented at legal boundaries into independently searchable child segments (`CPA_2019_SECTION_2_PART_001` through `CPA_2019_SECTION_2_PART_013`), with each segment guaranteed to fit within 512 tokens.
   - The individual definition clauses (`CPA_2019_SECTION_2_CLAUSE_1` to `46`) remain individual high-precision records. Clause 47 (*"unfair trade practice"*), which is 1,640 tokens, is independently segmented at statutory sub-clause boundaries into 4 child records (`CPA_2019_SECTION_2_CLAUSE_47_PART_001` through `PART_004`).
   - In Phase 4, the hybrid retriever can prioritize direct definition clauses for defined terms while utilizing parent section segments for broad structural inquiries.

---

## 5. Architectural Separation of Vector Collections

Under Phase 3C.1, ChromaDB is reorganized into **three strictly segregated collections**:

1. **`nyaya_saathi_current_law`**:
   - Contains strictly statutory instruments (`document_type`: `ACT`, `CENTRAL_ACT`, `RULES`, `CORRIGENDUM`, `AMENDMENT_RULES`) with `applicability_status: "CURRENTLY_IN_FORCE"`.
   - Procedural user manuals and guides are strictly excluded.
2. **`nyaya_saathi_procedural_guidance`**:
   - Contains official procedural manuals (`document_type`: `PROCEDURAL_GUIDE`, `PROCEDURAL_GUIDANCE`), such as the e-Jagriti user manual.
   - Procedural workflows cannot be confused with or cited as statutory law.
3. **`nyaya_saathi_future_law`**:
   - Contains prospective statutory enactments (`applicability_status: "FUTURE_EFFECTIVE"`), specifically the Consumer Protection (E-Commerce) (Amendment) Rules, 2026.
   - Strictly isolated to prevent premature citation as current law prior to 1 January 2027.

---

## 6. Post-Segmentation Inventory & Resolution of the 12-Record Discrepancy

### A. The 12-Record Reporting Inconsistency Explained
In the Phase 3C.1 narrative completion report, the total count for `nyaya_saathi_current_law` was correctly stated as **232 records**. However, the accompanying prose breakdown listed:
- CPA 2019: 196
- General Rules: 6
- CDRC Rules: 21
- E-Commerce Rules: 12
- Corrigendum: 2
- 2021 Amendment: 2
- Jurisdiction Rules: 5
*(Sum: 244 records, creating an apparent 12-record discrepancy against 232).*

**Forensic Audit Result:**
The physical ChromaDB database and the `data/legal_sources/embedding_records.json` dataset were **never** corrupted or miscalculated. The actual counts directly extracted from disk are:

| Document ID | Canonical Chunks | Non-Child Records | Overlength Parents | Generated Child Segments | Total Derived Records | Actual ChromaDB Records | Prose Error in 3C.1 Report |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `CPA_2019` | 154 | 144 | 10 | 36 | **180** | **180** | +16 (Reported 196 instead of 180) |
| `CP_CDRC_RULES_2020` | 17 | 11 | 6 | 13 | **24** | **24** | -3 (Reported 21 instead of 24) |
| `CP_ECOMMERCE_RULES_2020` | 8 | 3 | 5 | 10 | **13** | **13** | -1 (Reported 12 instead of 13) |
| `CP_GENERAL_RULES_2020` | 5 | 4 | 1 | 2 | **6** | **6** | 0 (Accurate) |
| `CP_ECOMMERCE_AMENDMENT_2021`| 1 | 0 | 1 | 2 | **2** | **2** | 0 (Accurate) |
| `CP_ECOMMERCE_CORRIGENDUM_2020`| 1 | 0 | 1 | 2 | **2** | **2** | 0 (Accurate) |
| `CP_JURISDICTION_RULES_2021` | 5 | 5 | 0 | 0 | **5** | **5** | 0 (Accurate) |
| **CURRENT LAW SUB-TOTAL** | **191** | **167** | **24** | **65** | **232** | **232** | **Net Prose Error: +12** |
| `EJAGRITI_FILING_GUIDE` (Procedural)| 13 | 13 | 0 | 0 | **13** | **13** | 0 (Accurate) |
| `CP_ECOMMERCE_AMENDMENT_2026` (Future)| 2 | 1 | 1 | 5 | **6** | **6** | 0 (Accurate) |
| **TOTAL (ALL COLLECTIONS)** | **206** | **181** | **25** | **70** | **251** | **251** | — |

**Discrepancy Formula:** $16 - 3 - 1 = 12$ records. The physical collections strictly contain **232**, **13**, and **6** records.

### B. Parent-to-Child Mapping in CPA 2019
In `CPA_2019`, exactly **10 parent chunks** exceeded the 512-token limit and were split into **36 child segments**:
1. `CPA_2019_SECTION_2` (Definitions): Split into 13 child segments (`PART_001` to `PART_013`).
2. `CPA_2019_SECTION_2_CLAUSE_47` (Unfair Trade Practice): Split into 4 child segments (`PART_001` to `PART_004`).
3. `CPA_2019_SECTION_18` (CCPA Powers): Split into 2 child segments (`PART_001` to `PART_002`).
4. `CPA_2019_SECTION_21` (CCPA Enforcement): Split into 2 child segments (`PART_001` to `PART_002`).
5. `CPA_2019_SECTION_38` (District Commission Procedure): Split into 4 child segments (`PART_001` to `PART_004`).
6. `CPA_2019_SECTION_39` (District Commission Findings): Split into 2 child segments (`PART_001` to `PART_002`).
7. `CPA_2019_SECTION_47` (State Commission Jurisdiction): Split into 2 child segments (`PART_001` to `PART_002`).
8. `CPA_2019_SECTION_65` (Service of Notice): Split into 2 child segments (`PART_001` to `PART_002`).
9. `CPA_2019_SECTION_101` (Central Govt Rule-Making): Split into 3 child segments (`PART_001` to `PART_003`).
10. `CPA_2019_SECTION_102` (State Govt Rule-Making): Split into 2 child segments (`PART_001` to `PART_002`).

The remaining **144 canonical chunks** in CPA 2019 were within 512 tokens and were indexed directly without splitting:
$144 + 36 = \mathbf{180 \text{ records}}$. All 154 canonical parent chunks are 100% accounted for, with zero discarded statutory text.

---
*End of Vector Index Audit Report.*
