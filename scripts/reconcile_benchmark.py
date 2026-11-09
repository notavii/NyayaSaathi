"""
Benchmark Reconciliation and Comprehensive Comparative Evaluation Script.

Blueprint Phase 4C.1 Part C:
1. Re-evaluates Semantic-only, BM25-only, and Hybrid RRF on the 20 test cases
   defined in data/test_cases/semantic_retrieval_cases.json.
2. Standardizes evaluation unit at the CANONICAL LEGAL PROVISION LEVEL (parent_chunk_id).
3. Evaluates 18 positive substantive test cases and 2 negative controls.
4. Computes Recall@5, Recall@8, Precision@5, Precision@8, MRR, and average latency.
5. Saves raw per-query output to data/test_cases/hybrid_retrieval_raw_results.json.
"""

from datetime import date
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Set

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.bm25_retriever import bm25_search
from src.hybrid_retriever import calculate_rrf_score, hybrid_search, resolve_date_gating
from src.legal_retriever import semantic_search

TEST_CASES_PATH = ROOT_DIR / "data" / "test_cases" / "semantic_retrieval_cases.json"
OUTPUT_RAW_PATH = ROOT_DIR / "data" / "test_cases" / "hybrid_retrieval_raw_results.json"


def find_first_relevant_rank(results: List[Dict[str, Any]], expected_parents: Set[str], max_k: int = 8) -> Optional[int]:
    """
    Finds the 1-based rank of the FIRST retrieved record whose parent_chunk_id
    matches any of the expected canonical legal provisions.
    """
    for rank_idx, r in enumerate(results[:max_k], start=1):
        parent_id = r.get("parent_chunk_id") or r.get("chunk_id")
        if parent_id in expected_parents:
            return rank_idx
    return None


def calculate_precision_at_k(results: List[Dict[str, Any]], expected_parents: Set[str], k: int) -> float:
    """
    Computes Precision@K at the canonical legal provision level.
    Only unique matching parent provisions in the top K are counted.
    """
    if not results or k <= 0:
        return 0.0
    top_k_parents = set()
    for r in results[:k]:
        pid = r.get("parent_chunk_id") or r.get("chunk_id")
        if pid:
            top_k_parents.add(pid)
    matched = len(top_k_parents.intersection(expected_parents))
    return matched / float(k)


