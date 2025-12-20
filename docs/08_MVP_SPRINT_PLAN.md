# Legal GraphRAG System - MVP Sprint Plan

## Document Information
- **Version**: 1.0 (MVP)
- **Last Updated**: 2025-12-13
- **Status**: Day 6 In Progress - Testing & Refinement (Codex)
- **Timeline**: 7 days (2025-12-11 to 2025-12-18)
- **Related**: [00_OVERVIEW.md](./00_OVERVIEW.md) | [07_TESTING_STRATEGY.md](./07_TESTING_STRATEGY.md) | [Refinement](./Refinement/README.md)

---

## 1. Sprint Overview

### Goal
Build a functional Legal GraphRAG chat system for Spanish artists that can answer legal questions using official sources (BOE, EUR-Lex) with high accuracy and zero hallucinations.

### Timeline
**Total**: 7 days (1 week)
**Team**: 1 developer + 1 AI assistant (Claude)

### Success Criteria
- ✅ 37 P1 sources ingested and searchable
- ✅ Hybrid search (semantic + lexical) working
- ✅ LLM generates structured answers with citations
- 🔄 Frontend built and ready for testing
- ⏳ 80%+ accuracy on 10 test queries (Day 6)
- ⏳ <5s average response time (Day 6)

**Progress**: Days 1-5 complete (5/7 days) | Day 6 testing in progress (API smoke checks + backend pytest done; UI/browser Chrome/Firefox/WebKit done; Edge/Safari pending)

---

## 2. Day-by-Day Plan

### Day 1 (Wednesday): Database & Models

**Hours**: 8h

**Tasks**:
1. **Database Setup** (2h)
   - [x] Enable pgvector extension in Digital Ocean PostgreSQL
   - [x] Verify connection from local machine
   - [x] Test vector operations

2. **Django App Creation** (3h)
   - [x] Create `apps/legal_graphrag` app
   - [x] Define models (CorpusSource, LegalDocument, DocumentChunk, ChatSession, ChatMessage)
   - [x] Create migrations
   - [x] Run migrations
   - [x] Register models in Django admin

3. **Import Corpus** (2h)
   - [x] Create management command `import_corpus_from_excel`
   - [x] Import 70 sources from Excel file
   - [x] Verify import in database (psql)

4. **Testing** (1h)
   - [x] Write model unit tests
   - [x] Run tests

**Deliverable**: Database tables created, 70 corpus sources imported

**Commands**:
```bash
# Database setup
python manage.py dbshell
CREATE EXTENSION IF NOT EXISTS vector;

# Create app and models
python manage.py startapp legal_graphrag apps/legal_graphrag
python manage.py makemigrations legal_graphrag
python manage.py migrate legal_graphrag

# Import corpus
python manage.py import_corpus_from_excel corpus_normativo_artisting_enriched.xlsx

# Verify
python manage.py shell
>>> from apps.legal_graphrag.models import CorpusSource
>>> print(CorpusSource.objects.count())  # Should be 70
```

---

### Day 2 (Thursday): Ingestion Pipeline ✅

**Hours**: 8h
**Status**: COMPLETE

**Tasks**:
1. **Connector Development** (4h)
   - [x] Implement BOEConnector
   - [x] Implement DOUEConnector
   - [x] Implement DGTConnector
   - [x] Test each connector with sample URL

2. **Normalizer** (2h)
   - [x] Implement LegalDocumentNormalizer
   - [x] Test normalization on 3 sample documents

3. **Celery Tasks** (2h)
   - [x] Implement `ingest_legal_source` task
   - [x] Implement `ingest_all_p1_sources` task
   - [x] Test task execution locally

**Deliverable**: ✅ Ingestion pipeline can fetch, parse, and store 1 source (Constitution - 182 chunks ingested)

**Commands**:
```bash
# Test ingestion locally
python manage.py ingest_source BOE-A-1978-31229 --sync

# Verify document created
python manage.py shell
>>> from apps.legal_graphrag.models import LegalDocument, DocumentChunk
>>> print(LegalDocument.objects.count())  # Should be 1
>>> print(DocumentChunk.objects.count())  # Should be >0
```

