# Instructions for AI Assistants (Claude Code)

## Document Information
- **Purpose**: Guide for AI assistants working on this project
- **Audience**: Claude Code (and other AI coding assistants)
- **Last Updated**: 2025-12-11

---

## 1. Project Context

You are working on the **Artisting Legal GraphRAG** system, a specialized Retrieval-Augmented Generation (RAG) application that helps Spanish artists navigate legal questions about taxes, labor, intellectual property, and grants.

### What Makes This Project Unique

1. **Legal Domain**: Requires extreme accuracy; zero tolerance for hallucinations
2. **Spanish Language**: Most sources and queries in Spanish
3. **Hierarchical Retrieval**: Must respect legal authority (Constitution > Law > Decree)
4. **Artist-Specific**: Tailored for cultural professionals, not general legal queries
5. **Source Attribution**: Every claim must be traceable to official sources (BOE, EUR-Lex)

---

## 🚨 CRITICAL RULES (Follow Strictly)

### Rule #0: QUESTIONS vs CHANGES - Know the Difference!

**When user asks a QUESTION** (how does X work? what is Y? why does Z happen?):
- ✅ Read files to understand
- ✅ Answer the question with explanation
- ❌ DO NOT modify ANY files
- ❌ DO NOT use Edit/Write/NotebookEdit tools

**When user requests a CHANGE** (fix X, update Y, implement Z):
1. ✅ Explain what you will do
2. ✅ List files you will modify
3. ✅ Wait for approval ("yes", "do it", "go ahead")
4. ✅ THEN make the changes
5. ❌ DO NOT touch code without approval

**Examples**:

❌ **WRONG** - User asks question, you modify files:
```
User: "how does the timeout work?"
You: *reads api.ts, then edits it to increase timeout*
Result: UNAUTHORIZED CHANGE
```

✅ **CORRECT** - User asks question, you only answer:
```
User: "how does the timeout work?"
You: *reads api.ts* "The timeout is set to 30000ms in api.ts:23. This means..."
Result: QUESTION ANSWERED, NO FILES MODIFIED
```

✅ **CORRECT** - User requests change, you ask first:
```
User: "fix the timeout issue"
You: "I'll increase the timeout from 30s to 120s in api.ts. Should I do it?"
User: "yes"
You: *makes the change*
Result: GOT PERMISSION, THEN MODIFIED
```

### Rule #1: ALWAYS ASK BEFORE MAKING CHANGES
**NEVER start modifications without explicit user approval**

When the user asks **how to do something**:
1. ✅ Propose the approach and explain what you would do
2. ✅ List the files you would modify
3. ✅ Wait for user confirmation ("yes", "go ahead", "approved")
4. ❌ DO NOT start coding immediately

**Example**:
- User asks: "How can we integrate the design system?"
- You respond: "I would copy the shadcn/ui config and update these 5 files: [list]. Should I proceed?"
- User says: "Yes"
- Then you start making changes

### Rule #2: TWO SEPARATE PROJECTS - NO CROSS-CONTAMINATION
**This Legal GraphRAG project is COMPLETELY SEPARATE from the parent Artisting project**

