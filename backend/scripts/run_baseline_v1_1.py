"""
Simple baseline runner for V1.1 fixes - outputs to JSON for comparison
"""

import os
import sys
import json
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')
django.setup()

from apps.legal_graphrag.services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1


def run_baseline():
    """Run baseline tests and save results as JSON"""

    engine = LegalRAGEngineV1_1()

    test_cases = [
        {
            "id": "meta_what_can_you_do",
            "query": "Que puedes hacer?",
            "description": "Meta query: what can you do"
        },
        {
            "id": "legal_no_citations",
            "query": "Explica el concepto general de IVA",
            "description": "Legal query with no citations expected"
        },
        {
            "id": "legal_one_citation",
            "query": "Cual es la ley que regula el IRPF en Espana?",
            "description": "Legal query with one citation expected"
        },
        {
            "id": "iva_rate_missing_evidence",
            "query": "Cual es el tipo de IVA aplicable a servicios de interpretacion musical?",
            "description": "IVA rate question with missing rate evidence"
        },
        {
            "id": "iva_conceptual",
            "query": "Que obligaciones tiene un autonomo respecto al IVA?",
            "description": "IVA conceptual question without rate request"
        }
    ]

    results = []
    for test_case in test_cases:
        print(f"Running: {test_case['id']}")
        try:
            result = engine.answer_query(query=test_case['query'], max_sources=10)

            # Extract key fields for comparison
            answer = result.get('answer', '')

            # Count "Fuentes utilizadas" section
            has_fuentes_section = "**Fuentes utilizadas**:" in answer

            # Extract cited IDs from answer
            import re
            cited_ids = set(re.findall(r"\[ID:\s*([^\]]+)\]", answer))

            test_result = {
                "id": test_case['id'],
                "query": test_case['query'],
                "description": test_case['description'],
                "answer_length": len(answer),
                "has_fuentes_section": has_fuentes_section,
                "cited_ids_count": len(cited_ids),
                "cited_ids": list(cited_ids),
                "total_sources": result.get('metadata', {}).get('total_sources', 0),
                "abstained": result.get('metadata', {}).get('abstained', False),
                "answer_preview": answer[:500]
            }
            results.append(test_result)
            print(f"  OK - {len(cited_ids)} citations, {result.get('metadata', {}).get('total_sources', 0)} sources")

        except Exception as e:
            print(f"  FAILED: {e}")
            results.append({
                "id": test_case['id'],
                "query": test_case['query'],
                "description": test_case['description'],
                "error": str(e)
            })

    # Save baseline
    with open('baseline_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nBaseline saved to baseline_results.json")
    print(f"Completed {len(results)} test cases")

    return results


if __name__ == '__main__':
    run_baseline()
