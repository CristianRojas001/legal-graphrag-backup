-- Initialize pgvector extension only
-- Django migrations will handle table creation

CREATE EXTENSION IF NOT EXISTS vector;
