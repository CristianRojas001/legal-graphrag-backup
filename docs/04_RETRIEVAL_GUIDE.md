# Legal GraphRAG System - Retrieval Guide

## Document Information
- **Version**: 1.1 (MVP build)
- **Last Updated**: 2025-12-16
- **Status**: Implementation In Progress
- **Related**: [01_ARCHITECTURE.md](./01_ARCHITECTURE.md) | [03_INGESTION_GUIDE.md](./03_INGESTION_GUIDE.md)

---

## 1. Retrieval Pipeline (Current)

The current retrieval pipeline is optimized for speed and legal hierarchy compliance.

```mermaid
flowchart TD
  query[User Query] --> intent[Intent Classifier]
  intent --> hybrid[Hybrid Search (Vector + FTS)]
  hybrid --> rrf[RRF Fusion]
  rrf --> split[Split by Naturaleza]
  split --> filter[Area Relevance Filter]
  filter --> gate[Evidence Gating]
  gate --> prompt[LLM Prompt with Hierarchy]
  prompt --> answer[Answer + Sources]
```

Key behaviors:
- **Single hybrid search** per query (faster than 3 separate searches).
- **RRF fusion** combines vector and lexical ranks.
- **Hierarchy split** keeps top Normativa/Doctrina/Jurisprudencia chunks.
- **Evidence gating** abstains when evidence is weak or off-topic.

---

## 2. Hybrid Search (Current Implementation)

Implemented in `apps/legal_graphrag/services/legal_search_engine.py`.

- **Vector search**: pgvector cosine distance (`CosineDistance`) with a threshold.
- **Lexical search**: PostgreSQL FTS with `SearchVector` and `SearchRank`.
- **Fusion**: Reciprocal Rank Fusion (RRF) with configurable weights.

RRF uses:
```
score(chunk) = sum(weight_i / (k + rank_i))
```

Defaults:
- `vector_weight = 0.6`
- `lexical_weight = 0.4`
- `rrf_k = 60`

---

## 3. Hierarchical Source Selection

After the hybrid list is built, results are split by `source_naturaleza`:

- Normativa: up to 5 chunks
- Doctrina administrativa: up to 3 chunks
- Jurisprudencia: up to 2 chunks

This respects legal authority while keeping answer length bounded.

---

## 4. Area Filtering and Evidence Gating

The `LegalRAGEngine` applies two safeguards:

1. **Area relevance filter**: Keeps sources matching area-specific tokens or law-family hints.
2. **Evidence gating**: Abstains when sources are missing, off-topic, or weakly matched.

Numeric claims (e.g., IVA rates) are only allowed if the rate appears in the sources. Otherwise the engine abstains.

---

## 5. Intent Classification (Current)

The intent classifier is a keyword-based classifier with a confidence score. It is used to:

- Label `area_principal` for metadata
- Improve filtering and abstention
- Inform the prompt of the legal area

---

## 6. Planned Retrieval Improvements (Post-MVP)

These are not implemented yet but remain in scope:

- Filters in `/search` (by area, prioridad, naturaleza)
- Cross-encoder reranking
- Citation graph expansion
- Query expansion and synonym handling
- Temporal versioning of laws

---

**Document End** | Next: [05_API_SPECIFICATION.md](./05_API_SPECIFICATION.md)
