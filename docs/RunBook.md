# Legal GraphRAG RunBook

Practical steps to run the system locally (backend + frontend) and verify it’s healthy.

## Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 15 with pgvector
- Redis 7+
- Gemini API key set in environment

## 1) Backend
```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate   # Windows
pip install -r requirements.txt

# Ensure pgvector enabled in DB
python manage.py dbshell
# in psql: CREATE EXTENSION IF NOT EXISTS vector; \q

# Run migrations (tables exist but keep schema in sync)
python manage.py migrate

# Optional: import corpus catalog if empty
python manage.py import_corpus_from_excel ../corpus_normativo_artisting_enriched.xlsx

# Start API
python manage.py runserver 0.0.0.0:8000
```

### Ingestion (optional)
```bash
# Start Redis separately, then:
celery -A ovra_backend worker -l info   # new terminal
python manage.py ingest_all_p1          # or run the mgmt command queued via Celery
```

### Health check
```bash
curl http://localhost:8000/api/v1/legal-graphrag/health/
```

## 2) Frontend
```bash
cd frontend-legal
npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL to backend URL
npm run dev -- --port 3001
```
Open http://localhost:3001

## 3) Quick API smoke tests
```bash
# Chat
curl -X POST http://localhost:8000/api/v1/legal-graphrag/chat/ \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"Puedo deducir gastos de mi home studio?\", \"max_sources\": 5}"

# Search
curl -X POST http://localhost:8000/api/v1/legal-graphrag/search/ \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"derechos de autor\", \"limit\": 5}"
```

## 4) Tests
```bash
cd backend
pytest
```

## 5) Troubleshooting
- Backend 500s: check `backend/runserver.err.log`
- Ingestion stuck: check Redis is running and Celery worker output
- No search results: confirm pgvector extension and embeddings exist in `legal_document_chunks`
- CORS/local API: ensure `NEXT_PUBLIC_API_URL` matches backend URL and includes port
