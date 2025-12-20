"""
Simple single query test for Legal RAG Engine
Quick test with a single query to verify everything works
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')
django.setup()

from apps.legal_graphrag.services.legal_rag_engine import LegalRAGEngine
import json


def main():
    """Test a single query"""

    query = "¿Puedo deducir gastos de home studio en el IRPF?"

    print(f"\nQuery: {query}\n")
    print("=" * 80)

    engine = LegalRAGEngine()
    result = engine.answer_query(query=query, area_principal="Fiscal")

    # Print answer
    print("\n### ANSWER ###\n")
    print(result['answer'])

    # Print sources summary
    print("\n### SOURCES ###\n")
    for idx, source in enumerate(result['sources'], 1):
        print(f"{idx}. {source['document_title']} - {source['label']}")
        print(f"   URL: {source['document_url']}")
        print(f"   Similarity: {source['similarity']:.4f}\n")

    # Print metadata
    print("\n### METADATA ###\n")
    print(json.dumps(result['metadata'], indent=2))

    # Save to file
    with open('test_output.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("\n\nFull result saved to test_output.json")


if __name__ == "__main__":
    main()
