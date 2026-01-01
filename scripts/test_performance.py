"""
Test script to measure RAG performance improvements
Runs a sample query and reports detailed timings
"""

import os
import sys
import django
import time

# Setup Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')
django.setup()

from apps.legal_graphrag.services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1

# Test queries covering different scenarios
TEST_QUERIES = [
    {
        "query": "¿Qué retenciones de IRPF aplican a artistas autónomos?",
        "expected_area": "Fiscal",
        "description": "Fiscal query (specific rate question)"
    },
    {
        "query": "¿Cuál es el tipo de IVA para servicios culturales?",
        "expected_area": "Fiscal",
        "description": "Fiscal query (IVA rate)"
    },
    {
        "query": "¿Qué derechos tienen los autores sobre obras musicales?",
        "expected_area": "Propiedad Intelectual",
        "description": "IP query (conceptual)"
    },
    {
        "query": "¿Cómo funciona el contrato de artista en régimen especial?",
        "expected_area": "Laboral",
        "description": "Labor query (contract question)"
    },
]

def test_performance():
    print("=" * 80)
    print("RAG PERFORMANCE TEST")
    print("=" * 80)
    print()

    engine = LegalRAGEngineV1_1()

    print(f"Configuration:")
    print(f"  - Area filtering enabled: {engine._area_filter_enabled}")
    print(f"  - Semantic matching enabled: {engine._semantic_match_enabled}")
    print()

    total_times = []

    for i, test_case in enumerate(TEST_QUERIES, 1):
        print(f"\n{'=' * 80}")
        print(f"Test {i}/{len(TEST_QUERIES)}: {test_case['description']}")
        print(f"Query: {test_case['query']}")
        print(f"Expected area: {test_case['expected_area']}")
        print(f"{'=' * 80}")

        t_start = time.time()

        try:
            result = engine.answer_query(
                query=test_case['query'],
                session_id=f"perf_test_{i}"
            )

            t_total = time.time() - t_start
            total_times.append(t_total)

            metadata = result.get('metadata', {})
            debug = metadata.get('debug_summary', {})

            print(f"\n[OK] Query completed in {t_total:.2f}s")
            print(f"\nResults:")
            print(f"  - Detected area: {metadata.get('area_principal')}")
            print(f"  - Total sources: {metadata.get('total_sources')}")
            print(f"  - Cited sources: {metadata.get('cited_count')}")
            print(f"  - Abstained: {metadata.get('abstained')}")
            print(f"  - Judge verdict: {metadata.get('judge', {}).get('verdict')}")

            # Show retrieval stats
            retrieval = debug.get('retrieval', {})
            print(f"\nRetrieval stats:")
            print(f"  - Queries expanded: {retrieval.get('query_expansion', {}).get('count', 0)}")
            print(f"  - Combined results: {retrieval.get('retrieval_counts', {}).get('combined_results', 0)}")
            print(f"  - After filters: {sum((retrieval.get('retrieval_counts', {}).get('post_filter', {})).values())}")

            print(f"\nAnswer preview:")
            answer = result.get('answer', '')
            print(f"  {answer[:200]}{'...' if len(answer) > 200 else ''}")

        except Exception as e:
            print(f"\n[ERROR] Query failed: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n\n{'=' * 80}")
    print(f"SUMMARY")
    print(f"{'=' * 80}")
    print(f"Tests completed: {len(total_times)}/{len(TEST_QUERIES)}")
    if total_times:
        print(f"Average time: {sum(total_times) / len(total_times):.2f}s")
        print(f"Min time: {min(total_times):.2f}s")
        print(f"Max time: {max(total_times):.2f}s")
        print(f"Total time: {sum(total_times):.2f}s")

    print(f"\nCheck backend/logs/ for detailed timing breakdowns")

if __name__ == '__main__':
    test_performance()
