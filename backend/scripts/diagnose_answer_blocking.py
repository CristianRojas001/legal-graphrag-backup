"""
Diagnostic script to find where answers are getting blocked.
Shows exactly which gate kills the answer.
"""

import os
import sys
import django
import logging

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')
django.setup()

from apps.legal_graphrag.services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1

# Monkey-patch to add diagnostics
original_validate = None
original_judge = None
original_should_abstain = None

diagnostics = {
    "retrieval": {},
    "abstain_check": {},
    "llm_response": {},
    "validation": {},
    "judge": {},
    "final_answer": {}
}

def diagnostic_validate_answer(self, answer, sources, area_principal, query):
    """Wrapper to log validation behavior"""
    print("\n" + "="*80)
    print("VALIDATION GATE")
    print("="*80)

    print(f"Answer before validation ({len(answer)} chars):")
    print(answer[:500])
    print("...")

    # Check for numeric patterns
    import re
    has_percent = re.search(r"\d+[\.,]?\d*\s*%", answer)
    has_tipo = re.search(r"tipo", answer, re.IGNORECASE)

    print(f"\nNumeric content detected:")
    print(f"  - Has percentage: {bool(has_percent)}")
    print(f"  - Has 'tipo': {bool(has_tipo)}")

    if has_percent or has_tipo:
        source_text = " ".join([src.get('chunk_text', '') for group in sources.values() for src in group])
        print(f"  - Source text length: {len(source_text)} chars")
        print(f"  - Has numeric in sources: {bool(re.search(r'\\d+%', source_text))}")

    # Call original
    result = original_validate(self, answer, sources, area_principal, query)

    if result != answer:
        print("\n[WARNING] VALIDATION CHANGED THE ANSWER!")
        print(f"New answer ({len(result)} chars):")
        print(result[:500])
        diagnostics["validation"]["blocked"] = True
        diagnostics["validation"]["reason"] = "Validation returned different answer (likely abstain)"
    else:
        print("\n[OK] Validation passed - answer unchanged")
        diagnostics["validation"]["blocked"] = False

    return result

def diagnostic_judge(self, query, answer, sources):
    """Wrapper to log judge behavior"""
    print("\n" + "="*80)
    print("JUDGE GATE")
    print("="*80)

    result = original_judge(self, query, answer, sources)

    print(f"Judge verdict: {result.get('verdict')}")
    print(f"Judge reasons: {result.get('reasons')}")

    diagnostics["judge"]["verdict"] = result.get("verdict")
    diagnostics["judge"]["reasons"] = result.get("reasons")

    if result.get("verdict") == "REDO":
        print("\n[WARNING] JUDGE TRIGGERED REDO - Answer will be regenerated with defensive prompt")
    else:
        print("\n[OK] Judge passed")

    return result

def diagnostic_should_abstain(self, query, area_principal, sources):
    """Wrapper to log abstain check"""
    print("\n" + "="*80)
    print("ABSTAIN CHECK GATE")
    print("="*80)

    result = original_should_abstain(self, query, area_principal, sources)

    total_sources = sum(len(v) for v in sources.values())
    print(f"Total sources: {total_sources}")
    print(f"  - Normativa: {len(sources.get('normativa', []))}")
    print(f"  - Doctrina: {len(sources.get('doctrina', []))}")
    print(f"  - Jurisprudencia: {len(sources.get('jurisprudencia', []))}")
    print(f"\nShould abstain: {result}")

    diagnostics["abstain_check"]["abstain"] = result
    diagnostics["abstain_check"]["total_sources"] = total_sources

    if result:
        print("[WARNING] ABSTAIN FLAG SET (but shouldn't block in v1.1)")
    else:
        print("[OK] Abstain check passed")

    return result


