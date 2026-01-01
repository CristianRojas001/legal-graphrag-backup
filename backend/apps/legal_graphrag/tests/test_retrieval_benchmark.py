import json
import os
from pathlib import Path

import pytest
from django.conf import settings

from apps.legal_graphrag.models import LegalDocument
from apps.legal_graphrag.services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1


def _load_cases() -> list[dict]:
    path = Path(__file__).resolve().parent / "fixtures" / "retrieval_benchmark.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _calculate_mrr(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    for rank, doc_id in enumerate(retrieved_ids, 1):
        if doc_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def _calculate_recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    retrieved_set = set(retrieved_ids[:k])
    relevant_set = set(relevant_ids)
    if not relevant_set:
        return 0.0
    return len(retrieved_set & relevant_set) / len(relevant_set)


@pytest.mark.django_db
@pytest.mark.slow
def test_retrieval_benchmark():
    if os.getenv("RAG_RUN_RETRIEVAL_BENCHMARK", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set RAG_RUN_RETRIEVAL_BENCHMARK=1 to run retrieval benchmark.")
    if not getattr(settings, "GEMINI_API_KEY", ""):
        pytest.skip("GEMINI_API_KEY not configured for retrieval benchmark.")

    cases = _load_cases()
    if not cases:
        pytest.skip("No benchmark cases found.")

    all_expected = {
        doc_id
        for case in cases
        for doc_id in (case.get("relevant_docs") or [])
        if doc_id
    }
    available_docs = set(
        LegalDocument.objects.filter(doc_id_oficial__in=all_expected)
        .values_list("doc_id_oficial", flat=True)
    )

    runnable_cases = [
        case
        for case in cases
        if any(doc_id in available_docs for doc_id in (case.get("relevant_docs") or []))
    ]
    if not runnable_cases:
        pytest.skip("No benchmark cases match documents present in the DB.")

    engine = LegalRAGEngineV1_1()
    enforce = os.getenv("RAG_BENCHMARK_ENFORCE", "").lower() in {"1", "true", "yes"}

    mrr_scores = []
    recall_at_5_scores = []
    recall_at_10_scores = []

    for case in runnable_cases:
        sources, _trace = engine._retrieve_hierarchical_sources_v1_1(
            query=case["query"],
            area_principal=case.get("area"),
            max_sources=10,
            expansion_max_total=4,
            expansion_llm_variants=0,
            per_query_limit=10,
            session_id="benchmark",
            intent_confidence=1.0,
            router_decision=None,
            expanded_queries=None,
        )

        retrieved_ids = [
            src.get("document_id")
            for bucket in sources.values()
            for src in bucket
            if src.get("document_id")
        ]

        relevant_ids = case.get("relevant_docs") or []
        mrr_scores.append(_calculate_mrr(retrieved_ids, relevant_ids))
        recall_at_5_scores.append(_calculate_recall_at_k(retrieved_ids, relevant_ids, 5))
        recall_at_10_scores.append(_calculate_recall_at_k(retrieved_ids, relevant_ids, 10))

        must_include = [doc_id for doc_id in (case.get("must_include") or []) if doc_id in available_docs]
        if enforce and must_include:
            for doc_id in must_include:
                assert doc_id in retrieved_ids[:10], (
                    f"Missing must-include doc {doc_id} for query: {case['query']}"
                )

    avg_mrr = sum(mrr_scores) / len(mrr_scores)
    avg_recall_5 = sum(recall_at_5_scores) / len(recall_at_5_scores)
    avg_recall_10 = sum(recall_at_10_scores) / len(recall_at_10_scores)

    print(f"\n=== Retrieval Benchmark Results ===")  # pytest captures but shows on failure.
    print(f"MRR: {avg_mrr:.3f}")
    print(f"Recall@5: {avg_recall_5:.3f}")
    print(f"Recall@10: {avg_recall_10:.3f}")

    if enforce:
        min_mrr = float(os.getenv("RAG_BENCHMARK_MIN_MRR", "0.60"))
        min_recall_5 = float(os.getenv("RAG_BENCHMARK_MIN_RECALL5", "0.70"))
        min_recall_10 = float(os.getenv("RAG_BENCHMARK_MIN_RECALL10", "0.85"))
        assert avg_mrr >= min_mrr, f"MRR below threshold: {avg_mrr:.3f}"
        assert avg_recall_5 >= min_recall_5, f"Recall@5 below threshold: {avg_recall_5:.3f}"
        assert avg_recall_10 >= min_recall_10, f"Recall@10 below threshold: {avg_recall_10:.3f}"
