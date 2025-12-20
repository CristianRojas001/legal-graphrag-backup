# Legal GraphRAG System - Data Model

## Document Information
- **Version**: 1.0 (MVP)
- **Last Updated**: 2025-12-11
- **Status**: Planning Phase
- **Related**: [01_ARCHITECTURE.md](./01_ARCHITECTURE.md) | [03_INGESTION_GUIDE.md](./03_INGESTION_GUIDE.md)

---

## 1. Database Schema Overview

The Legal GraphRAG system uses **PostgreSQL with pgvector** extension on the existing Digital Ocean database. All tables use the `legal_` prefix to avoid conflicts with existing tables.

### Entity Relationship Diagram

```
┌─────────────────────────┐
│   legal_corpus_sources  │  ← Catalog (from Excel)
├─────────────────────────┤
│ PK: id                  │
│     prioridad           │
│     naturaleza          │
│     area_principal      │
│     titulo              │
│     id_oficial (UNIQUE) │
│     url_oficial         │
│     estado              │
└─────────────────────────┘
            │
            │ 1:N
            ↓
┌─────────────────────────┐
│   legal_documents       │  ← Ingested documents
├─────────────────────────┤
│ PK: id (UUID)           │
│ FK: source_id           │
│     doc_title           │
│     doc_id_oficial      │
│     url                 │
│     raw_html            │
│     metadata (JSONB)    │
└─────────────────────────┘
            │
            │ 1:N
            ↓
┌─────────────────────────┐
│ legal_document_chunks   │  ← Searchable chunks
├─────────────────────────┤
│ PK: id (UUID)           │
│ FK: document_id         │
│     chunk_type          │
│     chunk_label         │
│     chunk_text          │
│     embedding (vector)  │  ← pgvector
│     metadata (JSONB)    │
└─────────────────────────┘


┌─────────────────────────┐
│   legal_chat_sessions   │  ← User conversations
├─────────────────────────┤
│ PK: id (UUID)           │
│ FK: user_id (nullable)  │
│     created_at          │
│     updated_at          │
└─────────────────────────┘
            │
            │ 1:N
            ↓
┌─────────────────────────┐
│  legal_chat_messages    │  ← Chat history
├─────────────────────────┤
│ PK: id (UUID)           │
│ FK: session_id          │
│     role                │
│     content             │
│     sources (JSONB)     │
│     created_at          │
└─────────────────────────┘
```

---

## 2. Table Definitions (SQL)

### 2.1 legal_corpus_sources

**Purpose**: Catalog of legal sources to ingest (derived from Excel file)

```sql
CREATE TABLE legal_corpus_sources (
    id SERIAL PRIMARY KEY,

    -- Priority & Classification
    prioridad VARCHAR(10) NOT NULL,  -- P1, P2, P3
    naturaleza VARCHAR(50) NOT NULL,  -- Normativa, Doctrina administrativa, Jurisprudencia
    area_principal VARCHAR(100),  -- Fiscal, Laboral, Propiedad Intelectual, etc.

    -- Document Metadata
    titulo TEXT NOT NULL,
    tipo VARCHAR(100),  -- Ley, Real Decreto, Orden, etc.
    ambito VARCHAR(50),  -- España, UE, Autonómico, etc.
    funcion_artisting TEXT,  -- Purpose/role in system

    -- Official Identifiers
    id_oficial VARCHAR(100) UNIQUE NOT NULL,  -- BOE-A-1978-31229, etc.
    url_oficial TEXT NOT NULL,

    -- Legal Context
    vigencia TEXT,  -- "Vigente desde 2006", "Derogada en 2020"
    nivel_autoridad VARCHAR(50),  -- Constitución, Ley, Real Decreto, etc.
    articulos_clave TEXT,  -- Key articles/sections
    frecuencia_actualizacion VARCHAR(50),  -- Muy baja, Media, Alta

    -- Ingestion Status
    estado VARCHAR(20) DEFAULT 'pending',  -- pending, ingesting, ingested, failed, skipped
    last_ingested_at TIMESTAMPTZ,
    ingestion_error TEXT,  -- Error message if failed

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- Indexes
    CONSTRAINT valid_prioridad CHECK (prioridad IN ('P1', 'P2', 'P3', 'P1 / P2 según caso', 'P2 / P3')),
    CONSTRAINT valid_estado CHECK (estado IN ('pending', 'ingesting', 'ingested', 'failed', 'skipped'))
);

-- Indexes for filtering
CREATE INDEX idx_corpus_prioridad ON legal_corpus_sources(prioridad);
CREATE INDEX idx_corpus_naturaleza ON legal_corpus_sources(naturaleza);
CREATE INDEX idx_corpus_area ON legal_corpus_sources(area_principal);
CREATE INDEX idx_corpus_estado ON legal_corpus_sources(estado);
CREATE INDEX idx_corpus_id_oficial ON legal_corpus_sources(id_oficial);

-- Full-text search on titulo
CREATE INDEX idx_corpus_titulo_fts ON legal_corpus_sources
USING GIN(to_tsvector('spanish', titulo));
```

