# Nyaya Saathi — Official Legal Sources Registry & Provenance Report

> **Authoritative Specification:** Nyaya Saathi Project Blueprint & Beginner Build Guide  
> **Status:** Phase 3B.1 Audited & Updated (6 November 2026)  
> **Repository Path:** `c:\Users\91995\Desktop\kuku\project\NyayaSaathi\data\legal_sources\`

---

## 1. Executive Summary & Verification State

This document serves as the provenance registry and physical file inventory for **NYAYA SAATHI: AI Consumer Dispute Assistant for India**.

In strict accordance with legal verification standards and the project blueprint, every statute, statutory rule, corrigendum, amendment, procedural guide, and historical reference must be verified against official Government of India repositories (Department of Consumer Affairs, India Code, e-Gazette, National Consumer Helpline, and e-Jagriti).

### Status Overview:
- **Statutory Instruments (Acts, Rules, Corrigenda, Amendments):** **7 official PDFs directly downloaded and verified** (covering 8 distinct catalogued legal instruments: `CPA_2019`, `CP_GENERAL_RULES_2020`, `CP_CDRC_RULES_2020`, `CP_ECOMMERCE_RULES_2020`, `CP_ECOMMERCE_CORRIGENDUM_2020`, `CP_ECOMMERCE_AMENDMENT_2021`, `CP_JURISDICTION_RULES_2021`, `CP_ECOMMERCE_AMENDMENT_2026`).
- **Procedural Guides:**
  - `EJAGRITI_FILING_GUIDE`: Verified on disk as `eJagriti_User_Manual_Consumer_Filing.pdf` (published March 2025 by NIC/MeitY, 13 pages).
  - `NCH_GRIEVANCE_GUIDE`: Documented as web-only procedural resource (`download_status: "MANUAL_DOWNLOAD_REQUIRED"`, `original_filename: null`, `retrieval_eligible: false`).
- **Historical Educational Reference:** `CONSUMER_HANDBOOK_2015` verified on disk as `CONSUMER_HANDBOOK_2015.pdf` (published 2015 by DoCA / IIPA, 78 pages). Segregated into `historical_reference_chunks.json` (`retrieval_eligible: false`, `applicability_status: "HISTORICAL_REFERENCE"`).
- **Combined Documents Handled:** `CP_GENERAL_RULES_2020` and `CP_CDRC_RULES_2020` share a single official combined Gazette PDF published by DoCA (`Consumer_Commission_Rules_and_General_Rules_2020.pdf`), preserving physical file integrity without fabrication.
- **Metadata Corrections Applied:** `CP_ECOMMERCE_AMENDMENT_2021` gazette reference corrected from `G.S.R. 333(E)` to **`G.S.R. 328(E)`** as published on 17 May 2021.
- **Unverified Dates Removed:** Invented dates for NCH and e-Jagriti guides have been set to `null` (e-Jagriti recorded as `publication_month: "2025-03"`).
- **Temporal Enforcement:** `CP_ECOMMERCE_AMENDMENT_2026` is confirmed as **`FUTURE_EFFECTIVE`** (notified 9 Sept 2026, commencing **1 Jan 2027**).

---

## 2. Inventory of Catalogued Documents & Physical File Status

| Document ID | Official Title | Local Filename | Exists on Disk? | SHA-256 Hash Status | Publication Date | Effective Date | Applicability Status | Download & Verification Status |
|:---|:---|:---|:---:|:---|:---:|:---:|:---:|:---:|
| `CPA_2019` | The Consumer Protection Act, 2019 | `A2019-35_Consumer_Protection_Act_2019.pdf` | **YES** | `0ae7f82ab5b7...` (Verified) | 2019-08-09 | 2020-07-20 | `CURRENTLY_IN_FORCE` | `OFFICIAL_SOURCE_CONFIRMED` |
| `CP_GENERAL_RULES_2020` | Consumer Protection (General) Rules, 2020 | `Consumer_Commission_Rules_and_General_Rules_2020.pdf` | **YES** (Shared) | `65b360f6a62b...` (Verified) | 2020-07-15 | 2020-07-20 | `CURRENTLY_IN_FORCE` | `OFFICIAL_SOURCE_CONFIRMED` |
| `CP_CDRC_RULES_2020` | Consumer Protection (CDRC) Rules, 2020 | `Consumer_Commission_Rules_and_General_Rules_2020.pdf` | **YES** (Shared) | `65b360f6a62b...` (Verified) | 2020-07-15 | 2020-07-20 | `CURRENTLY_IN_FORCE` | `OFFICIAL_SOURCE_CONFIRMED` |
| `CP_ECOMMERCE_RULES_2020` | Consumer Protection (E-Commerce) Rules, 2020 | `CP_Ecommerce_Rules_2020_GSR_462_E.pdf` | **YES** | `3012b37f6f6d...` (Verified) | 2020-07-23 | 2020-07-23 | `CURRENTLY_IN_FORCE` | `OFFICIAL_SOURCE_CONFIRMED` |
| `CP_ECOMMERCE_CORRIGENDUM_2020` | Corrigendum to E-Commerce Rules, 2020 | `CP_Ecommerce_Corrigendum_2020_GSR_468_E.pdf` | **YES** | `47f56d66c0df...` (Verified) | 2020-07-27 | 2020-07-27 | `CURRENTLY_IN_FORCE` | `OFFICIAL_SOURCE_CONFIRMED` |
| `CP_ECOMMERCE_AMENDMENT_2021` | CP (E-Commerce) (Amendment) Rules, 2021 | `CP_Ecommerce_Amendment_Rules_2021_GSR_328_E.pdf` | **YES** | `a7db1f7a8c90...` (Verified) | 2021-05-17 | 2021-05-17 | `CURRENTLY_IN_FORCE` | `OFFICIAL_SOURCE_CONFIRMED` |
| `CP_JURISDICTION_RULES_2021` | CP (Jurisdiction of Commissions) Rules, 2021 | `CP_Jurisdiction_Rules_2021_GSR_912_E.pdf` | **YES** | `dd22dbfa7ac8...` (Verified) | 2021-12-30 | 2021-12-30 | `CURRENTLY_IN_FORCE` | `OFFICIAL_SOURCE_CONFIRMED` |
| `CP_ECOMMERCE_AMENDMENT_2026` | CP (E-Commerce) (Amendment) Rules, 2026 | `CP_Ecommerce_Amendment_Rules_2026_GSR_789_E.pdf` | **YES** | `78b0b8de1b6c...` (Verified) | 2026-09-09 | **2027-01-01** | `FUTURE_EFFECTIVE` | `OFFICIAL_SOURCE_CONFIRMED` |
| `EJAGRITI_FILING_GUIDE` | e-Jagriti Online Complaint Filing Manual | `eJagriti_User_Manual_Consumer_Filing.pdf` | **YES** | `9e666f13c725...` (Verified) | `null` (2025-03) | `null` | `CURRENTLY_IN_FORCE` | `OFFICIAL_SOURCE_CONFIRMED` |
| `CONSUMER_HANDBOOK_2015` | Consumer Handbook (2015) | `CONSUMER_HANDBOOK_2015.pdf` | **YES** | `329bcae8d6ff...` (Verified) | `null` (2015) | `null` | `HISTORICAL_REFERENCE` | `OFFICIAL_SOURCE_CONFIRMED` |
| `NCH_GRIEVANCE_GUIDE` | National Consumer Helpline FAQs | `None` (Web-only) | **NO** | `null` | `null` | `null` | `CURRENTLY_IN_FORCE` | `MANUAL_DOWNLOAD_REQUIRED` |

---

## 3. Metadata Corrections Applied

### A. Correction of the 2021 E-Commerce Amendment Notification
- **Previous Value:** `G.S.R. 333(E)`
- **Audited Official Gazette Notification:** **`G.S.R. 328(E)`**
- **Authority Proof:**
  - Published in Gazette of India, Extraordinary, Part II, Section 3, Sub-section (i), Gazette Issue No. 262.
  - Notification dated: New Delhi, the 17th May, 2021.
  - Rule 1(2): *"They shall come into force on the date of their publication in the Official Gazette."* (2021-05-17).
  - Scope: Amends Rule 4(1) of the Principal Rules (G.S.R. 462(E)) requiring e-commerce entities to appoint a resident nodal contact person.
- **Source URL:** `https://consumeraffairs.gov.in/public/upload/files/Consumer%20Protection%20(E-Commerce)%20(Amendment)%20Rules,%202021_1732704241.pdf`

