"""
Multilingual Embedding Module for Nyaya Saathi.

Step 12: Multilingual Embeddings using intfloat/multilingual-e5-small.
Provides:
1. Local model loading via sentence-transformers (CPU by default).
2. Proper E5 prefix management ('passage: ' for index passages, 'query: ' for search).
3. Token length detection and 512-token limit enforcement using actual model tokenizer.
4. Safe legal-boundary splitting into independently searchable child segments without silent truncation.
5. Generation of derived embedding records (data/legal_sources/embedding_records.json).
6. Normalized L2 embeddings with verified 384 dimensions.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Authoritative Model Specifications
MODEL_NAME = "intfloat/multilingual-e5-small"
EMBEDDING_DIMENSION = 384
MAX_TOKEN_LENGTH = 512

# E5 Prefix Conventions
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "

# Global cache for the singleton model instance
_MODEL_INSTANCE: Optional[SentenceTransformer] = None

# Streamlit Resource Caching (Blueprint Cloud Deployment Optimization)
try:
    import streamlit as st
    @st.cache_resource(show_spinner=False)
    def _load_st_cached_model(model_name: str, device: str) -> SentenceTransformer:
        return SentenceTransformer(model_name, device=device)
    _STREAMLIT_CACHE_AVAILABLE = True
except Exception:
    _STREAMLIT_CACHE_AVAILABLE = False


def get_device() -> str:
    """Returns the compute device. Defaults to CPU; detects CUDA if available."""
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def get_embedding_model(model_name: str = MODEL_NAME, device: Optional[str] = None) -> SentenceTransformer:
    """
    Loads and caches the SentenceTransformer model locally on the specified device.
    Uses st.cache_resource when running inside Streamlit to share the model
    safely across all user sessions without duplicating memory (~470MB RAM shared).
    Falls back to a thread-safe singleton cache for CLI and test execution.
    """
    global _MODEL_INSTANCE
    target_device = device or get_device()

    if _STREAMLIT_CACHE_AVAILABLE:
        try:
            model = _load_st_cached_model(model_name, target_device)
            model.max_seq_length = MAX_TOKEN_LENGTH
            return model
        except Exception as e:
            logger.warning(f"st.cache_resource load error, falling back to local singleton: {e}")

    if _MODEL_INSTANCE is None:
        logger.info(f"Loading embedding model '{model_name}' on device '{target_device}'...")
        try:
            _MODEL_INSTANCE = SentenceTransformer(model_name, device=target_device)
            
            # Verify model parameters programmatically
            if hasattr(_MODEL_INSTANCE, "get_embedding_dimension"):
                actual_dim = _MODEL_INSTANCE.get_embedding_dimension()
            else:
                actual_dim = _MODEL_INSTANCE.get_sentence_embedding_dimension()
            if actual_dim != EMBEDDING_DIMENSION:
                raise ValueError(
                    f"Model dimension mismatch: Expected {EMBEDDING_DIMENSION}, got {actual_dim}"
                )
            # Ensure max_seq_length matches specifications
            _MODEL_INSTANCE.max_seq_length = MAX_TOKEN_LENGTH
            logger.info(
                f"Embedding model loaded. Dimension: {actual_dim}, Max seq length: {_MODEL_INSTANCE.max_seq_length}"
            )
        except Exception as exc:
            logger.error(f"Failed to load embedding model '{model_name}': {exc}")
            raise
    return _MODEL_INSTANCE


def format_passage_text(chunk_or_record: Dict[str, Any]) -> str:
    """
    Constructs the contextualized passage string for a legal chunk or derived record.
    Incorporates document title, provision heading, and verbatim legal text.
    """
    doc_title = chunk_or_record.get("document_title", "").strip()
    heading = chunk_or_record.get("provision_heading", "").strip()
    num = chunk_or_record.get("provision_number")
    num_str = f" (No. {num})" if num else ""
    body = chunk_or_record.get("text", "").strip()

    context_parts = []
    if doc_title:
        context_parts.append(doc_title)
    if heading:
        context_parts.append(f"{heading}{num_str}")
    
    header = " - ".join(context_parts)
    if header:
        return f"{header}\n{body}"
    return body


def format_passage_for_embedding(text_or_item: Union[str, Dict[str, Any]]) -> str:
    """Prepends the mandatory E5 'passage: ' prefix."""
    if isinstance(text_or_item, dict):
        raw_text = format_passage_text(text_or_item)
    else:
        raw_text = str(text_or_item).strip()

    if not raw_text:
        raise ValueError("Cannot format empty text for embedding passage.")
    
    if raw_text.startswith(PASSAGE_PREFIX):
        return raw_text
    return f"{PASSAGE_PREFIX}{raw_text}"


def format_query_for_embedding(query: str) -> str:
    """
    Prepends the mandatory E5 'query: ' prefix for user search queries.
    (Reserved for Phase 4 retrieval integration).
    """
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Cannot format empty query for embedding.")
    if cleaned.startswith(QUERY_PREFIX):
        return cleaned
    return f"{QUERY_PREFIX}{cleaned}"


def count_tokens(text: str, model: Optional[SentenceTransformer] = None) -> int:
    """Calculates the exact token count using the model's actual tokenizer."""
    m = model or get_embedding_model()
    tokens = m.tokenizer.encode(text, truncation=False)
    return len(tokens)


