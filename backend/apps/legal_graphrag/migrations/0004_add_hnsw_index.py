from django.db import migrations
from django.contrib.postgres.operations import AddIndexConcurrently


class Migration(migrations.Migration):
    atomic = False  # Required for CREATE INDEX CONCURRENTLY

    dependencies = [
        ('legal_graphrag', '0003_add_session_state'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS legal_document_chunks_embedding_hnsw_idx
            ON legal_document_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS legal_document_chunks_embedding_hnsw_idx;
            """
        ),
    ]
