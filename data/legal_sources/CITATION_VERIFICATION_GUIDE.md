# NYAYA SAATHI — CITATION AND CLAIM VERIFICATION GUIDE
## Blueprint Step 18: Deterministic Verification Architecture & Safeguards

---

### 1. What Citation Checking Does

In Nyaya Saathi, **Citation and Claim Verification** (`src/citation_checker.py`) acts as an independent, deterministic firewall between Gemini's generated legal explanations and the consumer. It audits every statement, legal provision, statute title, and quotation against the authoritative legal knowledge base:

1. **Source ID Provenance**: Verifies that every cited source exists in `source_catalog.json` and `legal_chunks.json` / `embedding_records.json`, and confirms that the source was **actually supplied** in the model's retrieved passages (`retrieved_sources` allowlist).
2. **Statutory Title Matching**: Confirms that the Act or Rule title matches official gazette and portal records (preventing cross-act attribution, e.g. attributing Section 35 of CPA 2019 to the E-Commerce Rules).
3. **Provision Reference Validation**: Verifies that cited section numbers, rule numbers, and subsections (e.g., Section 35, Section 2(10), Rule 4(1)) physically exist within the official text of that specific document.
4. **Verbatim Quotation Auditing**: Extracts all direct quotes and compares them character-by-character (after safe whitespace normalization) with the original statutory text.
5. **Claim-Level Support Evaluation**: Evaluates whether each substantive factual/legal assertion is supported by its attached source passage.
6. **Temporal Applicability Enforcement**: Verifies publication and commencement dates (e.g. enforcing that G.S.R. 789(E) is future-effective until 1 January 2027).

---

### 2. What Citation Checking CANNOT Prove

> [!WARNING]
> Deterministic Python validation can confirm **textual existence, citation provenance, and verbatim fidelity**. It **CANNOT** prove legal validity, advocate interpretation, or case outcomes.

Specifically, citation checking cannot:
- Prove that a particular statutory section applies to a user's unique dispute facts.
- Replace judicial interpretation, statutory construction, or case precedent.
- Determine whether an exception or proviso in another un-retrieved section overrides the cited provision.
- Verify whether an e-commerce platform's terms of service or specific contract language affects the dispute.
- Guarantee that a consumer will obtain a refund, replacement, or compensation from a Consumer Commission.

---

### 3. How Source IDs Are Checked

When an answer references a source ID (e.g. `CPA_2019_SECTION_83` or `CP_ECOMMERCE_RULES_2020_RULE_4`):
1. **Catalog Existence Check**: Does the ID exist in `legal_chunks.json`, `embedding_records.json`, `historical_reference_chunks.json`, or `source_catalog.json`?
   - If not, it is immediately flagged as `SOURCE_NOT_FOUND` (invented ID).
2. **Retrieved Allowlist Check**: Was the ID included in the specific list of passages supplied to Gemini during generation?
   - If it exists in the catalog but was **not retrieved** in the active session, it is flagged as `SOURCE_NOT_RETRIEVED`. An AI assistant is never permitted to claim support from passages it was not supplied.
3. **Document Attribution Check**: Does the chunk's parent document match the document cited in the response? If not, it is flagged as `DOCUMENT_MISMATCH`.

---

### 4. How Provision References Are Checked

Every provision reference (e.g. `Section 35`, `Section 2(10)`, `Section 39(1)`, `Rule 5`, `Rule 4(1)`) is parsed using structural regexes that isolate:
- Provision Type (`Section` vs `Rule` vs `Schedule` vs `Clause`).
- Provision Number (`35`, `83`, `4`).
- Subsection Identifier (`2(10)`, `4(1)`).

The validator validates that:
- An Act contains Sections, whereas Rules contain Rules (e.g. an answer cannot cite "Section 5 of E-Commerce Rules" when E-Commerce Rules only has Rules).
- The provision number exists in the document's known chunk index.
- Boundary checks prevent substring false positives: ordinary numbers in monetary amounts (₹35,000), percentages (100%), dates (2019, 2020), or timeframes (45 days) are never mistaken for section numbers. Section 888 is never mistaken for Section 8.

---

### 5. How Quotations Are Checked

