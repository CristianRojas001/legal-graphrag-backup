"""
Management Command - Ingest a legal source by ID or id_oficial
"""

from django.core.management.base import BaseCommand
from apps.legal_graphrag.models import CorpusSource
from apps.legal_graphrag.tasks import ingest_legal_source


class Command(BaseCommand):
    help = 'Ingest a legal source by ID or id_oficial'

    def add_arguments(self, parser):
        parser.add_argument('identifier', type=str, help='Source ID or id_oficial')
        parser.add_argument('--sync', action='store_true', help='Run synchronously (not via Celery)')

    def handle(self, *args, **options):
        identifier = options['identifier']

        # Try to get source by ID or id_oficial
        try:
            if identifier.isdigit():
                source = CorpusSource.objects.get(id=int(identifier))
            else:
                source = CorpusSource.objects.get(id_oficial=identifier)
        except CorpusSource.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Source not found: {identifier}'))
            return

        self.stdout.write(f'Ingesting: {source.titulo}')

        if options['sync']:
            # Run synchronously (for testing)
            result = ingest_legal_source(source.id)
            self.stdout.write(self.style.SUCCESS(f'✓ Ingested: {result["chunks_created"]} chunks'))
        else:
            # Queue as Celery task
            task = ingest_legal_source.delay(source.id)
            self.stdout.write(self.style.SUCCESS(f'✓ Queued: Task ID {task.id}'))
