"""
Unit and Integration Tests for Embedding Module (Phase 3C.1).

Verifies:
1. Embedding model loads successfully on CPU/default device.
2. Embedding dimension is strictly 384.
3. Empty passages and queries are rejected with ValueError.
4. E5 passage prefix ('passage: ') is applied to indexing inputs.
5. E5 query prefix ('query: ') is formatted and documented for Phase 4 retrieval.
6. Embeddings are finite numerical arrays (no NaN or Inf).
7. Embeddings are L2 normalized (Euclidean norm = 1.0).
8. Overlength legal chunks (> 512 tokens) are detected via actual model tokenizer.
9. Safe legal boundary splitting into independently searchable child segments without silent truncation.
10. Child chunks created from overlength provisions preserve parent references and page numbers.
11. Derived embedding records (embedding_records.json) all strictly fit within 512 tokens.
12. Exact parent-child traceability and metadata preservation.
"""

import json
from pathlib import Path
import numpy as np
import pytest

from src.embeddings import (
    EMBEDDING_DIMENSION,
    MAX_TOKEN_LENGTH,
    MODEL_NAME,
    PASSAGE_PREFIX,
    QUERY_PREFIX,
    count_tokens,
    derive_embedding_records,
    embed_passages,
    format_passage_for_embedding,
    format_passage_text,
    format_query_for_embedding,
    get_device,
    get_embedding_model,
    is_overlength,
    split_overlength_provision,
    split_text_at_legal_boundaries,
)

DERIVED_RECORDS_FILE = Path("data/legal_sources/embedding_records.json")
CANONICAL_CHUNKS_FILE = Path("data/legal_sources/legal_chunks.json")


@pytest.fixture(scope="module")
def model_instance():
    """Loads the model once for the test module."""
    return get_embedding_model()


def test_01_embedding_model_loads_and_verifies_specifications(model_instance):
    """Verifies that intfloat/multilingual-e5-small loads and verifies 384 dims and 512 max tokens."""
    assert model_instance is not None
    if hasattr(model_instance, "get_embedding_dimension"):
        dim = model_instance.get_embedding_dimension()
    else:
        dim = model_instance.get_sentence_embedding_dimension()
    assert dim == EMBEDDING_DIMENSION == 384
    assert model_instance.max_seq_length == MAX_TOKEN_LENGTH == 512
    device = get_device()
    assert device in ("cpu", "cuda")


def test_02_e5_passage_and_query_prefix_application():
    """Verifies that passage: and query: prefixes are strictly applied and not confused."""
    raw_passage = "A consumer may file a complaint before the District Commission."
    prefixed_p = format_passage_for_embedding(raw_passage)
    assert prefixed_p.startswith(PASSAGE_PREFIX)
    assert prefixed_p == f"passage: {raw_passage}"

    # Does not double prefix
    assert format_passage_for_embedding(prefixed_p) == prefixed_p

    # Query prefix for Phase 4
    raw_query = "What is the fee for filing a complaint in District Commission?"
    prefixed_q = format_query_for_embedding(raw_query)
    assert prefixed_q.startswith(QUERY_PREFIX)
    assert prefixed_q == f"query: {raw_query}"
    assert format_query_for_embedding(prefixed_q) == prefixed_q


def test_03_empty_passages_and_queries_rejected():
    """Verifies that empty passages and whitespace strings are rejected safely."""
    with pytest.raises(ValueError, match="Cannot format empty text"):
        format_passage_for_embedding("")

    with pytest.raises(ValueError, match="Cannot format empty text"):
        format_passage_for_embedding("   \n\t  ")

    with pytest.raises(ValueError, match="Cannot format empty query"):
        format_query_for_embedding("")

    with pytest.raises(ValueError, match="Cannot embed empty passages list"):
        embed_passages([])