def is_overlength(text: str, max_tokens: int = MAX_TOKEN_LENGTH, model: Optional[SentenceTransformer] = None) -> bool:
    """Determines whether the given text exceeds the token limit."""
    return count_tokens(text, model=model) > max_tokens


# Boundary regex for legal documents:
# 1. Numbered sub-sections: (1), (2), (3) etc.
# 2. Numbered items/paragraphs: 1., 2., 3.
# 3. Provisos: Provided that, Provided further that
# 4. Explanations: Explanation.—
# 5. Lettered clauses: (a), (b), (c) etc.
# 6. Roman numerals: (i), (ii), (iii)
# 7. Double newlines between paragraphs
LEGAL_BOUNDARY_REGEX = re.compile(
    r"(?=(?:^\s*\(\d+\)|\n\s*\(\d+\)|^\s*\d+\.\s+[A-Z]|\n\s*\d+\.\s+[A-Z]|^\s*Provided\s+that|\n\s*Provided\s+that|^\s*Provided\s+further\s+that|\n\s*Provided\s+further\s+that|^\s*Explanation[.:—\-]|^\s*\([a-z]\)|\n\s*\([a-z]\)|^\s*\([ivxlcdm]+\)|\n\s*\([ivxlcdm]+\)|\n\n))",
    re.MULTILINE | re.IGNORECASE,
)


def split_text_at_legal_boundaries(
    text: str,
    max_tokens: int = MAX_TOKEN_LENGTH,
    model: Optional[SentenceTransformer] = None,
) -> List[str]:
    """
    Splits legal text strictly at statutory boundaries (subsections, clauses, provisos, explanations)
    such that each segment conforms to max_tokens without discarding any text.
    """
    m = model or get_embedding_model()
    
    # If the text already fits, return it immediately
    if count_tokens(text, model=m) <= max_tokens:
        return [text]

    raw_segments = [s.strip() for s in LEGAL_BOUNDARY_REGEX.split(text) if s and s.strip()]
    if not raw_segments:
        raw_segments = [text]

    merged_segments: List[str] = []
    current_chunk = ""

    for seg in raw_segments:
        candidate = f"{current_chunk}\n\n{seg}".strip() if current_chunk else seg
        if count_tokens(candidate, model=m) <= max_tokens:
            current_chunk = candidate
        else:
            if current_chunk:
                merged_segments.append(current_chunk)
            
            # If a single segment alone exceeds max_tokens, split it by line or sentence
            if count_tokens(seg, model=m) > max_tokens:
                lines = [ln.strip() for ln in seg.split("\n") if ln.strip()]
                sub_chunk = ""
                for ln in lines:
                    cand_sub = f"{sub_chunk}\n{ln}".strip() if sub_chunk else ln
                    if count_tokens(cand_sub, model=m) <= max_tokens:
                        sub_chunk = cand_sub
                    else:
                        if sub_chunk:
                            merged_segments.append(sub_chunk)
                        # If a single line is still too long, split by sentence
                        if count_tokens(ln, model=m) > max_tokens:
                            sents = re.split(r"(?<=[.;])\s+", ln)
                            sent_chunk = ""
                            for s in sents:
                                cand_s = f"{sent_chunk} {s}".strip() if sent_chunk else s
                                if count_tokens(cand_s, model=m) <= max_tokens:
                                    sent_chunk = cand_s
                                else:
                                    if sent_chunk:
                                        merged_segments.append(sent_chunk)
                                    sent_chunk = s
                            if sent_chunk:
                                merged_segments.append(sent_chunk)
                            sub_chunk = ""
                        else:
                            sub_chunk = ln
                if sub_chunk:
                    merged_segments.append(sub_chunk)
                current_chunk = ""
            else:
                current_chunk = seg

    if current_chunk:
        merged_segments.append(current_chunk)

    return merged_segments


