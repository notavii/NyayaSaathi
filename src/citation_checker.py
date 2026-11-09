"""
Citation Verification, Source Validation, and Unsupported Claim Detection Module.

Blueprint Step 18: Citation and Claim Verification for Nyaya Saathi.

Independently validates legal citations, source IDs, Act and Rule titles,
provision references, direct quotations, and claim-level support in generated answers.
Validates deterministically against:
1. source_catalog.json (Official legal documents and gazette metadata)
2. legal_chunks.json and embedding_records.json (Canonical statutory chunks)
3. Extracted text files in data/legal_sources/extracted/
4. The retrieved_sources allowlist actually supplied to Gemini

DOES NOT use LLMs or Gemini to validate citations. All verification is deterministic Python.
"""

from datetime import date, datetime
import difflib
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("citation_checker")

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = PROJECT_ROOT / "data" / "legal_sources" / "source_catalog.json"
CHUNKS_PATH = PROJECT_ROOT / "data" / "legal_sources" / "legal_chunks.json"
HISTORICAL_CHUNKS_PATH = PROJECT_ROOT / "data" / "legal_sources" / "historical_reference_chunks.json"
EMBEDDING_RECORDS_PATH = PROJECT_ROOT / "data" / "legal_sources" / "embedding_records.json"
EXTRACTED_DIR = PROJECT_ROOT / "data" / "legal_sources" / "extracted"

# ---------------------------------------------------------------------------
# Status Constants (Blueprint Part C, D, E, F, G, H, I, J)
# ---------------------------------------------------------------------------

# Overall Report Status
STATUS_VALIDATED = "VALIDATED"
STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"
STATUS_UNSUPPORTED_CLAIMS_DETECTED = "UNSUPPORTED_CLAIMS_DETECTED"
STATUS_FAILED = "FAILED"

# Source ID & Document Retrieval Statuses
SOURCE_FOUND = "SOURCE_FOUND"
SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
SOURCE_NOT_RETRIEVED = "SOURCE_NOT_RETRIEVED"
DOCUMENT_MISMATCH = "DOCUMENT_MISMATCH"
SOURCE_METADATA_MISMATCH = "SOURCE_METADATA_MISMATCH"

# Document / Title Statuses
TITLE_MATCHED = "MATCHED"
TITLE_MISMATCH = "MISMATCH"
TITLE_NOT_SPECIFIED = "NOT_SPECIFIED"

# Provision Reference Statuses
REFERENCE_FOUND = "REFERENCE_FOUND"
REFERENCE_NOT_FOUND = "REFERENCE_NOT_FOUND"
REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
NEEDS_MANUAL_REVIEW = "NEEDS_MANUAL_REVIEW"

# Quotation Verification Statuses
VERBATIM_QUOTE_MATCH = "VERBATIM_QUOTE_MATCH"
QUOTE_MISMATCH = "QUOTE_MISMATCH"
PARAPHRASE_NOT_VERIFIED_AS_QUOTE = "PARAPHRASE_NOT_VERIFIED_AS_QUOTE"
QUOTE_NOT_APPLICABLE = "NOT_APPLICABLE"

# Claim Support Statuses
SUPPORTED_BY_PASSAGE = "SUPPORTED_BY_PASSAGE"
SUPPORT_NOT_ESTABLISHED = "SUPPORT_NOT_ESTABLISHED"
UNSUPPORTED_NO_CITATION = "UNSUPPORTED_NO_CITATION"
CLAIM_NEEDS_LEGAL_REVIEW = "NEEDS_LEGAL_REVIEW"

# Legal Review Statuses (Preserved from Catalogue)
REQUIRES_LEGAL_REVIEW = "REQUIRES_LEGAL_REVIEW"
OFFICIALLY_VERIFIED = "OFFICIALLY_VERIFIED"
HUMAN_REVIEWED = "HUMAN_REVIEWED"
NOT_REVIEWED = "NOT_REVIEWED"
SUPERSEDED = "SUPERSEDED"
HISTORICAL_REFERENCE = "HISTORICAL_REFERENCE"

# Temporal Statuses
CURRENTLY_IN_FORCE = "CURRENTLY_IN_FORCE"
FUTURE_EFFECTIVE = "FUTURE_EFFECTIVE"
TEMPORAL_NEEDS_LEGAL_REVIEW = "NEEDS_LEGAL_REVIEW"
NOT_APPLICABLE_PRE_COMMENCEMENT = "NOT_APPLICABLE_PRE_COMMENCEMENT"

# Transparent Result Labels for Users (Part H)
USER_LABEL_SOURCE_FOUND = "SOURCE FOUND"
USER_LABEL_REFERENCE_FOUND = "REFERENCE FOUND"
USER_LABEL_QUOTE_MATCHED = "QUOTE MATCHED"
USER_LABEL_SUPPORT_NOT_ESTABLISHED = "SUPPORT NOT ESTABLISHED"
USER_LABEL_NEEDS_LEGAL_REVIEW = "NEEDS LEGAL REVIEW"
USER_LABEL_REFERENCE_NOT_FOUND = "REFERENCE NOT FOUND"

# Future Law Key Dates
GSR_789_EFFECTIVE_DATE = date(2027, 1, 1)
GSR_789_PUBLICATION_DATE = date(2026, 9, 9)

# ---------------------------------------------------------------------------
# In-Memory Cached Knowledge Base Indexes
# ---------------------------------------------------------------------------

_CATALOG_CACHE: Optional[Dict[str, Any]] = None
_CHUNKS_CACHE: Optional[Dict[str, Any]] = None
_EXTRACTED_TEXT_CACHE: Dict[str, str] = {}