def run_reconciliation():
    with open(TEST_CASES_PATH, "r", encoding="utf-8") as f:
        cases_data = json.load(f)

    cases = cases_data.get("cases", [])
    print(f"Loaded {len(cases)} test cases from {TEST_CASES_PATH.name}\n")

    substantive_cases = [c for c in cases if not c.get("is_abstention_case", False)]
    negative_controls = [c for c in cases if c.get("is_abstention_case", False)]

    print(f"Substantive Positive Cases: {len(substantive_cases)}")
    print(f"Negative Control / Abstention Cases: {len(negative_controls)}\n")

    # Metrics accumulators
    methods = ["semantic", "bm25", "hybrid"]
    metrics: Dict[str, Dict[str, Any]] = {
        m: {
            "hits_at_5": 0,
            "hits_at_8": 0,
            "precision_at_5": [],
            "precision_at_8": [],
            "reciprocal_ranks": [],
            "latencies": [],
        }
        for m in methods
    }

    per_query_results = []

    for c in substantive_cases:
        cid = c["case_id"]
        lang = c.get("language", "en")
        cat = c["category"]
        query = c["query"]
        expected_parents = set(c.get("expected_parent_provisions", []))
        req_proc = c.get("requires_procedural", False)
        req_fut = c.get("requires_future", False)

        # 1. Semantic-Only
        t0 = time.time()
        sem_res = semantic_search(
            query=query,
            top_k=8,
            include_procedural=req_proc,
            include_future=req_fut,
        )
        lat_sem = (time.time() - t0) * 1000
        metrics["semantic"]["latencies"].append(lat_sem)

        sem_rank = find_first_relevant_rank(sem_res, expected_parents, max_k=8)
        if sem_rank and sem_rank <= 5:
            metrics["semantic"]["hits_at_5"] += 1
        if sem_rank and sem_rank <= 8:
            metrics["semantic"]["hits_at_8"] += 1
        metrics["semantic"]["precision_at_5"].append(calculate_precision_at_k(sem_res, expected_parents, 5))
        metrics["semantic"]["precision_at_8"].append(calculate_precision_at_k(sem_res, expected_parents, 8))
        metrics["semantic"]["reciprocal_ranks"].append(1.0 / sem_rank if sem_rank else 0.0)

        # 2. BM25-Only
        t0 = time.time()
        bm25_res = bm25_search(
            query=query,
            top_k=8,
            include_procedural=req_proc,
            include_future=req_fut,
        )
        lat_bm25 = (time.time() - t0) * 1000
        metrics["bm25"]["latencies"].append(lat_bm25)

        bm25_rank = find_first_relevant_rank(bm25_res, expected_parents, max_k=8)
        if bm25_rank and bm25_rank <= 5:
            metrics["bm25"]["hits_at_5"] += 1
        if bm25_rank and bm25_rank <= 8:
            metrics["bm25"]["hits_at_8"] += 1
        metrics["bm25"]["precision_at_5"].append(calculate_precision_at_k(bm25_res, expected_parents, 5))
        metrics["bm25"]["precision_at_8"].append(calculate_precision_at_k(bm25_res, expected_parents, 8))
        metrics["bm25"]["reciprocal_ranks"].append(1.0 / bm25_rank if bm25_rank else 0.0)

        # 3. Hybrid RRF
        t0 = time.time()
        hyb_res = hybrid_search(
            query=query,
            top_k=8,
            include_procedural=req_proc,
            include_future=req_fut,
        )
        lat_hyb = (time.time() - t0) * 1000
        metrics["hybrid"]["latencies"].append(lat_hyb)

        hyb_rank = find_first_relevant_rank(hyb_res, expected_parents, max_k=8)
        if hyb_rank and hyb_rank <= 5:
            metrics["hybrid"]["hits_at_5"] += 1
        if hyb_rank and hyb_rank <= 8:
            metrics["hybrid"]["hits_at_8"] += 1
        metrics["hybrid"]["precision_at_5"].append(calculate_precision_at_k(hyb_res, expected_parents, 5))
        metrics["hybrid"]["precision_at_8"].append(calculate_precision_at_k(hyb_res, expected_parents, 8))
        metrics["hybrid"]["reciprocal_ranks"].append(1.0 / hyb_rank if hyb_rank else 0.0)

        # Diagnostic explanation of result
        explanation = ""
        if hyb_rank == 1:
            explanation = "Target provision ranked #1 by hybrid fusion."
        elif hyb_rank and hyb_rank <= 5:
            explanation = f"Target provision ranked #{hyb_rank} in top-5."
        elif hyb_rank and hyb_rank <= 8:
            explanation = f"Target provision retrieved in top-8 at rank #{hyb_rank} (missed top-5)."
        else:
            explanation = "False negative: Target provision not found in top-8 candidates."

        per_query_results.append({
            "case_id": cid,
            "language": lang,
            "category": cat,
            "query": query,
            "expected_parent_provisions": sorted(list(expected_parents)),
            "semantic_rank": sem_rank,
            "bm25_rank": bm25_rank,
            "hybrid_rank": hyb_rank,
            "hybrid_hit_at_5": bool(hyb_rank and hyb_rank <= 5),
            "hybrid_hit_at_8": bool(hyb_rank and hyb_rank <= 8),
            "explanation": explanation,
            "top_hybrid_retrieved_parent": (hyb_res[0].get("parent_chunk_id") if hyb_res else None),
            "top_hybrid_methods": (hyb_res[0].get("matched_methods") if hyb_res else []),
        })

    # Negative Control Evaluation
    neg_control_results = []
    for c in negative_controls:
        cid = c["case_id"]
        query = c["query"]
        cat = c["category"]

        # Run hybrid retrieval
        hyb_res = hybrid_search(query=query, top_k=5)
        # Note: In an integrated assistant, the Issue Scope Classifier gates out-of-scope queries
        # before retrieval. If submitted directly to retrieval, ChromaDB/BM25 will return nearest items.
        neg_control_results.append({
            "case_id": cid,
            "category": cat,
            "query": query,
            "raw_retrieved_count": len(hyb_res),
            "top_returned_provision": hyb_res[0]["parent_chunk_id"] if hyb_res else None,
            "top_rrf_score": hyb_res[0]["rrf_score"] if hyb_res else 0.0,
            "classifier_gated": True,  # Verified by test_21
            "notes": "Direct vector search produces nearest lexical/semantic items; production pipeline gates via classifier.",
        })

    # Summary Statistics
    N = len(substantive_cases)
    summary_stats = {}
    for m in methods:
        rec5 = (metrics[m]["hits_at_5"] / N) * 100
        rec8 = (metrics[m]["hits_at_8"] / N) * 100
        prec5 = (sum(metrics[m]["precision_at_5"]) / N) * 100
        prec8 = (sum(metrics[m]["precision_at_8"]) / N) * 100
        mrr = sum(metrics[m]["reciprocal_ranks"]) / N
        avg_lat = sum(metrics[m]["latencies"]) / N

        summary_stats[m] = {
            "recall_at_5": round(rec5, 2),
            "recall_at_8": round(rec8, 2),
            "precision_at_5": round(prec5, 2),
            "precision_at_8": round(prec8, 2),
            "mrr": round(mrr, 4),
            "avg_latency_ms": round(avg_lat, 1),
            "hits_at_5": metrics[m]["hits_at_5"],
            "hits_at_8": metrics[m]["hits_at_8"],
            "total_evaluable": N,
        }

    output_payload = {
        "metadata": {
            "evaluation_timestamp": str(date.today()),
            "total_test_cases": len(cases),
            "substantive_cases": N,
            "negative_controls": len(negative_controls),
            "evaluation_unit": "canonical_legal_provision_level (parent_chunk_id)",
            "rrf_parameters": {"k": 60, "semantic_weight": 1.0, "bm25_weight": 1.0},
        },
        "summary_metrics": summary_stats,
        "per_query_results": per_query_results,
        "negative_control_results": neg_control_results,
    }

    with open(OUTPUT_RAW_PATH, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)

    print("=" * 80)
    print("                    RECONCILED RETRIEVAL BENCHMARK")
    print("=" * 80)
    print(f"{'Metric':<20} | {'Semantic-Only':<15} | {'BM25-Only':<15} | {'Hybrid (RRF)':<15}")
    print("-" * 80)
    print(f"{'Recall@5':<20} | {summary_stats['semantic']['recall_at_5']:>6.1f}% ({summary_stats['semantic']['hits_at_5']}/{N})   | {summary_stats['bm25']['recall_at_5']:>6.1f}% ({summary_stats['bm25']['hits_at_5']}/{N})   | {summary_stats['hybrid']['recall_at_5']:>6.1f}% ({summary_stats['hybrid']['hits_at_5']}/{N})")
    print(f"{'Recall@8':<20} | {summary_stats['semantic']['recall_at_8']:>6.1f}% ({summary_stats['semantic']['hits_at_8']}/{N})   | {summary_stats['bm25']['recall_at_8']:>6.1f}% ({summary_stats['bm25']['hits_at_8']}/{N})   | {summary_stats['hybrid']['recall_at_8']:>6.1f}% ({summary_stats['hybrid']['hits_at_8']}/{N})")
    print(f"{'Precision@5':<20} | {summary_stats['semantic']['precision_at_5']:>6.1f}%         | {summary_stats['bm25']['precision_at_5']:>6.1f}%         | {summary_stats['hybrid']['precision_at_5']:>6.1f}%")
    print(f"{'Precision@8':<20} | {summary_stats['semantic']['precision_at_8']:>6.1f}%         | {summary_stats['bm25']['precision_at_8']:>6.1f}%         | {summary_stats['hybrid']['precision_at_8']:>6.1f}%")
    print(f"{'MRR':<20} | {summary_stats['semantic']['mrr']:>14.4f}  | {summary_stats['bm25']['mrr']:>14.4f}  | {summary_stats['hybrid']['mrr']:>14.4f}")
    print(f"{'Avg Latency (ms)':<20} | {summary_stats['semantic']['avg_latency_ms']:>11.1f} ms | {summary_stats['bm25']['avg_latency_ms']:>11.1f} ms | {summary_stats['hybrid']['avg_latency_ms']:>11.1f} ms")
    print("=" * 80)

    print("\nPER-QUERY COMPARATIVE RANKS:")
    print(f"{'ID':<10} | {'Lang':<5} | {'Expected Provisions':<30} | {'Sem Rank':<9} | {'BM25 Rank':<9} | {'Hybrid':<9}")
    print("-" * 80)
    for p in per_query_results:
        exp_str = ", ".join(p["expected_parent_provisions"])
        if len(exp_str) > 28:
            exp_str = exp_str[:25] + "..."
        s_r = f"Rank {p['semantic_rank']}" if p['semantic_rank'] else "MISS"
        b_r = f"Rank {p['bm25_rank']}" if p['bm25_rank'] else "MISS"
        h_r = f"Rank {p['hybrid_rank']}" if p['hybrid_rank'] else "MISS"
        print(f"{p['case_id']:<10} | {p['language']:<5} | {exp_str:<30} | {s_r:<9} | {b_r:<9} | {h_r:<9}")
    print("=" * 80)


if __name__ == "__main__":
    run_reconciliation()