**Sample Data**:
```sql
INSERT INTO legal_corpus_sources (
    prioridad, naturaleza, area_principal, titulo, tipo, ambito,
    id_oficial, url_oficial, nivel_autoridad
) VALUES (
    'P1', 'Normativa', 'Marco general', 'Constitución española',
    'Constitución', 'España',
    'BOE-A-1978-31229',
    'https://www.boe.es/eli/es/c/1978/12/27/(1)/con',
    'Constitución'
);
```

---

### 2.2 legal_documents

**Purpose**: Store ingested legal documents

```sql
CREATE TABLE legal_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign Key to Corpus
    source_id INTEGER NOT NULL REFERENCES legal_corpus_sources(id) ON DELETE CASCADE,

    -- Document Identity
    doc_title TEXT NOT NULL,
    doc_id_oficial VARCHAR(100) UNIQUE NOT NULL,  -- Same as corpus id_oficial
    url TEXT NOT NULL,

    -- Content
    raw_html TEXT,  -- Original HTML for reference

    -- Metadata (derived from parsing)
    metadata JSONB DEFAULT '{}'::jsonb,
    /* Example metadata:
    {
        "fecha_publicacion": "1978-12-29",
        "seccion": "I",
        "departamento": "Jefatura del Estado",
        "num_articulos": 169,
        "naturaleza": "Normativa",
        "area_principal": "Marco general",
        "prioridad": "P1"
    }
    */

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_documents_source ON legal_documents(source_id);
CREATE INDEX idx_documents_id_oficial ON legal_documents(doc_id_oficial);
CREATE INDEX idx_documents_metadata_gin ON legal_documents USING GIN(metadata);
```

---

### 2.3 legal_document_chunks

**Purpose**: Searchable chunks (articles, sections) with embeddings