- Parent project location: `D:\IT workspace\infosubvenciones-api\ARTISTING-main\`
- **Legal GraphRAG location**: `D:\IT workspace\Legal GraphRAG\`

**NEVER**:
- ❌ Modify files in the parent project
- ❌ Import/reference parent project files directly
- ❌ Assume shared infrastructure in production
- ❌ Create dependencies between projects

**IF you need something from parent (login, payment, design)**:
1. Ask user first: "Should I copy [component] from parent project?"
2. Wait for approval
3. Copy and adapt to this project's folder structure
4. Keep as separate implementation

**Deployment**:
- These will deploy **separately** (different domains)
- Integration happens **later** (post-MVP)
- Current sprint: Build as standalone app

### Rule #3: Document Changes, Don't Make Them
1) Don't invent requirements. If unknown, write an **Assumptions** section.
2) Work in **small vertical slices** (UI → API → DB → tests).
3) Every change must include a **verification command** (tests/build/lint/run).
4) Prefer boring solutions. Only add deps with a short justification.
5) Update docs when decisions change (docs/ARCHITECTURE.md, docs/RUNBOOK.md).

## Commands (must stay accurate)

### Backend (run from `backend/`)
- Install dependencies: `pip install -r requirements.txt`
- Run dev server: `python manage.py runserver`
- Apply migrations: `python manage.py migrate`
- Import corpus catalog: `python manage.py import_corpus_from_excel <excel-file>`
- Queue ingestion tasks: `celery -A ovra_backend worker -l info`
- Tests: `pytest`

### Frontend (run from `frontend-legal/`)
- Install dependencies: `npm install`
- Development server: `npm run dev`
- Lint: `npm run lint`
- Build: `npm run build`
- Type check: `npx tsc --noEmit`

## Engineering standards
- TypeScript strict.
- Validate all external input at boundaries (API). Use shared schemas in packages/shared.
- No secrets in repo. Use .env + commit .env.example.
- Add minimal tests for each shipped feature (at least one happy-path + one edge case).
## 2. Core Principles

### DO

✅ **Prioritize accuracy over speed**
- Legal misinformation can have serious consequences
- Always cite sources correctly
- Admit when information is uncertain

✅ **Respect legal hierarchy**
- Constitution > Ley > Real Decreto > Orden > Doctrina > Jurisprudencia
- Never contradict higher authority with lower authority

✅ **Be artist-focused**
- Use plain language, not legalese
- Provide examples relevant to artists (home studios, royalties, gallery sales)
- Consider artist edge cases (intermittent income, international work)

✅ **Follow existing patterns**
- This project integrates with an existing grants system
- Reuse auth, billing, database patterns from grants app
- Match existing code style and conventions

✅ **Document everything**
- Code comments for complex logic
- Update docs when architecture changes
- Log important events (ingestion, search, errors)

### DON'T

❌ **Never invent legal information**
- Don't make up article numbers, laws, or cases
- If unsure, say "I don't have information on this"

❌ **Don't ignore hierarchy**
- A DGT ruling cannot override a law
- Always check nivel_autoridad in metadata

❌ **Don't break existing functionality**
- This is a new app in an existing Django project
- Don't modify shared tables without understanding impact
- Test auth/billing integration carefully

❌ **Don't skip validation**
- Validate all user inputs (query length, filters)
- Validate all ingested data (BOE IDs, URLs)
- Validate LLM outputs (no hallucinations)

❌ **Don't hardcode secrets**
- Use environment variables for API keys
- Never commit `.env` to Git
- Use Django settings for configuration



---

## 3. Development Workflow

### When Starting a New Task

1. **Read relevant documentation first**
   - Start with `00_OVERVIEW.md` for context
   - Check `01_ARCHITECTURE.md` for system design
   - Review `02_DATA_MODEL.md` for database schema

2. **Understand the "why"**
   - Why is this feature needed?
   - How does it fit into the larger system?
   - What are the acceptance criteria?

3. **Check existing code**
   - Does a similar feature exist in the grants app?
   - Can you reuse existing services/utilities?
   - Are there tests you can reference?

### When Writing Code

1. **Follow Django best practices**
   - Fat models, thin views
   - Business logic in service classes
   - Use Django ORM (avoid raw SQL unless necessary)

2. **Write tests first (TDD)**
   - Write test for expected behavior
   - Implement feature
   - Verify test passes

3. **Add docstrings**
   ```python
   def hybrid_search(query: str, filters: Dict) -> List[Dict]:
       """
       Perform hybrid search combining vector and lexical search

       Args:
           query: User query text
           filters: {naturaleza, prioridad, area_principal}

       Returns:
           List of ranked document chunks with scores
       """
   ```

4. **Use type hints**
   ```python
   from typing import List, Dict, Optional

   def search(query: str, limit: Optional[int] = 10) -> List[Dict]:
       pass
   ```

### When Debugging

1. **Check logs first**
   - `logs/legal_graphrag.log` for app logs
   - `logs/ingestion.log` for ingestion logs
   - Celery worker logs for background tasks

2. **Use Django shell**
   ```python
   python manage.py shell

   from apps.legal_graphrag.models import CorpusSource
   print(CorpusSource.objects.filter(estado='failed'))
   ```

3. **Test in isolation**
   - Test connectors independently (BOE, DOUE)
   - Test search without RAG
   - Test prompts without API call (mock LLM)

---

## 4. Specific Guidance by Component

### 4.1 Ingestion Pipeline

**Key Files**:
- `apps/legal_graphrag/services/ingestion/boe_connector.py`
- `apps/legal_graphrag/services/ingestion/normalizer.py`
- `apps/legal_graphrag/tasks.py`

**Common Issues**:
- **HTML structure changes**: BOE occasionally updates their website; parsers may break
  - Solution: Use multiple selectors (fallbacks)
  - Example: `.numero-articulo, .titulo-articulo, h3`

- **Encoding errors**: Spanish text has special characters (á, é, í, ó, ú, ñ, ¿, ¡)
  - Solution: Always use UTF-8 encoding
  - Example: `response.encoding = 'utf-8'`

- **Rate limiting**: BOE may rate limit requests
  - Solution: Add delays between requests
  - Example: `time.sleep(1)`

### 4.2 Search & Retrieval

**Key Files**:
- `apps/legal_graphrag/services/legal_search_engine.py`
- `apps/legal_graphrag/services/legal_rag_engine.py`

**Common Issues**:
- **Poor search results**: Vector search alone may miss exact matches
  - Solution: Use hybrid search (vector + lexical)
  - Check: Are embeddings generated correctly?

- **Slow queries**: Vector search can be slow on large corpora
  - Solution: Use IVFFlat index (MVP) or HNSW (production)
  - Check: Is index created? `\d legal_document_chunks` in psql

- **Wrong sources ranked first**: Legal authority not considered
  - Solution: Apply authority boost in reranking
  - Check: Is `nivel_autoridad` in metadata?

### 4.3 Prompt Engineering

**Key Files**:
- `apps/legal_graphrag/services/legal_rag_engine.py` (method: `_build_prompt`)

**Prompt Structure**:
```
1. System role & rules (hierarchy, hallucination prevention)
2. Normativa context (highest priority sources)
3. Doctrina context (administrative guidance)
4. Jurisprudencia context (case law, if any)
5. User query
6. Output format instructions
```

**Common Issues**:
- **LLM invents laws**: Not enough emphasis on "don't invent"
  - Solution: Add explicit prohibition in prompt
  - Example: "NUNCA inventes leyes, artículos o casos que no estén en el contexto"

- **LLM ignores hierarchy**: Cites doctrina before normativa
  - Solution: Format sources with clear labels ([Fuente N1], [Fuente D1])
  - Instruction: "Si hay NORMATIVA aplicable, cítala PRIMERO"

- **LLM uses legalese**: Too technical for artists
  - Solution: Add instruction: "Usa lenguaje claro y ejemplos relevantes para artistas"

### 4.4 Testing

**Key Files**:
- `apps/legal_graphrag/tests/test_artist_queries.py`
- `apps/legal_graphrag/tests/test_retrieval.py`

**Test Philosophy**:
- **Quality > Coverage**: Better to have 10 high-quality tests than 100 superficial ones
- **Real queries**: Test with actual artist questions, not synthetic data
- **Hallucination detection**: Always check for invented sources

**Must-Have Tests**:
1. Home studio deduction (fiscal)
2. Autónomo registration (laboral)
3. Copyright registration (IP)
4. Query with no information (edge case)

---

## 5. Common Tasks & How-To

### Task: Add a New Legal Source

1. Add to Excel file `corpus_normativo_artisting_enriched.xlsx`
2. Import: `python manage.py import_corpus_from_excel ...`
3. Ingest: `python manage.py ingest_source <id_oficial>`
4. Verify: Check `legal_documents` and `legal_document_chunks` tables

### Task: Improve Search Relevance

1. Test current query: `python manage.py shell`
2. Analyze results: Are correct sources retrieved?
3. Adjust:
   - If missing: Check filters, expand query
   - If irrelevant: Improve reranking, check embeddings
4. Retest with test suite

### Task: Fix Hallucination

1. Identify problematic query
2. Check retrieved sources: Do they contain the info?
3. Review prompt: Is instruction clear?
4. Test LLM directly (Gemini console)
5. Adjust prompt, retest

### Task: Add New API Endpoint

1. Define in `apps/legal_graphrag/urls.py`
2. Create view in `apps/legal_graphrag/views.py`
3. Create serializer in `apps/legal_graphrag/serializers.py`
4. Write API test in `apps/legal_graphrag/tests/test_api.py`
5. Document in `05_API_SPECIFICATION.md`

---

## 6. Code Style & Conventions

### Naming Conventions

**Models**:
- `CorpusSource`, `LegalDocument`, `DocumentChunk`
- Singular, PascalCase

**Services**:
- `LegalSearchEngine`, `EmbeddingService`
- PascalCase, descriptive

**Functions**:
- `hybrid_search`, `answer_query`, `ingest_legal_source`
- snake_case, verb-based

**Variables**:
- `query_embedding`, `normativa_results`
- snake_case, descriptive

### Django Patterns

**Model Methods**:
```python
class CorpusSource(models.Model):
    def is_p1(self) -> bool:
        """Check if source is P1 priority"""
        return self.prioridad == 'P1'

    def can_ingest(self) -> bool:
        """Check if source is ready for ingestion"""
        return self.estado == 'pending' and self.url_oficial