### B. Procedural Guidance Metadata & Removal of Unverified Dates
- **e-Jagriti (`EJAGRITI_FILING_GUIDE`):** Cover verified as NIC / MeitY, March 2025 (`publication_month: "2025-03"`, `publication_date: null`—no invented day).
- **NCH Portal (`NCH_GRIEVANCE_GUIDE`):** Kept as web-only procedural resource (`download_status: "MANUAL_DOWNLOAD_REQUIRED"`, `original_filename: null`, `retrieval_eligible: false`).
- **Correction:** In accordance with the rule *"Never invent dates to fill empty fields"*, unverified day fields are strictly set to `null`.

### C. Reclassification of the 2015 Consumer Handbook
- **Document Identity:** `CONSUMER_HANDBOOK_2015`
- **Document Type:** `HISTORICAL_EDUCATIONAL_REFERENCE`
- **Applicability Status:** `HISTORICAL_REFERENCE`
- **Retrieval Role:** Segregated into `data/legal_sources/historical_reference_chunks.json` (`retrieval_eligible: false`).

---

## 4. Combined-Document Architecture (General Rules & CDRC Rules)

On the official Department of Consumer Affairs portal, the *Consumer Protection (General) Rules, 2020* and *Consumer Protection (Consumer Disputes Redressal Commissions) Rules, 2020* are published as **one single combined PDF** (`Consumer Commission Rules & General Rules_1732703661.pdf`):
- **Physical File on Disk:** `data/legal_sources/originals/Consumer_Commission_Rules_and_General_Rules_2020.pdf` (18 pages, SHA-256: `65b360f6a62bb219ad35742adc48ee669ecda1dd3e28de7cd05f309f9f6f39da`).
- **Catalogue Handling:**
  - Separate logical entries are maintained: `CP_GENERAL_RULES_2020` and `CP_CDRC_RULES_2020`.
  - Both records declare `is_combined_document: true` and reference `shared_original_filename: "Consumer_Commission_Rules_and_General_Rules_2020.pdf"`.
