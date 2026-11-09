"""
BM25 Keyword-Based Legal Retrieval Module for Nyaya Saathi.

Blueprint Phase 4B — Step 15: Lexical Search using rank-bm25 (BM25Okapi).
Retrieves relevant Indian consumer protection statutory and procedural passages
through high-precision lexical token matching over derived embedding records.

Guarantees:
1. Lexical Grounding: Searches exact statutory text, headings, section numbers, and rule citations.
2. Cross-Collection Segregation: Strictly isolates current statutory law, procedural guidance, and future amendments.
3. Date Gating: Restricts future-effective enactments (effective 2027-01-01) unless explicitly requested
   or transaction_date / as_of_date >= 2027-01-01.
4. Historical Segregation: Repealed CPA 1986, Consumer Handbook 2015, and web-only NCH are strictly excluded.
5. Controlled Bilingual Support: Automatically expands Hindi and Hinglish dispute terminology to canonical
   statutory search terms via src.keyword_expansion without LLM hallucination or external API calls.
6. Zero Hallucination: Documents with no positive lexical match (score <= 0.0) are discarded; returns explicit empty list.
"""

from datetime import date, datetime
import json
import logging
from pathlib import Path
import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from rank_bm25 import BM25Okapi

from src.keyword_expansion import expand_query_terms
from src.vector_store import (
    COLLECTION_CURRENT_LAW,
    COLLECTION_FUTURE_LAW,
    COLLECTION_PROCEDURAL_GUIDANCE,
)

logger = logging.getLogger("bm25_retriever")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECORDS_PATH = PROJECT_ROOT / "data" / "legal_sources" / "embedding_records.json"
FUTURE_LAW_EFFECTIVE_DATE = date(2027, 1, 1)

# Documented English Stopwords (standard functional words)
# Explicitly excludes all negations and substantive legal terms
STOPWORDS = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "of",
    "by", "from", "as", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "shall", "will", "would",
    "should", "could", "may", "might", "must", "can", "it", "its",
    "this", "that", "these", "those", "i", "me", "my", "myself", "we",
    "our", "ours", "you", "your", "yours", "he", "him", "his", "she",
    "her", "hers", "they", "them", "their", "theirs", "what", "which",
    "who", "whom", "where", "when", "how", "all", "any", "both", "each",
    "few", "more", "most", "other", "some", "such"
}

# Protected words that MUST NEVER be removed by stopword filtering
PROTECTED_WORDS = {
    # Legally crucial negations
    "no", "not", "without", "neither", "never", "nor", "none",
    # Substantive legal concepts
    "deficiency", "defect", "unfair", "misleading", "consideration",
    "jurisdiction", "complaint", "liability", "damage", "goods", "service",
    "consumer", "seller", "manufacturer", "trader", "appeal", "commission",
    "district", "national", "state", "refund", "repayment", "replacement"
}


def parse_date(date_val: Optional[Union[str, date, datetime]]) -> Optional[date]:
    """Safely coerces diverse date representations into datetime.date."""
    if date_val is None:
        return None
    if isinstance(date_val, datetime):
        return date_val.date()
    if isinstance(date_val, date):
        return date_val
    if isinstance(date_val, str):
        cleaned = date_val.strip()
        if not cleaned:
            return None
        try:
            return date.fromisoformat(cleaned)
        except ValueError:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(cleaned, fmt).date()
                except ValueError:
                    pass
    return None


def normalize_text(text: str) -> str:
    """Normalizes text for legal lexical matching."""
    if not text:
        return ""
    norm = unicodedata.normalize("NFKC", str(text)).lower()
    norm = norm.replace("e-commerce", "ecommerce").replace("e-jagriti", "ejagriti").replace("e-filing", "efiling")
    return norm


