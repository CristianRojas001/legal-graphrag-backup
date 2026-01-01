#!/usr/bin/env python
"""Test RAG search with local database"""
import os
import sys
import django

# Fix console encoding
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')
django.setup()

from apps.legal_graphrag.services.legal_search_engine import LegalSearchEngine
from apps.legal_graphrag.models import DocumentChunk

# Check chunks in database
chunk_count = DocumentChunk.objects.count()
print(f"[OK] Total chunks in local database: {chunk_count}")

if chunk_count > 0:
    # Test vector search
    print("\n[TEST] Testing vector search for 'derechos fundamentales'...")
    engine = LegalSearchEngine()
    results = engine.vector_search("derechos fundamentales", limit=3)

    print(f"[OK] Found {len(results)} results\n")

    for i, result in enumerate(results[:3], 1):
        # Debug: print result structure
        if i == 1:
            print(f"[DEBUG] Result keys: {result.keys()}")

        # Handle different result structures
        if 'chunk_label' in result:
            print(f"{i}. {result['chunk_label']}")
            print(f"   Text: {result.get('chunk_text', '')[:100]}...")
            print(f"   Score: {result.get('score', 0):.3f}")
        else:
            print(f"{i}. Result: {list(result.keys())}")
        print()

    print("[SUCCESS] RAG vector search is working with local PostgreSQL!")
else:
    print("[ERROR] No chunks found - please ingest documents first")