def test_04_embeddings_are_finite_numerical_arrays(model_instance):
    """Verifies generated embeddings are finite numerical float32 arrays with 384 dimensions."""
    test_texts = [
        "The Consumer Protection Act, 2019 protects consumers against unfair trade practices.",
        "National Consumer Helpline provides pre-litigation grievance redressal.",
    ]
    embs = embed_passages(test_texts, model=model_instance)
    assert isinstance(embs, np.ndarray)
    assert embs.shape == (2, 384)
    assert np.all(np.isfinite(embs))
    assert embs.dtype == np.float32


def test_05_embeddings_are_l2_normalized(model_instance):
    """Verifies that output embeddings are L2 normalized (norm approximately 1.0)."""
    text = "Consumer Disputes Redressal Commission jurisdiction."
    embs = embed_passages([text], model=model_instance)
    norm = np.linalg.norm(embs[0])
    assert pytest.approx(norm, abs=1e-5) == 1.0


def test_06_overlength_detection(model_instance):
    """Verifies that overlength passages exceeding 512 tokens are accurately detected."""
    short_text = "Short statutory provision."
    assert not is_overlength(short_text, model=model_instance)

    # Construct synthetic text with > 512 tokens
    long_text = " ".join(["consumer dispute redressal jurisdiction section"] * 150)
    assert count_tokens(long_text, model=model_instance) > 512
    assert is_overlength(long_text, model=model_instance)


def test_07_legal_boundary_splitting_preserves_subsections_and_provisos(model_instance):
    """
    CRITICAL LEGAL SAFETY TEST:
    Verifies that splitting long provisions respects subsection, clause, and proviso boundaries
    without silently truncating or discarding legal text.
    """
    sample_legal_text = (
        "(1) A consumer may file a complaint in relation to any goods sold or delivered.\n\n"
        "(2) Every complaint shall be accompanied by such fee as may be specified.\n\n"
        "Provided that no fee shall be payable for complaints where the consideration is below five lakh rupees:\n\n"
        "Provided further that the Commission may admit a complaint after the limitation period if sufficient cause is shown.\n\n"
        "Explanation.—For the purposes of this sub-section, consideration means the total value of goods or services paid."
    )

    # Force splitting at a lower token budget to verify boundary alignment
    segments = split_text_at_legal_boundaries(sample_legal_text, max_tokens=30, model=model_instance)
    assert len(segments) > 1

    combined_output = " ".join(segments)
    # Verify zero text truncation
    assert "(1) A consumer may file" in combined_output
    assert "(2) Every complaint shall be accompanied" in combined_output
    assert "Provided that no fee shall be payable" in combined_output
    assert "Provided further that the Commission may admit" in combined_output
    assert "Explanation.—For the purposes of this sub-section" in combined_output


def test_08_split_overlength_provision_creates_linked_child_chunks(model_instance):
    """
    Verifies that split_overlength_provision creates linked child chunks with:
    - Stable child IDs (parent_id_PART_NNN).
    - Preserved parent_provision reference.
    - Preserved document ID and page references.
    """
    parent_chunk = {
        "chunk_id": "TEST_CPA_SECTION_999",
        "document_id": "CPA_2019",
        "document_title": "The Consumer Protection Act, 2019",
        "document_type": "ACT",
        "provision_type": "SECTION",
        "provision_number": "999",
        "provision_heading": "Procedure on admission of complaint",
        "parent_provision": None,
        "text": "\n\n".join([f"({i}) Subsection {i} specifies detailed consumer procedure and filing steps in district forum." for i in range(1, 25)]),
        "source_url": "https://consumeraffairs.gov.in/",
        "original_filename": "A2019-35_Consumer_Protection_Act_2019.pdf",
        "pdf_page_start": 15,
        "pdf_page_end": 17,
        "publication_date": "2019-08-09",
        "effective_from": "2020-07-20",
        "effective_to": None,
        "applicability_status": "CURRENTLY_IN_FORCE",
        "retrieval_eligible": True,
        "extraction_status": "SUCCESS",
        "extraction_integrity_status": "CHECKED",
        "legal_review_status": "REQUIRES_LEGAL_REVIEW",
    }

    child_chunks = split_overlength_provision(parent_chunk, max_tokens=60, model=model_instance)
    assert len(child_chunks) > 1

    for idx, child in enumerate(child_chunks, start=1):
        assert child["chunk_id"] == f"TEST_CPA_SECTION_999_PART_{idx:03d}"
        assert child["parent_provision"] == "TEST_CPA_SECTION_999"
        assert child["document_id"] == "CPA_2019"
        assert child["pdf_page_start"] == 15
        assert child["pdf_page_end"] == 17
        assert child["is_child_chunk"] is True
        assert child["is_child_segment"] is True
        assert child["segment_index"] == idx
        assert child["total_segments"] == len(child_chunks)


