# Legal GraphRAG - Code Conventions & Standards

## Document Information
- **Purpose**: Coding standards and conventions for this project
- **Audience**: Developers and AI assistants
- **Last Updated**: 2025-12-11

---

## Golden rules (follow strictly)
1) Don’t invent requirements. If unknown, write an **Assumptions** section.
2) Work in **small vertical slices** (UI → API → DB → tests).
3) Every change must include a **verification command** (tests/build/lint/run).
4) Prefer boring solutions. Only add deps with a short justification.
5) Update docs when decisions change (docs/ARCHITECTURE.md, docs/RUNBOOK.md).

## Commands (must stay accurate)
- Install: pnpm install
- Dev: pnpm dev
- Web dev: pnpm --filter web dev
- API dev: pnpm --filter api dev
- Typecheck: pnpm typecheck
- Lint: pnpm lint
- Unit tests: pnpm test
- DB migrate: pnpm db:migrate
- DB seed: pnpm db:seed

## Engineering standards
- TypeScript strict.
- Validate all external input at boundaries (API). Use shared schemas in packages/shared.
- No secrets in repo. Use .env + commit .env.example.
- Add minimal tests for each shipped feature (at least one happy-path + one edge case).
## 1. Code Style

### 1.1 Python (Backend)

**Style Guide**: PEP 8 + Django best practices

**Formatter**: Black (line length: 100)

```python
# .flake8
[flake8]
max-line-length = 100
exclude = migrations, __pycache__, venv
ignore = E203, W503
```

**Linter**: Flake8 + isort

```bash
# Run before committing
black apps/legal_graphrag/
isort apps/legal_graphrag/
flake8 apps/legal_graphrag/
```

### 1.2 TypeScript (Frontend)

**Style Guide**: Airbnb TypeScript

**Formatter**: Prettier

```json
// .prettierrc
{
  "semi": true,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "es5",
  "printWidth": 100
}
```

**Linter**: ESLint

```bash
# Run before committing
npm run lint
npm run format
```

---

## 2. Naming Conventions

### 2.1 Python

**Files**:
- `snake_case.py`
- Examples: `legal_search_engine.py`, `embedding_service.py`

**Classes**:
- `PascalCase`
- Examples: `LegalSearchEngine`, `CorpusSource`, `BOEConnector`

**Functions/Methods**:
- `snake_case`
- Verb-based: `search_by_hierarchy`, `embed_batch`, `parse_article`

**Variables**:
- `snake_case`
- Descriptive: `query_embedding`, `normativa_results`, `chunk_label`

**Constants**:
- `UPPER_SNAKE_CASE`
- Examples: `MAX_QUERY_LENGTH`, `DEFAULT_LIMIT`, `P1_PRIORITY`

**Private Methods**:
- Prefix with `_`
- Example: `_parse_article`, `_extract_metadata`

### 2.2 TypeScript

**Files**:
- `kebab-case.tsx` or `PascalCase.tsx` (components)
- Examples: `legal-chat.service.ts`, `LegalChatInterface.tsx`

**Components**:
- `PascalCase`
- Examples: `LegalChatInterface`, `SourceCard`, `CitationDisplay`

**Functions**:
- `camelCase`
- Examples: `searchLegalDocs`, `formatSources`, `handleSubmit`

**Variables**:
- `camelCase`
- Examples: `queryText`, `chatResponse`, `isLoading`

**Constants**:
- `UPPER_SNAKE_CASE`
- Examples: `API_BASE_URL`, `MAX_SOURCES`

**Interfaces/Types**:
- `PascalCase`
- Examples: `ChatResponse`, `Source`, `QueryFilters`

---

## 3. Directory Structure

### 3.1 Backend

```
backend/
├── apps/
│   └── legal_graphrag/
│       ├── models.py               # Django models
│       ├── views.py                # DRF views
│       ├── serializers.py          # DRF serializers
│       ├── urls.py                 # URL routing
│       ├── admin.py                # Django admin
│       ├── tasks.py                # Celery tasks
│       ├── services/               # Business logic
│       │   ├── legal_search_engine.py
│       │   ├── legal_rag_engine.py
│       │   ├── embedding_service.py
│       │   ├── intent_classifier.py
│       │   └── ingestion/
│       │       ├── boe_connector.py
│       │       ├── doue_connector.py
│       │       ├── dgt_connector.py
│       │       └── normalizer.py
│       ├── management/
│       │   └── commands/
│       │       ├── import_corpus_from_excel.py
│       │       ├── ingest_source.py
│       │       └── ingest_all_p1.py
│       └── tests/
│           ├── test_models.py
│           ├── test_connectors.py
│           ├── test_search_engine.py
│           ├── test_rag_engine.py
│           ├── test_api.py
│           └── test_artist_queries.py
```

