"""
Test script for Legal Search Engine
Tests vector, lexical, and hybrid search
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')
django.setup()

from apps.legal_graphrag.services.legal_search_engine import LegalSearchEngine
from apps.legal_graphrag.models import DocumentChunk

def main():
    print("\n" + "="*70)
    print("LEGAL SEARCH ENGINE TEST")
    print("="*70 + "\n")

    # Check if we have data
    chunk_count = DocumentChunk.objects.count()
    print(f"Total chunks in database: {chunk_count}\n")

    if chunk_count == 0:
        print("ERROR: No chunks found. Please wait for ingestion to complete.")
        return

    # Initialize search engine
    engine = LegalSearchEngine()

    # Test queries
    test_queries = [
        "derechos de autor",
        "impuestos artistas",
        "seguridad social",
        "contratos",
        "propiedad intelectual"
    ]

    for query in test_queries:
        print(f"\n{'='*70}")
        print(f"QUERY: {query}")
        print(f"{'='*70}\n")

        # Hybrid search
        print("--- HYBRID SEARCH (Vector + Lexical + RRF) ---")
        try:
            results = engine.hybrid_search(query, limit=5)
            print(f"Found {len(results)} results\n")

            for i, result in enumerate(results, 1):
                print(f"{i}. [{result.get('source_title', 'N/A')[:40]}]")
                print(f"   {result.get('chunk_label', 'N/A')}")
                print(f"   RRF Score: {result.get('rrf_score', 0):.4f}")
                print(f"   Sources: {', '.join(result.get('rrf_sources', []))}")
                if 'vector_similarity' in result:
                    print(f"   Vector Similarity: {result['vector_similarity']:.4f}")
                if 'fts_rank' in result:
                    print(f"   FTS Rank: {result['fts_rank']:.4f}")
                print(f"   Text: {result.get('chunk_text', '')[:150]}...")
                print()

        except Exception as e:
            print(f"ERROR: {str(e)}\n")

    print(f"\n{'='*70}")
    print("TEST COMPLETE")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()