---

### Day 3 (Friday): Embeddings & Search ✅

**Hours**: 8h
**Status**: COMPLETE

**Tasks**:
1. **Embedding Service** (2h)
   - [x] Implement EmbeddingService (Gemini API)
   - [x] Test embedding generation
   - [x] Add embedding to ingestion pipeline

2. **Ingest P1 Sources** (3h)
   - [x] Re-import corpus with PDF URLs
   - [x] Start synchronous ingestion (Celery compatibility issues)
   - [x] Queue 28 P1 sources with valid PDF URLs for ingestion
   - [x] Monitor progress (3/28 ingested, 25 in progress)
   - [x] Fix ingestion errors (Unicode encoding, URL mismatches)

3. **Search Engine** (3h)
   - [x] Implement vector search
   - [x] Implement lexical search (PostgreSQL FTS)
   - [x] Implement RRF fusion
   - [x] Test search with sample queries

**Deliverable**: ✅ 3 P1 sources ingested (1,029 chunks), search engine returns relevant results with high accuracy

**Commands**:
```bash
# Re-import corpus with PDF URLs
python manage.py import_corpus_from_excel corpus_normativo_artisting_enriched_clean.xlsx

# Start P1 ingestion (synchronous script in background)
python ingest_p1_sync.py > ingestion_log.txt 2>&1 &

# Monitor progress
python manage.py shell -c "from apps.legal_graphrag.models import *; print(f'Ingested: {CorpusSource.objects.filter(prioridad=\"P1\", estado=\"ingested\").count()}/37'); print(f'Chunks: {DocumentChunk.objects.count()}')"

# Test search
python test_search.py

# Or interactive:
python manage.py shell
>>> from apps.legal_graphrag.services.legal_search_engine import LegalSearchEngine
>>> engine = LegalSearchEngine()
>>> results = engine.hybrid_search("gastos deducibles", limit=5)
>>> print(f"Found {len(results)} results")
```

---

### Day 4 (Saturday): RAG & API

**Hours**: 8h

**Tasks**:
1. **Intent Classifier** (1h) ✅
   - [x] Implement keyword-based intent classifier
   - [x] Test classification on sample queries (instructions provided for Codex)

2. **RAG Engine** (4h) ✅
   - [x] Implement LegalRAGEngine
   - [x] Build hierarchical prompt
   - [x] Test LLM answer generation (for Codex)
   - [x] Verify citations in answers (for Codex)

3. **API Endpoints** (3h)
   - [x] Implement `/chat/` endpoint (POST)
   - [x] Implement `/search/` endpoint (POST)
   - [x] Implement `/sources/` endpoint (GET)
   - [x] Test endpoints with Postman/curl

**Deliverable**: API endpoints functional, RAG pipeline generates answers with citations

**Commands**:
```bash
# Start Django dev server
python manage.py runserver

# Test API (separate terminal)
curl -X POST http://localhost:8000/api/v1/legal-graphrag/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "¿Puedo deducir gastos de home studio?"}'

# Expected: JSON response with answer + sources
```

---

### Day 5 (Sunday): Frontend ✅

**Hours**: 8h
**Status**: COMPLETE

**Tasks**:
1. **Next.js Setup** (2h) ✅
   - [x] Create Next.js 15 app with TypeScript
   - [x] Set up Tailwind CSS v4
   - [x] Configure API client service
   - [x] Install dependencies (react-markdown, axios, @tailwindcss/typography)
   - [x] Set up environment variables

2. **Chat Interface** (4h) ✅
   - [x] Build LegalChatInterface component
   - [x] Add query input form (with validation & char counter)
   - [x] Display answer (markdown rendering)
   - [x] Display source cards (expandable)
   - [x] Implement session management with UUIDs
   - [x] Add auto-scroll to latest message
   - [x] Add message timestamps

3. **Styling & UX** (2h) ✅
   - [x] Add loading states (skeleton UI with animation)
   - [x] Add error handling (dismissible error messages)
   - [x] Add legal disclaimer (dismissible banner)
   - [x] Responsive design (mobile & desktop)
   - [x] Source type color coding (BOE, EUR-Lex, DGT)
   - [x] Accessibility features (ARIA labels, semantic HTML)