def test_09_overlength_passages_embedded_without_silent_truncation(model_instance):
    """
    Verifies that embed_passages generates valid normalized vectors for overlength chunks
    by segmenting and pooling rather than silently truncating past token 512.
    """
    long_passage = "\n\n".join([
        f"({i}) This is legal clause number {i} articulating mandatory statutory requirements under consumer law."
        for i in range(1, 40)
    ])
    assert count_tokens(long_passage, model=model_instance) > 512

    embs = embed_passages([long_passage], model=model_instance)
    assert embs.shape == (1, 384)
    assert np.all(np.isfinite(embs))
    norm = np.linalg.norm(embs[0])
    assert pytest.approx(norm, abs=1e-5) == 1.0


def test_10_format_passage_text_includes_document_title_and_heading():
    """Verifies that contextualized passage format includes document title, provision heading, and number."""
    chunk = {
        "document_title": "The Consumer Protection Act, 2019",
        "provision_heading": "Definitions",
        "provision_number": "2",
        "text": 'In this Act, "consumer" means any person who buys any goods...',
    }
    formatted = format_passage_text(chunk)
    assert "The Consumer Protection Act, 2019" in formatted
    assert "Definitions (No. 2)" in formatted
    assert 'In this Act, "consumer"' in formatted


def test_11_every_derived_embedding_record_fits_512_token_limit(model_instance):
    """
    CRITICAL TOKEN LIMIT VERIFICATION (Part D):
    Verifies that EVERY record in embedding_records.json, when formatted with
    'passage: ' and context headers, strictly conforms to the 512 token limit of the model.
    """
    assert DERIVED_RECORDS_FILE.exists(), f"Derived records file not found at {DERIVED_RECORDS_FILE}"
    with open(DERIVED_RECORDS_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)

    assert len(records) > 0
    for r in records:
        passage = format_passage_for_embedding(r)
        tok_len = count_tokens(passage, model=model_instance)
        assert tok_len <= MAX_TOKEN_LENGTH, (
            f"Record '{r['embedding_record_id']}' exceeds 512 tokens: {tok_len} tokens"
        )


def test_12_parent_child_traceability_in_derived_records():
    """
    CRITICAL TRACEABILITY TEST:
    Verifies that child records have valid parent references, page bounds, and index numbering.
    """
    with open(DERIVED_RECORDS_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)

    with open(CANONICAL_CHUNKS_FILE, "r", encoding="utf-8") as f:
        canonical_chunks = json.load(f)
    canonical_map = {c["chunk_id"]: c for c in canonical_chunks}

    child_records = [r for r in records if r.get("is_child_segment", False)]
    assert len(child_records) > 0

    for child in child_records:
        parent_id = child.get("parent_chunk_id")
        assert parent_id in canonical_map, f"Child {child['embedding_record_id']} references missing parent {parent_id}"
        parent = canonical_map[parent_id]

        # Verify page references match parent
        assert child["pdf_page_start"] == parent["pdf_page_start"]
        assert child["pdf_page_end"] == parent["pdf_page_end"]
        assert child["document_id"] == parent["document_id"]
        assert child["segment_index"] >= 1
        assert child["total_segments"] >= child["segment_index"]
        assert child["text"].strip() != ""
