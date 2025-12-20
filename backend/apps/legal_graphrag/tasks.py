"""
Celery Tasks - Orchestrate async ingestion pipeline
"""

from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger('apps.legal_graphrag.ingestion')


@shared_task(bind=True, max_retries=3)
def ingest_legal_source(self, source_id: int):
    """
    Celery task: Ingest a single legal source

    Args:
        source_id: ID of CorpusSource to ingest

    Returns:
        dict: Ingestion results
    """
    from apps.legal_graphrag.models import CorpusSource, LegalDocument, DocumentChunk
    from apps.legal_graphrag.services.ingestion.boe_connector import BOEConnector
    from apps.legal_graphrag.services.ingestion.doue_connector import DOUEConnector
    from apps.legal_graphrag.services.ingestion.dgt_connector import DGTConnector
    from apps.legal_graphrag.services.ingestion.normalizer import LegalDocumentNormalizer
    from apps.legal_graphrag.services.embedding_service import EmbeddingService

    try:
        # Get source
        source = CorpusSource.objects.get(id=source_id)
        source.estado = 'ingesting'
        source.save()

        logger.info(f"Starting ingestion: {source.titulo}")

        # STAGE 1: Fetch document
        connector = get_connector(source)
        if isinstance(connector, BOEConnector):
            raw_doc = connector.fetch(source.url_oficial, boe_id=source.id_oficial)
        else:
            raw_doc = connector.fetch(source.url_oficial)

        logger.info(f"Fetched {len(raw_doc.get('structure', []))} chunks")

        # STAGE 2: Normalize
        normalizer = LegalDocumentNormalizer()
        normalized = normalizer.normalize(raw_doc, source)

        # STAGE 3: Create document record
        doc = LegalDocument.objects.create(
            source=source,
            doc_title=normalized['titulo'],
            doc_id_oficial=source.id_oficial,
            url=source.url_oficial,
            raw_html=raw_doc['html'],
            metadata=normalized['metadata']
        )

        logger.info(f"Created document: {doc.id}")

        # STAGE 4: Generate embeddings and create chunks
        embedding_service = EmbeddingService()
        chunks_created = 0

        for chunk in normalized['chunks']:
            text = (chunk.get('text') or '').strip()
            if not text:
                logger.warning(f"Skipping empty chunk for {source.titulo}: {chunk.get('label')}")
                continue

            # Generate embedding
            embedding = embedding_service.embed(text)

            # Create chunk
            DocumentChunk.objects.create(
                document=doc,
                chunk_type=chunk['type'],
                chunk_label=chunk['label'],
                chunk_text=text,
                embedding=embedding,
                metadata=chunk['metadata']
            )

            chunks_created += 1
            logger.info(f"Created chunk {chunks_created}: {chunk['label']}")

        # STAGE 5: Update source status
        source.estado = 'ingested'
        source.last_ingested_at = timezone.now()
        source.ingestion_error = None
        source.save()

        logger.info(f"✓ Ingestion complete: {source.titulo} ({chunks_created} chunks)")

        return {
            'source_id': source_id,
            'source_title': source.titulo,
            'chunks_created': chunks_created,
            'status': 'success'
        }

    except Exception as e:
        logger.error(f"Ingestion failed for source {source_id}: {e}")

        # Update source status
        try:
            source = CorpusSource.objects.get(id=source_id)
            source.estado = 'failed'
            source.ingestion_error = str(e)
            source.save()
        except:
            pass

        # Retry task
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task
def ingest_all_p1_sources():
    """
    Batch task: Ingest all P1 priority sources

    Usage:
        from apps.legal_graphrag.tasks import ingest_all_p1_sources
        ingest_all_p1_sources.delay()
    """
    from apps.legal_graphrag.models import CorpusSource

    p1_sources = CorpusSource.objects.filter(
        prioridad='P1',
        estado='pending'
    ).order_by('area_principal', 'titulo')

    logger.info(f"Queueing {p1_sources.count()} P1 sources for ingestion")

    for source in p1_sources:
        ingest_legal_source.delay(source.id)

    return f"Queued {p1_sources.count()} sources"


@shared_task
def update_source(source_id: int):
    """
    Update an existing source (re-ingest)

    Use case: Law has been updated, need to re-fetch
    """
    from apps.legal_graphrag.models import CorpusSource, LegalDocument

    source = CorpusSource.objects.get(id=source_id)

    # Delete old document and chunks (cascade)
    LegalDocument.objects.filter(source=source).delete()

    # Reset source status
    source.estado = 'pending'
    source.save()

    # Re-ingest
    ingest_legal_source.delay(source_id)


def get_connector(source):
    """Factory function to get appropriate connector"""
    from apps.legal_graphrag.services.ingestion.boe_connector import BOEConnector
    from apps.legal_graphrag.services.ingestion.doue_connector import DOUEConnector
    from apps.legal_graphrag.services.ingestion.dgt_connector import DGTConnector

    url = source.url_oficial.lower()

    if 'boe.es' in url:
        return BOEConnector()
    elif 'eur-lex.europa.eu' in url:
        return DOUEConnector()
    elif 'petete.tributos.hacienda.gob.es' in url or 'dgt' in url:
        return DGTConnector()
    else:
        # Default to BOE connector
        logger.warning(f"Unknown source type for {url}, using BOE connector")
        return BOEConnector()