### 3.2 Frontend

```
frontend-legal/
├── app/
│   ├── layout.tsx              # Root layout
│   ├── page.tsx                # Home page
│   └── chat/
│       └── page.tsx            # Chat page
├── components/
│   └── legal/
│       ├── LegalChatInterface.tsx
│       ├── CitationCard.tsx
│       ├── SourceCard.tsx
│       └── LegalSearchForm.tsx
├── lib/
│   ├── services/
│   │   └── legal-chat.service.ts
│   └── utils/
│       └── markdown.ts
└── types/
    └── legal.ts
```

---

## 4. Django Patterns

### 4.1 Models

**Always**:
- Use `models.Model` base class
- Add `Meta` class for table name, ordering
- Implement `__str__` method
- Use appropriate field types

**Example**:
```python
class CorpusSource(models.Model):
    """Catalog of legal sources to ingest"""

    # Choices as class attributes
    PRIORIDAD_CHOICES = [
        ('P1', 'P1 - Core'),
        ('P2', 'P2 - Important'),
        ('P3', 'P3 - Edge cases'),
    ]

    # Fields
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, db_index=True)
    titulo = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'legal_corpus_sources'
        ordering = ['prioridad', 'titulo']

    def __str__(self):
        return f"[{self.prioridad}] {self.titulo}"

    def is_p1(self) -> bool:
        """Check if source is P1 priority"""
        return self.prioridad == 'P1'
```

### 4.2 Views (DRF)

**Pattern**: Thin views, fat services

**Example**:
```python
class LegalChatView(APIView):
    """POST /chat/ - Main Q&A endpoint"""
    permission_classes = [AllowAny]

    def post(self, request):
        # 1. Validate input
        serializer = ChatQuerySerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': {'code': 'VALIDATION_ERROR', 'message': str(serializer.errors)}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 2. Delegate to service
        query = serializer.validated_data['query']
        rag_engine = LegalRAGEngine()
        result = rag_engine.answer_query(query)

        # 3. Return response
        return Response({
            'success': True,
            'data': result
        })
```

### 4.3 Services

**Pattern**: Service classes handle business logic

**Example**:
```python
class LegalSearchEngine:
    """
    Implements hybrid search for legal documents

    Combines:
    - Vector search (pgvector cosine similarity)
    - Lexical search (PostgreSQL FTS)
    - Reciprocal Rank Fusion
    """

    def __init__(self):
        self.embedding_service = EmbeddingService()

    def hybrid_search(
        self,
        query: str,
        filters: Optional[Dict] = None,
        limit: int = 5
    ) -> List[Dict]:
        """
        Perform hybrid search

        Args:
            query: User query text
            filters: Optional filters (naturaleza, prioridad, area_principal)
            limit: Max results to return

        Returns:
            List of ranked document chunks
        """
        # Implementation
        pass
```

### 4.4 Serializers

**Pattern**: Define request/response schemas

**Example**:
```python
class ChatQuerySerializer(serializers.Serializer):
    """Serializer for chat query request"""
    query = serializers.CharField(min_length=10, max_length=500)
    session_id = serializers.UUIDField(required=False, allow_null=True)
    filters = serializers.DictField(required=False, allow_null=True)

    def validate_query(self, value):
        """Custom validation for query field"""
        if not value.strip():
            raise serializers.ValidationError("Query cannot be empty")
        return value.strip()
```

### 4.5 Celery Tasks

**Pattern**: Async tasks for long-running operations

**Example**:
```python
@shared_task(bind=True, max_retries=3)
def ingest_legal_source(self, source_id: int):
    """
    Celery task: Ingest a single legal source

    Args:
        source_id: ID of CorpusSource to ingest

    Retries: 3 times with exponential backoff
    """
    try:
        source = CorpusSource.objects.get(id=source_id)
        # ... ingestion logic
        return {'status': 'success', 'chunks_created': 10}
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
```

---

## 5. React/Next.js Patterns

### 5.1 Components

**Pattern**: Functional components with TypeScript

**Example**:
```typescript
'use client';

import { useState } from 'react';
import { LegalChatService, ChatResponse } from '@/lib/services/legal-chat.service';

interface LegalChatInterfaceProps {
  initialQuery?: string;
}

export default function LegalChatInterface({ initialQuery = '' }: LegalChatInterfaceProps) {
  const [query, setQuery] = useState(initialQuery);
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const chatService = new LegalChatService();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const result = await chatService.chat({ query });
      setResponse(result);
    } catch (error) {
      console.error('Chat error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      {/* Component JSX */}
    </div>
  );
}
```

### 5.2 Services (API Clients)

**Pattern**: Class-based API clients

**Example**:
```typescript
// lib/services/legal-chat.service.ts

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ChatQuery {
  query: string;
  session_id?: string;
}

export class LegalChatService {
  async chat(query: ChatQuery): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE}/api/v1/legal-graphrag/chat/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(query),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
  }
}
```

