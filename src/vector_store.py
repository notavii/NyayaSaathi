"""
Persistent ChromaDB Vector Store Module for Nyaya Saathi.

Step 13: Local Persistent Vector Storage.
Manages three strictly segregated collections:
1. 'nyaya_saathi_current_law': In-force statutory legal sources (CPA 2019, rules, corrigenda, 2021 amendment).
2. 'nyaya_saathi_procedural_guidance': Official procedural guides and portals (e-Jagriti CC filing manual).
3. 'nyaya_saathi_future_law': Future-effective statutory amendments (2026 E-Commerce Amendment, effective 2027-01-01).

Guarantees:
- Strict segregation of substantive statutes, procedural guides, and future amendments.
- Complete preservation of statutory provenance metadata on every vector record.
- Idempotent indexing via upsert operations with zero duplicates.
- Stale record pruning without corrupting other collections.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set
import chromadb
from chromadb.api.models.Collection import Collection

# Authoritative Collection Names
COLLECTION_CURRENT_LAW = "nyaya_saathi_current_law"
COLLECTION_PROCEDURAL_GUIDANCE = "nyaya_saathi_procedural_guidance"
COLLECTION_FUTURE_LAW = "nyaya_saathi_future_law"

ALL_COLLECTIONS = [
    COLLECTION_CURRENT_LAW,
    COLLECTION_PROCEDURAL_GUIDANCE,
    COLLECTION_FUTURE_LAW,
]

# Default local database storage path (portable across Windows & Linux)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHROMA_DIR = PROJECT_ROOT / "data" / "legal_sources" / "chroma_db"

# Required Metadata Keys for downstream legal citation and filtering
REQUIRED_METADATA_KEYS = [
    "embedding_record_id",
    "parent_chunk_id",
    "chunk_id",
    "document_id",
    "document_title",
    "document_type",
    "provision_type",
    "provision_number",
    "provision_heading",
    "parent_provision",
    "segment_index",
    "total_segments",
    "is_child_segment",
    "source_url",
    "original_filename",
    "pdf_page_start",
    "pdf_page_end",
    "publication_date",
    "effective_from",
    "effective_to",
    "applicability_status",
    "retrieval_eligible",
    "extraction_status",
    "extraction_integrity_status",
    "legal_review_status",
]


def sanitize_metadata(record_or_chunk: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms record/chunk metadata into Chroma-compatible primitive values (str, int, float, bool).
    Converts None values to empty strings to satisfy ChromaDB Rust bindings.
    """
    sanitized: Dict[str, Any] = {}
    for key in REQUIRED_METADATA_KEYS:
        val = record_or_chunk.get(key)
        if val is None:
            # Fallbacks for record vs chunk key naming
            if key == "embedding_record_id" and "chunk_id" in record_or_chunk:
                sanitized[key] = str(record_or_chunk["chunk_id"])
            elif key == "parent_chunk_id" and "chunk_id" in record_or_chunk:
                sanitized[key] = str(record_or_chunk["chunk_id"])
            elif key == "chunk_id" and "embedding_record_id" in record_or_chunk:
                sanitized[key] = str(record_or_chunk["embedding_record_id"])
            elif key == "segment_index":
                sanitized[key] = 1
            elif key == "total_segments":
                sanitized[key] = 1
            elif key == "is_child_segment":
                sanitized[key] = False
            else:
                sanitized[key] = ""
        elif isinstance(val, (str, int, float, bool)):
            sanitized[key] = val
        else:
            sanitized[key] = str(val)

    # Carry forward amendment/corrigendum linkage if present
    if "amends_document_id" in record_or_chunk and record_or_chunk["amends_document_id"] is not None:
        sanitized["amends_document_id"] = str(record_or_chunk["amends_document_id"])
    else:
        sanitized["amends_document_id"] = ""

    return sanitized


class VectorStoreManager:
    """Manages persistent ChromaDB collections for Nyaya Saathi."""

    def __init__(self, persist_dir: Path = DEFAULT_CHROMA_DIR):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))

    def get_or_create_collection(self, name: str) -> Collection:
        """Retrieves or creates a collection by name with cosine distance space."""
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine", "description": f"Nyaya Saathi collection: {name}"},
        )

    def get_current_law_collection(self) -> Collection:
        """Returns the nyaya_saathi_current_law collection (statutory legislation in force)."""
        return self.get_or_create_collection(COLLECTION_CURRENT_LAW)

    def get_procedural_guidance_collection(self) -> Collection:
        """Returns the nyaya_saathi_procedural_guidance collection (user manuals and guides)."""
        return self.get_or_create_collection(COLLECTION_PROCEDURAL_GUIDANCE)

    def get_future_law_collection(self) -> Collection:
        """Returns the nyaya_saathi_future_law collection (future-effective enactments)."""
        return self.get_or_create_collection(COLLECTION_FUTURE_LAW)

    def upsert_records(
        self,
        collection_name: str,
        records: Sequence[Dict[str, Any]],
        embeddings: Sequence[Sequence[float]],
    ) -> int:
        """
        Idempotently upserts derived records into the specified collection.
        Uses embedding_record_id (or chunk_id) as the unique persistent vector ID.
        """
        if not records:
            return 0
        if len(records) != len(embeddings):
            raise ValueError(
                f"Mismatch: {len(records)} records provided but {len(embeddings)} embeddings given."
            )

        collection = self.get_or_create_collection(collection_name)

        ids: List[str] = [
            str(r.get("embedding_record_id") or r.get("chunk_id")) for r in records
        ]
        documents: List[str] = [r["text"] for r in records]
        metadatas: List[Dict[str, Any]] = [sanitize_metadata(r) for r in records]
        embedding_vectors: List[List[float]] = [
            list(map(float, vec)) for vec in embeddings
        ]

        # Chroma upsert is natively idempotent
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embedding_vectors,
        )

        return len(ids)

    def upsert_chunks(
        self,
        collection_name: str,
        chunks: Sequence[Dict[str, Any]],
        embeddings: Sequence[Sequence[float]],
    ) -> int:
        """Backward-compatible wrapper for upsert_records."""
        return self.upsert_records(collection_name, chunks, embeddings)

    def prune_stale_records(self, collection_name: str, active_ids: Set[str]) -> int:
        """
        Removes records from the collection that are no longer present in the active dataset.
        Ensures idempotency when documents or chunks are renamed or removed.
        """
        collection = self.get_or_create_collection(collection_name)
        existing_data = collection.get()
        existing_ids = set(existing_data["ids"]) if existing_data and "ids" in existing_data else set()

        stale_ids = existing_ids - active_ids
        if stale_ids:
            collection.delete(ids=list(stale_ids))
            return len(stale_ids)
        return 0

    def get_collection_counts(self) -> Dict[str, int]:
        """Returns record counts for all three segregated collections."""
        return {
            COLLECTION_CURRENT_LAW: self.get_current_law_collection().count(),
            COLLECTION_PROCEDURAL_GUIDANCE: self.get_procedural_guidance_collection().count(),
            COLLECTION_FUTURE_LAW: self.get_future_law_collection().count(),
        }

    def reset_collection(self, collection_name: str) -> None:
        """Deletes and recreates a collection cleanly."""
        try:
            self.client.delete_collection(name=collection_name)
        except Exception:
            pass
        self.get_or_create_collection(collection_name)
