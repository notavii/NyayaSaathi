"""
Developer Test CLI and Evaluation Harness for Hybrid Legal Retrieval in Nyaya Saathi.

Blueprint Phase 4C — Step 16: Semantic + BM25 Hybrid Retrieval with Reciprocal Rank Fusion (RRF).
Supports interactive command-line queries, temporal date filtering, procedural inclusion,
and full automated evaluation against the synthetic benchmark dataset.

Usage:
    # Single English query
    python scripts/test_hybrid_retrieval.py --query "My seller refuses to refund my money"

    # Hindi query with UTF-8 console output
    python scripts/test_hybrid_retrieval.py --query "दुकानदार पैसे वापस करने से मना कर रहा है"

    # Query with procedural filing guides included
    python scripts/test_hybrid_retrieval.py --query "How do I upload document on e-Jagriti?" --procedural

    # Query with future transaction date (effective 2027-01-01)
    python scripts/test_hybrid_retrieval.py --query "dark pattern rules for ecommerce" --date 2027-02-01

    # Full synthetic evaluation against ground truth
    python scripts/test_hybrid_retrieval.py --eval
"""

import argparse
from datetime import date, datetime
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Force UTF-8 encoding on standard I/O for native Windows PowerShell compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.bm25_retriever import bm25_search, normalize_text
from src.hybrid_retriever import (
    DEFAULT_RRF_K,
    DEFAULT_TOP_K,
    hybrid_search,
    resolve_date_gating,
)
from src.keyword_expansion import expand_query_terms
from src.legal_retriever import semantic_search

TEST_CASES_PATH = PROJECT_ROOT / "data" / "test_cases" / "semantic_retrieval_cases.json"


def run_single_query(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    include_procedural: bool = False,
    include_future: bool = False,
    date_str: Optional[str] = None,
    rrf_k: int = DEFAULT_RRF_K,
) -> None:
    """Executes a single test query and prints comprehensive diagnostic telemetry."""
    print("=" * 75)
    print("       NYAYA SAATHI — HYBRID LEGAL RETRIEVAL DIAGNOSTIC (RRF)")
    print("=" * 75)

    # 1. Query Analysis
    norm_query = normalize_text(query)
    expanded_terms, matched_keywords, detected_lang = expand_query_terms(query)

    print(f"1. Original Query:         {query}")
    print(f"2. Normalised Query:       {norm_query}")
    print(f"3. Detected Language:      {detected_lang.upper()}")
    print(f"4. Matched Dispute Terms:  {matched_keywords if matched_keywords else 'None'}")
    print(f"5. Expanded Search Terms:  {expanded_terms if expanded_terms else 'None'}")

    future_eligible, t_date, a_date, temporal_status = resolve_date_gating(
        include_future=include_future,
        transaction_date=date_str,
    )
    print(f"6. Date Gating Resolution:")
    print(f"   - Reference Date:       {date_str or 'None (defaults to today)'}")
    print(f"   - Future Law Eligible:  {future_eligible}")
    print(f"   - Temporal Status:      {temporal_status}")
    print(f"   - Include Procedural:   {include_procedural}")
    print(f"   - RRF Smoothing (k):    {rrf_k}")
    print("-" * 75)

    # 2. Execute Component Searches for Telemetry
    t0 = time.time()
    sem_results = semantic_search(
        query=query,
        top_k=top_k,
        include_procedural=include_procedural,
        include_future=future_eligible,
        transaction_date=date_str,
    )
    t_sem = (time.time() - t0) * 1000

    t1 = time.time()
    bm25_results = bm25_search(
        query=query,
        top_k=top_k,
        include_procedural=include_procedural,
        include_future=future_eligible,
        transaction_date=date_str,
    )
    t_bm25 = (time.time() - t1) * 1000

    # 3. Execute Hybrid Fusion
    t2 = time.time()
    fused_results = hybrid_search(
        query=query,
        top_k=top_k,
        include_procedural=include_procedural,
        include_future=include_future,
        transaction_date=date_str,
        rrf_k=rrf_k,
    )
    t_fused = (time.time() - t2) * 1000

    print(f"7. Execution Latency:")
    print(f"   - Semantic Search:      {t_sem:.1f} ms ({len(sem_results)} candidates)")
    print(f"   - BM25 Search:          {t_bm25:.1f} ms ({len(bm25_results)} candidates)")
    print(f"   - Total Hybrid Latency: {t_fused:.1f} ms ({len(fused_results)} fused records)")
    print("=" * 75)

    # 4. Component Results Summary
    print("\n--- [SEMANTIC TOP 3 CANDIDATES] ---")
    for r in sem_results[:3]:
        print(f"  Rank {r['retrieval_rank']} | {r['embedding_record_id']} | Dist: {r['distance']:.4f} | {r['provision_heading']}")

    print("\n--- [BM25 TOP 3 CANDIDATES] ---")
    for r in bm25_results[:3]:
        print(f"  Rank {r['retrieval_rank']} | {r['embedding_record_id']} | Score: {r['bm25_score']:.4f} | {r['provision_heading']}")

    print("\n" + "=" * 75)
    print("                    FINAL FUSED RESULTS (RRF)")
    print("=" * 75)

    if not fused_results:
        print("\n[!] Zero matching records retrieved (both retrieval methods returned empty).")
        print("=" * 75)
        return

    for res in fused_results:
        rank = res["final_rank"]
        rrf = res["rrf_score"]
        methods = ", ".join(res["matched_methods"])
        s_rank = res["semantic_rank"] if res["semantic_rank"] is not None else "N/A"
        s_dist = f"{res['semantic_distance']:.4f}" if res["semantic_distance"] is not None else "N/A"
        b_rank = res["bm25_rank"] if res["bm25_rank"] is not None else "N/A"
        b_score = f"{res['bm25_score']:.4f}" if res["bm25_score"] is not None else "N/A"

        rec_id = res["embedding_record_id"]
        doc_title = res["document_title"]
        prov_num = res["provision_number"]
        prov_type = res["provision_type"]
        prov_heading = res["provision_heading"]
        app_status = res["applicability_status"]
        rev_status = res["legal_review_status"]
        source_url = res["source_url"]
        p_start = res["pdf_page_start"]
        p_end = res["pdf_page_end"]
        raw_text = res["exact_original_text"]

        pages_str = f"pp. {p_start}-{p_end}" if p_start and p_end else "N/A"
        preview_text = raw_text[:200] + ("..." if len(raw_text) > 200 else "")

        print(f"\n[FINAL RANK {rank}] | RRF Score: {rrf:.6f} | Methods: [{methods}]")
        print(f"  Diagnostics:     Semantic Rank: {s_rank} (dist: {s_dist}) | BM25 Rank: {b_rank} (score: {b_score})")
        print(f"  Record ID:       {rec_id}")
        print(f"  Document Title:  {doc_title}")
        print(f"  Provision:       {prov_type} {prov_num}: {prov_heading}")
        print(f"  Applicability:   {app_status} | Legal Review: {rev_status}")
        print(f"  PDF Pages:       {pages_str}")
        print(f"  Source URL:      {source_url}")
        print(f"  Verbatim Text:   {preview_text}")
        print("-" * 75)


