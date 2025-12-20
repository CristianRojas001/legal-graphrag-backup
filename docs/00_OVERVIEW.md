# Legal GraphRAG System - Overview

## Document Information
- - **Version**: 1.1 (MVP build)
- - **Last Updated**: 2025-12-16
- - **Status**: Implementation In Progress
- **Project Timeline**: MVP in 1 week
- **Refinement**: [docs/Refinement/README.md](./Refinement/README.md)

---

## 1. Executive Summary

The **Artisting Legal Assistant** is a specialized Retrieval-Augmented Generation (RAG) system designed to provide accurate, grounded legal guidance to artists and cultural professionals in Spain. The system focuses on three core pillars of Spanish legal information:

1. **Normativa** (Hard Law) - Constitutional law, statutes, royal decrees, orders
2. **Doctrina Administrativa** (Administrative Guidance) - DGT tax rulings, AEAT criteria, social security guidance
3. **Jurisprudencia** (Case Law) - Supreme Court, TJUE, TEDH rulings

### Key Differentiators

- **Domain-Specific**: Tailored for artists, not general legal queries
- **Hierarchy-Aware**: Respects legal authority (Constitution > Law > Decree > Admin guidance > Case law)
- **Grounded**: Every answer cites specific articles, rulings, or guidance documents
- **Explainable**: Users see exactly which sources informed each answer
- **Non-Hallucinatory**: System admits when it lacks information rather than inventing answers

---

## Refinement (Answer Quality)

See the refinement plan and sprint for improving retrieval, abstention behavior, and citation grounding:
- [Refinement index](./Refinement/README.md)
- [RAG Quality & Citation Grounding Plan](./Refinement/01_RAG_QUALITY_PLAN.md)
- [Refinement Sprint Plan](./Refinement/02_REFINEMENT_SPRINT_PLAN.md)


---

## Current Build Snapshot

Implemented in this repo:
- Django app with chat, search, sources, and health endpoints
- Hybrid search (pgvector + PostgreSQL FTS) with RRF fusion
- RAG engine with intent classification, hierarchy-aware prompting, and evidence gating
- Ingestion pipeline (BOE/DOUE/DGT connectors) via Celery tasks
- Session-based chat history (for short follow-up questions)

Not yet implemented (planned):
- Auth/billing integration with the parent platform
- Extended endpoints (/documents, /feedback, /chat sessions)
- Cross-encoder reranking and citation graph
- Chat quality is measured against the North Star goal and automated rules in [docs/Chat Evaluation/NorthStarGoal.md](./Chat%20Evaluation/NorthStarGoal.md) and [docs/Chat Evaluation/AUTOMATED_EVAL_RULES.md](./Chat%20Evaluation/AUTOMATED_EVAL_RULES.md).

## 2. Problem Statement

### Current Pain Points for Artists

Artists and cultural professionals in Spain face unique legal challenges:

1. **Complex Tax Treatment**
   - Special VAT regimes for artists
   - Cultural sector tax exemptions (mecenazgo)
   - Deductible expenses for home studios
   - Copyright income vs. service income

2. **Labor & Social Security Confusion**
   - Autónomo vs. employed status
   - Artists-specific social security benefits
   - Intermittent work patterns
   - International contracts

3. **Intellectual Property Complexity**
   - Copyright registration and protection
   - SGAE/CEDRO/VEGAP collective management
   - Digital platform rights
   - Moral rights vs. economic rights

4. **Grant & Subsidy Navigation**
   - Cultural sector grants (Ministry of Culture, regional)
   - Eligibility criteria for artists
   - Application requirements and deadlines

5. **Fragmented Information**
   - BOE (official bulletin) is dense and technical
   - DGT rulings scattered across databases
   - No single source for artist-specific guidance
   - Generic legal advice doesn't address artist edge cases

### What Artists Need

- **Plain Language**: Legal concepts explained simply
- **Artist-Specific**: Examples relevant to their work (galleries, performances, royalties)
- **Actionable**: "What do I need to do?" not just "What does the law say?"
- **Trustworthy**: References to official sources they can verify
- **Up-to-Date**: Reflects current law, not outdated information

---

## 3. Solution: Legal GraphRAG Chat

### Core Capabilities (MVP)

