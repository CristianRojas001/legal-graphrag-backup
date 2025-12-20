// API Response Types for Legal GraphRAG System

export interface LegalSource {
  id: string;
  title: string;
  url: string;
  source_type: string;
  relevance_score?: number;
  excerpt?: string;
}

export interface ChatResponse {
  answer: string;
  sources: LegalSource[];
  query: string;
  timestamp?: string;
  session_id?: string;
}

export interface ChatRequest {
  query: string;
  session_id?: string;
}

export interface SearchRequest {
  query: string;
  limit?: number;
}

export interface SearchResult {
  chunk_id: string;
  document_title: string;
  document_url: string;
  chunk_text: string;
  similarity_score: number;
  source_type: string;
}

export interface SearchResponse {
  results: SearchResult[];
  query: string;
  total_results: number;
}

export interface CorpusSource {
  id: string;
  identificador: string;
  titulo: string;
  tipo_fuente: string;
  url: string;
  prioridad: string;
  estado: string;
}

export interface SourcesResponse {
  sources: CorpusSource[];
  total: number;
  p1_count: number;
}

export interface ApiError {
  error: string;
  detail?: string;
  status?: number;
}