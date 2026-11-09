"""
Semantic Legal Retriever Module for Nyaya Saathi.

Blueprint Phase 4 — Step 14: Semantic Search Using Multilingual E5 and ChromaDB.
Provides:
1. Validated semantic search interface over persistent ChromaDB collections.
2. Query embedding with mandatory E5 prefix ('query: ') using intfloat/multilingual-e5-small.
3. Strict collection routing:
   - nyaya_saathi_current_law: In-force statutory legislation (default).
   - nyaya_saathi_procedural_guidance: e-Jagriti user manual and e-filing workflow.
   - nyaya_saathi_future_law: 2026 E-Commerce Amendment (effective 2027-01-01).
4. Strict temporal filtering using explicit transaction/as-of dates.
5. Structured retrieval outputs with complete statutory provenance metadata and distances.
"""

from datetime import date, datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np

from src.embeddings import (
    EMBEDDING_DIMENSION,
    format_query_for_embedding,
    get_embedding_model,
)
from src.vector_store import (
    COLLECTION_CURRENT_LAW,
    COLLECTION_FUTURE_LAW,
    COLLECTION_PROCEDURAL_GUIDANCE,
    DEFAULT_CHROMA_DIR,
    VectorStoreManager,
)

logger = logging.getLogger(__name__)

# Date boundary for future-effective law (2026 E-Commerce Amendment)
FUTURE_LAW_EFFECTIVE_DATE = date(2027, 1, 1)


def parse_date(date_val: Optional[Union[str, date, datetime]]) -> Optional[date]:
    """Parses date inputs into a datetime.date object safely."""
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
        # Try ISO formats: YYYY-MM-DD or DD/MM/YYYY
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue
    return None


def embed_query(query: str) -> np.ndarray:
    """
    Generates a 384-dimensional L2-normalized query vector using the E5 model.
    Applies the mandatory 'query: ' prefix convention.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        raise ValueError("Cannot embed an empty or whitespace query.")

    prefixed_query = format_query_for_embedding(cleaned_query)
    model = get_embedding_model()

    # Encode with sentence-transformers normalize_embeddings=True
    vector = model.encode(prefixed_query, normalize_embeddings=True, show_progress_bar=False)
    vector = np.array(vector, dtype=np.float32)

    if vector.shape != (EMBEDDING_DIMENSION,):
        raise ValueError(
            f"Query embedding dimension mismatch: Expected ({EMBEDDING_DIMENSION},), got {vector.shape}"
        )
    if not np.all(np.isfinite(vector)):
        raise ValueError("Query embedding contains non-finite values (NaN or Inf).")

    return vector


def semantic_search(
    query: str,
    top_k: int = 8,
    include_procedural: bool = False,
    include_future: bool = False,
    transaction_date: Optional[Union[str, date, datetime]] = None,
    as_of_date: Optional[Union[str, date, datetime]] = None,
    persist_dir: Path = DEFAULT_CHROMA_DIR,
) -> List[Dict[str, Any]]:
    """
    Executes semantic nearest-neighbour search over persistent ChromaDB collections.
    
    Arguments:
        query: User dispute search inquiry (English, Hindi, or Hinglish).
        top_k: Number of ranked records to return (constrained between 1 and 10, default: 8).
        include_procedural: Whether to search official e-Jagriti / portal procedural guides.
        include_future: Explicit override to include future-effective statutory amendments.
        transaction_date: Date of dispute transaction (enables future law if >= 2027-01-01).
        as_of_date: Reference evaluation date (enables future law if >= 2027-01-01).
        persist_dir: Local Chroma database persistence directory.

    Returns:
        Ranked list of structured result dictionaries with provenance metadata and distance.
    """
    if not isinstance(query, str) or not query.strip():
        logger.warning("Empty or invalid query submitted to semantic_search.")
        return []

    # Enforce top_k boundaries
    clamped_top_k = max(1, min(10, int(top_k)))

    # 1. Determine Collection Routing based on intent and temporal dates
    t_date = parse_date(transaction_date)
    a_date = parse_date(as_of_date)

    # Future law is eligible if explicitly requested OR reference date >= 2027-01-01
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

    # 2. Compute Normalized Query Vector
    query_vector = embed_query(query)

    # 3. Query ChromaDB Collections
    manager = VectorStoreManager(persist_dir=persist_dir)
    candidate_records: List[Dict[str, Any]] = []

    for col_name in collections_to_query:
        coll = manager.get_or_create_collection(col_name)
        if coll.count() == 0:
            continue

        # Query collection for top_k results
        query_res = coll.query(
            query_embeddings=[query_vector.tolist()],
            n_results=min(clamped_top_k, coll.count()),
            include=["documents", "metadatas", "distances"],
        )

        ids = query_res["ids"][0] if query_res.get("ids") else []
        docs = query_res["documents"][0] if query_res.get("documents") else []
        metas = query_res["metadatas"][0] if query_res.get("metadatas") else []
        distances = query_res["distances"][0] if query_res.get("distances") else []

        for cid, doc, meta, dist in zip(ids, docs, metas, distances):
            candidate_records.append({
                "collection_name": col_name,
                "record_id": cid,
                "document": doc,
                "metadata": meta,
                "distance": float(dist),
            })

    if not candidate_records:
        return []

    # 4. Sort Candidates Globally by Cosine Distance (Ascending: 0.0 is closest)
    candidate_records.sort(key=lambda x: x["distance"])
    selected_records = candidate_records[:clamped_top_k]

    # 5. Format Structured Results
    results: List[Dict[str, Any]] = []
    for rank, item in enumerate(selected_records, start=1):
        m = item["metadata"]
        rec_id = item["record_id"]
        parent_id = m.get("parent_chunk_id") or m.get("chunk_id") or rec_id

        # Coerce page numbers to integers if present
        def parse_page(val: Any) -> Optional[int]:
            if val is None or val == "":
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        formatted_result = {
            "retrieval_rank": rank,
            "chunk_id": rec_id,
            "embedding_record_id": rec_id,
            "parent_chunk_id": parent_id,
            "document_id": m.get("document_id", ""),
            "document_title": m.get("document_title", ""),
            "document_type": m.get("document_type", ""),
            "provision_type": m.get("provision_type", ""),
            "provision_number": m.get("provision_number", ""),
            "provision_heading": m.get("provision_heading", ""),
            "exact_original_text": item["document"],
            "source_url": m.get("source_url", ""),
            "original_filename": m.get("original_filename", ""),
            "pdf_page_start": parse_page(m.get("pdf_page_start")),
            "pdf_page_end": parse_page(m.get("pdf_page_end")),
            "applicability_status": m.get("applicability_status", ""),
            "effective_from": m.get("effective_from") or None,
            "legal_review_status": m.get("legal_review_status", "REQUIRES_LEGAL_REVIEW"),
            "collection_name": item["collection_name"],
            "retrieval_method": "SEMANTIC_MULTILINGUAL_E5",
            "distance": round(item["distance"], 4),
        }
        results.append(formatted_result)

    return results
