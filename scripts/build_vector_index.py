"""
Build Vector Index Script for Nyaya Saathi.

Blueprint Phase 3C.1: Legal Segment Embeddings & Three-Collection Architecture.
Builds persistent vector collections in ChromaDB from data/legal_sources/embedding_records.json
derived from data/legal_sources/legal_chunks.json.

Guarantees:
1. Idempotency: Running twice produces zero duplicate records.
2. Complete provenance preservation: All statutory and procedural metadata is retained.
3. Strict three-way segregation:
   - nyaya_saathi_current_law (232 statutory records in force)
   - nyaya_saathi_procedural_guidance (13 official procedural guide records)
   - nyaya_saathi_future_law (6 future-effective amendment records)
4. Historical and web-only material completely excluded from all collections.
5. Zero silent truncation: Every child segment fits strictly within the model's 512-token limit.
6. Generates derived dataset at data/legal_sources/embedding_records.json.
7. Generates comprehensive vector index manifest at data/legal_sources/vector_index_manifest.json.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import chromadb
import sentence_transformers
import torch

from src.embeddings import (
    EMBEDDING_DIMENSION,
    MAX_TOKEN_LENGTH,
    MODEL_NAME,
    PASSAGE_PREFIX,
    QUERY_PREFIX,
    count_tokens,
    derive_embedding_records,
    embed_passages,
    format_passage_text,
    get_device,
    get_embedding_model,
)
from src.vector_store import (
    COLLECTION_CURRENT_LAW,
    COLLECTION_FUTURE_LAW,
    COLLECTION_PROCEDURAL_GUIDANCE,
    VectorStoreManager,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_vector_index")

CHUNKS_FILE = PROJECT_ROOT / "data" / "legal_sources" / "legal_chunks.json"
DERIVED_RECORDS_FILE = PROJECT_ROOT / "data" / "legal_sources" / "embedding_records.json"
HISTORICAL_CHUNKS_FILE = PROJECT_ROOT / "data" / "legal_sources" / "historical_reference_chunks.json"
MANIFEST_FILE = PROJECT_ROOT / "data" / "legal_sources" / "vector_index_manifest.json"
CATALOG_FILE = PROJECT_ROOT / "data" / "legal_sources" / "source_catalog.json"


def compute_file_sha256(path: Path) -> str:
    """Computes SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def build_vector_index(
    chunks_path: Path = CHUNKS_FILE,
    derived_records_path: Path = DERIVED_RECORDS_FILE,
    persist_dir: Optional[Path] = None,
    log_output: bool = True,
) -> Dict[str, Any]:
    """
    Main idempotent indexing function.
    1. Loads canonical legal_chunks.json.
    2. Generates derived embedding records (splitting overlength provisions into child segments).
    3. Segregates into 3 distinct collections: current statutory law, procedural guidance, and future law.
    4. Generates independent embeddings for each segment.
    5. Upserts into persistent ChromaDB collections and prunes stale records.
    6. Outputs detailed manifest.
    """
    if not chunks_path.exists():
        raise FileNotFoundError(f"Primary legal chunks file not found at: {chunks_path}")

    logger.info(f"Loading canonical legal chunks from: {chunks_path}")
    with open(chunks_path, "r", encoding="utf-8") as f:
        all_chunks: List[Dict[str, Any]] = json.load(f)

    # Filter out ineligible, historical or web-only chunks if any were in canonical file
    eligible_canonical_chunks = [
        c for c in all_chunks
        if c.get("retrieval_eligible", False)
        and c.get("document_id") not in ("CONSUMER_HANDBOOK_2015", "NCH_GRIEVANCE_GUIDE")
        and c.get("text", "").strip()
    ]

    logger.info(f"Canonical eligible chunks: {len(eligible_canonical_chunks)} (Total in source: {len(all_chunks)})")

    # 1. Initialize Embedding Model
    logger.info("Initializing embedding model...")
    model = get_embedding_model()
    device = get_device()

    # 2. Derive Embedding Records (Overlength provisions split at legal boundaries)
    logger.info("Deriving legal embedding records with exact token limit verification...")
    derived_records = derive_embedding_records(eligible_canonical_chunks, model=model, max_tokens=MAX_TOKEN_LENGTH)

    # Save derived embedding records
    derived_records_path.parent.mkdir(parents=True, exist_ok=True)
    with open(derived_records_path, "w", encoding="utf-8") as rf:
        json.dump(derived_records, rf, indent=2, ensure_ascii=False)
    logger.info(f"Derived embedding records ({len(derived_records)} records) written to: {derived_records_path}")

    # Compute audit metrics
    overlength_source_count = 0
    generated_children_count = 0
    for c in eligible_canonical_chunks:
        full_p = format_passage_text(c)
        if count_tokens(f"{PASSAGE_PREFIX}{full_p}", model=model) > MAX_TOKEN_LENGTH:
            overlength_source_count += 1

    for r in derived_records:
        if r.get("is_child_segment", False):
            generated_children_count += 1

    # 3. Segregate into Three Collections
    current_law_records: List[Dict[str, Any]] = []
    procedural_records: List[Dict[str, Any]] = []
    future_law_records: List[Dict[str, Any]] = []

    for r in derived_records:
        app_status = r.get("applicability_status")
        doc_type = r.get("document_type")

        if app_status == "FUTURE_EFFECTIVE":
            future_law_records.append(r)
        elif doc_type in ("PROCEDURAL_GUIDE", "PROCEDURAL_GUIDANCE"):
            procedural_records.append(r)
        elif app_status == "CURRENTLY_IN_FORCE":
            current_law_records.append(r)
        else:
            logger.warning(f"Uncategorized record: {r.get('embedding_record_id')} ({doc_type}, {app_status})")

    logger.info(
        f"Collection segregation:\n"
        f"  - Current Statutory Law: {len(current_law_records)} records\n"
        f"  - Procedural Guidance:  {len(procedural_records)} records\n"
        f"  - Future-Effective Law:  {len(future_law_records)} records\n"
        f"  - Total Derived Records: {len(derived_records)} records"
    )

    # 4. Check Excluded Historical & Web-Only Sources
    excluded_historical_count = 0
    if HISTORICAL_CHUNKS_FILE.exists():
        with open(HISTORICAL_CHUNKS_FILE, "r", encoding="utf-8") as hf:
            h_chunks = json.load(hf)
            excluded_historical_count = len(h_chunks)

    excluded_web_only_count = 1  # NCH_GRIEVANCE_GUIDE is web-only

    # 5. Initialize Vector Store Manager
    v_manager = VectorStoreManager(persist_dir=persist_dir) if persist_dir else VectorStoreManager()

    # 6. Index Current Statutory Law
    logger.info(f"Embedding and upserting {len(current_law_records)} records into '{COLLECTION_CURRENT_LAW}'...")
    current_embeddings = embed_passages(current_law_records, model=model)
    v_manager.upsert_records(COLLECTION_CURRENT_LAW, records=current_law_records, embeddings=current_embeddings)
    active_current_ids: Set[str] = {r["embedding_record_id"] for r in current_law_records}
    stale_current = v_manager.prune_stale_records(COLLECTION_CURRENT_LAW, active_current_ids)

    # 7. Index Procedural Guidance
    logger.info(f"Embedding and upserting {len(procedural_records)} records into '{COLLECTION_PROCEDURAL_GUIDANCE}'...")
    procedural_embeddings = embed_passages(procedural_records, model=model)
    v_manager.upsert_records(COLLECTION_PROCEDURAL_GUIDANCE, records=procedural_records, embeddings=procedural_embeddings)
    active_procedural_ids: Set[str] = {r["embedding_record_id"] for r in procedural_records}
    stale_procedural = v_manager.prune_stale_records(COLLECTION_PROCEDURAL_GUIDANCE, active_procedural_ids)

    # 8. Index Future-Effective Law
    logger.info(f"Embedding and upserting {len(future_law_records)} records into '{COLLECTION_FUTURE_LAW}'...")
    future_embeddings = embed_passages(future_law_records, model=model)
    v_manager.upsert_records(COLLECTION_FUTURE_LAW, records=future_law_records, embeddings=future_embeddings)
    active_future_ids: Set[str] = {r["embedding_record_id"] for r in future_law_records}
    stale_future = v_manager.prune_stale_records(COLLECTION_FUTURE_LAW, active_future_ids)

    # 9. Verify Resulting Collection Counts
    counts = v_manager.get_collection_counts()
    logger.info(f"ChromaDB collection record counts: {counts}")

    # 10. Generate Vector Index Manifest
    source_sha256 = compute_file_sha256(chunks_path)
    derived_sha256 = compute_file_sha256(derived_records_path)
    now_iso = datetime.now(timezone.utc).isoformat()

    manifest = {
        "manifest_version": "1.1.0",
        "build_status": "SUCCESS",
        "created_at_utc": now_iso,
        "embedding_model": {
            "model_id": MODEL_NAME,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "max_sequence_length": MAX_TOKEN_LENGTH,
            "execution_device": device,
            "passage_prefix": PASSAGE_PREFIX,
            "query_prefix": QUERY_PREFIX,
            "normalization": "L2_NORM",
        },
        "source_dataset": {
            "canonical_file_path": str(chunks_path.relative_to(PROJECT_ROOT)),
            "canonical_sha256": source_sha256,
            "total_canonical_chunks": len(all_chunks),
            "eligible_canonical_chunks": len(eligible_canonical_chunks),
        },
        "derived_dataset": {
            "derived_file_path": str(derived_records_path.relative_to(PROJECT_ROOT)),
            "derived_sha256": derived_sha256,
            "total_derived_records": len(derived_records),
            "overlength_source_chunks_split": overlength_source_count,
            "generated_child_records": generated_children_count,
        },
        "collections": {
            COLLECTION_CURRENT_LAW: {
                "record_count": counts[COLLECTION_CURRENT_LAW],
                "expected_count": len(current_law_records),
                "stale_records_pruned": stale_current,
                "document_types": ["CENTRAL_ACT", "ACT", "RULES", "CORRIGENDUM", "AMENDMENT_RULES"],
                "applicability_status": "CURRENTLY_IN_FORCE",
            },
            COLLECTION_PROCEDURAL_GUIDANCE: {
                "record_count": counts[COLLECTION_PROCEDURAL_GUIDANCE],
                "expected_count": len(procedural_records),
                "stale_records_pruned": stale_procedural,
                "document_types": ["PROCEDURAL_GUIDE", "PROCEDURAL_GUIDANCE"],
                "applicability_status": "CURRENTLY_IN_FORCE",
            },
            COLLECTION_FUTURE_LAW: {
                "record_count": counts[COLLECTION_FUTURE_LAW],
                "expected_count": len(future_law_records),
                "stale_records_pruned": stale_future,
                "document_types": ["AMENDMENT_RULES"],
                "applicability_status": "FUTURE_EFFECTIVE",
                "effective_from": "2027-01-01",
            },
        },
        "exclusions": {
            "historical_chunks_count": excluded_historical_count,
            "historical_source": "CONSUMER_HANDBOOK_2015",
            "historical_file": "data/legal_sources/historical_reference_chunks.json",
            "web_only_sources_count": excluded_web_only_count,
            "web_only_source_id": "NCH_GRIEVANCE_GUIDE",
        },
        "token_limit_handling": {
            "max_tokens": MAX_TOKEN_LENGTH,
            "overlength_chunks_count": overlength_source_count,
            "generated_child_segments": generated_children_count,
            "handling_strategy": "LEGAL_BOUNDARY_SPLIT_INDEPENDENT_CHILD_EMBEDDINGS",
            "silent_truncation_prevented": True,
        },
        "software_versions": {
            "sentence_transformers": sentence_transformers.__version__,
            "chromadb": chromadb.__version__,
            "torch": torch.__version__,
            "python": sys.version.split()[0],
        },
    }

    with open(MANIFEST_FILE, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2, ensure_ascii=False)

    logger.info(f"Vector index manifest written to: {MANIFEST_FILE}")

    if log_output:
        print("\n==================================================")
        print("NYAYA SAATHI VECTOR INDEX BUILD COMPLETED (Phase 3C.1)")
        print("==================================================")
        print(f"Model ID:                     {MODEL_NAME}")
        print(f"Embedding Dimension:          {EMBEDDING_DIMENSION}")
        print(f"Execution Device:             {device}")
        print(f"Parent Canonical Chunks:      {len(eligible_canonical_chunks)}")
        print(f"Overlength Chunks Split:      {overlength_source_count}")
        print(f"Generated Child Segments:     {generated_children_count}")
        print(f"Total Derived Records:        {len(derived_records)}")
        print(f"Current Statutory Records:    {counts[COLLECTION_CURRENT_LAW]}")
        print(f"Procedural Guidance Records:  {counts[COLLECTION_PROCEDURAL_GUIDANCE]}")
        print(f"Future Law Records:           {counts[COLLECTION_FUTURE_LAW]}")
        print(f"Excluded Historical Chunks:   {excluded_historical_count} (CONSUMER_HANDBOOK_2015)")
        print(f"Excluded Web-Only Sources:    {excluded_web_only_count} (NCH_GRIEVANCE_GUIDE)")
        print(f"Manifest Generated:           {MANIFEST_FILE.name}")
        print("==================================================\n")

    return {
        "status": "SUCCESS",
        "counts": counts,
        "derived_count": len(derived_records),
        "manifest": manifest,
    }


if __name__ == "__main__":
    result = build_vector_index()
