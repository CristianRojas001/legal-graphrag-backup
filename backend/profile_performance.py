"""
Performance profiling script for Legal GraphRAG
Measures time spent in each component of the RAG pipeline
"""

import os
import sys
import django
import time
from contextlib import contextmanager

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')
django.setup()

from apps.legal_graphrag.services.legal_rag_engine import LegalRAGEngine
from apps.legal_graphrag.services.legal_search_engine import LegalSearchEngine

@contextmanager
def timer(name):
    """Context manager to time code blocks"""
    start = time.time()
    yield
    elapsed = time.time() - start
    print(f"  {name}: {elapsed:.3f}s")
    return elapsed

def profile_search(query: str):
    """Profile search engine performance"""
    print(f"\n=== Profiling Search: '{query}' ===")
    engine = LegalSearchEngine()

    total_start = time.time()

    with timer("Vector search"):
        vector_results = engine.vector_search(query, limit=10)

    with timer("Lexical search"):
        lexical_results = engine.lexical_search(query, limit=10)

    with timer("RRF fusion"):
        hybrid_results = engine.hybrid_search(query, limit=10)

    total_elapsed = time.time() - total_start
    print(f"  TOTAL: {total_elapsed:.3f}s")
    print(f"  Results: {len(hybrid_results)} chunks")

    return total_elapsed

def profile_chat(query: str):
    """Profile RAG engine performance"""
    print(f"\n=== Profiling Chat: '{query}' ===")
    engine = LegalRAGEngine()

    total_start = time.time()

    # Manually profile each step
    print("\nStep 1: Intent Classification")
    with timer("Intent classification"):
        area_classification = engine.intent_classifier.classify_with_confidence(query)
        area_principal = area_classification.get('area')

    print(f"\nStep 2: Hierarchical Search (area: {area_principal})")
    with timer("Hierarchical search"):
        sources = engine._retrieve_hierarchical_sources(
            query=query,
            area_principal=area_principal,
            max_sources=10
        )

    print(f"\nStep 3: Build Prompt")
    with timer("Build prompt"):
        prompt = engine._build_hierarchical_prompt(
            query=query,
            sources=sources,
            area_principal=area_principal
        )
    print(f"  Prompt length: {len(prompt)} chars")

    print(f"\nStep 4: LLM Generation")
    with timer("LLM generation"):
        try:
            response = engine.model.generate_content(prompt)
            answer_text = response.text
        except Exception as e:
            print(f"  LLM failed: {str(e)}")
            answer_text = engine._generate_fallback_answer(query, sources)
    print(f"  Answer length: {len(answer_text)} chars")

    print(f"\nStep 5: Format Sources")
    with timer("Format sources"):
        formatted_sources = engine._format_sources(sources)
    print(f"  Sources: {len(formatted_sources)} items")

    total_elapsed = time.time() - total_start
    print(f"\n  TOTAL: {total_elapsed:.3f}s")

    return total_elapsed

if __name__ == '__main__':
    # Test queries
    test_query = "Puedo deducir gastos de home studio?"

    # Profile search
    search_time = profile_search(test_query)

    # Profile chat
    chat_time = profile_chat(test_query)

    # Summary
    print("\n" + "="*60)
    print("PERFORMANCE SUMMARY")
    print("="*60)
    print(f"Search: {search_time:.3f}s")
    print(f"Chat:   {chat_time:.3f}s")
    print(f"\nTarget: <5.0s")
    print(f"Search status: {'✓ PASS' if search_time < 5 else '✗ FAIL'}")
    print(f"Chat status:   {'✓ PASS' if chat_time < 5 else '✗ FAIL'}")