```sql
-- First, enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE legal_document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign Key to Document
    document_id UUID NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,

    -- Chunk Identity
    chunk_type VARCHAR(50) NOT NULL,  -- article, section, disposition, full_text
    chunk_label TEXT,  -- "Artículo 20", "Disposición Transitoria 3"

    -- Content
    chunk_text TEXT NOT NULL,  -- The actual legal text

    -- Vector Embedding
    embedding vector(768) NOT NULL,  -- Gemini text-embedding-004 (768 dimensions)

    -- Metadata (for filtering and display)
    metadata JSONB DEFAULT '{}'::jsonb,
    /* Example metadata:
    {
        "naturaleza": "Normativa",
        "area_principal": "Marco general",
        "prioridad": "P1",
        "nivel_autoridad": "Constitución",
        "tipo": "Constitución",
        "ambito": "España",
        "doc_title": "Constitución española",
        "doc_id_oficial": "BOE-A-1978-31229",
        "url": "https://www.boe.es/eli/es/c/1978/12/27/(1)/con",
        "fecha_publicacion": "1978-12-29",
        "seccion": "Capítulo I",
        "position": 20  // article number for ordering
    }
    */

    -- Full-text search
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('spanish', coalesce(chunk_label, '') || ' ' || chunk_text)
    ) STORED,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Vector similarity index (IVFFlat for MVP, good for <10k vectors)
CREATE INDEX idx_chunks_embedding ON legal_document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- For production (>10k vectors), use HNSW:
-- CREATE INDEX idx_chunks_embedding_hnsw ON legal_document_chunks
-- USING hnsw (embedding vector_cosine_ops)
-- WITH (m = 16, ef_construction = 64);

-- Full-text search index
CREATE INDEX idx_chunks_search_vector ON legal_document_chunks
USING GIN(search_vector);

-- Metadata indexes for filtering
CREATE INDEX idx_chunks_document ON legal_document_chunks(document_id);
CREATE INDEX idx_chunks_type ON legal_document_chunks(chunk_type);
CREATE INDEX idx_chunks_metadata_gin ON legal_document_chunks USING GIN(metadata);

-- Specific metadata filters (faster than JSONB gin)
CREATE INDEX idx_chunks_naturaleza ON legal_document_chunks ((metadata->>'naturaleza'));
CREATE INDEX idx_chunks_prioridad ON legal_document_chunks ((metadata->>'prioridad'));
CREATE INDEX idx_chunks_area ON legal_document_chunks ((metadata->>'area_principal'));
```

**Sample Data**:
```sql
INSERT INTO legal_document_chunks (
    document_id,
    chunk_type,
    chunk_label,
    chunk_text,
    embedding,
    metadata
) VALUES (
    '123e4567-e89b-12d3-a456-426614174000',  -- document_id from legal_documents
    'article',
    'Artículo 20',
    'Se reconocen y protegen los derechos a expresar y difundir libremente...',
    '[0.123, -0.456, 0.789, ...]'::vector(768),
    '{
        "naturaleza": "Normativa",
        "area_principal": "Marco general",
        "prioridad": "P1",
        "nivel_autoridad": "Constitución",
        "doc_title": "Constitución española",
        "doc_id_oficial": "BOE-A-1978-31229",
        "url": "https://www.boe.es/eli/es/c/1978/12/27/(1)/con",
        "position": 20
    }'::jsonb
);
```

---

### 2.4 legal_chat_sessions

**Purpose**: Track user chat conversations (for history and analytics)

```sql
CREATE TABLE legal_chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- User (nullable for anonymous queries)
    user_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,

    -- Session Metadata
    session_title TEXT,  -- Auto-generated from first query
    ip_address INET,  -- For rate limiting
    user_agent TEXT,  -- Browser info

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_chat_sessions_user ON legal_chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_created ON legal_chat_sessions(created_at DESC);
CREATE INDEX idx_chat_sessions_ip ON legal_chat_sessions(ip_address);
```

---

### 2.5 legal_chat_messages

**Purpose**: Store individual messages in chat conversations

