"""
Developer Retrieval Test Interface & Evaluation Script for Nyaya Saathi.

Blueprint Phase 4 — Step 14: Semantic Search Evaluation.
Provides:
1. Interactive or CLI execution of semantic search queries with detailed provenance inspection.
2. Formatted display of query embedding dimensions, selected collections, ranked results, distances, and PDF page numbers.
3. Automated evaluation of the 20 synthetic test cases (Recall@5, Recall@8, Precision@5, MRR) across
   English, Hindi, Hinglish, procedural, exact citation, and abstention queries.
"""

from datetime import date
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Enforce UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.embeddings import EMBEDDING_DIMENSION, get_device
from src.legal_retriever import (
    COLLECTION_CURRENT_LAW,
    COLLECTION_FUTURE_LAW,
    COLLECTION_PROCEDURAL_GUIDANCE,
    embed_query,
    semantic_search,
)

logging.basicConfig(level=logging.WARNING)

TEST_CASES_FILE = PROJECT_ROOT / "data" / "test_cases" / "semantic_retrieval_cases.json"


def run_developer_query(
    query: str,
    top_k: int = 8,
    include_procedural: bool = False,
    include_future: bool = False,
    transaction_date: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> None:
    """Executes a single search and prints a detailed developer diagnostic view."""
    print("\n" + "=" * 70)
    print("NYAYA SAATHI — DEVELOPER SEMANTIC RETRIEVAL DIAGNOSTIC")
    print("=" * 70)
    print(f"Original Query:          '{query}'")

    # 1. Query Embedding Diagnostic
    q_vec = embed_query(query)
    print(f"Query Vector Shape:      {q_vec.shape} (Dimension: {EMBEDDING_DIMENSION}, Device: {get_device()})")
    
    # 2. Selected Collections
    selected_cols = [COLLECTION_CURRENT_LAW]
    if include_procedural:
        selected_cols.append(COLLECTION_PROCEDURAL_GUIDANCE)
    if include_future:
        selected_cols.append(COLLECTION_FUTURE_LAW)
    print(f"Collections Queried:     {', '.join(selected_cols)}")
    print(f"Top-K Limit:             {top_k}")
    if transaction_date:
        print(f"Transaction Date:        {transaction_date}")
    if as_of_date:
        print(f"As-Of Date:              {as_of_date}")

    # 3. Execute Search
    results = semantic_search(
        query=query,
        top_k=top_k,
        include_procedural=include_procedural,
        include_future=include_future,
        transaction_date=transaction_date,
        as_of_date=as_of_date,
    )

    print(f"\nRetrieved Results:       {len(results)} records")
    print("-" * 70)

    if not results:
        print("No matching legal provisions retrieved.")
        print("=" * 70 + "\n")
        return

    for r in results:
        rank = r["retrieval_rank"]
        dist = r["distance"]
        num = r["provision_number"]
        num_str = f" No. {num}" if num else ""
        heading = r["provision_heading"]
        doc_title = r["document_title"]
        coll = r["collection_name"]
        app_status = r["applicability_status"]
        p_start = r["pdf_page_start"]
        p_end = r["pdf_page_end"]
        page_str = f"Pages {p_start}-{p_end}" if p_start and p_end else (f"Page {p_start}" if p_start else "N/A")
        parent_id = r["parent_chunk_id"]
        rec_id = r["chunk_id"]

        print(f"Rank {rank}: [Distance: {dist:.4f}] | {coll}")
        print(f"  Record ID:       {rec_id} (Parent: {parent_id})")
        print(f"  Instrument:      {doc_title}")
        print(f"  Provision:       {r['provision_type']}{num_str} — {heading}")
        print(f"  Physical PDF:    {page_str} ({r['original_filename']})")
        print(f"  Source URL:      {r['source_url']}")
        print(f"  Applicability:   {app_status}")
        snippet = r["exact_original_text"][:220].replace("\n", " ")
        print(f"  Verbatim Text:   \"{snippet}...\"")
        print("-" * 70)

    print("=" * 70 + "\n")


def evaluate_retrieval_dataset() -> Dict[str, Any]:
    """
    Evaluates semantic retrieval across all 20 synthetic test cases.
    Computes Recall@5, Recall@8, Precision@5, and MRR.
    """
    if not TEST_CASES_FILE.exists():
        raise FileNotFoundError(f"Test cases file not found at: {TEST_CASES_FILE}")

    with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]
    print(f"\nEvaluating {len(cases)} test cases from {TEST_CASES_FILE.name}...\n")

    results_summary = []
    
    mrr_total = 0.0
    recall_at_5_hits = 0
    recall_at_8_hits = 0
    precision_at_5_total = 0.0
    evaluable_cases_count = 0

    by_language: Dict[str, List[float]] = {"en": [], "hi": [], "hinglish": []}
    by_category: Dict[str, List[float]] = {}

    for tc in cases:
        cid = tc["case_id"]
        q = tc["query"]
        expected_parents = set(tc.get("expected_parent_provisions", []))
        req_proc = tc.get("requires_procedural", False)
        req_future = tc.get("requires_future", False)
        is_abstention = tc.get("is_abstention_case", False)
        lang = tc.get("language", "en")
        cat = tc.get("category", "GENERAL")

        retrieved = semantic_search(
            query=q,
            top_k=8,
            include_procedural=req_proc,
            include_future=req_future,
        )

        retrieved_parent_ids = [r["parent_chunk_id"] for r in retrieved]
        retrieved_record_ids = [r["chunk_id"] for r in retrieved]

        if is_abstention:
            # For abstention queries, success means no false-positive assertion of applicability
            # Since semantic search returns nearest neighbours in vector space,
            # we evaluate distances (typically higher distance > 0.65)
            first_dist = retrieved[0]["distance"] if retrieved else 1.0
            print(f"[{cid}] (Abstention/Out of Scope) '{q[:40]}...' -> Nearest distance: {first_dist:.4f}")
            results_summary.append({
                "case_id": cid,
                "category": cat,
                "is_abstention": True,
                "nearest_distance": first_dist,
            })
            continue

        evaluable_cases_count += 1

        # Check hits
        hit_ranks = []
        for rank, pid in enumerate(retrieved_parent_ids, start=1):
            if pid in expected_parents:
                hit_ranks.append(rank)

        r5 = 1.0 if any(r <= 5 for r in hit_ranks) else 0.0
        r8 = 1.0 if any(r <= 8 for r in hit_ranks) else 0.0

        p5_relevant = sum(1 for r in hit_ranks if r <= 5)
        p5 = p5_relevant / 5.0

        reciprocal_rank = 1.0 / hit_ranks[0] if hit_ranks else 0.0

        recall_at_5_hits += r5
        recall_at_8_hits += r8
        precision_at_5_total += p5
        mrr_total += reciprocal_rank

        by_language.setdefault(lang, []).append(r5)
        by_category.setdefault(cat, []).append(r5)

        status_str = f"HIT (Rank {hit_ranks[0]})" if hit_ranks else "MISS"
        print(f"[{cid}] [{lang}] [{cat:22}] {status_str:12} | Top: {retrieved_parent_ids[0] if retrieved_parent_ids else 'None'} (Dist: {retrieved[0]['distance'] if retrieved else 0:.4f})")

        results_summary.append({
            "case_id": cid,
            "category": cat,
            "language": lang,
            "recall_at_5": r5,
            "recall_at_8": r8,
            "precision_at_5": p5,
            "mrr": reciprocal_rank,
            "first_hit_rank": hit_ranks[0] if hit_ranks else None,
            "top_retrieved": retrieved_parent_ids[:3],
        })

    avg_recall_5 = recall_at_5_hits / evaluable_cases_count if evaluable_cases_count else 0.0
    avg_recall_8 = recall_at_8_hits / evaluable_cases_count if evaluable_cases_count else 0.0
    avg_precision_5 = precision_at_5_total / evaluable_cases_count if evaluable_cases_count else 0.0
    avg_mrr = mrr_total / evaluable_cases_count if evaluable_cases_count else 0.0

    print("\n" + "=" * 70)
    print("SEMANTIC RETRIEVAL EVALUATION REPORT")
    print("=" * 70)
    print(f"Total Test Cases:            {len(cases)}")
    print(f"Evaluable Relevant Cases:    {evaluable_cases_count}")
    print(f"Abstention/Coverage Cases:   {len(cases) - evaluable_cases_count}")
    print(f"Overall Recall@5:            {avg_recall_5 * 100:.1f}%")
    print(f"Overall Recall@8:            {avg_recall_8 * 100:.1f}%")
    print(f"Overall Precision@5:         {avg_precision_5 * 100:.1f}%")
    print(f"Overall MRR:                 {avg_mrr:.4f}")
    print("-" * 70)
    print("Performance by Language (Recall@5):")
    for lang, scores in by_language.items():
        if scores:
            print(f"  - {lang.upper():8}: {sum(scores)/len(scores)*100:5.1f}% ({len(scores)} cases)")
    print("=" * 70 + "\n")

    return {
        "evaluable_cases": evaluable_cases_count,
        "recall_at_5": avg_recall_5,
        "recall_at_8": avg_recall_8,
        "precision_at_5": avg_precision_5,
        "mrr": avg_mrr,
        "results_summary": results_summary,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--eval":
        evaluate_retrieval_dataset()
    elif len(sys.argv) > 1:
        user_q = " ".join(sys.argv[1:])
        run_developer_query(user_q)
    else:
        # Default run: sample dispute query and then run evaluation
        sample = "Explain what I can do if my seller refuses to refund my money."
        run_developer_query(sample)
        evaluate_retrieval_dataset()
