-- Initialize local PostgreSQL for Legal GraphRAG
-- Based on Django models from apps/legal_graphrag/models.py

-- Create required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create legal_corpus_sources table
CREATE TABLE IF NOT EXISTS public.legal_corpus_sources (
    id SERIAL PRIMARY KEY,
    prioridad VARCHAR(10) NOT NULL,
    naturaleza VARCHAR(50) NOT NULL,
    area_principal VARCHAR(100),
    titulo TEXT NOT NULL,
    tipo VARCHAR(100),
    ambito VARCHAR(50),
    funcion_artisting TEXT,
    id_oficial VARCHAR(100) UNIQUE NOT NULL,
    url_oficial TEXT NOT NULL,
    vigencia TEXT,
    nivel_autoridad VARCHAR(50),
    articulos_clave TEXT,
    frecuencia_actualizacion VARCHAR(50),
    estado VARCHAR(20) DEFAULT 'pending' NOT NULL,
    last_ingested_at TIMESTAMP,
    ingestion_error TEXT,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Create legal_documents table
CREATE TABLE IF NOT EXISTS public.legal_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id INTEGER NOT NULL REFERENCES public.legal_corpus_sources(id) ON DELETE CASCADE,
    doc_title TEXT NOT NULL,
    doc_id_oficial VARCHAR(100) UNIQUE NOT NULL,
    url TEXT NOT NULL,
    raw_html TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Create legal_document_chunks table
CREATE TABLE IF NOT EXISTS public.legal_document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES public.legal_documents(id) ON DELETE CASCADE,
    chunk_type VARCHAR(50) NOT NULL,
    chunk_label TEXT,
    chunk_text TEXT NOT NULL,
    embedding vector(768),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Create legal_chat_sessions table
CREATE TABLE IF NOT EXISTS public.legal_chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,
    session_title TEXT,
    ip_address INET,
    user_agent TEXT,
    session_state JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Create legal_chat_messages table
CREATE TABLE IF NOT EXISTS public.legal_chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.legal_chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    sources JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    feedback_rating INTEGER,
    feedback_comment TEXT,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Create indexes for legal_corpus_sources
CREATE INDEX IF NOT EXISTS idx_corpus_sources_prioridad ON public.legal_corpus_sources(prioridad);
CREATE INDEX IF NOT EXISTS idx_corpus_sources_naturaleza ON public.legal_corpus_sources(naturaleza);
CREATE INDEX IF NOT EXISTS idx_corpus_sources_area ON public.legal_corpus_sources(area_principal);
CREATE INDEX IF NOT EXISTS idx_corpus_sources_estado ON public.legal_corpus_sources(estado);
CREATE INDEX IF NOT EXISTS idx_corpus_sources_prioridad_estado ON public.legal_corpus_sources(prioridad, estado);
CREATE INDEX IF NOT EXISTS idx_corpus_sources_naturaleza_area ON public.legal_corpus_sources(naturaleza, area_principal);

-- Create indexes for legal_documents
CREATE INDEX IF NOT EXISTS idx_legal_docs_source ON public.legal_documents(source_id);
CREATE INDEX IF NOT EXISTS idx_legal_docs_id_oficial ON public.legal_documents(doc_id_oficial);
CREATE INDEX IF NOT EXISTS idx_legal_docs_created ON public.legal_documents(created_at DESC);

-- Create indexes for legal_document_chunks
CREATE INDEX IF NOT EXISTS idx_legal_chunks_document ON public.legal_document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_legal_chunks_type ON public.legal_document_chunks(chunk_type);
CREATE INDEX IF NOT EXISTS idx_legal_chunks_embedding ON public.legal_document_chunks USING hnsw (embedding vector_cosine_ops);

-- Create indexes for legal_chat_sessions
CREATE INDEX IF NOT EXISTS idx_legal_sessions_created ON public.legal_chat_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_legal_sessions_updated ON public.legal_chat_sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_legal_sessions_id_updated ON public.legal_chat_sessions(id, updated_at);

-- Create indexes for legal_chat_messages
CREATE INDEX IF NOT EXISTS idx_legal_messages_session ON public.legal_chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_legal_messages_created ON public.legal_chat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_legal_messages_role ON public.legal_chat_messages(role);
CREATE INDEX IF NOT EXISTS idx_legal_messages_session_created ON public.legal_chat_messages(session_id, created_at);

-- Grant privileges
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Legal GraphRAG database initialized successfully';
    RAISE NOTICE 'Tables created:';
    RAISE NOTICE '  - legal_corpus_sources';
    RAISE NOTICE '  - legal_documents';
    RAISE NOTICE '  - legal_document_chunks';
    RAISE NOTICE '  - legal_chat_sessions';
    RAISE NOTICE '  - legal_chat_messages';
END $$;