---

## 6. Documentation

### 6.1 Code Comments

**When to Comment**:
- Complex algorithms
- Non-obvious business logic
- Legal domain knowledge
- Workarounds or hacks

**Example**:
```python
# Extract citations from legal text
# Spanish legal citation format: "Ley 35/2006, de 28 de noviembre"
# Pattern: [Ley|RD|Orden] NUMBER/YEAR
citation_pattern = r'(Ley|Real Decreto|Orden)\s+\d+/\d{4}'
citations = re.findall(citation_pattern, text)
```

### 6.2 Docstrings

**Python**: Google-style docstrings

```python
def hybrid_search(query: str, filters: Dict, limit: int = 5) -> List[Dict]:
    """
    Perform hybrid search combining vector and lexical search

    This function implements Reciprocal Rank Fusion (RRF) to merge
    results from semantic (pgvector) and lexical (PostgreSQL FTS) search.

    Args:
        query: User query text
        filters: Search filters
            - naturaleza: Source type (Normativa, Doctrina, Jurisprudencia)
            - prioridad: Priority level (P1, P2, P3)
            - area_principal: Legal area (Fiscal, Laboral, etc.)
        limit: Maximum number of results to return (default: 5)

    Returns:
        List of document chunks sorted by relevance score. Each chunk contains:
            - id: UUID
            - chunk_text: Legal text content
            - similarity: Cosine similarity score (0-1)
            - metadata: Document metadata (tipo, nivel_autoridad, etc.)

    Raises:
        ValueError: If query is empty or filters are invalid

    Example:
        >>> engine = LegalSearchEngine()
        >>> results = engine.hybrid_search("gastos deducibles", {"naturaleza": "Normativa"}, 10)
        >>> print(len(results))
        10
    """
```

**TypeScript**: JSDoc

```typescript
/**
 * Fetch legal chat response from API
 *
 * @param query - Chat query object
 * @returns Promise resolving to chat response
 * @throws Error if API request fails
 *
 * @example
 * const service = new LegalChatService();
 * const response = await service.chat({ query: "¿Puedo deducir gastos?" });
 */
async chat(query: ChatQuery): Promise<ChatResponse> {
  // Implementation
}
```

---

## 7. Testing Conventions

### 7.1 Test Structure

**Pattern**: Arrange-Act-Assert

```python
def test_hybrid_search_returns_relevant_results():
    # Arrange
    search_engine = LegalSearchEngine()
    query = "gastos deducibles"
    filters = {'naturaleza': 'Normativa'}

    # Act
    results = search_engine.hybrid_search(query, filters, limit=5)

    # Assert
    assert len(results) > 0
    assert all('similarity' in r for r in results)
```

### 7.2 Test Naming

**Pattern**: `test_<function>_<scenario>_<expected_outcome>`

**Examples**:
- `test_search_with_valid_query_returns_results`
- `test_search_with_empty_query_raises_error`
- `test_ingest_source_with_invalid_url_fails`

### 7.3 Fixtures

**Pattern**: Use pytest fixtures for reusable test data

```python
@pytest.fixture
def sample_corpus_sources(db):
    """Create sample P1 fiscal sources"""
    sources = []
    for i in range(3):
        source = CorpusSource.objects.create(
            prioridad='P1',
            naturaleza='Normativa',
            titulo=f'Test Law {i}',
            id_oficial=f'TEST-{i}',
            url_oficial=f'https://example.com/{i}'
        )
        sources.append(source)
    return sources

def test_search_finds_p1_sources(sample_corpus_sources):
    # Test uses fixture
    pass
```

---

## 8. Error Handling

### 8.1 Django Views

**Pattern**: Structured error responses

```python
try:
    result = rag_engine.answer_query(query)
    return Response({'success': True, 'data': result})
except ValidationError as e:
    return Response({
        'success': False,
        'error': {'code': 'VALIDATION_ERROR', 'message': str(e)}
    }, status=status.HTTP_400_BAD_REQUEST)
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return Response({
        'success': False,
        'error': {'code': 'INTERNAL_ERROR', 'message': 'An error occurred'}
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

### 8.2 Services

**Pattern**: Raise specific exceptions

```python
class SearchError(Exception):
    """Raised when search fails"""
    pass

def hybrid_search(query: str) -> List[Dict]:
    if not query:
        raise ValueError("Query cannot be empty")

    try:
        results = self._vector_search(query)
    except DatabaseError as e:
        logger.error(f"Database error during search: {e}")
        raise SearchError("Search temporarily unavailable") from e

    return results
