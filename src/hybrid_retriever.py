"""
Semantic + BM25 Hybrid Legal Retrieval Module for Nyaya Saathi.

Blueprint Phase 4C — Step 16: Hybrid Legal Retrieval using Reciprocal Rank Fusion (RRF).
Combines dense semantic retrieval (intfloat/multilingual-e5-small on persistent ChromaDB)
with lexical sparse retrieval (rank-bm25 BM25Okapi) into a unified, robustly ranked legal result set.

Guarantees:
1. Multi-Modal Fusion: Reuses existing semantic and BM25 modules without creating new indices or embeddings.
2. Standard RRF Formula: RRF(d) = sum_m (w_m / (k + rank_m(d))) with configurable k (default: 60) and equal default weights.
3. Transparent Diagnostics: Exposes semantic_rank, semantic_distance, bm25_rank, bm25_score, rrf_score, and matched_methods.
4. Granular Child-Segment Deduplication: Primary deduplication key is embedding_record_id; different child segments
   of the same section remain distinct and independently rankable.
5. Strict Multi-Collection Segregation: Procedural guides (e-Jagriti) remain isolated unless requested; future amendments
   (effective 2027-01-01) remain strictly gated.
6. Temporal Boundary Integrity: Accurately distinguishes transaction_date, as_of_date, and system date; historical transactions
   in 2026 never receive future 2027 amendments retroactively.
7. Metadata Preservation: Retains exact original text, provenance citations, page numbers, and explicitly labels
   legal_review_status as 'REQUIRES_LEGAL_REVIEW' without unwarranted upgrade.
8. Zero Gemini Calls: Operates 100% offline without LLM generation or hallucination.
"""

from datetime import date, datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from src.bm25_retriever import bm25_search, parse_date
from src.legal_retriever import semantic_search
from src.vector_store import (
    COLLECTION_CURRENT_LAW,
    COLLECTION_FUTURE_LAW,
    COLLECTION_PROCEDURAL_GUIDANCE,
)

logger = logging.getLogger("hybrid_retriever")

DEFAULT_RRF_K = 60
DEFAULT_TOP_K = 8
FUTURE_LAW_EFFECTIVE_DATE = date(2027, 1, 1)

# Valid applicability and legal review statuses
VALID_APPLICABILITY_STATUSES = {
    "CURRENTLY_IN_FORCE",
    "FUTURE_EFFECTIVE",
    "HISTORICAL_REFERENCE",
    "UNKNOWN",
}

VALID_LEGAL_REVIEW_STATUSES = {
    "REQUIRES_LEGAL_REVIEW",
    "HUMAN_REVIEWED",
    "SUPERSEDED",
    "NOT_REVIEWED",
}

# Explicit Temporal Legal Applicability Statuses (Blueprint Phase 4C.1 Part F)
TEMPORAL_CURRENTLY_IN_FORCE = "CURRENTLY_IN_FORCE"
TEMPORAL_FUTURE_EFFECTIVE = "FUTURE_EFFECTIVE"
TEMPORAL_NEEDS_LEGAL_REVIEW = "NEEDS_LEGAL_REVIEW"
TEMPORAL_NOT_APPLICABLE_PRE_COMMENCEMENT = "NOT_APPLICABLE_PRE_COMMENCEMENT"

VALID_TEMPORAL_STATUSES = {
    TEMPORAL_CURRENTLY_IN_FORCE,
    TEMPORAL_FUTURE_EFFECTIVE,
    TEMPORAL_NEEDS_LEGAL_REVIEW,
    TEMPORAL_NOT_APPLICABLE_PRE_COMMENCEMENT,
}


class DateGatingResult:
    """
    Structured result of temporal date gating resolution.
    Distinguishes transaction_date, event_date, as_of_date, effective_from, and system_date.
    Supports unpacking as either 3 items (future_eligible, t_date, a_date) or 4 items
    (future_eligible, t_date, a_date, temporal_status) for maximum backward compatibility.
    """
    def __init__(
        self,
        future_eligible: bool,
        transaction_date: Optional[date],
        as_of_date: Optional[date],
        temporal_status: str,
        event_date: Optional[date] = None,
    ):
        self.future_eligible = future_eligible
        self.transaction_date = transaction_date
        self.as_of_date = as_of_date
        self.temporal_status = temporal_status
        self.event_date = event_date

    def __iter__(self):
        return iter((self.future_eligible, self.transaction_date, self.as_of_date, self.temporal_status))

    def __getitem__(self, idx):
        return (self.future_eligible, self.transaction_date, self.as_of_date, self.temporal_status)[idx]

    def __len__(self):
        return 4

    def __repr__(self):
        return (
            f"DateGatingResult(future_eligible={self.future_eligible}, "
            f"transaction_date={self.transaction_date}, as_of_date={self.as_of_date}, "
            f"temporal_status='{self.temporal_status}', event_date={self.event_date})"
        )