def tokenize_legal_text(text: str, remove_stopwords: bool = True) -> List[str]:
    """
    Tokenizes legal passages and queries, preserving section numbers, rule identifiers,
    statutory subclauses, numerals, and legal terms while normalizing case and punctuation.

    Examples:
        'Section 35 of Consumer Protection Act' -> ['section', '35', 'consumer', 'protection', 'act']
        'Rule 4(1) of E-Commerce Rules' -> ['4(1)', '4', '1', 'rule', 'ecommerce', 'rules']
    """
    if not text:
        return []

    norm = normalize_text(text)

    # 1. Extract composite statutory citations like 4(1), 2(10), 35(1)(a)
    citations = re.findall(r"\b\d+\([a-z0-9]+\)", norm)

    # 2. Extract alphanumeric word tokens
    words = re.findall(r"\b[a-z0-9]+\b", norm)

    tokens: List[str] = []

    # Preserve citations and their numerical/alphabetical components
    for cit in citations:
        tokens.append(cit)
        m = re.match(r"(\d+)\(([a-z0-9]+)\)", cit)
        if m:
            tokens.append(m.group(1))
            tokens.append(m.group(2))

    for w in words:
        if remove_stopwords:
            if w in PROTECTED_WORDS or w not in STOPWORDS:
                tokens.append(w)
        else:
            tokens.append(w)

    return tokens


def format_record_for_indexing(record: Dict[str, Any]) -> str:
    """
    Constructs the searchable passage string for a legal chunk or derived record.
    Incorporates document title, provision type, provision number, provision heading,
    and verbatim statutory body text.
    """
    parts = []
    doc_title = record.get("document_title", "").strip()
    prov_type = record.get("provision_type", "").strip()
    prov_num = record.get("provision_number", "")
    prov_num_str = str(prov_num).strip() if prov_num is not None else ""
    heading = record.get("provision_heading", "").strip()
    body = record.get("text", "").strip()

    if doc_title:
        parts.append(doc_title)
    if prov_type and prov_num_str:
        parts.append(f"{prov_type} {prov_num_str}")
    elif prov_num_str:
        parts.append(f"No. {prov_num_str}")
    if heading:
        parts.append(heading)
    if body:
        parts.append(body)

    return "\n".join(parts)


