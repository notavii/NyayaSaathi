"""
Developer Test CLI and Evaluation Harness for BM25 Retrieval in Nyaya Saathi.

Step 15: Lexical Search using rank-bm25 (BM25Okapi).
Supports interactive command-line queries, temporal date filtering, procedural inclusion,
and full automated evaluation across the synthetic benchmark dataset.

Usage:
    # Single English query
    python scripts/test_bm25_retrieval.py --query "My seller refused to refund my money"

    # Hindi query with UTF-8 console output
    python scripts/test_bm25_retrieval.py --query "दुकानदार पैसे वापस करने से मना कर रहा है"

    # Query with procedural filing guides included
    python scripts/test_bm25_retrieval.py --query "How do I upload document on e-Jagriti?" --procedural

    # Query with future transaction date (effective 2027-01-01)
    python scripts/test_bm25_retrieval.py --query "dark pattern rules for ecommerce" --date 2027-02-01

    # Full synthetic evaluation against ground truth
    python scripts/test_bm25_retrieval.py --eval
"""

import argparse
from datetime import date, datetime
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Force UTF-8 encoding on standard I/O for native Windows PowerShell compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.bm25_retriever import (
    COLLECTION_CURRENT_LAW,
    COLLECTION_FUTURE_LAW,
    COLLECTION_PROCEDURAL_GUIDANCE,
    bm25_search,
    normalize_text,
    tokenize_legal_text,
)
from src.keyword_expansion import expand_query_terms

TEST_CASES_PATH = PROJECT_ROOT / "data" / "test_cases" / "semantic_retrieval_cases.json"


def run_single_query(
    query: str,
    top_k: int = 8,
    include_procedural: bool = False,
    include_future: bool = False,
    date_str: Optional[str] = None,
) -> None:
    """Executes a single test query and prints comprehensive diagnostic telemetry."""
    print("=" * 70)
    print("          NYAYA SAATHI — BM25 LEXICAL RETRIEVAL DIAGNOSTIC")
    print("=" * 70)

    # 1. Query Analysis
    norm_query = normalize_text(query)
    expanded_terms, matched_keywords, detected_lang = expand_query_terms(query)
    q_tokens = tokenize_legal_text(query)
    exp_tokens = tokenize_legal_text(" ".join(expanded_terms)) if expanded_terms else []

    all_tokens = []
    seen = set()
    for t in q_tokens + exp_tokens:
        if t not in seen:
            seen.add(t)
            all_tokens.append(t)

    print(f"1. Original Query:         {query}")
    print(f"2. Normalised Query:       {norm_query}")
    print(f"3. Detected Language:      {detected_lang.upper()}")
    print(f"4. Matched Dispute Terms:  {matched_keywords if matched_keywords else 'None'}")
    print(f"5. Expanded Search Terms:  {expanded_terms if expanded_terms else 'None'}")
    print(f"6. Tokenised Query Tokens: {all_tokens}")

    # 2. Selected Search Category / Collections
    collections = [COLLECTION_CURRENT_LAW]
    if include_procedural:
        collections.append(COLLECTION_PROCEDURAL_GUIDANCE)
    if include_future or (date_str and date_str >= "2027-01-01"):
        collections.append(COLLECTION_FUTURE_LAW)

    print(f"7. Selected Collections:   {', '.join(collections)}")
    if date_str:
        print(f"   Reference Date:         {date_str}")
    print("-" * 70)

    # 3. Execute BM25 Retrieval
    results = bm25_search(
        query=query,
        top_k=top_k,
        include_procedural=include_procedural,
        include_future=include_future,
        transaction_date=date_str,
    )

    print(f"8. Retrieved Record Count: {len(results)}")
    print("=" * 70)

    if not results:
        print("\n[!] Zero matching records retrieved (positive score threshold not met).")
        print("=" * 70)
        return

    # 4. Print Ranked Results
    for res in results:
        rank = res["retrieval_rank"]
        score = res["bm25_score"]
        rec_id = res["embedding_record_id"]
        doc_title = res["document_title"]
        prov_num = res["provision_number"]
        prov_type = res["provision_type"]
        prov_heading = res["provision_heading"]
        status = res["applicability_status"]
        source_url = res["source_url"]
        p_start = res["pdf_page_start"]
        p_end = res["pdf_page_end"]
        raw_text = res["exact_original_text"]

        pages_str = f"pp. {p_start}-{p_end}" if p_start and p_end else "N/A"
        preview_text = raw_text[:200] + ("..." if len(raw_text) > 200 else "")

        print(f"\n[RANK {rank}] | BM25 Score: {score:.4f} | Collection: {res['collection_name']}")
        print(f"  Record ID:       {rec_id}")
        print(f"  Document Title:  {doc_title}")
        print(f"  Provision:       {prov_type} {prov_num}: {prov_heading}")
        print(f"  Status:          {status}")
        print(f"  PDF Pages:       {pages_str}")
        print(f"  Source URL:      {source_url}")
        print(f"  Verbatim Text:   {preview_text}")
        print("-" * 70)


