# Nyaya Saathi — Text Extraction & Legal Chunking Report

> **Phase:** Blueprint Phase 3B & Phase 3B.1 (Legal Source Classification, PDF Text Extraction & Legal-Aware Chunk Quality Correction)  
> **Extraction Engine:** PyMuPDF (`fitz`) v2.1  
> **Report Date:** 6 November 2026  
> **Status:** **SUCCESSFUL (10 Physical Extractions, 1 Web-Only Resource, 206 Primary Chunks, 74 Historical Chunks)**

---

## 1. Executive Summary

This report documents the text extraction, legal classification, and quality correction of all authoritative legal and procedural documents in **NYAYA SAATHI: AI Consumer Dispute Assistant for India**.

In strict adherence to the project blueprint and Phase 3B.1 specifications:
1. **PyMuPDF (`fitz`)** was utilized to perform non-destructive, read-only text extraction page-by-page.
2. **Physical PDF page numbers** are strictly preserved across all extractions and chunks (1-based physical page tracking).
3. **Consumer Handbook 2015 Reclassified**: The 78-page PDF published in 2015 by DoCA and the Indian Institute of Public Administration (IIPA) has been reclassified as `CONSUMER_HANDBOOK_2015` (`document_type: "HISTORICAL_EDUCATIONAL_REFERENCE"`). Its 74 chunks have been completely excluded from the primary legal retrieval dataset and safely segregated into `data/legal_sources/historical_reference_chunks.json`.
4. **National Consumer Helpline (NCH) Source Record Corrected**: `NCH_GRIEVANCE_GUIDE` remains unacquired as a local PDF (`download_status: "MANUAL_DOWNLOAD_REQUIRED"`, `original_filename: null`, `retrieval_eligible: false`), functioning as a web-only procedural reference to `https://consumerhelpline.gov.in/`.
5. **e-Jagriti Filing Guide Grounding**: Verified against the physical manual published by NIC / MeitY in March 2025 (`publication_month: "2025-03"`, `publication_date: null`—no fabricated day). Generates 13 procedural steps in the primary retrieval dataset.
6. **Fine-Grained Verification Statuses**: Programmatic extraction integrity is strictly decoupled from substantive legal review. All chunks carry:
   - `extraction_status: "SUCCESS"`
   - `extraction_integrity_status: "CHECKED"`
   - `legal_review_status: "REQUIRES_LEGAL_REVIEW"`
7. **Combined Document Boundaries Verified**: `CP_CDRC_RULES_2020` (English pages 9–16) and `CP_GENERAL_RULES_2020` (English pages 17–18) are extracted cleanly from the shared Gazette issue without text bleeding or duplication.
8. **Temporal Isolation Preserved**: The 2026 E-Commerce Amendment chunks (`FUTURE_EFFECTIVE`, commencing 1 Jan 2027) are isolated from current rules.

---

## 2. Document Extraction & Chunking Inventory