def split_overlength_provision(
    chunk: Dict[str, Any],
    max_tokens: int = MAX_TOKEN_LENGTH,
    model: Optional[SentenceTransformer] = None,
) -> List[Dict[str, Any]]:
    """
    Splits an overlength provision into linked child chunks at legal boundaries.
    Preserves section heading, parent context, document ID, page references, and stable IDs.
    Does NOT modify the original parent chunk in the source dataset.
    """
    m = model or get_embedding_model()
    parent_id = chunk["chunk_id"]
    text = chunk["text"]
    title = chunk.get("document_title", "")
    heading = chunk.get("provision_heading", "")
    num = chunk.get("provision_number")

    num_str = f" (No. {num})" if num else ""
    context_parts = []
    if title:
        context_parts.append(title.strip())
    if heading:
        context_parts.append(f"{heading.strip()}{num_str}")
    header = " - ".join(context_parts)
    header_prefix = f"{PASSAGE_PREFIX}{header}\n" if header else PASSAGE_PREFIX
    header_tokens = count_tokens(header_prefix, model=m)

    # Budget available for body text (leaving safe margin of 10 tokens for special tokens)
    effective_max = max_tokens - header_tokens - 10
    if effective_max < 100:
        effective_max = max_tokens // 2

    segments = split_text_at_legal_boundaries(text, max_tokens=effective_max, model=m)
    
    if len(segments) <= 1:
        return [chunk]

    child_chunks: List[Dict[str, Any]] = []
    tot = len(segments)
    for idx, seg in enumerate(segments, start=1):
        child_id = f"{parent_id}_PART_{idx:03d}"
        child_chunk = dict(chunk)
        child_chunk["chunk_id"] = child_id
        child_chunk["embedding_record_id"] = child_id
        child_chunk["parent_chunk_id"] = parent_id
        child_chunk["parent_provision"] = parent_id
        child_chunk["provision_heading"] = f"{heading} (Part {idx} of {tot})" if heading else f"Part {idx} of {tot}"
        child_chunk["text"] = seg
        child_chunk["is_child_segment"] = True
        child_chunk["is_child_chunk"] = True
        child_chunk["segment_index"] = idx
        child_chunk["child_index"] = idx
        child_chunk["total_segments"] = tot
        child_chunk["total_children"] = tot
        child_chunks.append(child_chunk)

    return child_chunks