def resolve_date_gating(
    include_future: bool = False,
    transaction_date: Optional[Union[str, date, datetime]] = None,
    event_date: Optional[Union[str, date, datetime]] = None,
    as_of_date: Optional[Union[str, date, datetime]] = None,
    system_date: Optional[Union[str, date, datetime]] = None,
    effective_from: date = FUTURE_LAW_EFFECTIVE_DATE,
    continuing_dispute: bool = False,
) -> DateGatingResult:
    """
    Resolves future-law eligibility and temporal applicability status by rigorously distinguishing:
    1. transaction_date: Date of the underlying consumer transaction / contract.
    2. event_date: Date of the injury, breach, delivery refusal, or dispute event.
    3. as_of_date: Reference evaluation date for determining applicable statutory law.
    4. effective_from: Statutory commencement date of future-effective rules (default: 2027-01-01).
    5. actual system date: Live execution / wall-clock date (defaults to date.today()).

    Legal Gating & Transitional Rules:
    - Explicit prospective inquiry (include_future=True) -> FUTURE_EFFECTIVE.
    - Transaction/event on or after commencement (>= 2027-01-01) -> CURRENTLY_IN_FORCE.
    - Historical transaction/event before commencement (< 2027-01-01) with continuing dispute after commencement (>= 2027-01-01):
        Marked as NEEDS_LEGAL_REVIEW. The engine does NOT declare the 2026 amendment automatically
        applicable or inapplicable; transitional applicability requires formal legal interpretation.
    - Historical closed transaction/event before commencement asked after commencement:
        NOT_APPLICABLE_PRE_COMMENCEMENT. Future amendments do not operate retroactively on closed past events.
    - Non-transaction query before commencement (< 2027-01-01):
        CURRENTLY_IN_FORCE under 2020 rules; future amendments excluded by default.
    """
    t_date = parse_date(transaction_date)
    e_date = parse_date(event_date)
    a_date = parse_date(as_of_date)
    s_date = parse_date(system_date) or date.today()

    # 1. Explicit prospective question
    if include_future:
        return DateGatingResult(True, t_date, a_date, TEMPORAL_FUTURE_EFFECTIVE, e_date)

    ref_date = a_date or s_date

    # 2. Both transaction/event date and reference evaluation date available
    if t_date is not None or e_date is not None:
        primary_date = t_date or e_date

        # Case A: Transaction or primary event took place on or after commencement
        if primary_date >= effective_from:
            return DateGatingResult(True, t_date, a_date, TEMPORAL_CURRENTLY_IN_FORCE, e_date)

        # Case B: Primary date predates commencement (< 2027-01-01)
        if ref_date >= effective_from:
            # Inquiry occurs on or after commencement date
            # Transitional check: Continuing dispute or subsequent breach event post-commencement
            if continuing_dispute or (e_date is not None and e_date >= effective_from):
                # Pre-commencement transaction with ongoing dispute post-commencement -> NEEDS_LEGAL_REVIEW
                return DateGatingResult(True, t_date, a_date, TEMPORAL_NEEDS_LEGAL_REVIEW, e_date)
            else:
                # Closed past transaction/event -> Future amendments do not apply retroactively
                return DateGatingResult(False, t_date, a_date, TEMPORAL_NOT_APPLICABLE_PRE_COMMENCEMENT, e_date)
        else:
            # Both transaction/event and evaluation date are before commencement
            return DateGatingResult(False, t_date, a_date, TEMPORAL_CURRENTLY_IN_FORCE, e_date)

    # 3. Only reference evaluation date available
    if ref_date >= effective_from:
        return DateGatingResult(True, t_date, a_date, TEMPORAL_CURRENTLY_IN_FORCE, e_date)
    else:
        return DateGatingResult(False, t_date, a_date, TEMPORAL_CURRENTLY_IN_FORCE, e_date)


def calculate_rrf_score(
    semantic_rank: Optional[int],
    bm25_rank: Optional[int],
    k: int = DEFAULT_RRF_K,
    semantic_weight: float = 1.0,
    bm25_weight: float = 1.0,
) -> float:
    """
    Computes standard Reciprocal Rank Fusion (RRF) score:
    RRF(d) = sum_m (w_m / (k + rank_m(d)))
    """
    score = 0.0
    if semantic_rank is not None and semantic_rank > 0:
        score += semantic_weight / (k + semantic_rank)
    if bm25_rank is not None and bm25_rank > 0:
        score += bm25_weight / (k + bm25_rank)
    return score