class BM25IndexManager:
    """
    Manages in-memory BM25 indices across three strictly segregated legal collections:
    1. nyaya_saathi_current_law (232 records)
    2. nyaya_saathi_procedural_guidance (13 records)
    3. nyaya_saathi_future_law (6 records)
    """

    def __init__(self, records_path: Path = DEFAULT_RECORDS_PATH):
        self.records_path = Path(records_path)
        self.all_records: List[Dict[str, Any]] = []
        self.tokenized_records: List[List[str]] = []
        self.record_collections: List[str] = []
        self._indices: Dict[Tuple[str, ...], BM25Okapi] = {}
        self._collection_record_map: Dict[Tuple[str, ...], List[int]] = {}
        self._load_and_index()

    def _load_and_index(self) -> None:
        """Loads derived embedding records and constructs BM25 indices."""
        if not self.records_path.exists():
            raise FileNotFoundError(f"Derived embedding records file not found at: {self.records_path}")

        with open(self.records_path, "r", encoding="utf-8") as f:
            raw_records: List[Dict[str, Any]] = json.load(f)

        self.all_records = []
        self.tokenized_records = []
        self.record_collections = []

        for r in raw_records:
            doc_id = r.get("document_id", "")
            # Strict historical and out-of-scope exclusions
            if doc_id in ("CONSUMER_HANDBOOK_2015", "NCH_GRIEVANCE_GUIDE"):
                continue
            if not r.get("retrieval_eligible", False):
                continue
            if not r.get("text", "").strip():
                continue

            app_status = r.get("applicability_status")
            doc_type = r.get("document_type")

            # Route to authoritative collection
            if app_status == "FUTURE_EFFECTIVE":
                col_name = COLLECTION_FUTURE_LAW
            elif doc_type in ("PROCEDURAL_GUIDE", "PROCEDURAL_GUIDANCE"):
                col_name = COLLECTION_PROCEDURAL_GUIDANCE
            elif app_status == "CURRENTLY_IN_FORCE":
                col_name = COLLECTION_CURRENT_LAW
            else:
                col_name = COLLECTION_CURRENT_LAW

            record_copy = dict(r)
            record_copy["collection_name"] = col_name

            searchable_text = format_record_for_indexing(record_copy)
            tokens = tokenize_legal_text(searchable_text)

            self.all_records.append(record_copy)
            self.tokenized_records.append(tokens)
            self.record_collections.append(col_name)

        logger.info(
            f"BM25 loaded {len(self.all_records)} eligible records "
            f"(Current Law: {self.record_collections.count(COLLECTION_CURRENT_LAW)}, "
            f"Procedural: {self.record_collections.count(COLLECTION_PROCEDURAL_GUIDANCE)}, "
            f"Future: {self.record_collections.count(COLLECTION_FUTURE_LAW)})"
        )

    def get_index_for_collections(
        self, collections: Sequence[str]
    ) -> Tuple[BM25Okapi, List[Dict[str, Any]], List[int]]:
        """
        Retrieves or builds a cached BM25Okapi index for the specified collections.
        Returns:
            (bm25_instance, sub_records, original_indices)
        """
        key = tuple(sorted(set(collections)))
        if key not in self._indices:
            sub_indices: List[int] = [
                i for i, col in enumerate(self.record_collections) if col in key
            ]
            sub_tokens = [self.tokenized_records[i] for i in sub_indices]
            sub_records = [self.all_records[i] for i in sub_indices]

            if not sub_tokens:
                # Fallback for empty collection
                bm25_instance = BM25Okapi([["empty"]])
            else:
                bm25_instance = BM25Okapi(sub_tokens)

            self._indices[key] = bm25_instance
            self._collection_record_map[key] = sub_indices

        sub_indices = self._collection_record_map[key]
        sub_records = [self.all_records[i] for i in sub_indices]
        return self._indices[key], sub_records, sub_indices


# Singleton in-memory index manager
_GLOBAL_BM25_MANAGER: Optional[BM25IndexManager] = None


def get_bm25_manager(records_path: Path = DEFAULT_RECORDS_PATH) -> BM25IndexManager:
    """Returns or initializes the singleton BM25 index manager."""
    global _GLOBAL_BM25_MANAGER
    if _GLOBAL_BM25_MANAGER is None or _GLOBAL_BM25_MANAGER.records_path != Path(records_path):
        _GLOBAL_BM25_MANAGER = BM25IndexManager(records_path=records_path)
    return _GLOBAL_BM25_MANAGER


