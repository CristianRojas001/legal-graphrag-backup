# Legal GraphRAG System - API Specification

## Document Information
- **Version**: 1.1 (MVP build)
- **Last Updated**: 2025-12-16
- **Status**: Implementation In Progress
- **Related**: [01_ARCHITECTURE.md](./01_ARCHITECTURE.md) | [04_RETRIEVAL_GUIDE.md](./04_RETRIEVAL_GUIDE.md)

---

## 1. API Overview

### Base URL

```
Development: http://localhost:8000/api/v1/legal-graphrag/
Production:  https://api.artisting.es/api/v1/legal-graphrag/
```

### Authentication

**MVP**: Anonymous queries allowed (no authentication required)

**Post-MVP**: JWT authentication (shared with existing auth system)

```http
Authorization: Bearer <jwt_token>
```

### Response Format (Current)

Endpoints return direct payloads (no `success/data` wrapper):

```json
{
  "session_id": "...",
  "answer": "...",
  "sources": [],
  "metadata": {}
}
```

---

## 2. Implemented Endpoints (Current)

### 2.1 POST /chat/

**Purpose**: Conversational legal Q&A

**Request**:

```http
POST /api/v1/legal-graphrag/chat/
Content-Type: application/json

{
  "query": "Puedo deducir gastos de mi home studio?",
  "session_id": "optional-uuid",
  "area_principal": "Fiscal",
  "max_sources": 8
}
```

**Response**:

```json
{
  "session_id": "7b3c6d3e-2a0a-4f7c-9b8c-8d4a6c0d3f21",
  "answer": "**Normativa aplicable**
...",
  "sources": [
    {
      "id": "BOE-A-2006-20764",
      "title": "Ley 35/2006 del IRPF",
      "url": "https://www.boe.es/eli/es/l/2006/11/28/35/con",
      "source_type": "Normativa",
      "relevance_score": 0.83,
      "excerpt": "Son gastos deducibles aquellos que...",
      "label": "Articulo 30.2",
      "source_title": "Ley IRPF",
      "source_priority": "P1",
      "chunk_type": "article"
    }
  ],
  "metadata": {
    "area_principal": "Fiscal",
    "model": "gemini-2.5-flash",
    "normativa_count": 3,
    "doctrina_count": 1,
    "jurisprudencia_count": 0,
    "total_sources": 4,
    "abstained": false
  }
}
```

**Notes**:
- If the query is a greeting/chitchat, the response includes `metadata.greeting = true` and empty sources.
- If the query looks like a follow-up and the session has history, the response includes `metadata.follow_up = true` and uses recent conversation context.

---

### 2.2 POST /search/

**Purpose**: Hybrid search (no LLM answer generation)

**Request**:

```http
POST /api/v1/legal-graphrag/search/
Content-Type: application/json

{
  "query": "derechos de autor",
  "limit": 10
}
```

**Response**:

```json
{
  "count": 2,
  "results": [
    {
      "rank": 1,
      "chunk_id": "4b2d3f1e-...",
      "chunk_label": "Articulo 14",
      "chunk_text": "Corresponde al autor...",
      "chunk_type": "article",
      "document_title": "Texto Refundido de la Ley de Propiedad Intelectual",
      "document_id": "BOE-A-1996-8930",
      "document_url": "https://www.boe.es/eli/es/rdleg/1996/04/12/1/con",
      "source_title": "TR LPI",
      "source_priority": "P1",
      "source_naturaleza": "Normativa",
      "search_method": "hybrid",
      "rrf_score": 0.016
    }
  ]
}
```

---

### 2.3 GET /sources/

**Purpose**: List corpus sources with optional filters

**Request**:

```http
GET /api/v1/legal-graphrag/sources/?prioridad=P1&area_principal=Fiscal
```

**Response**:

```json
{
  "count": 70,
  "results": [
    {
      "id": 1,
      "prioridad": "P1",
      "naturaleza": "Normativa",
      "area_principal": "Fiscal",
      "titulo": "Ley 35/2006 del IRPF",
      "tipo": "Ley",
      "ambito": "Espana",
      "funcion_artisting": "Base fiscal para artistas",
      "id_oficial": "BOE-A-2006-20764",
      "url_oficial": "https://www.boe.es/eli/es/l/2006/11/28/35/con",
      "vigencia": "Vigente",
      "nivel_autoridad": "Ley",
      "estado": "ingested",
      "last_ingested_at": "2025-12-16T12:00:00Z"
    }
  ]
}
```

**Query Parameters**:
- `prioridad`: P1, P2, P3
- `naturaleza`: Normativa, Doctrina administrativa, Jurisprudencia
- `area_principal`: Fiscal, Laboral, Propiedad Intelectual, etc.
- `estado`: pending, ingesting, ingested, failed, skipped

---

### 2.4 GET /health/

**Purpose**: Health check for monitoring

**Request**:

```http
GET /api/v1/legal-graphrag/health/
```

**Response**:

```json
{
  "status": "healthy",
  "database": "healthy",
  "corpus": {
    "total_sources": 70,
    "ingested_sources": 37
  },
  "version": "1.0.0"
}
```

---

## 3. V1.1 Endpoints (Planned)

V1.1 will be exposed via a separate endpoint to avoid affecting V1.0 behavior.

### 3.1 POST /v1_1/chat/

**Purpose**: Multi-query retrieval + hierarchy-safe fusion + judge/redo pipeline.

**Request/Response**: Same shape as `/chat/`, with additional `metadata.judge` fields.

---

## 3. Planned Endpoints (Not Implemented Yet)

These are part of the roadmap and will be added post-MVP:

- `GET /documents/{doc_id}/` - Full document with all chunks
- `GET /sources/{source_id}/` - Source detail with ingestion status
- `POST /feedback/` - Answer quality feedback
- `GET /chat/sessions/{session_id}/` - Chat history for a session

---

## 4. Error Handling

Validation errors return DRF standard 400 responses (field errors). Server-side failures return 500 responses with a `detail` field.

---

**Document End** | Next: [06_DEPLOYMENT_GUIDE.md](./06_DEPLOYMENT_GUIDE.md)