| Document ID | Document Type | Original Filename | Extracted Pages | Empty Pages | Quality Status | Applicability Status | Retrieval Eligible | Chunks Generated | Dataset File |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| `CPA_2019` | `ACT` | `A2019-35_Consumer_Protection_Act_2019.pdf` | 40 / 40 | 0 | `HIGH_QUALITY_TEXT` | `CURRENTLY_IN_FORCE` | **Yes** | **154** (107 Secs + 47 Defs) | `legal_chunks.json` |
| `CP_GENERAL_RULES_2020` | `RULES` | `Consumer_Commission_Rules_and_General_Rules_2020.pdf` | 2 (pp 17–18) | 0 | `HIGH_QUALITY_TEXT` | `CURRENTLY_IN_FORCE` | **Yes** | **5** (Rules 1–5) | `legal_chunks.json` |
| `CP_CDRC_RULES_2020` | `RULES` | `Consumer_Commission_Rules_and_General_Rules_2020.pdf` | 8 (pp 9–16) | 0 | `HIGH_QUALITY_TEXT` | `CURRENTLY_IN_FORCE` | **Yes** | **17** (Rules 1–17) | `legal_chunks.json` |
| `CP_ECOMMERCE_RULES_2020` | `RULES` | `CP_Ecommerce_Rules_2020_GSR_462_E.pdf` | 11 / 11 | 0 | `HIGH_QUALITY_TEXT` | `CURRENTLY_IN_FORCE` | **Yes** | **8** (Rules 1–8) | `legal_chunks.json` |
| `CP_ECOMMERCE_CORRIGENDUM_2020` | `CORRIGENDUM` | `CP_Ecommerce_Corrigendum_2020_GSR_468_E.pdf` | 1 / 1 | 0 | `HIGH_QUALITY_TEXT` | `CURRENTLY_IN_FORCE` | **Yes** | **1** (G.S.R. 488(E)) | `legal_chunks.json` |
| `CP_ECOMMERCE_AMENDMENT_2021` | `AMENDMENT_RULES` | `CP_Ecommerce_Amendment_Rules_2021_GSR_328_E.pdf` | 2 / 2 | 0 | `HIGH_QUALITY_TEXT` | `CURRENTLY_IN_FORCE` | **Yes** | **1** (G.S.R. 328(E)) | `legal_chunks.json` |
| `CP_JURISDICTION_RULES_2021` | `RULES` | `CP_Jurisdiction_Rules_2021_GSR_912_E.pdf` | 2 / 2 | 0 | `HIGH_QUALITY_TEXT` | `CURRENTLY_IN_FORCE` | **Yes** | **5** (Rules 1–5) | `legal_chunks.json` |
| `CP_ECOMMERCE_AMENDMENT_2026` | `AMENDMENT_RULES` | `CP_Ecommerce_Amendment_Rules_2026_GSR_789_E.pdf` | 7 / 7 | 0 | `HIGH_QUALITY_TEXT` | `FUTURE_EFFECTIVE` | **Yes** | **2** (G.S.R. 789(E)) | `legal_chunks.json` |
| `EJAGRITI_FILING_GUIDE` | `PROCEDURAL_GUIDE` | `eJagriti_User_Manual_Consumer_Filing.pdf` | 13 / 13 | 0 | `HIGH_QUALITY_TEXT` | `CURRENTLY_IN_FORCE` | **Yes** | **13** (e-Filing Steps) | `legal_chunks.json` |
| `CONSUMER_HANDBOOK_2015` | `HISTORICAL_EDUCATIONAL_REFERENCE` | `CONSUMER_HANDBOOK_2015.pdf` | 78 / 78 | 3 | `HIGH_QUALITY_TEXT` | `HISTORICAL_REFERENCE` | **No** | **74** (Historical Chunks) | `historical_reference_chunks.json` |
| `NCH_GRIEVANCE_GUIDE` | `PROCEDURAL_GUIDE` | `None` (Web-only) | — | — | `WEB_SOURCE_ONLY` | `CURRENTLY_IN_FORCE` | **No** | **0** (Web resource) | N/A |
| **TOTALS** | **11 Catalogue Entries** | **9 Physical Files** | **164 Pages** | **3** | — | — | — | **206 Primary / 74 Historical** | **2 Datasets** |

---

## 3. Knowledge Base Classification & Quality Metrics

### A. Document Counts
- **Physical PDF Files on Disk:** **9 files** (22.28 MB total).
- **Logical Document Catalogue Entries:** **11 entries** (8 statutory instruments, 1 procedural guide on disk, 1 web-only procedural resource, 1 historical educational reference).

