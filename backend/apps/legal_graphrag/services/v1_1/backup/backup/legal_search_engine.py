"""
Legal Search Engine
Implements hybrid search (vector + lexical) with RRF fusion
"""

import logging
import re
from typing import List, Dict, Any
from django.conf import settings
from django.db.models import F, Q
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from pgvector.django import CosineDistance

from apps.legal_graphrag.models import DocumentChunk
from apps.legal_graphrag.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class LegalSearchEngine:
    """
    Hybrid search engine combining semantic (vector) and lexical (full-text) search.
    Uses Reciprocal Rank Fusion (RRF) to combine results from both methods.
    """

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self._max_chunks_per_doc = getattr(settings, "RAG_MAX_CHUNKS_PER_DOC", 2)
        self._rerank_enabled = getattr(settings, "RAG_RERANK_ENABLED", False)
        self._rerank_model_name = getattr(settings, "RAG_RERANK_MODEL", "")
        self._rerank_top_k = getattr(settings, "RAG_RERANK_TOP_K", 30)
        self._adaptive_rrf = getattr(settings, "RAG_ADAPTIVE_RRF", True)
        self._default_vector_weight = getattr(settings, "RAG_HYBRID_VECTOR_WEIGHT", 0.6)
        self._default_lexical_weight = getattr(settings, "RAG_HYBRID_LEXICAL_WEIGHT", 0.4)
        self._reranker = None
        if self._rerank_enabled and self._rerank_model_name:
            try:
                from sentence_transformers import CrossEncoder
                self._reranker = CrossEncoder(self._rerank_model_name)
            except Exception:
                logger.exception("Reranker initialization failed")
                self._reranker = None

    def _adaptive_weights(self, query: str) -> tuple[float, float]:
        if not self._adaptive_rrf:
            return self._default_vector_weight, self._default_lexical_weight

        normalized = query.lower()
        if re.search(r"boe-a-\d{4}-\d+|ley\s+\d+/\d{4}|art\w*\.\s*\d+", normalized):
            return 0.3, 0.7
        if any(token in normalized for token in ["que es", "como funciona", "diferencia entre"]):
            return 0.8, 0.2

        return self._default_vector_weight, self._default_lexical_weight

    def hybrid_search(
        self,
        query: str,
        limit: int = 10,
        vector_weight: float = 0.6,
        lexical_weight: float = 0.4,
        rrf_k: int = 60,
        diversity_max_per_doc: int | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search using vector and lexical search with RRF fusion.

        Args:
            query: Search query text
            limit: Number of results to return
            vector_weight: Weight for vector search in final ranking (0-1)
            lexical_weight: Weight for lexical search in final ranking (0-1)
            rrf_k: RRF constant (default 60, higher = more conservative fusion)

        Returns:
            List of search results with metadata
        """
        logger.info(f"Hybrid search: '{query}' (limit={limit})")

        # OPTIMIZATION: Fetch limit results instead of limit*2 to reduce DB queries
        # We still get good fusion because RRF combines overlapping results
        vector_results = self.vector_search(query, limit=limit)
        lexical_results = self.lexical_search(query, limit=limit)

        adaptive_vector_weight, adaptive_lexical_weight = self._adaptive_weights(query)

        # Apply RRF fusion
        fused_results = self._reciprocal_rank_fusion(
            vector_results=vector_results,
            lexical_results=lexical_results,
            k=rrf_k,
            vector_weight=adaptive_vector_weight,
            lexical_weight=adaptive_lexical_weight,
            diversity_max_per_doc=diversity_max_per_doc,
        )

        fused_results = self._maybe_rerank(query, fused_results, limit)

        # Return top N results
        return fused_results[:limit]

    def _maybe_rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        limit: int,
    ) -> List[Dict[str, Any]]:
        if not self._reranker or not results or len(results) <= limit:
            return results

        rerank_pool = results[: max(self._rerank_top_k, limit)]
        pairs = [(query, chunk.get("chunk_text", "")) for chunk in rerank_pool]

        try:
            scores = self._reranker.predict(pairs)
        except Exception:
            logger.exception("Reranking failed")
            return results

        for chunk, score in zip(rerank_pool, scores):
            chunk["rerank_score"] = float(score)

        reranked = sorted(rerank_pool, key=lambda item: item.get("rerank_score", 0), reverse=True)
        return reranked + results[len(rerank_pool):]

    def _enforce_diversity(
        self,
        results: List[Dict[str, Any]],
        max_per_doc: int,
    ) -> List[Dict[str, Any]]:
        if max_per_doc <= 0:
            return results
        counts: Dict[str, int] = {}
        diverse = []
        for result in results:
            doc_id = result.get("document_id")
            count = counts.get(doc_id, 0)
            if doc_id and count >= max_per_doc:
                continue
            diverse.append(result)
            if doc_id:
                counts[doc_id] = count + 1
        return diverse

    def vector_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Semantic search using vector embeddings and cosine similarity.

        Args:
            query: Search query text
            limit: Number of results to return

        Returns:
            List of search results ordered by similarity
        """
        logger.info(f"Vector search: '{query}' (limit={limit})")

        # Generate embedding for query
        query_embedding = self.embedding_service.embed(query)

        # Query database using pgvector cosine similarity
        chunks = DocumentChunk.objects.annotate(
            distance=CosineDistance('embedding', query_embedding)
        ).filter(
            distance__lt=0.7  # Similarity threshold (cosine distance < 0.7)
        ).select_related(
            'document',
            'document__source'
        ).order_by('distance')[:limit]

        # Format results
        results = []
        for idx, chunk in enumerate(chunks, 1):
            similarity = 1 - chunk.distance  # Convert distance to similarity
            results.append({
                'rank': idx,
                'chunk_id': str(chunk.id),
                'chunk_label': chunk.chunk_label or chunk.chunk_type,
                'chunk_text': chunk.chunk_text,
                'chunk_type': chunk.chunk_type,
                'distance': chunk.distance,
                'similarity': similarity,
                'document_title': chunk.document.doc_title,
                'document_id': chunk.document.doc_id_oficial,
                'document_url': chunk.document.url,
                'source_title': chunk.document.source.titulo,
                'source_priority': chunk.document.source.prioridad,
                'source_naturaleza': chunk.document.source.naturaleza,
                'metadata': chunk.metadata,
                'search_method': 'vector'
            })

        logger.info(f"Vector search found {len(results)} results")
        return results

    def lexical_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Full-text search using PostgreSQL's built-in FTS.

        Args:
            query: Search query text
            limit: Number of results to return

        Returns:
            List of search results ordered by relevance
        """
        logger.info(f"Lexical search: '{query}' (limit={limit})")

        # Create search vector and query
        search_vector = SearchVector('chunk_text', 'chunk_label', weight='A') + \
                       SearchVector('document__doc_title', weight='B')

        search_query = SearchQuery(query, search_type='websearch')

        # Query database using PostgreSQL FTS
        chunks = DocumentChunk.objects.annotate(
            search=search_vector,
            rank=SearchRank(search_vector, search_query)
        ).filter(
            rank__gt=0.01  # Relevance threshold
        ).select_related(
            'document',
            'document__source'
        ).order_by('-rank')[:limit]

        # Format results
        results = []
        for idx, chunk in enumerate(chunks, 1):
            results.append({
                'rank': idx,
                'chunk_id': str(chunk.id),
                'chunk_label': chunk.chunk_label or chunk.chunk_type,
                'chunk_text': chunk.chunk_text,
                'chunk_type': chunk.chunk_type,
                'fts_rank': float(chunk.rank),
                'document_title': chunk.document.doc_title,
                'document_id': chunk.document.doc_id_oficial,
                'document_url': chunk.document.url,
                'source_title': chunk.document.source.titulo,
                'source_priority': chunk.document.source.prioridad,
                'source_naturaleza': chunk.document.source.naturaleza,
                'metadata': chunk.metadata,
                'search_method': 'lexical'
            })

        logger.info(f"Lexical search found {len(results)} results")
        return results

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Dict[str, Any]],
        lexical_results: List[Dict[str, Any]],
        k: int = 60,
        vector_weight: float = 0.6,
        lexical_weight: float = 0.4,
        diversity_max_per_doc: int | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Combine results from vector and lexical search using Reciprocal Rank Fusion.

        RRF formula: score(chunk) = Σ(weight_i / (k + rank_i))

        Args:
            vector_results: Results from vector search
            lexical_results: Results from lexical search
            k: RRF constant (higher = more conservative)
            vector_weight: Weight for vector search
            lexical_weight: Weight for lexical search

        Returns:
            Fused and re-ranked results
        """
        logger.info(f"RRF fusion: {len(vector_results)} vector + {len(lexical_results)} lexical (k={k})")

        # Create lookup dicts by chunk_id
        chunk_scores = {}
        chunk_data = {}

        # Process vector results
        for result in vector_results:
            chunk_id = result['chunk_id']
            rank = result['rank']
            rrf_score = vector_weight / (k + rank)

            chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + rrf_score
            chunk_data[chunk_id] = result
            chunk_data[chunk_id]['rrf_sources'] = ['vector']
            chunk_data[chunk_id]['vector_rank'] = rank
            if 'similarity' in result:
                chunk_data[chunk_id]['vector_similarity'] = result['similarity']

        # Process lexical results
        for result in lexical_results:
            chunk_id = result['chunk_id']
            rank = result['rank']
            rrf_score = lexical_weight / (k + rank)

            chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + rrf_score

            if chunk_id in chunk_data:
                chunk_data[chunk_id]['rrf_sources'].append('lexical')
                chunk_data[chunk_id]['lexical_rank'] = rank
                if 'fts_rank' in result:
                    chunk_data[chunk_id]['fts_rank'] = result['fts_rank']
            else:
                chunk_data[chunk_id] = result
                chunk_data[chunk_id]['rrf_sources'] = ['lexical']
                chunk_data[chunk_id]['lexical_rank'] = rank

        # Sort by RRF score
        fused_results = []
        for chunk_id, score in sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True):
            result = chunk_data[chunk_id]
            result['rrf_score'] = score
            result['search_method'] = 'hybrid'
            fused_results.append(result)

        diversity_limit = diversity_max_per_doc
        if diversity_limit is None:
            diversity_limit = self._max_chunks_per_doc
        fused_results = self._enforce_diversity(fused_results, diversity_limit)

        logger.info(f"RRF fusion produced {len(fused_results)} unique results")
        return fused_results