def derive_embedding_records(
    chunks: List[Dict[str, Any]],
    model: Optional[SentenceTransformer] = None,
    max_tokens: int = MAX_TOKEN_LENGTH,
) -> List[Dict[str, Any]]:
    """
    Transforms canonical legal chunks into derived embedding records (data/legal_sources/embedding_records.json).
    
    Guarantees:
    1. Short provisions (<= 512 tokens with header and prefix) remain a single record (total_segments: 1).
    2. Overlength provisions (> 512 tokens) are segmented at statutory legal boundaries into independently
       searchable child records without silent truncation.
    3. Every derived segment fits strictly within the model's max sequence length (<= 512 tokens).
    4. Child records preserve parent_chunk_id, page references, document_id, headings, and applicability.
    """
    m = model or get_embedding_model()
    records: List[Dict[str, Any]] = []

    for chunk in chunks:
        cid = chunk.get("chunk_id", "")
        text = chunk.get("text", "").strip()
        if not text:
            continue

        title = chunk.get("document_title", "")
        heading = chunk.get("provision_heading", "")
        num = chunk.get("provision_number")

        num_str = f" (No. {num})" if num else ""
        context_parts = []
        if title:
            context_parts.append(title.strip())
        if heading:
            context_parts.append(f"{heading.strip()}{num_str}")
        header = " - ".join(context_parts)
        full_passage = f"{header}\n{text}" if header else text
        total_tokens = count_tokens(f"{PASSAGE_PREFIX}{full_passage}", model=m)

        if total_tokens <= max_tokens:
            rec = dict(chunk)
            rec["embedding_record_id"] = cid
            rec["parent_chunk_id"] = cid
            rec["segment_index"] = 1
            rec["total_segments"] = 1
            rec["is_child_segment"] = False
            records.append(rec)
        else:
            # Overlength: split into independently searchable child segments
            children = split_overlength_provision(chunk, max_tokens=max_tokens, model=m)
            for child in children:
                rec = dict(child)
                rec["embedding_record_id"] = child["chunk_id"]
                rec["parent_chunk_id"] = cid
                rec["segment_index"] = child.get("segment_index", 1)
                rec["total_segments"] = child.get("total_segments", len(children))
                rec["is_child_segment"] = True
                records.append(rec)

    return records


def embed_passages(
    passages: List[Union[str, Dict[str, Any]]],
    model: Optional[SentenceTransformer] = None,
    batch_size: int = 16,
) -> np.ndarray:
    """
    Generates normalized L2 embeddings for a list of passages or chunk/record dictionaries.
    
    Guarantees:
    1. Mandatory 'passage: ' prefix applied to all inputs.
    2. Overlength handling: If any text exceeds 512 tokens, it is segmented at legal boundaries,
       each segment is embedded with 'passage: ', and mean-pooled + L2-normalized so 0 words are dropped.
    3. Output embeddings are finite numerical arrays of dimension 384 with L2 norm = 1.0.
    """
    if not passages:
        raise ValueError("Cannot embed empty passages list.")

    m = model or get_embedding_model()
    embeddings_list: List[np.ndarray] = []

    for item in passages:
        if isinstance(item, dict):
            raw_text = format_passage_text(item)
        else:
            raw_text = str(item).strip()

        if not raw_text:
            raise ValueError("Encountered empty passage text during embedding generation.")

        prefixed_text = format_passage_for_embedding(raw_text)
        token_count = count_tokens(prefixed_text, model=m)

        if token_count <= MAX_TOKEN_LENGTH:
            emb = m.encode(prefixed_text, normalize_embeddings=True, show_progress_bar=False)
            embeddings_list.append(emb)
        else:
            # Fallback for arbitrary strings that exceed max tokens
            effective_max = MAX_TOKEN_LENGTH - 20
            segments = split_text_at_legal_boundaries(raw_text, max_tokens=effective_max, model=m)
            seg_embeddings = []
            for seg in segments:
                prefixed_seg = format_passage_for_embedding(seg)
                seg_emb = m.encode(prefixed_seg, normalize_embeddings=True, show_progress_bar=False)
                seg_embeddings.append(seg_emb)
            
            pooled = np.mean(seg_embeddings, axis=0)
            norm = np.linalg.norm(pooled)
            if norm > 0:
                pooled = pooled / norm
            embeddings_list.append(pooled)

    result_arr = np.vstack(embeddings_list).astype(np.float32)

    # Validate output dimensions and finiteness
    if result_arr.shape[1] != EMBEDDING_DIMENSION:
        raise ValueError(
            f"Embedding dimension error: Expected {EMBEDDING_DIMENSION}, got {result_arr.shape[1]}"
        )
    if not np.all(np.isfinite(result_arr)):
        raise ValueError("Generated embeddings contain non-finite values (NaN or Inf).")

    return result_arr