```sql
CREATE TABLE legal_chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign Key to Session
    session_id UUID NOT NULL REFERENCES legal_chat_sessions(id) ON DELETE CASCADE,

    -- Message Content
    role VARCHAR(20) NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,  -- Query or answer

    -- Sources (for assistant messages)
    sources JSONB DEFAULT '[]'::jsonb,
    /* Example sources:
    [
        {
            "chunk_id": "uuid",
            "label": "Artículo 20",
            "text": "Se reconocen y protegen...",
            "url": "https://www.boe.es/...",
            "doc_title": "Constitución española",
            "naturaleza": "Normativa",
            "similarity": 0.92
        }
    ]
    */

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    /* Example metadata:
    {
        "area_principal": "Marco general",
        "model": "gemini-2.5-flash",
        "response_time_ms": 3200,
        "normativa_count": 5,
        "doctrina_count": 3,
        "tokens_used": 1200
    }
    */

    -- Feedback (optional)
    feedback_rating INTEGER,  -- 1 (thumbs down) or 5 (thumbs up)
    feedback_comment TEXT,

    -- Timestamp
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_role CHECK (role IN ('user', 'assistant')),
    CONSTRAINT valid_rating CHECK (feedback_rating IS NULL OR feedback_rating IN (1, 5))
);

-- Indexes
CREATE INDEX idx_chat_messages_session ON legal_chat_messages(session_id);
CREATE INDEX idx_chat_messages_created ON legal_chat_messages(created_at DESC);
CREATE INDEX idx_chat_messages_role ON legal_chat_messages(role);
CREATE INDEX idx_chat_messages_sources_gin ON legal_chat_messages USING GIN(sources);

-- Full-text search on messages
CREATE INDEX idx_chat_messages_content_fts ON legal_chat_messages
USING GIN(to_tsvector('spanish', content));
```

---

## 3. Django Models

### 3.1 models.py

```python
# apps/legal_graphrag/models.py

from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from pgvector.django import VectorField
import uuid

class CorpusSource(models.Model):
    """Catalog of legal sources to ingest"""

    PRIORIDAD_CHOICES = [
        ('P1', 'P1 - Core'),
        ('P2', 'P2 - Important'),
        ('P3', 'P3 - Edge cases'),
    ]

    ESTADO_CHOICES = [
        ('pending', 'Pending'),
        ('ingesting', 'Ingesting'),
        ('ingested', 'Ingested'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]

    # Priority & Classification
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, db_index=True)
    naturaleza = models.CharField(max_length=50, db_index=True)
    area_principal = models.CharField(max_length=100, db_index=True, null=True, blank=True)

    # Document Metadata
    titulo = models.TextField()
    tipo = models.CharField(max_length=100, null=True, blank=True)
    ambito = models.CharField(max_length=50, null=True, blank=True)
    funcion_artisting = models.TextField(null=True, blank=True)

    # Official Identifiers
    id_oficial = models.CharField(max_length=100, unique=True)
    url_oficial = models.TextField()

    # Legal Context
    vigencia = models.TextField(null=True, blank=True)
    nivel_autoridad = models.CharField(max_length=50, null=True, blank=True)
    articulos_clave = models.TextField(null=True, blank=True)
    frecuencia_actualizacion = models.CharField(max_length=50, null=True, blank=True)

    # Ingestion Status
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pending', db_index=True)
    last_ingested_at = models.DateTimeField(null=True, blank=True)
    ingestion_error = models.TextField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'legal_corpus_sources'
        ordering = ['prioridad', 'area_principal', 'titulo']
        indexes = [
            models.Index(fields=['prioridad', 'estado']),
            models.Index(fields=['naturaleza', 'area_principal']),
        ]

    def __str__(self):
        return f"[{self.prioridad}] {self.titulo}"


class LegalDocument(models.Model):
    """Ingested legal document"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Foreign Key
    source = models.ForeignKey(CorpusSource, on_delete=models.CASCADE, related_name='documents')

    # Document Identity
    doc_title = models.TextField()
    doc_id_oficial = models.CharField(max_length=100, unique=True)
    url = models.TextField()

    # Content
    raw_html = models.TextField(null=True, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'legal_documents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source']),
            models.Index(fields=['doc_id_oficial']),
        ]

    def __str__(self):
        return f"{self.doc_title} ({self.doc_id_oficial})"


class DocumentChunk(models.Model):
    """Searchable chunk with embedding"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Foreign Key
    document = models.ForeignKey(LegalDocument, on_delete=models.CASCADE, related_name='chunks')

    # Chunk Identity
    chunk_type = models.CharField(max_length=50)  # article, section, etc.
    chunk_label = models.TextField(null=True, blank=True)

    # Content
    chunk_text = models.TextField()

    # Vector Embedding (pgvector)
    embedding = VectorField(dimensions=768)

    # Metadata
    metadata = models.JSONField(default=dict)

    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'legal_document_chunks'
        ordering = ['document', 'chunk_type']
        indexes = [
            models.Index(fields=['document']),
            models.Index(fields=['chunk_type']),
        ]

    def __str__(self):
        return f"{self.chunk_label or self.chunk_type} - {self.document.doc_title}"


class ChatSession(models.Model):
    """User chat session"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # User (nullable for anonymous)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='legal_chat_sessions')

    # Session Metadata
    session_title = models.TextField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'legal_chat_sessions'
        ordering = ['-updated_at']

    def __str__(self):
        return f"Session {self.id} - {self.created_at.strftime('%Y-%m-%d')}"


class ChatMessage(models.Model):
    """Individual chat message"""

    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Foreign Key
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')

    # Message Content
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()

    # Sources (for assistant messages)
    sources = models.JSONField(default=list)

    # Metadata
    metadata = models.JSONField(default=dict)

    # Feedback
    feedback_rating = models.IntegerField(null=True, blank=True, choices=[(1, 'Bad'), (5, 'Good')])
    feedback_comment = models.TextField(null=True, blank=True)

    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'legal_chat_messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        return f"[{self.role}] {self.content[:50]}"
```