- **Extraction Boundary Mapping:**
  - `CP_CDRC_RULES_2020` (G.S.R. 448(E) / 459(E)): English text **Pages 9 to 16**.
  - `CP_GENERAL_RULES_2020` (G.S.R. 449(E) / 458(E)): English text **Pages 17 to 18**.

---

## 5. Strict Temporal Rules: The 2026 E-Commerce Amendment Rules

- **Gazette Identification:** G.S.R. 789(E) (Gazette Electronic ID: `CG-DL-E-10092026-276125`).
- **Gazette Publication Date:** 9 September 2026.
- **Rule 1(2) Commencement Provision:**
  > *"They shall come into force with effect from 1st January, 2027."*
- **Operational Status:** **`FUTURE_EFFECTIVE`** as of 6 November 2026.
- **Enforcement Rule:** The application must not treat the new provisions as currently binding law for any consumer disputes or legal advice during calendar year 2026.

---

## 6. Pecuniary Jurisdiction Reference Rules

Under `CP_JURISDICTION_RULES_2021` (G.S.R. 912(E) dated 30 December 2021, verified on disk):
- **District Commission:** Value of goods/services paid does not exceed **₹50 Lakhs**.
- **State Commission:** Value of goods/services paid exceeds **₹50 Lakhs but does not exceed ₹2 Crores**.
- **National Commission (NCDRC):** Value of goods/services paid exceeds **₹2 Crores**.

---

## 7. SHA-256 Cryptographic Hash Registry & Authenticity Notice

> **Authenticity & Integrity Distinction:**  
> The issuing government authorities (Department of Consumer Affairs, India Code, e-Gazette, e-Jagriti) do **not** publish SHA-256 cryptographic hashes on their web portals.  
> - **Source Provenance:** Established by direct acquisition from verified official government web portals (`consumeraffairs.gov.in`, `indiacode.nic.in`, `egazette.gov.in`, `e-jagriti.gov.in`).  
> - **Local Integrity Checksums:** The SHA-256 hashes listed below were calculated locally upon file acquisition. They serve as cryptographic baselines to detect corruption, unauthorized edits, or local tampering. They are **not** official portal-published checksums.