```

**Service Classes**:
```python
class LegalSearchEngine:
    """
    Search engine for legal documents

    Combines vector search (pgvector) and lexical search (PostgreSQL FTS)
    """

    def __init__(self):
        self.embedding_service = EmbeddingService()

    def search(self, query: str) -> List[Dict]:
        # Implementation
```

**Views**:
```python
class LegalChatView(APIView):
    """POST /chat/ - Main Q&A endpoint"""
    permission_classes = [AllowAny]

    def post(self, request):
        # Validate
        # Process
        # Return response
```

---

## 7. Debugging Checklist

### Search Not Returning Results

- [ ] Are sources ingested? Check `legal_corpus_sources.estado`
- [ ] Are embeddings generated? Check `legal_document_chunks.embedding IS NOT NULL`
- [ ] Is pgvector index created? `\di` in psql
- [ ] Is query embedding valid? Print `query_embedding[:5]`
- [ ] Are filters too restrictive? Try without filters

### LLM Generating Poor Answers

- [ ] Are relevant sources retrieved? Check `sources` list
- [ ] Is prompt well-structured? Print full prompt
- [ ] Is context too long? Check token count (<8000)
- [ ] Is hierarchy clear? Check source labels ([N1], [D1])

### Ingestion Failing

- [ ] Is URL accessible? Test in browser
- [ ] Is connector correct? (BOE vs DOUE vs DGT)
- [ ] Are selectors valid? Inspect HTML
- [ ] Is Celery worker running? `celery -A ovra_backend status`
- [ ] Check logs: `tail -f logs/ingestion.log`

---

## 8. Integration with Existing System

### Shared Components

This project shares infrastructure with the existing **Artisting Grants** system:

**Database**: Same PostgreSQL instance
- Use `legal_` prefix for all tables
- Don't modify existing tables without consulting

**Authentication**: JWT-based (djangorestframework-simplejwt)
- Use `request.user` for authenticated users
- Check `request.user.is_authenticated`

**Billing**: Stripe integration
- Future: Deduct credits for queries
- Use existing `billing` app models

**Celery**: Shared workers
- Queue name: Use default or `legal_graphrag`
- Don't block other tasks (use reasonable timeouts)

### Testing with Existing System

1. **Local**: Run both grant and legal apps simultaneously
2. **Staging**: Deploy to separate app, test integration
3. **Production**: Monitor impact on shared resources (DB connections, Celery queue)

---

## 9. Security Considerations

### Input Validation

Always validate user inputs:
```python
# Good
if len(query) < 10 or len(query) > 500:
    raise ValidationError("Query must be 10-500 characters")