### B. Primary Retrieval Dataset (`data/legal_sources/legal_chunks.json`)
- **Total Primary Chunks:** **206**
- **Statutory Sections (`SECTION`):** 107 chunks (all 107 sections of CPA 2019).
- **Definition Clauses (`DEFINITION_CLAUSE`):** 47 chunks (all individual definition clauses linked to parent Section 2 of CPA 2019).
- **Statutory Rules (`RULE`):** 35 chunks (General Rules: 5, CDRC Rules: 17, E-Commerce Rules: 8, Jurisdiction Rules: 5).
- **Amendment Items (`AMENDMENT_ITEM`):** 3 chunks (2021 Amendment: 1 chunk; 2026 Amendment: 2 chunks).
- **Corrigendum Items (`CORRIGENDUM_ITEM`):** 1 chunk (2020 E-Commerce Corrigendum).
- **Procedural Guidance (`PROCEDURAL_GUIDANCE`):** 13 chunks (e-Jagriti User Manual, step-by-step consumer complaint filing guide; zero invented section numbers).
- **Primary Retrieval Eligibility:** **100% (206 of 206 marked `retrieval_eligible: true`)**.
- **Temporal Status:** 204 chunks `CURRENTLY_IN_FORCE`, 2 chunks `FUTURE_EFFECTIVE`.

### C. Historical Reference Dataset (`data/legal_sources/historical_reference_chunks.json`)
- **Total Historical Chunks:** **74**
- **Document ID:** `CONSUMER_HANDBOOK_2015`
- **Document Type:** `HISTORICAL_EDUCATIONAL_REFERENCE`
- **Applicability Status:** `HISTORICAL_REFERENCE` (0 chunks marked `CURRENTLY_IN_FORCE`).
- **Retrieval Eligibility:** `retrieval_eligible: false` (100% excluded from primary legal retrieval).
- **Purpose:** Retained strictly for historical background and consumer education context; prohibited from being cited as current law.

---

## 4. Verification Status Architecture

To prevent false confidence and comply with legal AI safety requirements, programmatic extraction checks are decoupled from substantive legal review:

```json
{
  "extraction_status": "SUCCESS",
  "extraction_integrity_status": "CHECKED",
  "legal_review_status": "REQUIRES_LEGAL_REVIEW",
  "applicability_status": "CURRENTLY_IN_FORCE"
}
```

- **Extraction Status (`extraction_status`):** `SUCCESS` (indicates PyMuPDF successfully extracted digital text without parser crash).
- **Extraction Integrity Status (`extraction_integrity_status`):** `CHECKED` (indicates automated programmatic validation passed: section/rule boundary recognized, sequential page numbers preserved, no zero-length text, parent-child links intact).
- **Legal Review Status (`legal_review_status`):** `REQUIRES_LEGAL_REVIEW` across all 280 chunks. Programmatic extraction is **never** represented as substantive legal verification by a qualified Indian advocate.
- **Applicability Status (`applicability_status`):**
  - `CURRENTLY_IN_FORCE`: For all 8 in-force statutory instruments and the active e-Jagriti filing manual (204 primary chunks).
  - `FUTURE_EFFECTIVE`: For the 2026 E-Commerce Amendment Rules (2 primary chunks, commencing 1 Jan 2027).
  - `HISTORICAL_REFERENCE`: For the 2015 Consumer Handbook (74 historical chunks).

---

## 5. Unacquired & Web-Only Resources (Action Required)

### `NCH_GRIEVANCE_GUIDE` (National Consumer Helpline FAQs)
- **Status:** `download_status: "MANUAL_DOWNLOAD_REQUIRED"`
- **Physical File:** `null` (No fabricated PDF or synthetic text created).
- **Source Portal:** `https://consumerhelpline.gov.in/`
- **Retrieval Role:** Marked `retrieval_eligible: false`. In the initial MVP, the official portal URL is maintained as a direct reference for consumers without injecting unverified offline text into the RAG pipeline.

---

## 6. Extraction Limitations

1. **Table Structure Linearization**: Procedural flow tables and multi-column fee schedules (e.g., in e-Jagriti manual and CDRC Rules) were extracted as linearized text. While complete and legible, tabulations are represented as line-delimited text blocks rather than structured relational tables.
2. **Dynamic Portal Workflows**: The e-Jagriti filing guide reflects portal UI as of March 2025. Consumer commission portal workflows are subject to administrative updates by NIC/MeitY and may evolve over time.
3. **No Optical Character Recognition (OCR) Needed**: All 9 acquired PDFs are official digital publications (not scanned bitmaps); 100% selectable text was extracted without OCR loss.
