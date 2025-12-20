# Legal GraphRAG System - Future Roadmap

## Document Information
- **Version**: 1.0
- **Last Updated**: 2025-12-11
- **Status**: Planning Phase
- **Related**: [00_OVERVIEW.md](./00_OVERVIEW.md) | [08_MVP_SPRINT_PLAN.md](./08_MVP_SPRINT_PLAN.md)

---

## 1. Roadmap Overview

### Vision (12 Months)
Transform from simple Q&A system → Comprehensive legal intelligence platform for Spanish artists

### Phases
1. **MVP** (Week 1): Basic RAG with 37 P1 sources
2. **Phase 2** (Months 2-3): Enhanced retrieval + P2 sources
3. **Phase 3** (Months 4-6): Graph capabilities + versioning
4. **Phase 4** (Months 7-9): Proactive assistance + analytics
5. **Phase 5** (Months 10-12): Advanced features + scale

---

## 2. Phase 2: Enhanced Retrieval (Months 2-3)

### Goals
- Improve answer quality and relevance
- Expand corpus coverage
- Add multi-turn conversation

### Features

#### 2.1 P2 Source Ingestion
**Why**: Cover more edge cases (23 additional sources)

**Tasks**:
- Ingest 23 P2 sources (important but not core)
- Add regional laws (Catalonia, Basque Country)
- Include more DGT rulings

**Timeline**: 2 weeks

#### 2.2 Multi-Turn Conversation
**Why**: Users often ask follow-up questions

**Features**:
- Session persistence (save chat history)
- Context awareness (reference previous questions)
- Clarification prompts ("Did you mean...?")

**Example**:
```
User: ¿Puedo deducir gastos de home studio?
Bot: Sí, según el IRPF Artículo 30...

User: ¿Y qué documentación necesito?
Bot: [Understands "documentación" refers to home studio deductions]
```

**Timeline**: 3 weeks

#### 2.3 Query Expansion
**Why**: Improve recall for ambiguous queries

**Features**:
- Synonym expansion ("gastos" → "costes", "erogaciones")
- Related term injection ("autónomo" → "trabajador por cuenta propia")
- Legal term mapping ("copyright" → "derechos de autor")

**Timeline**: 1 week

#### 2.4 Cross-Encoder Reranking
**Why**: Better relevance ranking

**Current**: RRF fusion (reciprocal rank fusion)
**Future**: Fine-tuned cross-encoder model for Spanish legal text

**Model**: Fine-tune `multilingual-miniLM` on legal Q&A pairs

**Timeline**: 2 weeks

---

## 3. Phase 3: Graph & Versioning (Months 4-6)

### Goals
- Enable citation network traversal
- Track law changes over time
- Discover related laws automatically

### Features

#### 3.1 Citation Graph
**Why**: Laws cite other laws; case law cites laws

**Implementation**:
- Extract citations during ingestion (regex patterns)
- Store in graph structure (Neo4j or PostgreSQL graph)
- Enable graph queries: "Find all laws citing Article X"

**Example**:
```
User: ¿Qué leyes se refieren al IRPF Artículo 30?
Bot: He encontrado 5 leyes que citan este artículo:
  1. Real Decreto 439/2007 (Reglamento IRPF)
  2. Ley 35/2006, Artículo 31 (gastos no deducibles)
  ...
```

**Timeline**: 4 weeks

#### 3.2 Temporal Versioning
**Why**: Laws change; users ask "What was the law in 2020?"

**Features**:
- Store document versions (track BOE amendments)
- Date-aware search ("Show me the 2020 version of IRPF")
- Display law change timeline

**Example**:
```
User: ¿Cuál era el tipo de IVA cultural en 2020?
Bot: En 2020, el tipo de IVA cultural era 10%.
     [Nota: Cambió a 21% en 2023 según RD 123/2023]
```

**Timeline**: 3 weeks

#### 3.3 Auto-Discovery of Related Laws
**Why**: Users don't know what they don't know

**Features**:
- "Users also asked" suggestions
- "Related laws" sidebar
- Automatic topic clustering

**Timeline**: 2 weeks

---

## 4. Phase 4: Proactive Assistance (Months 7-9)

### Goals
- Monitor law changes
- Alert users to relevant updates
- Personalized recommendations

### Features

#### 4.1 Law Change Monitoring
**Why**: BOE publishes new laws daily

**Implementation**:
- Daily BOE scraper
- Detect amendments to tracked sources
- Classify relevance (Fiscal, Laboral, IP)

**User Experience**:
```
Email: "Nueva ley que te afecta"
Contenido:
- Real Decreto 123/2025 modifica el IRPF Artículo 30
- Ahora puedes deducir hasta 50% de gastos de home studio
- Entra en vigor: 2025-01-01
```

**Timeline**: 4 weeks

#### 4.2 Personalized Alerts
**Why**: Users care about specific topics

**Features**:
- User subscribes to topics ("IVA", "derechos de autor")
- Alert when relevant law changes
- Digest: weekly summary of updates

**Timeline**: 3 weeks

#### 4.3 Query Analytics Dashboard
**Why**: Understand user needs, improve system

**Metrics**:
- Top queries
- Queries with low confidence
- Queries with no results
- User feedback trends

**Use Case**: Identify missing sources, improve prompts

**Timeline**: 2 weeks

---

## 5. Phase 5: Advanced Features (Months 10-12)

### Goals
- Multi-lingual support
- Document comparison
- Integration with grants system

### Features

#### 5.1 Catalan & English Support
**Why**: Catalonia has bilingual legal corpus; EU law in English