def evaluate_benchmark(test_cases_path: Path = TEST_CASES_PATH) -> None:
    """
    Evaluates Hybrid retrieval against the synthetic benchmark cases.
    Computes Recall@5, Recall@8, Precision@5, Mean Reciprocal Rank (MRR), and Latency.
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
    latencies: List[float] = []

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
            # Evaluate negative control / out of scope
            t0 = time.time()
            res = hybrid_search(query=query, top_k=5, include_procedural=req_proc, include_future=req_fut)
            latencies.append((time.time() - t0) * 1000)
            top_rrf = res[0]["rrf_score"] if res else 0.0
            print(f"[{cid}] (Abstention/Out of Scope) '{query[:40]}...' -> Retrieved: {len(res)}, Top RRF: {top_rrf:.6f}")
            continue

        total_evaluable += 1
        if lang not in lang_stats:
            lang_stats[lang] = {"total": 0, "hits_5": 0}
        lang_stats[lang]["total"] += 1

        t0 = time.time()
        results = hybrid_search(
            query=query,
            top_k=8,
            include_procedural=req_proc,
            include_future=req_fut,
        )
        latencies.append((time.time() - t0) * 1000)

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
        top_rrf = results[0]["rrf_score"] if results else 0.0
        methods = results[0]["matched_methods"] if results else []
        print(f"[{cid}] [{lang:8s}] [{cat:24s}] {status_str} | Top: {top_rec} (RRF: {top_rrf:.6f}, Methods: {methods})")

    # Aggregate Metrics
    recall_5 = (hits_at_5 / total_evaluable * 100) if total_evaluable else 0.0
    recall_8 = (hits_at_8 / total_evaluable * 100) if total_evaluable else 0.0
    prec_5 = (total_precision_at_5_hits / (total_evaluable * 5) * 100) if total_evaluable else 0.0
    mrr = (sum(reciprocal_ranks) / len(reciprocal_ranks)) if reciprocal_ranks else 0.0
    avg_latency = (sum(latencies) / len(latencies)) if latencies else 0.0

    print("\n" + "=" * 75)
    print("                HYBRID RETRIEVAL EVALUATION REPORT (RRF)")
    print("=" * 75)
    print(f"Total Test Cases:            {len(cases)}")
    print(f"Evaluable Relevant Cases:    {total_evaluable}")
    print(f"Abstention/Coverage Cases:   {len(cases) - total_evaluable}")
    print(f"Overall Recall@5:            {recall_5:.1f}% ({hits_at_5}/{total_evaluable})")
    print(f"Overall Recall@8:            {recall_8:.1f}% ({hits_at_8}/{total_evaluable})")
    print(f"Overall Precision@5:         {prec_5:.1f}%")
    print(f"Overall MRR:                 {mrr:.4f}")
    print(f"Average Latency:             {avg_latency:.1f} ms")
    print("-" * 75)
    print("Performance by Language (Recall@5):")
    for l_key, l_data in lang_stats.items():
        l_tot = l_data["total"]
        if l_tot > 0:
            l_rec = (l_data["hits_5"] / l_tot) * 100
            print(f"  - {l_key.upper():8s}: {l_rec:5.1f}% ({l_data['hits_5']}/{l_tot} cases)")
    print("=" * 75 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Nyaya Saathi Hybrid Legal Retrieval CLI (RRF)")
    parser.add_argument("--query", type=str, help="Search query (English, Hindi, or Hinglish)")
    parser.add_argument("--top_k", type=int, default=DEFAULT_TOP_K, help="Number of records to retrieve (1-10)")
    parser.add_argument("--procedural", action="store_true", help="Include procedural guidance collection")
    parser.add_argument("--future", action="store_true", help="Explicitly include future law collection")
    parser.add_argument("--date", type=str, help="Reference transaction or evaluation date (YYYY-MM-DD)")
    parser.add_argument("--eval", action="store_true", help="Run synthetic evaluation benchmark")
    parser.add_argument("--k", type=int, default=DEFAULT_RRF_K, help="RRF smoothing constant (default: 60)")

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
            rrf_k=args.k,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