**Deliverable**: ✅ Functional frontend ready for backend integration (build successful, no TypeScript/ESLint errors)

**Components Created**:
- LegalChatInterface.tsx (240 lines)
- SourceCard.tsx (100 lines)
- LoadingSkeleton.tsx (30 lines)
- ErrorMessage.tsx (45 lines)
- LegalDisclaimer.tsx (55 lines)
- API client service (120 lines)
- TypeScript types (60 lines)

**Documentation**:
- README.md (complete frontend docs)
- INSTRUCTIONS_FOR_CODEX.md (testing guide)
- QUICK_START.md (startup guide)
- DAY_5_FRONTEND_COMPLETE.md (completion summary)

**Commands**:
```bash
# Create Next.js app
npx create-next-app@latest frontend-legal --typescript --tailwind --app

# Install dependencies
cd frontend-legal
npm install react-markdown axios @tailwindcss/typography

# Run dev server
npm run dev

# Visit http://localhost:3000
```

**Next**: Integration testing with backend (for Codex)

---

### Day 6 (Monday): Testing & Refinement

**Hours**: 8h
**Status**: IN PROGRESS (Codex) | API smoke tests complete; backend pytest passing; UI/browser checks done for Chrome/Firefox/WebKit (Edge/Safari pending) | Report: `frontend-legal/FRONTEND_TEST_REPORT.md`

**Tasks**:
0. **Smoke Tests (Codex)** (1h)
   - [x] Start backend + frontend locally
   - [x] Run chat/search API sanity checks (CLI)
   - [x] Log results in `FRONTEND_TEST_REPORT.md`
   - [x] Run browser UI checklist from `frontend-legal/INSTRUCTIONS_FOR_CODEX.md`

1. **Unit Tests** (2h)
   - [x] Write model tests
   - [x] Write connector tests
   - [x] Write search engine tests
   - [x] Run all tests

2. **Integration Tests** (2h)
   - [ ] Write RAG engine tests
   - [ ] Write API endpoint tests
   - [ ] Test with 10 artist query scenarios

3. **Quality Assurance** (4h)
   - [ ] Test all 10 artist query scenarios manually
   - [ ] Verify citations are correct
   - [ ] Check for hallucinations
   - [ ] Measure response times
   - [ ] Fix bugs

**Deliverable**: 80%+ test pass rate, 0 hallucinations detected

**Findings so far**:
- GEMINI_API_KEY válido; se usa Gemini 2.5 flash (calidad LLM aún no validada con set de verdad terreno)
- Latencia alta: chat ~7–13.5s, búsqueda ~10.8s (objetivo <5s)
- UI/UX checklist completada (desktop + mobile); warning de React por keys duplicadas mitigado en frontend
- `/api/v1/legal-graphrag/health/` agregado (200 OK)
- Pytest (backend): 34 passed (solo warnings menores)
- Gating de fuentes ajustado (tokens + hints por área; abstención si evidencia no coincide)
- Evaluador de escenarios agregado: `backend/scripts/eval_refinement.py` (reporta a `docs/Refinement/scenario_eval_latest.*`)
- Validador de citas/números: se eliminan IDs no recuperados y se abstiene si hay %/tipo sin soporte; guardia IVA solo permite 0/4/5/10/21%
- Re-evaluación 14 escenarios (gating + validador): lat ~6–10s, 2–5 fuentes; mayoría responde "No tengo información..." (abstiene cuando falta evidencia); IVA concierto y nuevas preguntas de IVA/PI/laboral ya no inventan tipos
- 10 escenarios de artistas ejercitados vía API (Gemini 2.5 flash, P1 corpus); respuestas genéricas con citas poco pertinentes o incorrectas (IRPF/IVA/PI)
- Cross-browser: Chrome/Firefox OK; WebKit OK (5 tarjetas); Edge/Safari pendiente