def evaluate_benchmark(test_cases_path: Path = TEST_CASES_PATH) -> None:
    """
    Evaluates BM25 retrieval against the synthetic benchmark cases.
    Computes Recall@5, Recall@8, Precision@5, and Mean Reciprocal Rank (MRR).
    """
    if not test_cases_path.exists():
        print(f"Error: Test cases file not found at {test_cases_path}")
        sys.exit(1)

    with open(test_cases_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data.get("cases", [])
    print(f"\nEvaluating {len(cases)} test cases from {test_cases_path.name}...\n")

    total_evaluable = 0
    hits_at_5 = 0
    hits_at_8 = 0
    total_precision_at_5_hits = 0
    reciprocal_ranks: List[float] = []

    lang_stats: Dict[str, Dict[str, int]] = {
        "en": {"total": 0, "hits_5": 0},
        "hi": {"total": 0, "hits_5": 0},
        "hinglish": {"total": 0, "hits_5": 0},
    }

    for case in cases:
        cid = case["case_id"]
        cat = case["category"]
        lang = case.get("language", "en")
        query = case["query"]
        expected_parents = set(case.get("expected_parent_provisions", []))
        req_proc = case.get("requires_procedural", False)
        req_fut = case.get("requires_future", False)
        is_abstention = case.get("is_abstention_case", False)

        if is_abstention:
            # Evaluate abstention / out-of-scope queries
            res = bm25_search(query=query, top_k=5, include_procedural=req_proc, include_future=req_fut)
            top_score = res[0]["bm25_score"] if res else 0.0
            print(f"[{cid}] (Abstention/Out of Scope) '{query[:40]}...' -> Retrieved: {len(res)}, Top BM25: {top_score:.4f}")
            continue

        total_evaluable += 1
        if lang not in lang_stats:
            lang_stats[lang] = {"total": 0, "hits_5": 0}
        lang_stats[lang]["total"] += 1

        results = bm25_search(
            query=query,
            top_k=8,
            include_procedural=req_proc,
            include_future=req_fut,
        )

        retrieved_parents = [r.get("parent_chunk_id") for r in results]

        # Check hits
        hit_rank = None
        for rank_idx, pid in enumerate(retrieved_parents, start=1):
            if pid in expected_parents:
                hit_rank = rank_idx
                break

        # Recall@5 and Recall@8
        is_hit_5 = hit_rank is not None and hit_rank <= 5
        is_hit_8 = hit_rank is not None and hit_rank <= 8

        if is_hit_5:
            hits_at_5 += 1
            lang_stats[lang]["hits_5"] += 1

        if is_hit_8:
            hits_at_8 += 1

        # Precision@5
        parents_at_5 = set(retrieved_parents[:5])
        matched_at_5 = len(parents_at_5.intersection(expected_parents))
        total_precision_at_5_hits += matched_at_5

        # MRR
        if hit_rank is not None:
            reciprocal_ranks.append(1.0 / hit_rank)
        else:
            reciprocal_ranks.append(0.0)

        # Log line
        status_str = f"HIT (Rank {hit_rank})" if hit_rank else "MISS        "
        top_rec = results[0]["parent_chunk_id"] if results else "NONE"
        top_score = results[0]["bm25_score"] if results else 0.0
        print(f"[{cid}] [{lang:8s}] [{cat:24s}] {status_str} | Top: {top_rec} (BM25: {top_score:.4f})")

    # Aggregate Metrics
    recall_5 = (hits_at_5 / total_evaluable * 100) if total_evaluable else 0.0
    recall_8 = (hits_at_8 / total_evaluable * 100) if total_evaluable else 0.0
    prec_5 = (total_precision_at_5_hits / (total_evaluable * 5) * 100) if total_evaluable else 0.0
    mrr = (sum(reciprocal_ranks) / len(reciprocal_ranks)) if reciprocal_ranks else 0.0

    print("\n" + "=" * 70)
    print("                    BM25 RETRIEVAL EVALUATION REPORT")
    print("=" * 70)
    print(f"Total Test Cases:            {len(cases)}")
    print(f"Evaluable Relevant Cases:    {total_evaluable}")
    print(f"Abstention/Coverage Cases:   {len(cases) - total_evaluable}")
    print(f"Overall Recall@5:            {recall_5:.1f}% ({hits_at_5}/{total_evaluable})")
    print(f"Overall Recall@8:            {recall_8:.1f}% ({hits_at_8}/{total_evaluable})")
    print(f"Overall Precision@5:         {prec_5:.1f}%")
    print(f"Overall MRR:                 {mrr:.4f}")
    print("-" * 70)
    print("Performance by Language (Recall@5):")
    for l_key, l_data in lang_stats.items():
        l_tot = l_data["total"]
        if l_tot > 0:
            l_rec = (l_data["hits_5"] / l_tot) * 100
            print(f"  - {l_key.upper():8s}: {l_rec:5.1f}% ({l_data['hits_5']}/{l_tot} cases)")
    print("=" * 70 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Nyaya Saathi BM25 Legal Retrieval CLI")
    parser.add_argument("--query", type=str, help="Search query (English, Hindi, or Hinglish)")
    parser.add_argument("--top_k", type=int, default=8, help="Number of records to retrieve (1-10)")
    parser.add_argument("--procedural", action="store_true", help="Include procedural guidance collection")
    parser.add_argument("--future", action="store_true", help="Explicitly include future law collection")
    parser.add_argument("--date", type=str, help="Reference transaction or evaluation date (YYYY-MM-DD)")
    parser.add_argument("--eval", action="store_true", help="Run synthetic evaluation benchmark")

    args = parser.parse_args()

    if args.eval:
        evaluate_benchmark()
    elif args.query:
        run_single_query(
            query=args.query,
            top_k=args.top_k,
            include_procedural=args.procedural,
            include_future=args.future,
            date_str=args.date,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