1. **Conversational Legal Q&A**
   - Natural language questions: "¿Puedo deducir gastos de home studio?"
   - Light follow-up handling: Short in-session questions use recent chat context
   - Intent detection: Tax? Labor? IP? Grants?

2. **Hybrid Search**
   - Semantic search: Understanding intent beyond keywords
   - Lexical search: Exact article/law references (BM25)
   - Filter-based: Area (fiscal, laboral), jurisdiction (España, UE, autonómico)

3. **Hierarchical Retrieval**
   - Search order: Normativa (P1) → Doctrina (P1) → Jurisprudencia (P1/P2)
   - Authority weighting: Constitution > Ley > Real Decreto > Orden > DGT > TS
   - Priority-based coverage: P1 sources (core) before P2 (important) before P3 (edge cases)

4. **Structured Answers**
   ```
   1. Resumen ejecutivo (1 paragraph)
   2. Normativa aplicable (laws + articles + explanation)
   3. Criterios administrativos (DGT/AEAT/SS guidance)
   4. Jurisprudencia relevante (case law if exists)
   5. Notas y requisitos (caveats, next steps)
   ```

5. **Citation Transparency**
   - Every claim backed by source reference
   - Expandable source cards: Article text, BOE ID, URL
   - Confidence indicators: "Alta confianza" vs. "Información limitada"

### Post-MVP Features (Phase 2+)

- Document version history (law changes over time)
- Graph-based citation network (find cases citing Article X)
- Multi-lingual support (Catalan, English for EU law)
- Proactive alerts (law changes affecting your saved queries)
- Comparative analysis (compare regional laws)

---

## 4. Target Users

### Primary Persona: **Elena - Independent Visual Artist**

**Profile**:
- Age: 32
- Location: Madrid
- Status: Autónomo (self-employed)
- Income: €25k/year (mix of gallery sales, commissions, grants)
- Legal knowledge: Basic (filed taxes once, confused about deductions)

**Pain Points**:
- Doesn't know which expenses are deductible
- Confused about VAT rates (21% vs. 10% for art?)
- Unsure if she needs facturas for everything
- Heard about "mecenazgo" tax benefits but doesn't understand them
- Wants to hire an assistant but doesn't know labor law implications

**Use Cases**:
- "¿Puedo deducir el alquiler de mi estudio?"
- "¿Qué IVA aplico si vendo un cuadro a una empresa?"
- "¿Cómo registro mis derechos de autor?"
- "¿Hay ayudas para artistas que quieran exponer en el extranjero?"

### Secondary Persona: **Carlos - Music Producer (Freelance)**

**Profile**:
- Age: 28
- Location: Barcelona
- Status: Started as autónomo 6 months ago
- Income: €40k/year (producing for labels, sync licensing)
- Legal knowledge: Minimal (relies on asesor fiscal)

**Pain Points**:
- International clients (copyright jurisdiction?)
- Spotify/streaming royalties (how to declare?)
- Wants to form a cooperative with other producers
- Social security contribution calculation confusing

**Use Cases**:
- "¿Cómo tributan los royalties de Spotify?"
- "¿Necesito un contrato específico para producción musical?"
- "¿Puedo formar una cooperativa de productores?"
- "¿Qué pasa si trabajo con un cliente de EEUU?"

### Tertiary Persona: **Ana - Cultural Association Manager**

**Profile**:
- Age: 45
- Location: Seville
- Status: Manages a non-profit cultural association
- Budget: €100k/year (mix of grants, memberships, ticket sales)
- Legal knowledge: Intermediate (knows basics, needs specific guidance)

**Pain Points**:
- Grant eligibility and compliance
- Non-profit accounting requirements
- Tax exemptions for cultural activities
- Volunteer vs. employee classification

**Use Cases**:
- "¿Qué subvenciones podemos solicitar como asociación cultural?"
- "¿Cómo se contabilizan las donaciones en una asociación?"
- "¿Podemos contratar artistas como colaboradores o deben ser empleados?"

---

## 5. Success Criteria (MVP)

### Functional Metrics

1. **Coverage**
   - ✅ 37 P1 sources ingested (Constitution, core tax/labor/IP laws)
   - ✅ 70+ document chunks with embeddings
   - ✅ All 4 main areas covered: Fiscal, Laboral, Propiedad Intelectual, Contabilidad