**Commands**:
```bash
# Run all tests
pytest apps/legal_graphrag/tests/

# Run artist query tests
pytest apps/legal_graphrag/tests/test_artist_queries.py -v

# Check coverage
pytest --cov=apps.legal_graphrag --cov-report=html
```

---

### Day 7 (Tuesday): Deployment

**Hours**: 8h

**Tasks**:
1. **Backend Deployment** (3h)
   - [ ] Create `.do/app.yaml` spec
   - [ ] Set environment variables in DO
   - [ ] Deploy backend to Digital Ocean
   - [ ] Verify deployment (health check)
   - [ ] Run migrations on production DB

2. **Frontend Deployment** (2h)
   - [ ] Build Next.js app
   - [ ] Deploy frontend to Digital Ocean
   - [ ] Verify deployment
   - [ ] Test API connection

3. **Post-Deployment** (2h)
   - [ ] Ingest P1 sources on production (Celery)
   - [ ] Test end-to-end with production URLs
   - [ ] Set up monitoring/logging

4. **Documentation** (1h)
   - [ ] Update README
   - [ ] Document deployment process
   - [ ] Create user guide (optional)

**Deliverable**: System live at legal.artisting.es, fully functional

**Commands**:
```bash
# Backend deployment
git add .
git commit -m "Deploy Legal GraphRAG MVP"
git push origin main

# Digital Ocean auto-deploys

# Verify
curl https://api.artisting.es/api/v1/health/
curl https://legal.artisting.es

# Ingest sources on production
doctl apps exec <app-id> -- python manage.py ingest_all_p1
```

---

## 3. Risk Mitigation

### High-Risk Items

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| BOE parsing fails for some sources | High | Medium | Implement fallback to full-text chunk |
| Gemini API rate limit hit | Medium | High | Cache embeddings, use delay between requests |
| Slow vector search (>1s) | Low | Medium | Use IVFFlat index, limit corpus to P1 for MVP |
| LLM hallucinates laws | Medium | Critical | Strict prompt engineering, test with validation set |

### Contingency Plans

**If Day 3 ingestion fails**:
- Manual ingestion of top 10 critical sources
- Defer P2/P3 to post-MVP

**If Day 5 frontend blocked**:
- Use simple HTML form + AJAX instead of Next.js
- Deploy frontend post-MVP

**If Day 7 deployment fails**:
- Extend to Day 8
- Deploy backend only, frontend stays local

---

## 4. Daily Standup Template

```
**Yesterday**:
- What did I complete?
- Any blockers?

**Today**:
- What will I work on?
- Expected deliverables?

**Risks**:
- Anything that could delay the sprint?
```

---

## 5. Definition of Done (DoD)

### For Each Task
- [ ] Code written and tested locally
- [ ] Unit tests pass
- [ ] No linting errors
- [ ] Committed to Git

### For MVP (End of Sprint)
- [ ] All P1 sources ingested (37/37)
- [ ] Search returns relevant results (manual verification)
- [ ] LLM generates answers with citations (10/10 test queries)
- [ ] Frontend accessible at legal.artisting.es
- [ ] Backend accessible at api.artisting.es
- [ ] 0 hallucinations detected (10/10 test queries)
- [ ] Average response time <5s
- [ ] Documentation updated

---

## 6. Tools & Resources

### Development Tools
- **Code Editor**: VS Code
- **API Testing**: Postman, curl
- **Database**: psql, DBeaver
- **Version Control**: Git, GitHub
- **Task Queue**: Celery, Redis

### Reference URLs
- **BOE**: https://www.boe.es
- **EUR-Lex**: https://eur-lex.europa.eu
- **Gemini API**: https://ai.google.dev/docs
- **pgvector**: https://github.com/pgvector/pgvector

---

## 7. Post-Sprint Review

### After Day 7

**What Went Well**:
- [To be filled after sprint]

**What Could Be Improved**:
- [To be filled after sprint]

**Next Steps**:
- Ingest P2 sources (23 sources)
- Add multi-turn conversation support
- Improve prompt for better answers
- User testing with real artists

---

**Document End** | Next: [09_FUTURE_ROADMAP.md](./09_FUTURE_ROADMAP.md)