def _normalize_string(s: str) -> str:
    """Normalizes whitespace, casing, and basic punctuation for robust matching."""
    if not s:
        return ""
    # Strip smart quotes, dashes, collapse whitespace
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = s.replace("—", "-").replace("–", "-")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _normalize_title(title: str) -> str:
    """Normalizes legal act/rule title for canonical matching."""
    t = _normalize_string(title).lower()
    t = re.sub(r"^the\s+", "", t)
    t = re.sub(r"[,\(\)\-\.]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def load_knowledge_base_indexes(force_reload: bool = False) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Loads and caches source_catalog.json and legal_chunks.json indexes."""
    global _CATALOG_CACHE, _CHUNKS_CACHE

    if not force_reload and _CATALOG_CACHE is not None and _CHUNKS_CACHE is not None:
        return _CATALOG_CACHE, _CHUNKS_CACHE

    # 1. Load Catalog
    catalog_docs: Dict[str, Dict[str, Any]] = {}
    title_to_doc_id: Dict[str, str] = {}

    if CATALOG_PATH.exists():
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                cat_data = json.load(f)
            for doc in cat_data.get("sources", []):
                did = doc.get("document_id")
                if did:
                    catalog_docs[did] = doc
                    norm_t = _normalize_title(doc.get("document_title", ""))
                    if norm_t:
                        title_to_doc_id[norm_t] = did
                    # Also register common abbreviations / shorthands
                    if did == "CPA_2019":
                        title_to_doc_id["consumer protection act 2019"] = did
                        title_to_doc_id["cpa 2019"] = did
                    elif did == "CP_ECOMMERCE_RULES_2020":
                        title_to_doc_id["consumer protection e commerce rules 2020"] = did
                        title_to_doc_id["e commerce rules 2020"] = did
                        title_to_doc_id["ecommerce rules 2020"] = did
                    elif did == "CP_ECOMMERCE_AMENDMENT_2026":
                        title_to_doc_id["consumer protection e commerce amendment rules 2026"] = did
                        title_to_doc_id["e commerce amendment rules 2026"] = did
                        title_to_doc_id["ecommerce amendment rules 2026"] = did
                    elif did == "CP_ECOMMERCE_AMENDMENT_2021":
                        title_to_doc_id["consumer protection e commerce amendment rules 2021"] = did
                    elif did == "CP_GENERAL_RULES_2020":
                        title_to_doc_id["consumer protection general rules 2020"] = did
                    elif did == "CP_CDRC_RULES_2020":
                        title_to_doc_id["consumer protection consumer disputes redressal commissions rules 2020"] = did
                    elif did == "CP_JURISDICTION_RULES_2021":
                        title_to_doc_id["consumer protection jurisdiction of the district commission the state commission and the national commission rules 2021"] = did
        except Exception as e:
            logger.error(f"Error loading source_catalog.json: {e}")

    # 2. Load Chunks & Embedding Records
    chunks_by_id: Dict[str, Dict[str, Any]] = {}
    doc_provisions: Dict[str, Set[str]] = {}
    doc_chunk_map: Dict[Tuple[str, str], List[str]] = {}

    def _index_chunk(c: Dict[str, Any], key_id: str):
        chunks_by_id[key_id] = c
        did = c.get("document_id")
        pnum = c.get("provision_number")
        if did and pnum:
            doc_provisions.setdefault(did, set()).add(str(pnum).strip())
            doc_chunk_map.setdefault((did, str(pnum).strip()), []).append(key_id)

    if CHUNKS_PATH.exists():
        try:
            with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
                c_list = json.load(f)
            for c in c_list:
                cid = c.get("chunk_id")
                if cid:
                    _index_chunk(c, cid)
        except Exception as e:
            logger.error(f"Error loading legal_chunks.json: {e}")

    if HISTORICAL_CHUNKS_PATH.exists():
        try:
            with open(HISTORICAL_CHUNKS_PATH, "r", encoding="utf-8") as f:
                h_list = json.load(f)
            for h in h_list:
                cid = h.get("chunk_id")
                if cid:
                    _index_chunk(h, cid)
        except Exception as e:
            logger.error(f"Error loading historical_reference_chunks.json: {e}")

    if EMBEDDING_RECORDS_PATH.exists():
        try:
            with open(EMBEDDING_RECORDS_PATH, "r", encoding="utf-8") as f:
                rec_list = json.load(f)
            for r in rec_list:
                rid = r.get("embedding_record_id")
                if rid:
                    _index_chunk(r, rid)
        except Exception as e:
            logger.error(f"Error loading embedding_records.json: {e}")

    _CATALOG_CACHE = {
        "catalog_docs": catalog_docs,
        "title_to_doc_id": title_to_doc_id,
    }
    _CHUNKS_CACHE = {
        "chunks_by_id": chunks_by_id,
        "doc_provisions": doc_provisions,
        "doc_chunk_map": doc_chunk_map,
    }

    return _CATALOG_CACHE, _CHUNKS_CACHE


def get_extracted_document_text(document_id: str) -> str:
    """Loads and returns extracted raw text for a given document from disk."""
    if document_id in _EXTRACTED_TEXT_CACHE:
        return _EXTRACTED_TEXT_CACHE[document_id]

    extracted_file = EXTRACTED_DIR / f"{document_id}_extracted.json"
    if not extracted_file.exists():
        return ""

    try:
        with open(extracted_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        pages = data.get("pages", [])
        full_text = "\n".join(p.get("text", "") for p in pages)
        _EXTRACTED_TEXT_CACHE[document_id] = full_text
        return full_text
    except Exception as e:
        logger.error(f"Error loading extracted document text for {document_id}: {e}")
        return ""


# ---------------------------------------------------------------------------
# Provision & Reference Extraction Helpers
# ---------------------------------------------------------------------------

PROVISION_REGEX = re.compile(
    r"\b(?P<type>Section|Sec\.?|Rule|Schedule|Clause)\s+(?P<num>\d+(?:\([0-9a-zA-Z]+\))*|[IVXLCDM]+|\d+)",
    re.IGNORECASE,
)


def extract_provision_references_from_text(text: str) -> List[Dict[str, str]]:
    """
    Extracts legal provision references (e.g. Section 35, Rule 5, Section 2(10)) from text.
    Carefully ignores monetary numbers, percentages, dates, and non-statutory numerals.
    """
    if not text:
        return []

    results = []
    seen = set()

    for match in PROVISION_REGEX.finditer(text):
        raw_type = match.group("type").strip().rstrip(".").capitalize()
        num = match.group("num").strip()

        # Normalize Section vs Sec -> Section
        prov_type = "Section" if raw_type.lower().startswith("sec") else raw_type

        # Avoid phone numbers or 4-digit years like Section 2019
        if num in ("2019", "2020", "2021", "2026", "2027", "1915"):
            continue

        ref_str = f"{prov_type} {num}"
        if ref_str not in seen:
            seen.add(ref_str)
            results.append({
                "provision_type": prov_type,
                "provision_number": num,
                "provision_reference": ref_str,
                "match_start": match.start(),
                "match_end": match.end(),
            })

    return results


def extract_direct_quotations(text: str) -> List[str]:
    """
    Extracts direct legal quotations enclosed in double or single quotes.
    Ignores short trivial words or numbers.
    """
    if not text:
        return []

    # Matches text enclosed in quotes of length >= 8
    patterns = [
        r'["“]([^"”]{8,})["”]',
        r"['‘]([^'’]{12,})['’]",
    ]
    quotes = []
    seen = set()
    for pat in patterns:
        for m in re.finditer(pat, text):
            q_text = m.group(1).strip()
            # Ignore trivial short strings
            if len(q_text) >= 8 and q_text not in seen:
                seen.add(q_text)
                quotes.append(q_text)
    return quotes


# ---------------------------------------------------------------------------
# Citation & Source Verification Logic
# ---------------------------------------------------------------------------

def _match_document_title(doc_title: Optional[str], catalog_docs: Dict[str, Any], title_to_doc_id: Dict[str, str]) -> Tuple[str, Optional[str]]:
    """Checks whether a given document title matches official catalog."""
    if not doc_title or not doc_title.strip():
        return TITLE_NOT_SPECIFIED, None

    norm = _normalize_title(doc_title)
    if norm in title_to_doc_id:
        return TITLE_MATCHED, title_to_doc_id[norm]

    # Partial substring check against known catalog titles
    for cat_norm, did in title_to_doc_id.items():
        if cat_norm in norm or norm in cat_norm:
            return TITLE_MATCHED, did

    return TITLE_MISMATCH, None


def verify_source_id(
    source_id: str,
    retrieved_allowlist: Dict[str, Dict[str, Any]],
    catalog_docs: Dict[str, Any],
    chunks_by_id: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Validates a source ID against the catalog, chunks, and retrieved allowlist.
    """
    res = {
        "source_id": source_id,
        "retrieval_status": SOURCE_NOT_FOUND,
        "document_id": None,
        "is_retrieved": False,
        "chunk_data": None,
        "doc_data": None,
        "limitations": [],
    }

    # 1. Check whether it exists anywhere in knowledge base (chunks or catalog)
    is_in_chunks = source_id in chunks_by_id
    is_in_catalog = source_id in catalog_docs

    if not is_in_chunks and not is_in_catalog:
        res["retrieval_status"] = SOURCE_NOT_FOUND
        res["limitations"].append(f"Source ID '{source_id}' does not exist in the official legal catalog or knowledge base.")
        return res

    # 2. Extract Document ID
    doc_id = None
    if is_in_chunks:
        chunk = chunks_by_id[source_id]
        res["chunk_data"] = chunk
        doc_id = chunk.get("document_id")
    elif is_in_catalog:
        doc_id = source_id

    res["document_id"] = doc_id
    if doc_id and doc_id in catalog_docs:
        res["doc_data"] = catalog_docs[doc_id]

    # 3. Check whether source was supplied in retrieved allowlist
    if source_id in retrieved_allowlist:
        res["is_retrieved"] = True
        res["retrieval_status"] = SOURCE_FOUND
    else:
        res["is_retrieved"] = False
        res["retrieval_status"] = SOURCE_NOT_RETRIEVED
        res["limitations"].append(f"Source ID '{source_id}' exists in the knowledge base but was NOT supplied in retrieved passages.")

    return res


def verify_provision_in_document(
    document_id: str,
    prov_type: str,
    prov_num: str,
    doc_provisions: Dict[str, Set[str]],
    catalog_docs: Dict[str, Any],
) -> str:
    """
    Verifies that a provision (e.g. Section 35, Rule 5) actually exists in the specified document.
    """
    if not document_id or document_id not in catalog_docs:
        return REFERENCE_NOT_FOUND

    doc_meta = catalog_docs[document_id]
    expected_doc_type = doc_meta.get("document_type", "").upper()

    # Document type vs Provision type check
    # Acts contain SECTIONS; Rules contain RULES
    if "RULE" in expected_doc_type and prov_type.upper() == "SECTION":
        return DOCUMENT_MISMATCH
    if expected_doc_type == "ACT" and prov_type.upper() == "RULE":
        return DOCUMENT_MISMATCH

    # Check chunks index
    known_provs = doc_provisions.get(document_id, set())
    clean_num = prov_num.strip()

    # Exact match on provision number
    if clean_num in known_provs:
        return REFERENCE_FOUND

    # Sub-clause / sub-section match (e.g., searching 2(10) when 2 is known or vice versa)
    base_num = re.split(r"[\(\[]", clean_num)[0].strip()
    if base_num in known_provs:
        return REFERENCE_FOUND

    for p in known_provs:
        # Match "2(10)" when p is "2", but NOT "888" when p is "8"
        if clean_num.startswith(f"{p}(") or clean_num.startswith(f"{p}["):
            return REFERENCE_FOUND
        if p.startswith(f"{clean_num}(") or p.startswith(f"{clean_num}["):
            return REFERENCE_FOUND

    # Search raw extracted text as secondary verification
    extracted_text = get_extracted_document_text(document_id)
    if extracted_text:
        # Match pattern like: \b35\.\s+ or \bSection\s+35\b or \bRule\s+5\b
        if prov_type.upper() == "SECTION":
            patterns = [
                rf"\b{re.escape(base_num)}\.\s+",
                rf"\bSection\s+{re.escape(base_num)}\b",
                rf"\bSection\s+{re.escape(clean_num)}\b",
            ]
        else:
            patterns = [
                rf"\b{re.escape(base_num)}\.\s+",
                rf"\bRule\s+{re.escape(base_num)}\b",
                rf"\bRule\s+{re.escape(clean_num)}\b",
            ]
        for pat in patterns:
            if re.search(pat, extracted_text, re.IGNORECASE):
                # Extra check: if matching base_num. in text, ensure it's not matching unrelated number
                m = re.search(pat, extracted_text, re.IGNORECASE)
                if m:
                    # If clean_num is 888 and we only matched base_num which is 888, check base_num <= 107
                    # CPA 2019 has sections 1 to 107
                    try:
                        num_val = int(base_num)
                        if document_id == "CPA_2019" and num_val > 107:
                            continue
                    except ValueError:
                        pass
                    return REFERENCE_FOUND

    return REFERENCE_NOT_FOUND


def verify_quotation(
    quote: str,
    target_texts: List[str],
) -> Tuple[str, Optional[float]]:
    """
    Compares a quotation against target texts with normalized whitespace.
    Returns (status, similarity_ratio).
    """
    if not quote or not target_texts:
        return QUOTE_NOT_APPLICABLE, None

    norm_quote = _normalize_string(quote).lower()
    if len(norm_quote) < 6:
        return QUOTE_NOT_APPLICABLE, None

    # 1. Exact Substring Match after normalization
    for t in target_texts:
        norm_t = _normalize_string(t).lower()
        if norm_quote in norm_t:
            return VERBATIM_QUOTE_MATCH, 1.0

    # 2. Substring search in sliding window for approximate match diagnostics
    best_ratio = 0.0
    for t in target_texts:
        norm_t = _normalize_string(t).lower()
        # Find best ratio in chunks
        q_len = len(norm_quote)
        step = max(20, q_len // 2)
        for i in range(0, max(1, len(norm_t) - q_len + 1), step):
            window = norm_t[i : i + q_len]
            ratio = difflib.SequenceMatcher(None, norm_quote, window).ratio()
            if ratio > best_ratio:
                best_ratio = ratio

    if best_ratio >= 0.85:
        # Materially altered quotation or near-match
        return QUOTE_MISMATCH, round(best_ratio, 3)
    elif best_ratio >= 0.50:
        return PARAPHRASE_NOT_VERIFIED_AS_QUOTE, round(best_ratio, 3)
    else:
        return QUOTE_MISMATCH, round(best_ratio, 3)


# ---------------------------------------------------------------------------
# Claim-Level Support Checking (Part G)
# ---------------------------------------------------------------------------

def split_into_claims(text: str) -> List[str]:
    """Splits plain text into substantive sentences or clauses representing legal claims."""
    if not text:
        return []
    # Split on period, exclamation, or newline followed by whitespace/capital
    raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    claims = []
    for s in raw_sentences:
        clean = s.strip()
        if len(clean) >= 15:
            # Filter out pure greetings, headers, or meta labels
            if not clean.lower().startswith(("user statement", "case facts", "note on")):
                claims.append(clean)
    return claims


def evaluate_claim_support(
    claim_text: str,
    cited_source_ids: List[str],
    retrieved_allowlist: Dict[str, Dict[str, Any]],
    chunks_by_id: Dict[str, Any],
) -> Tuple[str, List[str]]:
    """
    Evaluates whether a claim is supported by its attached cited sources.
    Uses conservative, cautious deterministic evaluation.
    """
    limitations = []

    if not cited_source_ids:
        # Check if the claim makes a specific statutory assertion without citation
        prov_refs = extract_provision_references_from_text(claim_text)
        if prov_refs:
            limitations.append(f"Claim references specific statutory provision '{prov_refs[0]['provision_reference']}' without an attached source citation.")
            return UNSUPPORTED_NO_CITATION, limitations
        return SUPPORT_NOT_ESTABLISHED, ["General assertion without supporting statutory source citation."]

    # Check if attached source IDs exist in allowlist
    valid_passages: List[str] = []
    valid_prov_numbers: Set[str] = set()
    for sid in cited_source_ids:
        if sid in retrieved_allowlist:
            s_data = retrieved_allowlist[sid]
            passage = s_data.get("exact_original_text") or s_data.get("text", "")
            if passage:
                valid_passages.append(passage)
            p_num = str(s_data.get("provision_number", "")).strip()
            if p_num:
                valid_prov_numbers.add(p_num)
            p_head = str(s_data.get("provision_heading", "")).strip()
            if p_head:
                valid_passages.append(p_head)
            # Also capture chunk_id for section number clues
            valid_prov_numbers.add(sid)
        elif sid in chunks_by_id:
            limitations.append(f"Source ID '{sid}' was cited but was not in the retrieved passages supplied to the model.")
        else:
            limitations.append(f"Source ID '{sid}' cited for this claim does not exist in the knowledge base.")

    if not valid_passages:
        return SUPPORT_NOT_ESTABLISHED, limitations

    # Conservative Support Checking:
    # Check if the claim mentions specific provisions or keywords that exist in the valid passages or metadata
    claim_provs = extract_provision_references_from_text(claim_text)
    combined_passage_text = " ".join(valid_passages).lower()

    if claim_provs:
        matched_any_prov = False
        for p in claim_provs:
            p_num = p["provision_number"]
            base_num = re.sub(r"\(.*?\)", "", p_num).strip()
            # Look for provision number or base section number in passages or source metadata
            if (p_num in combined_passage_text or any(p_num in vpn for vpn in valid_prov_numbers) or
                base_num in combined_passage_text or any(base_num == vpn or vpn.endswith(f"_{base_num}") for vpn in valid_prov_numbers)):
                matched_any_prov = True
                break
        if not matched_any_prov:
            limitations.append(f"Provision reference in claim ({claim_provs[0]['provision_reference']}) is not found in the text or metadata of the cited source.")
            return SUPPORT_NOT_ESTABLISHED, limitations

    # Keyword concept overlap check
    # Extract significant non-stop words (length >= 4) from claim
    stopwords = {"this", "that", "with", "from", "have", "been", "under", "which", "their", "there", "about", "would", "could", "should", "shall", "these", "those", "where"}
    claim_words = {w.lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", claim_text) if w.lower() not in stopwords}

    if not claim_words:
        return SUPPORTED_BY_PASSAGE, limitations

    matched_words = {w for w in claim_words if w in combined_passage_text}
    overlap_ratio = len(matched_words) / len(claim_words)

    if overlap_ratio >= 0.25:
        # Check if claim asserts definitive legal liability, entitlement, or judicial conclusion
        legal_concl_patterns = [
            r"\b(strictly\s+liable|proven\s+deficiency|definitely\s+guilty|guaranteed\s+compensation|entitled\s+as\s+a\s+matter\s+of\s+law|conclusively\s+proves?)\b",
            r"\b(automatically\s+entitled|undisputed\s+liability|court\s+will\s+rule|certain\s+remedy)\b",
        ]
        if any(re.search(pat, claim_text, re.IGNORECASE) for pat in legal_concl_patterns):
            limitations.append(
                "Passage contains textual overlap with claim keywords, but determining definitive legal liability or remedy requires professional advocate or judicial interpretation."
            )
            return CLAIM_NEEDS_LEGAL_REVIEW, limitations

        return SUPPORTED_BY_PASSAGE, limitations
    else:
        limitations.append("The cited source passages do not contain substantial textual overlap with this claim's legal assertion.")
        return SUPPORT_NOT_ESTABLISHED, limitations


# ---------------------------------------------------------------------------
# Main Public Validator Function (Part B & J)
# ---------------------------------------------------------------------------

def validate_legal_answer(
    generated_answer: Union[Dict[str, Any], str],
    retrieved_sources: Optional[List[Dict[str, Any]]] = None,
    as_of_date: Optional[Union[str, date]] = None,
    transaction_date: Optional[Union[str, date]] = None,
    event_date: Optional[Union[str, date]] = None,
) -> Dict[str, Any]:
    """
    Independently validates legal citations, source IDs, Act and Rule titles,
    provision references, quotations, and claim-level support in a generated answer.

    Deterministic Python implementation. NEVER calls Gemini or LLMs.

    Args:
        generated_answer: The structured response dictionary or JSON string from Step 17.
        retrieved_sources: List of legal chunk/record dicts actually supplied to the generator.
        as_of_date: Reference date for legal in-force evaluation (default: today).
        transaction_date: Date when transaction occurred (for temporal analysis).
        event_date: Date when dispute or grievance event occurred.

    Returns:
        Structured validation report conforming to Blueprint Part J.
    """
    validated_at = datetime.now().isoformat()

    # Parse as_of_date
    if isinstance(as_of_date, str):
        try:
            ref_date = date.fromisoformat(as_of_date)
        except Exception:
            ref_date = date.today()
    elif isinstance(as_of_date, date):
        ref_date = as_of_date
    else:
        ref_date = date.today()

    # Parse transaction_date and event_date
    t_date: Optional[date] = None
    if isinstance(transaction_date, str):
        try:
            t_date = date.fromisoformat(transaction_date)
        except Exception:
            pass
    elif isinstance(transaction_date, date):
        t_date = transaction_date

    e_date: Optional[date] = None
    if isinstance(event_date, str):
        try:
            e_date = date.fromisoformat(event_date)
        except Exception:
            pass
    elif isinstance(event_date, date):
        e_date = event_date

    # 1. Parse generated_answer input
    answer_dict: Dict[str, Any] = {}
    if isinstance(generated_answer, str):
        try:
            answer_dict = json.loads(generated_answer)
        except Exception as e:
            return {
                "overall_status": STATUS_FAILED,
                "validated_at": validated_at,
                "as_of_date": ref_date.isoformat(),
                "citations": [],
                "claims": [],
                "unsupported_references": ["Answer input is malformed or unparseable JSON."],
                "unsupported_claims": [],
                "warnings": [f"Malformed input: {e}"],
                "requires_professional_review": True,
            }
    elif isinstance(generated_answer, dict):
        answer_dict = generated_answer
    else:
        return {
            "overall_status": STATUS_FAILED,
            "validated_at": validated_at,
            "as_of_date": ref_date.isoformat(),
            "citations": [],
            "claims": [],
            "unsupported_references": ["Answer input must be a dictionary or JSON string."],
            "unsupported_claims": [],
            "warnings": ["Invalid answer input type."],
            "requires_professional_review": True,
        }

    # 2. Build retrieved_sources allowlist
    retrieved_allowlist: Dict[str, Dict[str, Any]] = {}
    if isinstance(retrieved_sources, list):
        for s in retrieved_sources:
            if isinstance(s, dict):
                cid = s.get("chunk_id")
                rid = s.get("embedding_record_id")
                if cid:
                    retrieved_allowlist[cid] = s
                if rid:
                    retrieved_allowlist[rid] = s

    # 3. Load Knowledge Base Indexes
    cat_cache, chunks_cache = load_knowledge_base_indexes()
    catalog_docs = cat_cache["catalog_docs"]
    title_to_doc_id = cat_cache["title_to_doc_id"]
    chunks_by_id = chunks_cache["chunks_by_id"]
    doc_provisions = chunks_cache["doc_provisions"]

    # 4. Collect citations to verify
    # From relevant_official_sources list
    raw_sources_list = answer_dict.get("relevant_official_sources", [])
    raw_ids_used = answer_dict.get("source_ids_used", [])

    # Text bodies to analyze
    what_says = str(answer_dict.get("what_the_source_says", ""))
    how_relates = str(answer_dict.get("how_it_may_relate_to_your_problem", ""))
    combined_answer_text = f"{what_says}\n{how_relates}".strip()

    # Track overall issues
    unsupported_references: List[str] = []
    unsupported_claims: List[str] = []
    warnings: List[str] = []
    requires_prof_review = False

    # Extract all text-level citations & quotes
    text_prov_refs = extract_provision_references_from_text(combined_answer_text)
    direct_quotes = extract_direct_quotations(combined_answer_text)

    # 5. Process Citations
    citation_reports: List[Dict[str, Any]] = []
    seen_citation_keys: Set[str] = set()

    # A. Inspect structured sources in `relevant_official_sources`
    for src in raw_sources_list:
        if not isinstance(src, dict):
            continue
        sid = src.get("source_id") or ""
        doc_title = src.get("document_title") or ""
        prov_ref = src.get("provision_reference") or ""
        src_url = src.get("source_url")

        # Deduplicate identical citation tuples
        cite_key = f"{sid}_{doc_title}_{prov_ref}".strip()
        if cite_key in seen_citation_keys:
            continue
        seen_citation_keys.add(cite_key)

        cite_report: Dict[str, Any] = {
            "source_id": sid,
            "document_id": None,
            "document_title": doc_title,
            "title_status": TITLE_NOT_SPECIFIED,
            "provision_reference": prov_ref,
            "provision_status": REFERENCE_NOT_FOUND,
            "retrieval_status": SOURCE_NOT_FOUND,
            "source_url_status": "NOT_CHECKED",
            "quote_status": QUOTE_NOT_APPLICABLE,
            "legal_review_status": REQUIRES_LEGAL_REVIEW,
            "temporal_status": CURRENTLY_IN_FORCE,
            "limitations": [],
        }

        # Step C: Verify Source ID
        sid_res = verify_source_id(sid, retrieved_allowlist, catalog_docs, chunks_by_id)
        cite_report["retrieval_status"] = sid_res["retrieval_status"]
        cite_report["document_id"] = sid_res["document_id"]
        cite_report["limitations"].extend(sid_res["limitations"])

        if sid_res["retrieval_status"] == SOURCE_NOT_FOUND:
            unsupported_references.append(f"Invented or unknown Source ID: '{sid}'")
        elif sid_res["retrieval_status"] == SOURCE_NOT_RETRIEVED:
            unsupported_references.append(f"Unsupplied Source ID '{sid}' cited in answer without being retrieved.")

        # Step D: Title Validation
        t_stat, matched_did = _match_document_title(doc_title, catalog_docs, title_to_doc_id)
        cite_report["title_status"] = t_stat
        if t_stat == TITLE_MATCHED and matched_did:
            # Check document attribution mismatch
            if sid_res["document_id"] and sid_res["document_id"] != matched_did:
                cite_report["title_status"] = TITLE_MISMATCH
                cite_report["limitations"].append(
                    f"Document Title '{doc_title}' ({matched_did}) does not match chunk document '{sid_res['document_id']}'."
                )
                unsupported_references.append(f"Document attribution mismatch for source ID '{sid}'")
        elif t_stat == TITLE_MISMATCH:
            cite_report["limitations"].append(f"Document title '{doc_title}' not recognized in official source catalog.")
            warnings.append(f"Unrecognized document title: '{doc_title}'")

        # Step E: Provision Reference Validation
        # Extract provision type and number from prov_ref
        prov_parsed = extract_provision_references_from_text(prov_ref)
        if not prov_parsed and sid_res["chunk_data"]:
            # Fall back to chunk data provision
            ptype = sid_res["chunk_data"].get("provision_type", "Section").capitalize()
            pnum = sid_res["chunk_data"].get("provision_number", "")
            if pnum:
                prov_parsed = [{"provision_type": ptype, "provision_number": pnum, "provision_reference": f"{ptype} {pnum}"}]
                cite_report["provision_reference"] = f"{ptype} {pnum}"

        target_doc_id = sid_res["document_id"] or matched_did
        if prov_parsed and target_doc_id:
            first_p = prov_parsed[0]
            p_stat = verify_provision_in_document(
                document_id=target_doc_id,
                prov_type=first_p["provision_type"],
                prov_num=first_p["provision_number"],
                doc_provisions=doc_provisions,
                catalog_docs=catalog_docs,
            )
            cite_report["provision_status"] = p_stat
            if p_stat == REFERENCE_NOT_FOUND:
                cite_report["limitations"].append(
                    f"Provision '{first_p['provision_reference']}' not found in official document '{target_doc_id}'."
                )
                unsupported_references.append(f"Non-existent provision '{first_p['provision_reference']}' in '{target_doc_id}'")
            elif p_stat == DOCUMENT_MISMATCH:
                cite_report["limitations"].append(
                    f"Provision type '{first_p['provision_type']}' does not match document type of '{target_doc_id}'."
                )
                unsupported_references.append(f"Provision type mismatch for '{first_p['provision_reference']}' in '{target_doc_id}'")
        elif prov_ref:
            cite_report["provision_status"] = NEEDS_MANUAL_REVIEW
            cite_report["limitations"].append(f"Could not parse provision reference structure from '{prov_ref}'.")

        # Step F: Quotation check against this citation's chunk
        if direct_quotes and sid_res["chunk_data"]:
            chunk_txt = sid_res["chunk_data"].get("exact_original_text") or sid_res["chunk_data"].get("text", "")
            q_statuses = []
            for q in direct_quotes:
                q_stat, ratio = verify_quotation(q, [chunk_txt])
                if q_stat == VERBATIM_QUOTE_MATCH:
                    q_statuses.append(VERBATIM_QUOTE_MATCH)
                elif q_stat == QUOTE_MISMATCH:
                    q_statuses.append(QUOTE_MISMATCH)
                    cite_report["limitations"].append(f"Direct quote altered from original text (similarity {ratio}): \"{q[:40]}...\"")
                    warnings.append(f"Material quotation mismatch: \"{q[:40]}...\"")
                elif q_stat == PARAPHRASE_NOT_VERIFIED_AS_QUOTE:
                    q_statuses.append(PARAPHRASE_NOT_VERIFIED_AS_QUOTE)
                    cite_report["limitations"].append(f"Quotation appears to be a paraphrase rather than verbatim: \"{q[:40]}...\"")

            if VERBATIM_QUOTE_MATCH in q_statuses:
                cite_report["quote_status"] = VERBATIM_QUOTE_MATCH
            elif QUOTE_MISMATCH in q_statuses:
                cite_report["quote_status"] = QUOTE_MISMATCH
            elif PARAPHRASE_NOT_VERIFIED_AS_QUOTE in q_statuses:
                cite_report["quote_status"] = PARAPHRASE_NOT_VERIFIED_AS_QUOTE

        # URL validation against catalogue
        if src_url and sid_res["doc_data"]:
            official_url = sid_res["doc_data"].get("official_source_url")
            if official_url and src_url.strip() != official_url.strip():
                cite_report["source_url_status"] = "URL_MISMATCH"
                cite_report["limitations"].append(f"Source URL '{src_url}' differs from official catalog URL '{official_url}'.")
            else:
                cite_report["source_url_status"] = "MATCHED"

        # Step H: Legal Review Status preservation
        if sid_res["chunk_data"]:
            c_stat = sid_res["chunk_data"].get("legal_review_status", REQUIRES_LEGAL_REVIEW)
            cite_report["legal_review_status"] = c_stat
        elif sid_res["doc_data"]:
            c_stat = sid_res["doc_data"].get("legal_review_status", REQUIRES_LEGAL_REVIEW)
            cite_report["legal_review_status"] = c_stat

        if cite_report["legal_review_status"] == REQUIRES_LEGAL_REVIEW:
            requires_prof_review = True

        # Step I: Temporal Status Validation
        if sid_res["doc_data"]:
            doc_app = sid_res["doc_data"].get("applicability_status", CURRENTLY_IN_FORCE)
            cite_report["temporal_status"] = doc_app

            # GSR 789(E) commencement check
            if target_doc_id == "CP_ECOMMERCE_AMENDMENT_2026":
                cite_report["temporal_status"] = FUTURE_EFFECTIVE
                if ref_date < GSR_789_EFFECTIVE_DATE:
                    cite_report["limitations"].append(
                        f"G.S.R. 789(E) commences on {GSR_789_EFFECTIVE_DATE} and is FUTURE-EFFECTIVE (not operative as of {ref_date})."
                    )
                    warnings.append("Citation references future amendment G.S.R. 789(E) before commencement date.")

            # Superseded / historical status check
            if doc_app in (SUPERSEDED, HISTORICAL_REFERENCE):
                cite_report["limitations"].append(f"Document has '{doc_app}' status and cannot be presented as currently operative law.")
                warnings.append(f"Referenced source has '{doc_app}' status.")

        # Check transitional applicability
        if t_date and t_date < GSR_789_EFFECTIVE_DATE and (e_date or ref_date) >= GSR_789_EFFECTIVE_DATE:
            if target_doc_id == "CP_ECOMMERCE_AMENDMENT_2026":
                cite_report["temporal_status"] = TEMPORAL_NEEDS_LEGAL_REVIEW
                cite_report["limitations"].append(
                    "Dispute spans pre-commencement transaction with continuing post-commencement events. Transitional applicability is unsettled."
                )
                requires_prof_review = True

        citation_reports.append(cite_report)

    # B. Also check any source_ids_used that weren't in relevant_official_sources
    for sid in raw_ids_used:
        if isinstance(sid, str) and not any(c["source_id"] == sid for c in citation_reports):
            sid_res = verify_source_id(sid, retrieved_allowlist, catalog_docs, chunks_by_id)
            c_rep = {
                "source_id": sid,
                "document_id": sid_res["document_id"],
                "document_title": sid_res["doc_data"].get("document_title", "") if sid_res["doc_data"] else "",
                "title_status": TITLE_MATCHED if sid_res["doc_data"] else TITLE_NOT_SPECIFIED,
                "provision_reference": sid_res["chunk_data"].get("provision_number", "") if sid_res["chunk_data"] else "",
                "provision_status": REFERENCE_FOUND if sid_res["chunk_data"] else REFERENCE_NOT_FOUND,
                "retrieval_status": sid_res["retrieval_status"],
                "source_url_status": "NOT_CHECKED",
                "quote_status": QUOTE_NOT_APPLICABLE,
                "legal_review_status": sid_res["chunk_data"].get("legal_review_status", REQUIRES_LEGAL_REVIEW) if sid_res["chunk_data"] else REQUIRES_LEGAL_REVIEW,
                "temporal_status": sid_res["doc_data"].get("applicability_status", CURRENTLY_IN_FORCE) if sid_res["doc_data"] else CURRENTLY_IN_FORCE,
                "limitations": sid_res["limitations"],
            }
            if sid_res["retrieval_status"] == SOURCE_NOT_FOUND:
                unsupported_references.append(f"Invented or unknown Source ID in source_ids_used: '{sid}'")
            elif sid_res["retrieval_status"] == SOURCE_NOT_RETRIEVED:
                unsupported_references.append(f"Unsupplied Source ID '{sid}' in source_ids_used.")
            citation_reports.append(c_rep)

    # 6. Step G: Claim-Level Support Checking
    claims_report: List[Dict[str, Any]] = []

    # Check if answer_dict already provides structured claims
    structured_claims = answer_dict.get("claims")
    if isinstance(structured_claims, list) and structured_claims:
        for idx, c_item in enumerate(structured_claims, start=1):
            if not isinstance(c_item, dict):
                continue
            cid = c_item.get("claim_id") or f"CLM_{idx:03d}"
            c_text = str(c_item.get("claim_text", "")).strip()
            c_sids = c_item.get("source_ids", [])
            if not isinstance(c_sids, list):
                c_sids = [c_sids] if c_sids else []
            c_prov = c_item.get("referenced_provision")
            if not c_prov:
                c_provs = extract_provision_references_from_text(c_text)
                c_prov = c_provs[0]["provision_reference"] if c_provs else None

            c_status, c_limitations = evaluate_claim_support(
                claim_text=c_text,
                cited_source_ids=c_sids,
                retrieved_allowlist=retrieved_allowlist,
                chunks_by_id=chunks_by_id,
            )
            if c_status in (SUPPORT_NOT_ESTABLISHED, UNSUPPORTED_NO_CITATION):
                unsupported_claims.append(f"[{cid}] {c_text[:80]}... ({c_status})")

            claims_report.append({
                "claim_id": cid,
                "claim_text": c_text,
                "source_ids": c_sids,
                "referenced_provision": c_prov,
                "support_status": c_status,
                "limitations": c_limitations,
            })
    else:
        substantive_claims = split_into_claims(combined_answer_text)
        all_cited_source_ids = [c["source_id"] for c in citation_reports if c["source_id"]]

        for idx, claim_str in enumerate(substantive_claims, start=1):
            cid = f"CLM_{idx:03d}"
            claim_provs = extract_provision_references_from_text(claim_str)
            referenced_prov = claim_provs[0]["provision_reference"] if claim_provs else None

            # Associate source IDs: match provision or document name, never blindly associate all to unreferenced claims
            matched_sids: List[str] = []
            if referenced_prov:
                base_prov = re.sub(r"\(.*?\)", "", referenced_prov).strip()
                for c_rep in citation_reports:
                    c_prov = str(c_rep.get("provision_reference", "")).strip()
                    c_sid = str(c_rep.get("source_id", ""))
                    doc_t = str(c_rep.get("document_title", ""))
                    if (c_prov and (referenced_prov.lower() in c_prov.lower() or c_prov.lower() in referenced_prov.lower() or base_prov.lower() in c_prov.lower())) or \
                       (c_sid and base_prov.split()[-1] in c_sid.split("_")):
                        matched_sids.append(c_rep["source_id"])
            else:
                for c_rep in citation_reports:
                    doc_t = c_rep.get("document_title", "").lower()
                    p_num = str(c_rep.get("provision_reference", "")).lower()
                    c_sid = str(c_rep.get("source_id", "")).lower()
                    if (doc_t and ("e-commerce" in claim_str.lower() and "e-commerce" in doc_t)) or \
                       (doc_t and ("2019" in claim_str and "2019" in doc_t)) or \
                       (doc_t and ("e-jagriti" in claim_str.lower() and "e-jagriti" in doc_t)) or \
                       ("e-jagriti" in claim_str.lower() and "ejagriti" in c_sid) or \
                       (p_num and p_num in claim_str.lower()):
                        matched_sids.append(c_rep["source_id"])

            # If an answer cited only a single official source, attribute claim to that single source
            if not matched_sids and len(citation_reports) == 1:
                matched_sids.append(citation_reports[0]["source_id"])

            c_status, c_limitations = evaluate_claim_support(
                claim_text=claim_str,
                cited_source_ids=matched_sids,
                retrieved_allowlist=retrieved_allowlist,
                chunks_by_id=chunks_by_id,
            )

            if c_status in (SUPPORT_NOT_ESTABLISHED, UNSUPPORTED_NO_CITATION):
                unsupported_claims.append(f"[{cid}] {claim_str[:80]}... ({c_status})")

            claims_report.append({
                "claim_id": cid,
                "claim_text": claim_str,
                "source_ids": matched_sids,
                "referenced_provision": referenced_prov,
                "support_status": c_status,
                "limitations": c_limitations,
            })

    # 7. Check if response marked unconfirmed facts or requires professional review
    if answer_dict.get("response_status") == "UNCONFIRMED_FACTS_PROVISIONAL":
        warnings.append("Case facts remain unconfirmed by the consumer. Legal analysis is provisional.")
        requires_prof_review = True

    if answer_dict.get("needs_professional_review") is True:
        requires_prof_review = True

    # Check temporal status of answer
    if answer_dict.get("temporal_applicability_status") == TEMPORAL_NEEDS_LEGAL_REVIEW:
        requires_prof_review = True

    # 8. Determine Overall Status
    if unsupported_references:
        overall_status = STATUS_FAILED
    elif unsupported_claims:
        overall_status = STATUS_UNSUPPORTED_CLAIMS_DETECTED
    elif requires_prof_review or any(c["provision_status"] == NEEDS_MANUAL_REVIEW for c in citation_reports):
        overall_status = STATUS_NEEDS_REVIEW
    else:
        overall_status = STATUS_VALIDATED

    return {
        "overall_status": overall_status,
        "validated_at": validated_at,
        "as_of_date": ref_date.isoformat(),
        "citations": citation_reports,
        "claims": claims_report,
        "unsupported_references": unsupported_references,
        "unsupported_claims": unsupported_claims,
        "warnings": warnings,
        "requires_professional_review": requires_prof_review,
    }


# ---------------------------------------------------------------------------
# Safe Answer Handling (Part K)
# ---------------------------------------------------------------------------

def produce_safe_validated_answer(
    generated_answer: Dict[str, Any],
    validation_report: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Sanitizes and marks a generated answer based on validation results.
    Suppresses unsupported claims, attaches transparent disclaimers,
    and preserves original response for developer audit without inventing facts.
    """
    safe_answer = dict(generated_answer)
    safe_answer["original_unvalidated_answer"] = dict(generated_answer)
    safe_answer["citation_verification_report"] = validation_report

    status = validation_report.get("overall_status")
    unsupported_refs = validation_report.get("unsupported_references", [])
    unsupported_claims = validation_report.get("unsupported_claims", [])

    limitations = list(safe_answer.get("limitations_and_uncertainties", []))

    if status in (STATUS_FAILED, STATUS_UNSUPPORTED_CLAIMS_DETECTED):
        safe_answer["response_status"] = "UNSUPPORTED_CLAIMS_SUPPRESSED"
        safe_answer["needs_professional_review"] = True

        disclaimer = (
            "SAFETY WARNING: One or more legal citations or specific claims could not be verified "
            "against official statutory sources. Unverified claims have been flagged."
        )
        if disclaimer not in limitations:
            limitations.insert(0, disclaimer)

        for uref in unsupported_refs:
            limitations.append(f"Unverified Citation: {uref}")
        for uclm in unsupported_claims:
            limitations.append(f"Unverified Claim: {uclm}")

        # Material unsupported claims must not remain in the presented legal guidance
        for c in validation_report.get("claims", []):
            if c.get("support_status") in (
                SUPPORT_NOT_ESTABLISHED,
                UNSUPPORTED_NO_CITATION,
                REFERENCE_NOT_FOUND,
                TITLE_MISMATCH,
                DOCUMENT_MISMATCH,
                SOURCE_NOT_RETRIEVED,
                QUOTE_MISMATCH,
            ):
                c_txt = c.get("claim_text", "").strip()
                if c_txt:
                    if safe_answer.get("what_the_source_says"):
                        safe_answer["what_the_source_says"] = safe_answer["what_the_source_says"].replace(c_txt, "").strip()
                    if safe_answer.get("how_it_may_relate_to_your_problem"):
                        safe_answer["how_it_may_relate_to_your_problem"] = safe_answer["how_it_may_relate_to_your_problem"].replace(c_txt, "").strip()

        # If all source explanation text was suppressed, replace with explicit insufficiency statement
        clean_says = re.sub(r"[\s,;.\-:]+", "", safe_answer.get("what_the_source_says", ""))
        if not clean_says:
            safe_answer["what_the_source_says"] = "The available legal sources in Nyaya Saathi are insufficient to verify this point."
        clean_relates = re.sub(r"[\s,;.\-:]+", "", safe_answer.get("how_it_may_relate_to_your_problem", ""))
        if not clean_relates:
            safe_answer["how_it_may_relate_to_your_problem"] = "No matching official statutory provisions were verified for this specific question."

    elif status == STATUS_NEEDS_REVIEW:
        notice = "This explanation references legal provisions requiring professional review or provisional facts."
        if notice not in limitations:
            limitations.append(notice)
        safe_answer["needs_professional_review"] = True

    safe_answer["limitations_and_uncertainties"] = limitations
    return safe_answer