2. **Accuracy**
   - ✅ 80%+ of answers cite correct legal articles
   - ✅ 0% hallucinated laws or articles
   - ✅ 90%+ of citations verifiable (URL works, text matches)

3. **Response Quality**
   - ✅ Average response time < 5 seconds
   - ✅ Answers include 1-3 primary sources minimum
   - ✅ Structured format followed (Resumen → Normativa → Doctrina → Juris)

### User Experience Metrics

1. **Usability**
   - ✅ User can ask question without legal jargon
   - ✅ Citations expandable to see full text
   - ✅ Plain language explanations (no legalese)

2. **Trust**
   - ✅ Every answer includes BOE/official source links
   - ✅ System admits uncertainty ("No tengo información sobre esto")
   - ✅ Caveats displayed: "Consulta con asesor fiscal para tu caso específico"

### Technical Metrics

1. **Performance**
   - ✅ Vector search < 500ms
   - ✅ LLM response generation < 3 seconds
   - ✅ Total end-to-end < 5 seconds

2. **Reliability**
   - ✅ 99%+ uptime
   - ✅ Graceful error handling (no 500 errors to user)
   - ✅ Rate limiting prevents abuse

3. **Cost Efficiency**
   - ✅ < €0.05 per query (Gemini API + compute)
   - ✅ 100 queries/day = €5/day = €150/month budget

---

## 6. Scope Definition

### In Scope (MVP - Week 1)

✅ **Core Legal Areas**:
- Fiscal (IVA, IRPF, IS, mecenazgo)
- Laboral (autónomos, contratos, SS)
- Propiedad Intelectual (derechos de autor, SGAE)
- Contabilidad (PGC, obligaciones)

✅ **Source Types**:
- Normativa P1 (37 sources)
- Basic Doctrina P1 (DGT, AEAT if available)
- No Jurisprudencia for MVP (too complex)

✅ **Functionality**:
- Single-turn Q&A with limited in-session follow-up context
- Hybrid search (semantic + filters)
- Structured answer format
- Citation display

✅ **User Features**:
- Anonymous queries (no login required for MVP)
- Spanish language only
- Web interface (responsive)

### Out of Scope (MVP - Deferred to Phase 2+)

❌ **Advanced Features**:
- Multi-turn conversation memory
- Graph-based citation network
- Temporal versioning (law changes over time)
- Proactive law change alerts
- Document comparison

❌ **Additional Sources**:
- P2/P3 sources (23 + 8 sources)
- CENDOJ case law (complex ingestion)
- Regional/municipal laws (too granular)
- Non-Spanish languages

❌ **User Management**:
- User accounts (will use existing auth system but not required for queries)
- Query history (no persistence)
- Saved searches
- Personalized recommendations

❌ **Edge Cases**:
- International tax treaties
- Cross-border IP disputes
- Regional language laws (Catalan, Basque)

---

## 7. System Boundaries

### What the System IS

- 📚 **Legal information retrieval system** - Finds relevant laws/guidance
- 🤖 **AI-powered Q&A assistant** - Answers questions using retrieved sources
- 🔗 **Citation transparency layer** - Shows which sources informed answers
- 🎯 **Artist-specialized filter** - Focuses on cultural sector issues

### What the System IS NOT

- ❌ **Not a lawyer replacement** - Always disclaims: "Consulta con un asesor"
- ❌ **Not legal advice** - Informational only, no attorney-client relationship
- ❌ **Not a decision-maker** - User must evaluate applicability to their case
- ❌ **Not exhaustive** - Limited to corpus sources, not all Spanish law
- ❌ **Not real-time** - Law updates ingested weekly, not immediately

### Legal Disclaimers (Required in UI)

```
⚠️ AVISO LEGAL
Esta herramienta proporciona información legal general con fines
educativos. No constituye asesoramiento legal personalizado. Para
decisiones específicas sobre tu situación, consulta con un abogado
o asesor fiscal colegiado. Artisting no se responsabiliza por
decisiones tomadas basándose únicamente en esta información.
```

---

## 8. Integration with Existing Systems

### Shared Infrastructure (Artisting Grant Chat)

The Legal GraphRAG system will integrate with the existing Artisting grant chat platform:

