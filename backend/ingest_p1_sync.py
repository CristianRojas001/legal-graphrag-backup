"""
Synchronous P1 ingestion script
Ingests all P1 sources with valid PDF URLs without using Celery
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')
django.setup()

from apps.legal_graphrag.models import CorpusSource
from apps.legal_graphrag.tasks import ingest_legal_source
import time

def main():
    # Get all P1 sources that need ingestion
    sources = CorpusSource.objects.filter(
        prioridad='P1',
        estado='pending'
    ).exclude(
        url_oficial__isnull=True
    ).exclude(
        url_oficial=''
    ).order_by('id')

    # Filter to only PDF and EUR-Lex sources
    valid_sources = []
    for src in sources:
        url = src.url_oficial.lower()
        # Accept .pdf URLs or EUR-Lex URLs with CELEX
        if '.pdf' in url or ('eur-lex.europa.eu' in url and 'celex:' in url):
            valid_sources.append(src)

    total = len(valid_sources)
    print(f"\n{'='*70}")
    print(f"STARTING INGESTION OF {total} P1 SOURCES")
    print(f"{'='*70}\n")

    for i, source in enumerate(valid_sources, 1):
        print(f"\n[{i}/{total}] Processing: {source.titulo[:60]}")
        print(f"         URL: {source.url_oficial[:80]}")
        print(f"         ID: {source.id_oficial}")

        try:
            # Call the task synchronously
            result = ingest_legal_source(source.id)

            # Refresh to get updated status
            source.refresh_from_db()

            if source.estado == 'ingested':
                chunks = source.documents.first().chunks.count() if source.documents.exists() else 0
                print(f"         [OK] SUCCESS - {chunks} chunks created")
            else:
                print(f"         [FAIL] {source.ingestion_error[:100] if source.ingestion_error else 'Unknown error'}")

        except Exception as e:
            print(f"         [ERROR] {str(e)[:100]}")

        # Small delay to avoid rate limiting
        if i < total:
            time.sleep(2)

    # Final summary
    print(f"\n{'='*70}")
    print("INGESTION COMPLETE - SUMMARY")
    print(f"{'='*70}")

    ingested = CorpusSource.objects.filter(prioridad='P1', estado='ingested').count()
    failed = CorpusSource.objects.filter(prioridad='P1', estado='failed').count()
    pending = CorpusSource.objects.filter(prioridad='P1', estado='pending').count()

    print(f"Ingested: {ingested}")
    print(f"Failed:   {failed}")
    print(f"Pending:  {pending}")
    print(f"\nTotal documents: {CorpusSource.objects.filter(prioridad='P1', estado='ingested').aggregate(count=django.db.models.Count('documents'))['count']}")

    from apps.legal_graphrag.models import DocumentChunk
    print(f"Total chunks: {DocumentChunk.objects.filter(document__source__prioridad='P1').count()}")
    print()

if __name__ == '__main__':
    main()