```text
0ae7f82ab5b77d50087cd4cd2dd2dbc12755c0bdb31371fdefd042b020d50756  A2019-35_Consumer_Protection_Act_2019.pdf
65b360f6a62bb219ad35742adc48ee669ecda1dd3e28de7cd05f309f9f6f39da  Consumer_Commission_Rules_and_General_Rules_2020.pdf
329bcae8d6fff1ac6322fb124dcf1e51ebd25a6b85371f07e0f246ad98cc6480  CONSUMER_HANDBOOK_2015.pdf
a7db1f7a8c900e0bc9c7fcb1f2921130ff85e6fac517fb5222efcf76cf559654  CP_Ecommerce_Amendment_Rules_2021_GSR_328_E.pdf
78b0b8de1b6c0e9c8b9c639e4b2bc17ec65abcb807b34690529129e2a3014ab3  CP_Ecommerce_Amendment_Rules_2026_GSR_789_E.pdf
47f56d66c0df51a58694acb8b2833714bd65a85bd781161535708dfa59fb2086  CP_Ecommerce_Corrigendum_2020_GSR_468_E.pdf
3012b37f6f6dba2d29523abf10f43fbb3a503768e578ef0fa02e4b9e4593bd0c  CP_Ecommerce_Rules_2020_GSR_462_E.pdf
dd22dbfa7ac8bc0ef968765d6cd521ad7a29742afb071b9a919c164f83b765b7  CP_Jurisdiction_Rules_2021_GSR_912_E.pdf
9e666f13c725cf9a9f2ce17b1807d9b0ca5c4b4d66219b2659e924a0d8c0fa37  eJagriti_User_Manual_Consumer_Filing.pdf
```

---

## 8. Missing Source Register & Blueprint Coverage

Using the authoritative source status taxonomy:
- `PRESENT_AND_EXTRACTED`
- `PRESENT_NOT_EXTRACTED`
- `WEB_ONLY`
- `NOT_ACQUIRED`
- `REQUIRES_SOURCE_VERIFICATION`
- `NOT_REQUIRED_FOR_CURRENT_MVP`

| Source Item | Formal Legal Instrument | Status | Acquisition / Coverage Notes |
|:---|:---|:---:|:---|
| 1. CPA 2019 | The Consumer Protection Act, 2019 (Act 35 of 2019) | `PRESENT_AND_EXTRACTED` | 154 canonical chunks; full statutory coverage. |
| 2. General Rules 2020 | Consumer Protection (General) Rules, 2020 | `PRESENT_AND_EXTRACTED` | 5 canonical chunks; shared combined PDF. |
| 3. CDRC Rules 2020 | Consumer Protection (CDRC) Rules, 2020 | `PRESENT_AND_EXTRACTED` | 17 canonical chunks; shared combined PDF. |
| 4. E-Commerce Rules 2020 | Consumer Protection (E-Commerce) Rules, 2020 | `PRESENT_AND_EXTRACTED` | 8 canonical chunks; principal marketplace rules. |
| 5. Corrigendum 2020 | Corrigendum to E-Commerce Rules [F. No. J-24/42/2020-CPU] | `PRESENT_AND_EXTRACTED` | 1 canonical chunk; rectifies typographical errors. |
| 6. 2021 Amendment | CP (E-Commerce) (Amendment) Rules, 2021 [G.S.R. 328(E)] | `PRESENT_AND_EXTRACTED` | 1 canonical chunk; resident nodal officer requirement. |
| 7. 2021 Jurisdiction Rules | CP (Jurisdiction of Commissions) Rules, 2021 [G.S.R. 912(E)] | `PRESENT_AND_EXTRACTED` | 5 canonical chunks; pecuniary limits updated. |
| 8. 2026 Amendment | CP (E-Commerce) (Amendment) Rules, 2026 [G.S.R. 789(E)] | `PRESENT_AND_EXTRACTED` | 2 canonical chunks (6 vectors); date-gated (effective 2027-01-01). |
| 9. e-Jagriti Guide | e-Jagriti CC Online Filing User Manual (March 2025) | `PRESENT_AND_EXTRACTED` | 13 procedural chunks; isolated procedural collection. |
| 10. Consumer Handbook 2015 | Consumer Handbook (2015, DoCA/IIPA) | `PRESENT_AND_EXTRACTED` | 74 historical chunks; excluded from retrieval (`retrieval_eligible: false`). |
| 11. NCH Grievance Guidance | National Consumer Helpline Portal Resources | `WEB_ONLY` | Pre-litigation portal reference (`consumerhelpline.gov.in`); no local PDF. |
| 12. NCDRC Regulations 2020 | Consumer Protection (CDRC) Regulations, 2020 | `NOT_ACQUIRED` | Under acquisition review; not yet ingested. |
| 13. Supreme Court e-SCR | Supreme Court Case Law Decisions on Consumer Disputes | `NOT_REQUIRED_FOR_CURRENT_MVP` | Blueprint § 18: "Case-law retrieval is outside the minimum scope." |