---

## 4. Database Functions (PostgreSQL)

### 4.1 Vector Similarity Search

```sql
-- Function: Search chunks by vector similarity
CREATE OR REPLACE FUNCTION search_legal_chunks_by_vector(
    query_embedding vector(768),
    match_count INT DEFAULT 10,
    filter_naturaleza TEXT DEFAULT NULL,
    filter_prioridad TEXT DEFAULT NULL,
    filter_area TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    chunk_label TEXT,
    chunk_text TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE SQL STABLE
AS $$
    SELECT
        legal_document_chunks.id,
        legal_document_chunks.chunk_label,
        legal_document_chunks.chunk_text,
        legal_document_chunks.metadata,
        1 - (legal_document_chunks.embedding <=> query_embedding) AS similarity
    FROM legal_document_chunks
    WHERE
        (filter_naturaleza IS NULL OR legal_document_chunks.metadata->>'naturaleza' = filter_naturaleza)
        AND (filter_prioridad IS NULL OR legal_document_chunks.metadata->>'prioridad' = filter_prioridad)
        AND (filter_area IS NULL OR legal_document_chunks.metadata->>'area_principal' = filter_area)
    ORDER BY legal_document_chunks.embedding <=> query_embedding
    LIMIT match_count;
$$;
```

**Usage in Django**:
```python
from django.db import connection

def vector_search(query_embedding, filters=None):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT * FROM search_legal_chunks_by_vector(
                %s::vector(768),
                %s,
                %s,
                %s,
                %s
            )
        """, [
            query_embedding,
            filters.get('limit', 10),
            filters.get('naturaleza'),
            filters.get('prioridad'),
            filters.get('area_principal')
        ])

        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

### 4.2 Full-Text Search

```sql
-- Function: Search chunks by full-text
CREATE OR REPLACE FUNCTION search_legal_chunks_by_text(
    search_query TEXT,
    match_count INT DEFAULT 10,
    filter_naturaleza TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    chunk_label TEXT,
    chunk_text TEXT,
    metadata JSONB,
    rank FLOAT
)
LANGUAGE SQL STABLE
AS $$
    SELECT
        legal_document_chunks.id,
        legal_document_chunks.chunk_label,
        legal_document_chunks.chunk_text,
        legal_document_chunks.metadata,
        ts_rank(legal_document_chunks.search_vector, to_tsquery('spanish', search_query)) AS rank
    FROM legal_document_chunks
    WHERE
        legal_document_chunks.search_vector @@ to_tsquery('spanish', search_query)
        AND (filter_naturaleza IS NULL OR legal_document_chunks.metadata->>'naturaleza' = filter_naturaleza)
    ORDER BY rank DESC
    LIMIT match_count;
