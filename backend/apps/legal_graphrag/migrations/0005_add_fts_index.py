# Generated migration for adding GIN FTS index

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex


class Migration(migrations.Migration):

    dependencies = [
        ('legal_graphrag', '0004_add_hnsw_index'),
    ]

    # Allow for concurrent index creation (non-blocking)
    atomic = False

    operations = [
        # Add generated tsvector column for Spanish full-text search
        migrations.RunSQL(
            sql="""
                ALTER TABLE legal_document_chunks
                ADD COLUMN IF NOT EXISTS chunk_search tsvector
                GENERATED ALWAYS AS (
                    to_tsvector('spanish', coalesce(chunk_text, '')) ||
                    to_tsvector('spanish', coalesce(chunk_label, ''))
                ) STORED;
            """,
            reverse_sql="""
                ALTER TABLE legal_document_chunks
                DROP COLUMN IF EXISTS chunk_search;
            """
        ),

        # Create GIN index on the tsvector column (concurrently to avoid blocking)
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunk_search_gin
                ON legal_document_chunks USING gin(chunk_search);
            """,
            reverse_sql="""
                DROP INDEX CONCURRENTLY IF EXISTS idx_chunk_search_gin;
            """
        ),
    ]