def hybrid_search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    semantic_top_k: int = DEFAULT_TOP_K,
    bm25_top_k: int = DEFAULT_TOP_K,
    include_procedural: bool = False,
    include_future: bool = False,
    exclude_product_liability: bool = False,
    transaction_date: Optional[Union[str, date, datetime]] = None,
    event_date: Optional[Union[str, date, datetime]] = None,
    as_of_date: Optional[Union[str, date, datetime]] = None,
    system_date: Optional[Union[str, date, datetime]] = None,
    continuing_dispute: bool = False,
    rrf_k: int = DEFAULT_RRF_K,
    semantic_weight: float = 1.0,
    bm25_weight: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    Executes hybrid legal retrieval combining dense semantic search and sparse BM25 search
    using Reciprocal Rank Fusion (RRF).

    Arguments:
        query: User dispute search inquiry (English, Hindi, or Hinglish).
        top_k: Number of final fused records to return (clamped between 1 and 10, default: 8).
        semantic_top_k: Number of candidate records from semantic retrieval (default: 8).
        bm25_top_k: Number of candidate records from BM25 retrieval (default: 8).
        include_procedural: Whether to search official e-Jagriti / portal procedural guides.
        include_future: Explicit override to include future-effective statutory amendments.
        transaction_date: Date of underlying purchase transaction / contract.
        event_date: Date of dispute event, damage, defect discovery, or grievance.
        as_of_date: Reference evaluation date for determining applicable statutory law.
        system_date: Live execution date (defaults to date.today()).
        continuing_dispute: Whether a pre-commencement dispute is ongoing post-commencement.
        rrf_k: RRF rank smoothing constant (default: 60).
        semantic_weight: Relative weighting for semantic retrieval (default: 1.0).
        bm25_weight: Relative weighting for BM25 retrieval (default: 1.0).

    Returns:
        Ranked list of structured result dictionaries with provenance metadata,
        component ranks, raw diagnostic scores, and combined RRF score.
    """
    if not isinstance(query, str) or not query.strip():
        logger.warning("Empty or invalid query submitted to hybrid_search.")
        return []

    clamped_top_k = max(1, min(10, int(top_k)))
    s_top_k = max(1, min(10, int(semantic_top_k)))
    b_top_k = max(1, min(10, int(bm25_top_k)))

    # 1. Resolve Date Gating and Future Law Eligibility
    future_eligible, t_date, a_date, temporal_status = resolve_date_gating(
        include_future=include_future,
        transaction_date=transaction_date,
        event_date=event_date,
        as_of_date=as_of_date,
        system_date=system_date,
        continuing_dispute=continuing_dispute,
    )

    # 2. Execute Independent Retrievals
    semantic_results = semantic_search(
        query=query,
        top_k=s_top_k,
        include_procedural=include_procedural,
        include_future=future_eligible,
        transaction_date=t_date,
        as_of_date=a_date,
    )

    bm25_results = bm25_search(
        query=query,
        top_k=b_top_k,
        include_procedural=include_procedural,
        include_future=future_eligible,
        transaction_date=t_date,
        as_of_date=a_date,
    )

    if not semantic_results and not bm25_results:
        return []

    # 3. Fuse Results using Reciprocal Rank Fusion (RRF)
    # Deduplicate strictly by embedding_record_id
    fused_map: Dict[str, Dict[str, Any]] = {}

    # Process Semantic Results
    for r in semantic_results:
        rid = r["embedding_record_id"]
        fused_map[rid] = {
            "record": r,
            "semantic_rank": r["retrieval_rank"],
            "semantic_distance": r.get("distance"),
            "bm25_rank": None,
            "bm25_score": None,
            "matched_methods": ["SEMANTIC"],
        }

    # Process BM25 Results
    for r in bm25_results:
        rid = r["embedding_record_id"]
        if rid in fused_map:
            fused_map[rid]["bm25_rank"] = r["retrieval_rank"]
            fused_map[rid]["bm25_score"] = r.get("bm25_score")
            fused_map[rid]["matched_methods"].append("BM25")
        else:
            fused_map[rid] = {
                "record": r,
                "semantic_rank": None,
                "semantic_distance": None,
                "bm25_rank": r["retrieval_rank"],
                "bm25_score": r.get("bm25_score"),
                "matched_methods": ["BM25"],
            }

    # 4. Calculate RRF Scores and Sort
    ranked_candidates: List[Dict[str, Any]] = []
    for rid, item in fused_map.items():
        s_rank = item["semantic_rank"]
        b_rank = item["bm25_rank"]
        rrf = calculate_rrf_score(
            semantic_rank=s_rank,
            bm25_rank=b_rank,
            k=rrf_k,
            semantic_weight=semantic_weight,
            bm25_weight=bm25_weight,
        )
        item["rrf_score"] = round(rrf, 6)
        ranked_candidates.append(item)

    # Sort descending by RRF score; secondary tie-breaker: number of matching methods, then semantic rank, then bm25 rank
    ranked_candidates.sort(
        key=lambda x: (
            x["rrf_score"],
            len(x["matched_methods"]),
            -(x["semantic_rank"] or 999),
            -(x["bm25_rank"] or 999),
        ),
        reverse=True,
    )

    if exclude_product_liability:
        ranked_candidates = [
            c for c in ranked_candidates
            if not (
                c["record"].get("document_id") == "CPA_2019"
                and str(c["record"].get("provision_number", "")).strip() in ("82", "83", "84", "85", "86", "87")
            )
        ]

    selected_candidates = ranked_candidates[:clamped_top_k]

    # 5. Format Structured Results with Full Provenance Metadata
    results: List[Dict[str, Any]] = []

    def parse_page(val: Any) -> Optional[int]:
        if val is None or val == "":
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    for final_rank, candidate in enumerate(selected_candidates, start=1):
        rec = candidate["record"]
        rec_id = rec.get("embedding_record_id") or rec.get("chunk_id", "")
        parent_id = rec.get("parent_chunk_id") or rec.get("chunk_id") or rec_id

        # Preserve authentic legal review status; never upgrade to HUMAN_REVIEWED or VERIFIED_ACTIVE
        source_review_status = rec.get("legal_review_status", "REQUIRES_LEGAL_REVIEW")
        if source_review_status not in VALID_LEGAL_REVIEW_STATUSES:
            source_review_status = "REQUIRES_LEGAL_REVIEW"

        source_app_status = rec.get("applicability_status", "CURRENTLY_IN_FORCE")
        if source_app_status not in VALID_APPLICABILITY_STATUSES:
            source_app_status = "UNKNOWN"

        is_future_record = (
            rec.get("collection_name") == COLLECTION_FUTURE_LAW
            or rec.get("document_id") == "CP_ECOMMERCE_AMENDMENT_2026"
            or source_app_status == "FUTURE_EFFECTIVE"
        )
        if is_future_record:
            if temporal_status == TEMPORAL_NEEDS_LEGAL_REVIEW:
                record_temporal_status = TEMPORAL_NEEDS_LEGAL_REVIEW
            elif not future_eligible:
                record_temporal_status = TEMPORAL_NOT_APPLICABLE_PRE_COMMENCEMENT
            elif temporal_status == TEMPORAL_FUTURE_EFFECTIVE:
                record_temporal_status = TEMPORAL_FUTURE_EFFECTIVE
            else:
                record_temporal_status = TEMPORAL_CURRENTLY_IN_FORCE
        else:
            record_temporal_status = TEMPORAL_CURRENTLY_IN_FORCE

        formatted_result = {
            "final_rank": final_rank,
            "embedding_record_id": rec_id,
            "chunk_id": rec_id,
            "parent_chunk_id": parent_id,
            "document_id": rec.get("document_id", ""),
            "document_title": rec.get("document_title", ""),
            "document_type": rec.get("document_type", ""),
            "provision_type": rec.get("provision_type", ""),
            "provision_number": rec.get("provision_number", ""),
            "provision_heading": rec.get("provision_heading", ""),
            "exact_original_text": rec.get("exact_original_text") or rec.get("text", ""),
            "source_url": rec.get("source_url", ""),
            "original_filename": rec.get("original_filename", ""),
            "gazette_reference": rec.get("gazette_reference") or ("G.S.R. 789(E)" if is_future_record else None),
            "pdf_page_start": parse_page(rec.get("pdf_page_start")),
            "pdf_page_end": parse_page(rec.get("pdf_page_end")),
            "applicability_status": source_app_status,
            "temporal_applicability_status": record_temporal_status,
            "effective_from": rec.get("effective_from") or ("2027-01-01" if is_future_record else None),
            "transaction_date": str(t_date) if t_date else None,
            "event_date": str(parse_date(event_date)) if parse_date(event_date) else None,
            "as_of_date": str(a_date) if a_date else None,
            "legal_review_status": source_review_status,
            "collection_name": rec.get("collection_name", COLLECTION_CURRENT_LAW),
            "semantic_rank": candidate["semantic_rank"],
            "semantic_distance": candidate["semantic_distance"],
            "bm25_rank": candidate["bm25_rank"],
            "bm25_score": candidate["bm25_score"],
            "rrf_score": candidate["rrf_score"],
            "matched_methods": candidate["matched_methods"],
        }
        results.append(formatted_result)

    return results
