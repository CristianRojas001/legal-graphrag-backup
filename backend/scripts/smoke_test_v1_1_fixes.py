"""
Smoke tests for V1.1 fixes:
- Authority pack for hierarchy questions
- Unicode/accent preservation
- No "Failed to generate answer" crashes
- Proper handling of meta-legal questions
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')
django.setup()

from apps.legal_graphrag.services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1


def print_separator():
    print("\n" + "="*80 + "\n")


def test_query(engine, query, test_name):
    """Run a single test query and display results."""
    print(f"TEST: {test_name}")
    print(f"Query: {query}")
    print("-" * 80)

    try:
        result = engine.answer_query(query=query, max_sources=10)

        # Check for encoding issues
        answer = result.get('answer', '')
        has_question_marks = '?' in answer and not '¿' in query

        print(f"✓ Status: SUCCESS")
        print(f"✓ Answer length: {len(answer)} chars")
        print(f"✓ Sources: {result.get('metadata', {}).get('total_sources', 0)}")
        print(f"✓ Authority question: {result.get('metadata', {}).get('authority_question', False)}")
        print(f"✓ Authority pack added: {result.get('metadata', {}).get('authority_pack_added', False)}")
        print(f"✓ Authority pack count: {result.get('metadata', {}).get('authority_pack_count', 0)}")
        print(f"✓ Abstained: {result.get('metadata', {}).get('abstained', False)}")
        print(f"✓ Judge verdict: {result.get('metadata', {}).get('judge', {}).get('verdict', 'N/A')}")
        print(f"✓ Postprocess errors: {result.get('metadata', {}).get('postprocess_errors', None)}")

        # Display expanded queries
        expanded = result.get('metadata', {}).get('expanded_queries', [])
        if expanded:
            print(f"✓ Expanded queries ({len(expanded)}):")
            for i, eq in enumerate(expanded[:5], 1):
                print(f"  {i}. {eq}")

        # Check for encoding issues
        if has_question_marks:
            print("⚠ WARNING: Possible encoding issue detected (question marks in answer)")

        # Display answer preview
        print(f"\nAnswer preview (first 300 chars):")
        print(answer[:300])
        if len(answer) > 300:
            print("...")

        # Check for "no evidence" only answers
        no_evidence_phrases = [
            "no puedo afirmar",
            "no hay informacion",
            "no se encontraron fuentes",
        ]
        is_unhelpful = any(phrase in answer.lower() for phrase in no_evidence_phrases)
        if is_unhelpful and result.get('metadata', {}).get('total_sources', 0) > 0:
            print("⚠ WARNING: Answer appears unhelpful despite having sources")

        return True

    except Exception as e:
        print(f"✗ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("="*80)
    print("Legal GraphRAG V1.1 - Smoke Tests for Fixes")
    print("="*80)

    engine = LegalRAGEngineV1_1()

    # Test cases for meta-legal/authority questions
    test_cases = [
        (
            "¿Cuál es la norma con mayor rango jurídico en España?",
            "Test 1: Hierarchy - Top norm (Constitución)"
        ),
        (
            "¿Puede un reglamento contradecir una ley?",
            "Test 2: Hierarchy - Reglamento vs Ley"
        ),
        (
            "¿Qué diferencia hay entre ley orgánica y ley ordinaria?",
            "Test 3: Hierarchy - Ley orgánica vs ordinaria"
        ),
        (
            "¿Cómo funciona la jerarquía normativa en España?",
            "Test 4: Hierarchy - General question"
        ),
        (
            "¿Qué tipos de retenciones existen en IRPF?",
            "Test 5: Regular question with accents (típicos, más)"
        ),
        (
            "¿Cómo se aplica el procedimiento administrativo común?",
            "Test 6: Regular question - should not trigger authority pack"
        ),
    ]

    results = []
    for query, test_name in test_cases:
        print_separator()
        success = test_query(engine, query, test_name)
        results.append((test_name, success))

    # Summary
    print_separator()
    print("SUMMARY")
    print("-" * 80)
    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print()

    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {test_name}")

    print_separator()

    if passed == total:
        print("✓ ALL TESTS PASSED!")
        return 0
    else:
        print(f"✗ {total - passed} TEST(S) FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