```

---

## 9. Logging

### 9.1 Log Levels

**Use**:
- `DEBUG`: Detailed information for debugging
- `INFO`: General informational messages
- `WARNING`: Warning messages (e.g., fallback used)
- `ERROR`: Error messages (e.g., ingestion failed)
- `CRITICAL`: Critical errors (e.g., database unavailable)

### 9.2 Log Format

```python
import logging

logger = logging.getLogger('apps.legal_graphrag.search')

# Good
logger.info(f"Query processed: '{query[:50]}...' (area: {area}, {len(sources)} sources, {time_ms}ms)")

# Bad
logger.info(f"Query: {query}")  # Too short, missing context
```

---

## 10. Git Conventions

### 10.1 Commit Messages

**Format**: `<type>(<scope>): <subject>`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style (formatting)
- `refactor`: Code refactoring
- `test`: Add/update tests
- `chore`: Maintenance

**Examples**:
- `feat(search): implement hybrid search with RRF`
- `fix(ingestion): handle encoding errors in BOE connector`
- `docs(api): update API specification for /chat/ endpoint`

### 10.2 Branch Naming

**Pattern**: `<type>/<short-description>`

**Examples**:
- `feat/multi-turn-conversation`
- `fix/hallucination-prevention`
- `docs/update-architecture`

---

## 11. Security

### 11.1 Never Hardcode Secrets

```python
# Good
API_KEY = os.getenv('GEMINI_API_KEY')

# Bad
API_KEY = 'AIzaSy...'
```

### 11.2 Validate All Inputs

```python
# Good
if len(query) < 10 or len(query) > 500:
    raise ValidationError("Query must be 10-500 characters")

# Bad
result = process_query(query)  # No validation
```

### 11.3 Sanitize User Input

```python
# Good
from django.utils.html import escape
safe_query = escape(query)

# Bad
response_html = f"<p>You asked: {query}</p>"  # XSS vulnerability
```

---

## 12. Performance

### 12.1 Database Queries

**Avoid N+1 queries**:
```python
# Good
chunks = DocumentChunk.objects.select_related('document').filter(...)

# Bad
chunks = DocumentChunk.objects.filter(...)
for chunk in chunks:
    doc = chunk.document  # N+1 query
```

**Use indexes**:
```python
# In models.py
class Meta:
    indexes = [
        models.Index(fields=['prioridad', 'estado']),
    ]
```

### 12.2 Caching

```python
from django.core.cache import cache

def get_search_results(query: str) -> List[Dict]:
    cache_key = f"search:{query}"
    cached = cache.get(cache_key)

    if cached:
        return cached

    results = perform_search(query)
    cache.set(cache_key, results, timeout=3600)  # 1 hour
    return results
```

---

## 13. Current Testing Task (2025-12-13)

### What Was Just Implemented: Intent Classifier

**File**: `backend/apps/legal_graphrag/services/intent_classifier.py`
**Purpose**: Classify legal queries into areas (Fiscal, Laboral, IP, etc.)
**Status**: ✅ Ready for testing

### Quick Test (30 seconds)

```bash
# Navigate to backend
cd "d:\IT workspace\Legal GraphRAG\backend"

# Start Django shell
python manage.py shell
```

```python
from apps.legal_graphrag.services.intent_classifier import IntentClassifier

classifier = IntentClassifier()

# Test 1: Fiscal
print(classifier.classify_area("¿Puedo deducir gastos de IVA?"))
# Expected: "Fiscal"

# Test 2: Laboral
print(classifier.classify_area("¿Cómo me doy de alta como autónomo?"))
# Expected: "Laboral"

# Test 3: IP
print(classifier.classify_area("¿Dónde registro mis derechos de autor?"))
# Expected: "Propiedad Intelectual"
```

### Full Testing Instructions

📄 **Complete testing guide**: [DAY_4_INTENT_CLASSIFIER_TESTING.md](./DAY_4_INTENT_CLASSIFIER_TESTING.md)

### Test Sections
1. ✅ Basic Functionality (Fiscal, Laboral, IP queries)
2. ✅ Edge Cases (empty strings, ambiguous queries)
3. ✅ Keyword Extraction
4. ✅ Utility Methods
5. ✅ Confidence Scoring
6. ✅ Performance (should be <1ms per query)
7. ✅ Real-world Integration Test

### Success Criteria

✅ **PASS** if:
- Fiscal queries → "Fiscal" (>80% accuracy)
- Laboral queries → "Laboral" (>80% accuracy)
- IP queries → "Propiedad Intelectual" (>80% accuracy)
- No crashes on edge cases
- Performance <1ms per query

### Report Results

Create: `docs/DAY_4_INTENT_CLASSIFIER_TEST_RESULTS.md`

Include:
- Date/time of testing
- Pass/fail for each section
- Overall accuracy (should be >80%)
- Performance metrics
- Any bugs found

---

**End of Code Conventions**