**Implementation**:
- Multi-lingual embeddings (mT5, multilingual-E5)
- Language detection
- Cross-lingual search (query in Catalan, find Spanish law)

**Timeline**: 6 weeks

#### 5.2 Document Comparison
**Why**: "How does this law differ from that law?"

**Example**:
```
User: Compara el régimen fiscal de artistas en España vs Francia
Bot: [Table comparing IRPF vs French income tax for artists]
```

**Timeline**: 3 weeks

#### 5.3 Integration with Grants System
**Why**: Shared user base, complementary features

**Features**:
- Unified dashboard (grants + legal chat)
- Cross-reference: "Find grants related to this law"
- Legal requirements for grant eligibility

**Example**:
```
User views grant: "Ayuda a la creación artística"
Bot suggests: "Requisitos fiscales para esta ayuda: [Legal FAQ]"
```

**Timeline**: 4 weeks

#### 5.4 Contract Analysis (AI-Powered)
**Why**: Artists sign contracts (galleries, publishers, labels)

**Features**:
- Upload contract PDF
- AI extracts key clauses
- Compares to legal standards
- Flags unfavorable terms

**Example**:
```
User uploads gallery contract
Bot: "Esta cláusula de exclusividad podría violar el Artículo X..."
```

**Timeline**: 6 weeks (complex NLP)

---

## 6. Technical Debt & Refactoring

### 6.1 Replace Intent Classifier
**Current**: Keyword-based
**Future**: Fine-tuned BERT classifier

**Timeline**: 1 week

### 6.2 Optimize Vector Search
**Current**: IVFFlat index
**Future**: HNSW index (better for >10k documents)

**Timeline**: 1 week

### 6.3 Add Caching Layer
**Current**: No caching
**Future**: Redis cache for frequent queries

**Timeline**: 1 week

### 6.4 Migrate to FastAPI
**Current**: Django REST Framework
**Future**: FastAPI (faster, async, better for LLM streaming)

**Timeline**: 3 weeks (if needed)

---

## 7. Infrastructure Scaling

### 7.1 Database Scaling
**When**: >100 queries/second

**Actions**:
- Read replicas for search
- Connection pooling (PgBouncer)
- Vertical scaling (larger instance)

### 7.2 API Scaling
**When**: >1000 concurrent users

**Actions**:
- Horizontal scaling (3+ app instances)
- Load balancer (Digital Ocean Load Balancer)
- CDN for static assets

### 7.3 Cost Optimization
**When**: Gemini API costs >€100/month

**Actions**:
- Switch to self-hosted LLM (Llama 3, Mixtral)
- Batch embed requests
- Reduce embedding dimensions (768 → 384)

---

## 8. Research & Innovation

### 8.1 Legal LLM Fine-Tuning
**Why**: Better understanding of Spanish legal language

**Approach**:
- Collect legal Q&A pairs (1000+)
- Fine-tune Gemini/Llama on legal corpus
- Evaluate on test set

**Timeline**: 2 months

### 8.2 Table & Image Extraction
**Why**: Some laws have tables (tax rates) and diagrams

**Tools**:
- Camelot/Tabula for table extraction
- Tesseract OCR for scanned PDFs
- Vision API for diagrams

**Timeline**: 1 month

### 8.3 Precedent Analysis (Jurisprudencia)
**Why**: Case law is critical for ambiguous situations

**Challenges**:
- Complex to ingest (CENDOJ database)
- Requires legal expertise to interpret

**Timeline**: 3 months (post-Phase 5)

---

## 9. Business Model Evolution

### 9.1 Pricing Tiers (Post-MVP)

**Free**:
- 10 queries/day
- Access to P1 sources only
- No history

**Basic** (€9.99/month):
- 100 queries/day
- Access to P1+P2 sources
- Chat history (30 days)

**Plus** (€24.99/month):
- 500 queries/day
- Access to all sources (P1+P2+P3)
- Chat history (unlimited)
- Priority support

**Enterprise** (€99/month):
- Unlimited queries
- Custom sources (firm-specific docs)
- API access
- Dedicated support

### 9.2 Revenue Projections

**Month 6**:
- 100 free users
- 20 basic users (€200/month)
- 5 plus users (€125/month)
- Total: €325/month

**Month 12**:
- 500 free users
- 100 basic users (€1000/month)
- 30 plus users (€750/month)
- 2 enterprise (€200/month)
- Total: €1950/month

---

## 10. Community & Ecosystem

### 10.1 Open Source Components
**Why**: Build trust, attract contributors

**What to Open Source**:
- Spanish legal text parsers (BOE, EUR-Lex)
- Legal corpus dataset (metadata only)
- Evaluation benchmarks

### 10.2 Partnerships
**Potential Partners**:
- SGAE (copyright management)
- Asesorías fiscales (tax advisors)
- Art schools (educational use)

### 10.3 User Community
**Features**:
- Forum for artists to ask questions
- Vetted answers from lawyers
- Upvote/downvote system

---

## 11. Success Metrics (12 Months)

### Product Metrics
- **Users**: 500+ registered users
- **Queries**: 10,000+ queries/month
- **Accuracy**: 90%+ citation accuracy
- **NPS**: 40+ Net Promoter Score

### Technical Metrics
- **Uptime**: 99.5%+
- **Response Time**: <3s average
- **Corpus Size**: 150+ sources (P1+P2+P3)

### Business Metrics
- **Revenue**: €2000/month
- **Churn**: <10%/month
- **CAC**: <€20 per user

---

**Document End** | Next: [CLAUDE.md](./CLAUDE.md)