When a generated explanation uses quotation marks (`"..."` or `“...”`):
1. **Whitespace & Punctuation Normalization**: Non-material whitespace and smart quotes are normalized.
2. **Exact Substring Comparison**: The normalized quote is checked against the original statutory text of the cited provision.
   - If an exact match is found: `VERBATIM_QUOTE_MATCH`.
3. **Similarity Diagnostic**: If exact match fails, a sequence-matcher computes similarity against the provision text:
   - High similarity ($\ge 85\%$) with altered wording: `QUOTE_MISMATCH`.
   - Moderate similarity ($50\% - 84\%$): `PARAPHRASE_NOT_VERIFIED_AS_QUOTE`.
   - **Crucial Rule**: An approximate paraphrase is **never** labeled as `VERBATIM_QUOTE_MATCH`, and the system never silently alters Gemini's text.

---

### 6. How Unsupported Claims Are Handled

When a claim:
- References a non-existent section or invented source ID;
- Contains an altered quotation; or
- Makes a sweeping statutory promise (e.g. *"Section 99 guarantees an immediate refund without filing"*) without source support:

The validator triggers **Safe Answer Handling** (`produce_safe_validated_answer`):
1. The response status is updated to `UNSUPPORTED_CLAIMS_SUPPRESSED`.
2. A prominent safety warning is prepended to `limitations_and_uncertainties`.
3. The unsupported claims and unverified citations are explicitly enumerated in limitations.
4. The raw unvalidated model output is preserved internally in `original_unvalidated_answer` for developer audit.
5. The system **never fabricates** a replacement legal opinion.

---

### 7. How Legal Review Status Is Displayed

Nyaya Saathi strictly preserves source review statuses from the official catalogue:
- `REQUIRES_LEGAL_REVIEW`: Applied to automated chunk extractions that have not undergone human legal review.
- `OFFICIALLY_VERIFIED` / `HUMAN_REVIEWED`: Reserved for passages verified by legal counsel.
- `HISTORICAL_REFERENCE` / `SUPERSEDED`: Applied to repealed laws (1986 Act) or guidance materials.

Transparent user-facing status labels:
- `SOURCE FOUND`
- `REFERENCE FOUND`
- `QUOTE MATCHED`
- `SUPPORT NOT ESTABLISHED`
- `NEEDS LEGAL REVIEW`
- `REFERENCE NOT FOUND`

> [!NOTE]
> The checker **NEVER** displays a green "Legally Verified" badge. Even when all citations exist, the answer is informational assistance and may require professional legal counsel.

---

### 8. How Future-Effective Amendments Are Handled

For the **Consumer Protection (E-Commerce) (Amendment) Rules, 2026** (G.S.R. 789(E)):
- Publication Date: **2026-09-09**
- Effective Date (Commencement): **2027-01-01**

The checker enforces 5-date gating:
1. Prior to 1 January 2027, the rules are flagged as `FUTURE_EFFECTIVE`.
2. Any answer citing G.S.R. 789(E) as currently operative before 2027-01-01 receives an explicit limitation warning.
3. If an inquiry involves a purchase before 2027-01-01 with continuing dispute events after commencement, the validator flags the matter as `NEEDS_LEGAL_REVIEW` because transitional applicability is legally unsettled.

---

### 9. Why a Valid Citation Does Not Prove Legal Interpretation

Finding that Section 83 of CPA 2019 exists and is cited accurately proves only that:
- Section 83 is a real statute.
- It was retrieved from the official gazette.
- The model quoted or summarized its wording faithfully.

It does **not** prove that the user has satisfied the legal burden of proof under Section 83 (e.g. demonstrating that a defect caused actionable harm, or proving that the seller was a 'product seller' under Section 2(37)). Statutory application requires human judgment, context, and formal legal representation.

---

### 10. How a Human Reviewer Can Inspect Failed Validations

Developers and legal reviewers can inspect validation failures via:
1. **Developer CLI Runner**:
   ```powershell
   python scripts/test_citation_checker.py --scenario all
   python scripts/test_citation_checker.py --scenario <id> --verbose
   ```
2. **Validation Report Dictionary**:
   Inspect `rep["unsupported_references"]`, `rep["unsupported_claims"]`, and `rep["warnings"]`.
3. **Audit Trail**:
   In any sanitized answer, access `safe_answer["original_unvalidated_answer"]` to see the unedited raw text generated by the model alongside `safe_answer["citation_verification_report"]`.