**Shared Components**:
- ✅ **Authentication** - Django users app (JWT tokens)
- ✅ **Billing** - Stripe subscription system (credit deduction)
- ✅ **Database** - Digital Ocean PostgreSQL (main DB)
- ✅ **Infrastructure** - Celery workers, Redis, deployment pipeline

**Separate Components**:
- ⚡ **Frontend** - New Next.js app (initially separate domain: legal.artisting.es)
- ⚡ **Backend App** - New Django app: `apps/legal_graphrag`
- ⚡ **Data** - New tables: legal_corpus_sources, legal_documents, legal_document_chunks
- ⚡ **API Endpoints** - New routes: `/api/v1/legal-graphrag/*`

**Integration Points**:
```
User logs in → Existing auth system (shared)
User subscribes → Existing billing system (shared)
User queries legal chat → New legal_graphrag endpoints
System deducts credits → Existing credit system (shared)
```

**Future Merge (Phase 2)**:
- Unified dashboard: `/grants` (existing) + `/legal-chat` (new)
- Single navigation bar
- Cross-reference: "Find grants related to this law"
- Shared chat history across both systems

---

## 9. Key Assumptions & Constraints

### Assumptions

1. **User Assumptions**:
   - ✅ Users speak Spanish (primary interface language)
   - ✅ Users have basic internet literacy
   - ✅ Users understand "this is not legal advice"
   - ✅ Users can evaluate answer relevance to their case

2. **Technical Assumptions**:
   - ✅ BOE website remains accessible (no major structural changes)
   - ✅ Gemini API stays free/affordable for embeddings + chat
   - ✅ Digital Ocean PostgreSQL handles 100-500 queries/day
   - ✅ Existing auth/billing system stable

3. **Legal Assumptions**:
   - ✅ Providing legal information (not advice) is legally permissible
   - ✅ Fair use allows indexing official legal texts
   - ✅ Citing sources with URLs constitutes proper attribution

### Constraints

1. **Technical Constraints**:
   - ⏱️ **Timeline**: MVP in 1 week (limits scope)
   - 💰 **Budget**: Free tier Gemini API (rate limits apply)
   - 🗄️ **Storage**: PostgreSQL on existing plan (no extra DB cost)
   - 👥 **Team**: 1 developer (you) + 1 AI assistant (me)

2. **Data Constraints**:
   - 📚 **Corpus Size**: 70 sources (manual curation, not comprehensive)
   - 🔄 **Update Frequency**: Weekly manual checks (not real-time)
   - 📅 **Historical Data**: No version history (current law only for MVP)
   - 🌍 **Jurisdiction**: Spain + EU only (no international law)

3. **Legal/Compliance Constraints**:
   - ⚖️ **No Legal Advice**: Must include disclaimers
   - 🔒 **GDPR**: Don't store personally identifiable query data without consent
   - 🎯 **Professional Boundaries**: Don't suggest we're replacing lawyers

---

## 10. Dependencies

### External Dependencies

1. **Data Sources**:
   - BOE.es (Spanish Official Bulletin) - Public, free access
   - EUR-Lex (EU law) - Public, free access
   - DGT PETETE database (tax rulings) - Public, free access

2. **APIs & Services**:
   - Gemini API (Google AI) - Embeddings + chat LLM
   - Digital Ocean PostgreSQL - Database hosting
   - Existing Stripe integration - Payment processing

3. **Libraries & Frameworks**:
   - Django 5 + DRF - Backend framework
   - Next.js 15 - Frontend framework
   - pgvector - Vector similarity search
   - Celery + Redis - Async task processing
   - Beautiful Soup / PyPDF2 - Document parsing

### Internal Dependencies

1. **Existing Artisting Systems**:
   - users app (authentication)
   - billing app (subscriptions)
   - Main PostgreSQL database
   - Celery workers

2. **Team Knowledge**:
   - Django patterns (from grants app)
   - Next.js frontend (from grants frontend)
   - PostgreSQL + pgvector (from grants embedding system)

---

## 11. Risks & Mitigations

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| BOE website changes structure | Low | High | Cache raw HTML; parser includes fallback logic |
| Gemini API rate limits | Medium | Medium | Implement request throttling; consider caching embeddings |
| pgvector slow on large corpus | Low | Medium | Start with 70 sources; monitor query times; add indexes |
| Parsing fails for some PDFs | High | Low | Log failures; manual fallback for critical sources |