$$;
```

---

## 5. Data Migration Plan

### 5.1 Initial Setup

```bash
# 1. Enable pgvector extension
python manage.py dbshell
```

```sql
CREATE EXTENSION IF NOT EXISTS vector;
\q
```

```bash
# 2. Create models
python manage.py makemigrations legal_graphrag
python manage.py migrate legal_graphrag

# 3. Import corpus from Excel
python manage.py import_corpus_from_excel corpus/corpus_normativo_artisting_enriched.xlsx
```

### 5.2 Import Script

```python
# apps/legal_graphrag/management/commands/import_corpus_from_excel.py

from django.core.management.base import BaseCommand
import pandas as pd
from apps.legal_graphrag.models import CorpusSource

class Command(BaseCommand):
    help = 'Import corpus sources from Excel file'

    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='Path to Excel file')

    def handle(self, *args, **options):
        df = pd.read_excel(options['excel_file'])

        for _, row in df.iterrows():
            CorpusSource.objects.update_or_create(
                id_oficial=row['ID oficial'],
                defaults={
                    'prioridad': row['Prioridad'],
                    'naturaleza': row['Naturaleza'],
                    'area_principal': row['Área principal'],
                    'titulo': row['Norma / fuente (título resumido)'],
                    'tipo': row['Tipo'],
                    'ambito': row['Ámbito'],
                    'funcion_artisting': row['Función en ARTISTING'],
                    'url_oficial': row['URL oficial'],
                    'vigencia': row['Vigencia'],
                    'nivel_autoridad': row['Nivel de autoridad'],
                    'articulos_clave': row['Artículos clave/alcance'],
                    'frecuencia_actualizacion': row['Frecuencia de actualización'],
                }
            )
            self.stdout.write(f"✓ Imported: {row['Norma / fuente (título resumido)']}")

        self.stdout.write(self.style.SUCCESS(f"✓ Imported {len(df)} sources"))
```

---

## 6. Sample Queries

### 6.1 Find Sources to Ingest

```sql
-- All P1 sources not yet ingested
SELECT id, titulo, url_oficial, estado
FROM legal_corpus_sources
WHERE prioridad = 'P1' AND estado = 'pending'
ORDER BY area_principal, titulo;
```

### 6.2 Vector Search with Filters

```python
# Search for "gastos deducibles" in Fiscal normativa
from apps.legal_graphrag.services.embedding_service import EmbeddingService

embedding_service = EmbeddingService()
query_embedding = embedding_service.embed("gastos deducibles home studio")

results = search_legal_chunks_by_vector(
    query_embedding,
    match_count=5,
    filter_naturaleza='Normativa',
    filter_area='Fiscal'
)
```

### 6.3 Get Document with All Chunks

```python
from apps.legal_graphrag.models import LegalDocument

doc = LegalDocument.objects.get(doc_id_oficial='BOE-A-2006-20764')
chunks = doc.chunks.filter(chunk_type='article').order_by('metadata__position')

for chunk in chunks:
    print(f"{chunk.chunk_label}: {chunk.chunk_text[:100]}")
```

### 6.4 User Query History

```sql
-- Get user's recent queries
SELECT
    m.content,
    m.created_at,
    m.metadata->>'area_principal' as area,
    jsonb_array_length(m.sources) as source_count
FROM legal_chat_messages m
JOIN legal_chat_sessions s ON m.session_id = s.id
WHERE s.user_id = 123
  AND m.role = 'user'
ORDER BY m.created_at DESC
LIMIT 20;
```

---

**Document End** | Next: [03_INGESTION_GUIDE.md](./03_INGESTION_GUIDE.md)