def test_query(query):
    """Test a single query with full diagnostics"""
    global original_validate, original_judge, original_should_abstain, diagnostics

    print("\n" + "="*80)
    print("="*80)
    print(f"TESTING QUERY: {query}")
    print("="*80)
    print("="*80)

    # Reset diagnostics
    diagnostics = {
        "retrieval": {},
        "abstain_check": {},
        "llm_response": {},
        "validation": {},
        "judge": {},
        "final_answer": {}
    }

    # Create engine and monkey-patch
    engine = LegalRAGEngineV1_1()

    # Save originals
    from apps.legal_graphrag.services.legal_rag_engine import LegalRAGEngine
    original_validate = LegalRAGEngine._validate_answer
    original_should_abstain = LegalRAGEngine._should_abstain

    from apps.legal_graphrag.services.v1_1.judge_v1_1 import AnswerJudgeV1_1
    original_judge = AnswerJudgeV1_1.judge

    # Monkey-patch
    LegalRAGEngine._validate_answer = diagnostic_validate_answer
    LegalRAGEngine._should_abstain = diagnostic_should_abstain
    AnswerJudgeV1_1.judge = diagnostic_judge

    try:
        # Run query
        result = engine.answer_query(query=query, max_sources=10)

        print("\n" + "="*80)
        print("RETRIEVAL RESULTS")
        print("="*80)
        diagnostics["retrieval"]["expanded_queries"] = result.get('metadata', {}).get('expanded_queries', [])
        diagnostics["retrieval"]["total_sources"] = result.get('metadata', {}).get('total_sources', 0)
        diagnostics["retrieval"]["authority_question"] = result.get('metadata', {}).get('authority_question', False)
        diagnostics["retrieval"]["authority_pack_added"] = result.get('metadata', {}).get('authority_pack_added', False)

        print(f"Expanded queries ({len(diagnostics['retrieval']['expanded_queries'])}):")
        for i, eq in enumerate(diagnostics['retrieval']['expanded_queries'][:5], 1):
            print(f"  {i}. {eq}")
        print(f"\nTotal sources retrieved: {diagnostics['retrieval']['total_sources']}")
        print(f"Authority question: {diagnostics['retrieval']['authority_question']}")
        print(f"Authority pack added: {diagnostics['retrieval']['authority_pack_added']}")

        print("\n" + "="*80)
        print("FINAL ANSWER")
        print("="*80)
        answer = result.get('answer', '')
        diagnostics["final_answer"]["length"] = len(answer)
        diagnostics["final_answer"]["preview"] = answer[:300]

        print(f"Length: {len(answer)} chars")
        print(f"\nPreview (first 300 chars):")
        print(answer[:300])
        if len(answer) > 300:
            print("...")

        # Check if answer is unhelpful
        unhelpful_phrases = [
            "no puedo afirmar",
            "no hay información",
            "no se encontraron fuentes",
            "no tengo información",
            "con las fuentes disponibles no puedo"
        ]
        is_unhelpful = any(phrase in answer.lower() for phrase in unhelpful_phrases)
        diagnostics["final_answer"]["is_unhelpful"] = is_unhelpful

        if is_unhelpful:
            print("\n[WARNING] ANSWER APPEARS UNHELPFUL - contains defensive phrases")

        print("\n" + "="*80)
        print("DIAGNOSIS SUMMARY")
        print("="*80)

        # Identify the blocker
        blockers = []

        if diagnostics["abstain_check"].get("abstain"):
            blockers.append("[WARN] ABSTAIN flag set (metadata only in v1.1)")

        if diagnostics["validation"].get("blocked"):
            blockers.append("[BLOCK] VALIDATION blocked/changed the answer")

        if diagnostics["judge"].get("verdict") == "REDO":
            blockers.append("[BLOCK] JUDGE triggered REDO with defensive prompt")

        if diagnostics["retrieval"]["total_sources"] == 0:
            blockers.append("[BLOCK] NO SOURCES retrieved")
        elif diagnostics["retrieval"]["total_sources"] < 3:
            blockers.append("[WARN] Very few sources retrieved")

        if is_unhelpful and diagnostics["retrieval"]["total_sources"] > 0:
            blockers.append("[BLOCK] Answer is unhelpful despite having sources")

        if blockers:
            print("\nPROBLEMS DETECTED:")
            for blocker in blockers:
                print(f"  {blocker}")
        else:
            print("\n[OK] No obvious blockers detected")

        print(f"\nMetadata:")
        print(f"  - Abstained: {result.get('metadata', {}).get('abstained')}")
        print(f"  - Redo performed: {result.get('metadata', {}).get('redo_performed')}")
        print(f"  - Postprocess errors: {result.get('metadata', {}).get('postprocess_errors')}")

        return result, diagnostics

    except Exception as e:
        print(f"\n[ERROR] EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return None, diagnostics
    finally:
        # Restore originals
        LegalRAGEngine._validate_answer = original_validate
        LegalRAGEngine._should_abstain = original_should_abstain
        AnswerJudgeV1_1.judge = original_judge


if __name__ == '__main__':
    # Test queries - pick ones that are likely problematic
    test_queries = [
        "¿Cuál es el tipo de IVA para servicios digitales?",
        "¿Qué retención se aplica en actividades artísticas?",
        "¿Cómo funciona la jerarquía normativa en España?",
    ]

    if len(sys.argv) > 1:
        # User provided a query
        query = ' '.join(sys.argv[1:])
        test_query(query)
    else:
        # Run all test queries
        for i, query in enumerate(test_queries, 1):
            print(f"\n\n{'#'*80}")
            print(f"TEST {i}/{len(test_queries)}")
            print(f"{'#'*80}")
            test_query(query)
            if i < len(test_queries):
                input("\nPress Enter to continue to next test...")