### Data Quality Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Outdated laws in corpus | Medium | High | Weekly update checks; display "last updated" date |
| Incorrect article extraction | Medium | High | Manual validation of P1 sources; automated tests |
| Missing key laws | Medium | Medium | Curated corpus (Excel) prioritizes most-used laws |
| Citation extraction errors | High | Medium | Fallback to document-level citation if article parsing fails |

### User Experience Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Users treat as legal advice | High | High | Prominent disclaimers; "consult advisor" in every answer |
| Hallucinated answers trusted | Low | Critical | Strict prompt engineering; citation validation; no answer if no source |
| Poor answer quality | Medium | High | Curated test set (20 questions); iterative prompt tuning |
| Slow response times | Low | Medium | Target <5s; monitor performance; optimize vector search |

### Legal/Compliance Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Unauthorized practice of law | Low | Critical | Clear disclaimers; informational only; no personalized advice |
| Copyright issues (indexing laws) | Very Low | Medium | Official laws are public domain; cite all sources |
| GDPR violations | Low | High | Anonymous queries by default; don't store PII without consent |

---

## 12. Next Steps

### Immediate Actions (Before Implementation)

1. ✅ **Enable pgvector** in Digital Ocean PostgreSQL
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

2. ✅ **Verify database access** - Test connection with doadmin credentials

3. ✅ **Review corpus Excel** - Confirm P1 sources are correct and URLs work

4. ✅ **Set up development environment** - Clone repos, install dependencies

### Documentation to Read Next

- **[01_ARCHITECTURE.md](./01_ARCHITECTURE.md)** - Technical stack and component design
- **[08_MVP_SPRINT_PLAN.md](./08_MVP_SPRINT_PLAN.md)** - Day-by-day implementation plan
- **[CLAUDE.md](./CLAUDE.md)** - AI assistant instructions for this project

### First Development Tasks (Day 1)

1. Create Django app: `apps/legal_graphrag`
2. Define database models (CorpusSource, LegalDocument, DocumentChunk)
3. Run migrations
4. Import Excel corpus → legal_corpus_sources table
5. Test ingestion for 1 source (Spanish Constitution)

---

## 13. Contact & Governance

### Project Owner
- **Team**: Artisting Development Team
- **Timeline**: MVP - 1 week (2025-12-11 to 2025-12-18)
- **Budget**: Existing infrastructure (no new costs for MVP)

### Change Management
- **Scope Changes**: Documented in `docs/SCOPE_CHANGES.md` (to be created)
- **Architecture Decisions**: Recorded in `docs/01_ARCHITECTURE.md`
- **Bug Tracking**: GitHub issues (to be set up)

### Documentation Maintenance
- **Owner**: Lead Developer (you)
- **Update Frequency**: After each major milestone
- **Review Process**: Update docs before merging to main branch

---

## 14. Glossary

### Legal Terms

- **BOE** - Boletín Oficial del Estado (Spanish Official Bulletin)
- **DOUE** - Diario Oficial de la Unión Europea (EU Official Journal)
- **DGT** - Dirección General de Tributos (Tax authority, issues binding rulings)
- **AEAT** - Agencia Estatal de Administración Tributaria (Tax agency)
- **CENDOJ** - Centro de Documentación Judicial (Court case law database)
- **ELI** - European Legislation Identifier (law URI scheme)
- **ECLI** - European Case Law Identifier (case URI scheme)

### Technical Terms

- **RAG** - Retrieval-Augmented Generation (LLM + search)
- **pgvector** - PostgreSQL extension for vector similarity search
- **Embedding** - Vector representation of text (768-dimensional for Gemini)
- **Hybrid Search** - Combination of semantic (vector) + lexical (BM25) search
- **Chunk** - Document segment (e.g., article, section)

### System-Specific Terms

- **Corpus Sources** - The 70 laws/docs defined in Excel (catalog)
- **P1/P2/P3** - Priority levels (P1 = core, P2 = important, P3 = edge cases)
- **Naturaleza** - Source type (Normativa, Doctrina, Jurisprudencia)
- **Nivel de autoridad** - Legal authority level (Constitución > Ley > RD > Orden)

---

**Document End** | Next: [01_ARCHITECTURE.md](./01_ARCHITECTURE.md)
