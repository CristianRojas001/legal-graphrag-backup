"""Direct test of F04 query with new query expansion"""
import sys
sys.path.insert(0, 'D:\\IT workspace\\Legal GraphRAG\\backend')

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')

import django
django.setup()

from apps.legal_graphrag.services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1

# Initialize RAG engine
engine = LegalRAGEngineV1_1()

# Test F04 query
query = "Facturo a una empresa española como artista. ¿Debo aplicar retención? ¿De qué depende?"

print("=" * 80)
print(f"Testing: {query}")
print("=" * 80)

result = engine.answer_query(query=query, area_principal="Fiscal")

print(f"\nAbstained: {result.get('metadata', {}).get('abstained')}")
print(f"Total sources: {result.get('metadata', {}).get('total_sources')}")
print(f"Cited sources: {result.get('metadata', {}).get('cited_count')}")
print(f"\nAnswer preview:")
print(result.get('answer', '')[:300])
print("\nSources:")
for src in result.get('sources', [])[:5]:
    cited = "✓" if src.get('is_cited') else " "
    print(f"  [{cited}] {src.get('id')}: {src.get('title')}")