def bm25_search(
    query: str,
    top_k: int = 8,
    include_procedural: bool = False,
    include_future: bool = False,
    transaction_date: Optional[Union[str, date, datetime]] = None,
    as_of_date: Optional[Union[str, date, datetime]] = None,
    records_path: Path = DEFAULT_RECORDS_PATH,
) -> List[Dict[str, Any]]:
    """
    Executes BM25 keyword-based lexical retrieval over derived legal child segments.

    Arguments:
        query: User dispute search inquiry (English, Hindi, or Hinglish).
        top_k: Number of ranked records to return (clamped between 1 and 10, default: 8).
        include_procedural: Whether to search official e-Jagriti / portal procedural guides.
        include_future: Explicit override to include future-effective statutory amendments.
        transaction_date: Date of dispute transaction (enables future law if >= 2027-01-01).
        as_of_date: Reference evaluation date (enables future law if >= 2027-01-01).
        records_path: Local path to derived embedding_records.json.

    Returns:
        Ranked list of structured result dictionaries with provenance metadata and BM25 score.
    """
    if not isinstance(query, str) or not query.strip():
        logger.warning("Empty or invalid query submitted to bm25_search.")
        return []

    clamped_top_k = max(1, min(10, int(top_k)))

    # 1. Determine Collection Routing based on intent and temporal dates
    t_date = parse_date(transaction_date)
    a_date = parse_date(as_of_date)

    future_eligible = include_future
    if t_date and t_date >= FUTURE_LAW_EFFECTIVE_DATE:
        future_eligible = True
    elif a_date and a_date >= FUTURE_LAW_EFFECTIVE_DATE:
        future_eligible = True

    collections_to_query: List[str] = [COLLECTION_CURRENT_LAW]
    if include_procedural:
        collections_to_query.append(COLLECTION_PROCEDURAL_GUIDANCE)
    if future_eligible:
        collections_to_query.append(COLLECTION_FUTURE_LAW)

    # 2. Controlled Bilingual Keyword Expansion
    expanded_terms, matched_keywords, detected_lang = expand_query_terms(query)

    # 3. Tokenize Query and Expanded Terms
    query_tokens = tokenize_legal_text(query)
    expanded_tokens: List[str] = []
    if expanded_terms:
        expanded_tokens = tokenize_legal_text(" ".join(expanded_terms))

    # Combine tokens (preserve order, avoid duplicate terms in query weighting)
    search_tokens: List[str] = []
    seen_search_tokens: Set[str] = set()
    for tok in query_tokens + expanded_tokens:
        if tok not in seen_search_tokens:
            seen_search_tokens.add(tok)
            search_tokens.append(tok)

    if not search_tokens:
        logger.info(f"Query '{query}' produced zero valid search tokens.")
        return []

    # 4. Execute BM25 Retrieval
    manager = get_bm25_manager(records_path=records_path)
    bm25_model, sub_records, _ = manager.get_index_for_collections(collections_to_query)

    if not sub_records:
        return []

    scores = bm25_model.get_scores(search_tokens)

    # 5. Filter Positive Matches & Rank
    candidate_records: List[Tuple[float, Dict[str, Any]]] = []
    for score, rec in zip(scores, sub_records):
        score_val = float(score)
        # Discard non-matching or negative scores
        if score_val > 0.0:
            candidate_records.append((score_val, rec))

    if not candidate_records:
        return []

    # Sort candidates globally by BM25 score (Descending: higher is more relevant)
    candidate_records.sort(key=lambda x: x[0], reverse=True)
    selected_records = candidate_records[:clamped_top_k]

    # 6. Format Structured Results
    results: List[Dict[str, Any]] = []

    def parse_page(val: Any) -> Optional[int]:
        if val is None or val == "":
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    for rank, (score_val, rec) in enumerate(selected_records, start=1):
        rec_id = rec.get("embedding_record_id") or rec.get("chunk_id", "")
        parent_id = rec.get("parent_chunk_id") or rec.get("chunk_id") or rec_id

        formatted_result = {
            "retrieval_rank": rank,
            "retrieval_method": "BM25",
            "embedding_record_id": rec_id,
            "chunk_id": rec_id,
            "parent_chunk_id": parent_id,
            "document_id": rec.get("document_id", ""),
            "document_title": rec.get("document_title", ""),
            "document_type": rec.get("document_type", ""),
            "provision_type": rec.get("provision_type", ""),
            "provision_number": rec.get("provision_number", ""),
            "provision_heading": rec.get("provision_heading", ""),
            "exact_original_text": rec.get("text", ""),
            "source_url": rec.get("source_url", ""),
            "original_filename": rec.get("original_filename", ""),
            "pdf_page_start": parse_page(rec.get("pdf_page_start")),
            "pdf_page_end": parse_page(rec.get("pdf_page_end")),
            "applicability_status": rec.get("applicability_status", ""),
            "effective_from": rec.get("effective_from") or None,
            "legal_review_status": rec.get("legal_review_status", "REQUIRES_LEGAL_REVIEW"),
            "collection_name": rec.get("collection_name", COLLECTION_CURRENT_LAW),
            "bm25_score": round(score_val, 4),
            "original_query": query,
            "expanded_search_terms": expanded_terms,
        }
        results.append(formatted_result)

    return results
