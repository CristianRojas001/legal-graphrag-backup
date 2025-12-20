"""
Management Command - Ingest all P1 priority sources
"""

from django.core.management.base import BaseCommand
from apps.legal_graphrag.tasks import ingest_all_p1_sources


class Command(BaseCommand):
    help = 'Ingest all P1 priority sources'

    def handle(self, *args, **options):
        self.stdout.write('Queueing all P1 sources for ingestion...')

        result = ingest_all_p1_sources.delay()

        self.stdout.write(self.style.SUCCESS(f'[OK] Task queued: {result.id}'))
        self.stdout.write('Monitor progress with: celery -A ovra_backend inspect active')