# Bad
result = rag_engine.answer_query(query)  # No validation
```

### SQL Injection Prevention

Use Django ORM (parameterized queries):
```python
# Good
DocumentChunk.objects.filter(metadata__naturaleza='Normativa')

# Bad
cursor.execute(f"SELECT * FROM chunks WHERE metadata->>'naturaleza' = '{naturaleza}'")
```

### PII Handling

Don't log personally identifiable information:
```python
# Good
logger.info(f"Query processed: {query[:50]}...")

# Bad
logger.info(f"User {user.email} asked: {query}")
```

---

## 10. When You Get Stuck

### Resources

1. **Documentation**: Start with `docs/00_OVERVIEW.md`
2. **Existing Code**: Check `apps/grants` for similar patterns
3. **Tests**: Look at `apps/legal_graphrag/tests/` for examples
4. **Django Docs**: https://docs.djangoproject.com/
5. **pgvector Docs**: https://github.com/pgvector/pgvector

### Ask for Help

If stuck for >30 minutes:
1. Document what you've tried
2. Identify the specific blocker
3. Ask the user/developer for guidance

---

## 11. Success Criteria

You're doing well if:

✅ Tests pass (especially artist query scenarios)
✅ No hallucinations detected
✅ Code follows Django patterns
✅ Documentation is updated
✅ Logs are informative
✅ Performance is <5s per query

---

**End of Instructions** | Good luck! 🚀
