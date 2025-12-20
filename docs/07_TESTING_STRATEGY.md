# Legal GraphRAG System - Testing Strategy

## Document Information
- **Version**: 1.0 (MVP)
- **Last Updated**: 2025-12-11
- **Status**: Planning Phase
- **Related**: [08_MVP_SPRINT_PLAN.md](./08_MVP_SPRINT_PLAN.md) | [04_RETRIEVAL_GUIDE.md](./04_RETRIEVAL_GUIDE.md)

---

## 1. Testing Philosophy

### Core Principles

1. **Answer Quality > Code Coverage**: Legal accuracy matters more than 100% test coverage
2. **Real User Scenarios**: Test with actual artist queries
3. **Source Attribution**: Every claim must be traceable to a source
4. **Hallucination Detection**: Zero tolerance for invented laws/articles
5. **Progressive Testing**: Unit → Integration → System → User Acceptance

### Chat evaluation references
- North Star goal: [NorthStarGoal.md](./Chat%20Evaluation/NorthStarGoal.md)
- Prompt contract: [PROMPT_CONTRACT.md](./Chat%20Evaluation/PROMPT_CONTRACT.md)
- Automated eval rules: [AUTOMATED_EVAL_RULES.md](./Chat%20Evaluation/AUTOMATED_EVAL_RULES.md)
- How to run evals: [RUN_EVAL_RUNBOOK.md](./Chat%20Evaluation/RUN_EVAL_RUNBOOK.md)


---

## 2. Test Pyramid

```
                   ┌──────────────┐
                   │     UAT      │  5 tests
                   │  (End-to-End)│  Manual testing with real users
                   └──────────────┘
                 ┌──────────────────┐
                 │   System Tests   │  15 tests
                 │ (Query scenarios)│  Test full RAG pipeline
                 └──────────────────┘
              ┌──────────────────────────┐
              │   Integration Tests      │  30 tests
              │ (Search + RAG + API)     │  Test component interactions
              └──────────────────────────┘
           ┌──────────────────────────────────┐
           │        Unit Tests                │  50+ tests
           │ (Models, Services, Connectors)   │  Test individual functions
           └──────────────────────────────────┘
```

---

## 3. Unit Tests

### 3.1 Model Tests

```python
# apps/legal_graphrag/tests/test_models.py

import pytest
from apps.legal_graphrag.models import CorpusSource, LegalDocument, DocumentChunk

@pytest.mark.django_db
class TestCorpusSource:
    def test_create_source(self):
        """Test creating a corpus source"""
        source = CorpusSource.objects.create(
            prioridad='P1',
            naturaleza='Normativa',
            area_principal='Fiscal',
            titulo='Test Law',
            id_oficial='TEST-001',
            url_oficial='https://example.com',
            tipo='Ley',
            nivel_autoridad='Ley'
        )

        assert source.estado == 'pending'
        assert str(source) == '[P1] Test Law'

    def test_source_validation(self):
        """Test source validation"""
        with pytest.raises(Exception):
            CorpusSource.objects.create(
                prioridad='INVALID',  # Should fail
                naturaleza='Normativa'
            )

@pytest.mark.django_db
class TestDocumentChunk:
    def test_create_chunk_with_embedding(self):
        """Test creating chunk with vector embedding"""
        source = CorpusSource.objects.create(...)
        doc = LegalDocument.objects.create(source=source, ...)

        embedding = [0.1] * 768  # 768-dim vector

        chunk = DocumentChunk.objects.create(
            document=doc,
            chunk_type='article',
            chunk_label='Artículo 1',
            chunk_text='Test text',
            embedding=embedding,
            metadata={'test': 'value'}
        )

        assert chunk.embedding is not None
        assert len(chunk.embedding) == 768
```

### 3.2 Connector Tests

```python
# apps/legal_graphrag/tests/test_connectors.py

import pytest
from apps.legal_graphrag.services.ingestion.boe_connector import BOEConnector

class TestBOEConnector:
    def test_fetch_constitution(self):
        """Test fetching Spanish Constitution"""
        connector = BOEConnector()
        url = 'https://www.boe.es/eli/es/c/1978/12/27/(1)/con'

        result = connector.fetch(url)

        assert result['html'] is not None
        assert result['metadata']['titulo'] is not None
        assert len(result['structure']) > 0

    def test_parse_article(self):
        """Test parsing article from HTML"""
        connector = BOEConnector()
        # Mock HTML for article
        html = """
        <div class="articulo">
            <div class="numero-articulo">Artículo 30</div>
            <p>Son gastos deducibles...</p>
        </div>
        """

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        article = soup.select_one('.articulo')

        result = connector._parse_article(article, 1)

        assert result['type'] == 'article'
        assert 'Artículo 30' in result['label']
        assert 'gastos deducibles' in result['text']
```

### 3.3 Embedding Service Tests

```python
# apps/legal_graphrag/tests/test_embedding_service.py

import pytest
from apps.legal_graphrag.services.embedding_service import EmbeddingService

class TestEmbeddingService:
    def test_embed_single_text(self):
        """Test generating embedding for text"""
        service = EmbeddingService()
        text = "Son gastos deducibles aquellos que..."

        embedding = service.embed(text)

        assert len(embedding) == 768
        assert all(isinstance(x, float) for x in embedding)

    def test_embed_truncates_long_text(self):
        """Test that long text is truncated"""
        service = EmbeddingService()
        text = "x" * 10000  # Very long text

        embedding = service.embed(text)

        # Should still work (truncated)
        assert len(embedding) == 768
```

---

## 4. Integration Tests

### 4.1 Search Engine Tests

```python
# apps/legal_graphrag/tests/test_search_engine.py

import pytest
from apps.legal_graphrag.services.legal_search_engine import LegalSearchEngine

@pytest.mark.django_db
class TestLegalSearchEngine:
    @pytest.fixture
    def search_engine(self):
        return LegalSearchEngine()

    @pytest.fixture
    def sample_chunks(self, db):
        """Create sample document chunks for testing"""
        from apps.legal_graphrag.models import CorpusSource, LegalDocument, DocumentChunk

        # Create source
        source = CorpusSource.objects.create(
            prioridad='P1',
            naturaleza='Normativa',
            area_principal='Fiscal',
            titulo='Ley IRPF',
            id_oficial='BOE-A-2006-20764',
            url_oficial='https://www.boe.es/...'
        )

        # Create document
        doc = LegalDocument.objects.create(
            source=source,
            doc_title='Ley IRPF',
            doc_id_oficial='BOE-A-2006-20764',
            url='https://www.boe.es/...'
        )

        # Create chunks
        chunks = []
        for i in range(5):
            chunk = DocumentChunk.objects.create(
                document=doc,
                chunk_type='article',
                chunk_label=f'Artículo {i+1}',
                chunk_text=f'Texto del artículo {i+1} sobre gastos deducibles',
                embedding=[0.1] * 768,
                metadata={
                    'naturaleza': 'Normativa',
                    'prioridad': 'P1',
                    'area_principal': 'Fiscal'
                }
            )
            chunks.append(chunk)

        return chunks

    def test_hybrid_search(self, search_engine, sample_chunks):
        """Test hybrid search (vector + lexical)"""
        query = "gastos deducibles"
        filters = {'naturaleza': 'Normativa'}

        results = search_engine.hybrid_search(query, filters, limit=5)

        assert len(results) > 0
        assert all('similarity' in r or 'rrf_score' in r for r in results)

    def test_search_by_hierarchy(self, search_engine, sample_chunks):
        """Test hierarchical search (Normativa > Doctrina > Juris)"""
        query = "gastos deducibles"

        results = search_engine.search_by_hierarchy(query, 'Fiscal')

        assert 'normativa' in results
        assert 'doctrina' in results
        assert 'jurisprudencia' in results
        assert len(results['normativa']) > 0
```

### 4.2 RAG Engine Tests

```python
# apps/legal_graphrag/tests/test_rag_engine.py

import pytest
from apps.legal_graphrag.services.legal_rag_engine import LegalRAGEngine

@pytest.mark.django_db
class TestLegalRAGEngine:
    @pytest.fixture
    def rag_engine(self):
        return LegalRAGEngine()

    def test_answer_query_structure(self, rag_engine, sample_chunks):
        """Test that answer has correct structure"""
        query = "¿Puedo deducir gastos de home studio?"

        result = rag_engine.answer_query(query)

        # Check structure
        assert 'answer' in result
        assert 'sources' in result
        assert 'metadata' in result

        # Check metadata
        assert 'area_principal' in result['metadata']
        assert 'model' in result['metadata']
        assert 'normativa_count' in result['metadata']

    def test_answer_includes_disclaimer(self, rag_engine, sample_chunks):
        """Test that answer includes legal disclaimer"""
        query = "¿Cómo tributan los royalties?"

        result = rag_engine.answer_query(query)

        answer_lower = result['answer'].lower()
        assert any(word in answer_lower for word in ['advertencia', 'consulta', 'asesor'])
```

---

## 5. System Tests (Query Scenarios)

### 5.1 Artist Query Test Suite

```python
# apps/legal_graphrag/tests/test_artist_queries.py

import pytest
from apps.legal_graphrag.services.legal_rag_engine import LegalRAGEngine

@pytest.mark.django_db
@pytest.mark.slow
class TestArtistQueryScenarios:
    """
    Test real-world queries from artist personas
    These are our acceptance criteria for MVP
    """

    @pytest.fixture
    def rag_engine(self):
        return LegalRAGEngine()

    # FISCAL QUERIES

    def test_home_studio_deduction(self, rag_engine):
        """Elena asks: Can I deduct home studio expenses?"""
        query = "¿Puedo deducir gastos de mi estudio en casa como artista autónoma?"

        result = rag_engine.answer_query(query)

        # Area classification
        assert result['metadata']['area_principal'] == 'Fiscal'

        # Source quality
        assert len(result['sources']) > 0

        # Check for IRPF law
        source_titles = [s['doc_title'] for s in result['sources']]
        assert any('IRPF' in title or 'Impuesto sobre la Renta' in title for title in source_titles)

        # Answer quality
        answer_lower = result['answer'].lower()
        assert any(word in answer_lower for word in ['deducir', 'gastos', 'deducibles'])

    def test_vat_rate_for_art_sales(self, rag_engine):
        """Elena asks: What VAT rate for selling art?"""
        query = "¿Qué IVA aplico si vendo un cuadro a una empresa?"

        result = rag_engine.answer_query(query)

        assert result['metadata']['area_principal'] == 'Fiscal'
        assert len(result['sources']) > 0

    def test_mecenazgo_tax_benefits(self, rag_engine):
        """Elena asks: What are mecenazgo tax benefits?"""
        query = "¿Qué beneficios fiscales tiene el mecenazgo para artistas?"

        result = rag_engine.answer_query(query)

        assert len(result['sources']) > 0

    # LABORAL QUERIES

    def test_autonomo_registration(self, rag_engine):
        """Carlos asks: How to register as autónomo?"""
        query = "¿Cómo me doy de alta como autónomo siendo músico?"

        result = rag_engine.answer_query(query)

        assert result['metadata']['area_principal'] == 'Laboral'
        assert len(result['sources']) > 0

    def test_hiring_assistant(self, rag_engine):
        """Elena asks: Can I hire an assistant?"""
        query = "¿Puedo contratar un asistente? ¿Qué tipo de contrato necesito?"

        result = rag_engine.answer_query(query)

        assert result['metadata']['area_principal'] == 'Laboral'

    # PROPIEDAD INTELECTUAL QUERIES

    def test_copyright_registration(self, rag_engine):
        """Elena asks: How to register copyright?"""
        query = "¿Cómo registro mis derechos de autor en España?"

        result = rag_engine.answer_query(query)

        assert result['metadata']['area_principal'] == 'Propiedad Intelectual'
        assert len(result['sources']) > 0

    def test_spotify_royalties(self, rag_engine):
        """Carlos asks: How to declare Spotify royalties?"""
        query = "¿Cómo tributan los royalties de Spotify?"

        result = rag_engine.answer_query(query)

        # Should find fiscal sources (tax treatment)
        assert len(result['sources']) > 0

    # SUBVENCIONES QUERIES

    def test_cultural_grants(self, rag_engine):
        """Ana asks: What grants are available?"""
        query = "¿Qué subvenciones hay para asociaciones culturales?"

        result = rag_engine.answer_query(query)

        assert len(result['sources']) > 0

    # EDGE CASES

    def test_no_information_available(self, rag_engine):
        """Test query with no matching sources"""
        query = "¿Cómo tributan los NFTs de arte cripto-espacial en Marte?"

        result = rag_engine.answer_query(query)

        # Should admit lack of information
        answer_lower = result['answer'].lower()
        assert any(phrase in answer_lower for phrase in [
            'no tengo información',
            'no he encontrado',
            'no dispongo'
        ])

    def test_hallucination_prevention(self, rag_engine):
        """Test that system doesn't invent laws"""
        query = "¿Qué dice el Artículo 999 de la Ley Ficticia sobre artistas?"

        result = rag_engine.answer_query(query)

        # Should not claim to have found "Artículo 999"
        answer_lower = result['answer'].lower()
        assert 'no tengo' in answer_lower or 'no existe' in answer_lower
```

### 5.2 Source Quality Tests

```python
# apps/legal_graphrag/tests/test_source_quality.py

import pytest

@pytest.mark.django_db
class TestSourceQuality:
    """Validate that retrieved sources are accurate"""

    def test_all_sources_have_citations(self, rag_engine):
        """Every source must have BOE/official ID"""
        query = "¿Puedo deducir gastos de formación?"

        result = rag_engine.answer_query(query)

        for source in result['sources']:
            assert source['doc_id_oficial'] is not None
            assert source['url'] is not None

    def test_sources_are_verifiable(self, rag_engine):
        """URLs should be accessible (not broken)"""
        import requests

        query = "¿Qué es el IRPF?"

        result = rag_engine.answer_query(query)

        for source in result['sources'][:3]:  # Check first 3
            response = requests.head(source['url'], timeout=10)
            # Should be 200 or redirect
            assert response.status_code in [200, 301, 302]

    def test_normativa_cited_first(self, rag_engine):
        """Normativa should appear before Doctrina"""
        query = "¿Qué gastos puedo deducir?"

        result = rag_engine.answer_query(query)

        normativa_indices = [
            i for i, s in enumerate(result['sources'])
            if s['category'] == 'normativa'
        ]

        doctrina_indices = [
            i for i, s in enumerate(result['sources'])
            if s['category'] == 'doctrina'
        ]

        if normativa_indices and doctrina_indices:
            assert min(normativa_indices) < min(doctrina_indices)
```

---

## 6. API Tests

```python
# apps/legal_graphrag/tests/test_api.py

import pytest
from rest_framework.test import APIClient

@pytest.mark.django_db
class TestLegalChatAPI:
    @pytest.fixture
    def client(self):
        return APIClient()

    def test_chat_endpoint_success(self, client):
        """Test /chat/ endpoint with valid query"""
        response = client.post('/api/v1/legal-graphrag/chat/', {
            'query': '¿Puedo deducir gastos de home studio?'
        }, format='json')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'answer' in data['data']
        assert 'sources' in data['data']

    def test_chat_endpoint_validation(self, client):
        """Test validation errors"""
        # Query too short
        response = client.post('/api/v1/legal-graphrag/chat/', {
            'query': 'Hola'
        }, format='json')

        assert response.status_code == 400
        data = response.json()
        assert data['success'] is False

    def test_rate_limiting(self, client):
        """Test rate limit enforcement"""
        # Make 101 requests
        for i in range(101):
            response = client.post('/api/v1/legal-graphrag/chat/', {
                'query': f'Test query {i}'
            }, format='json')

            if i < 100:
                assert response.status_code == 200
            else:
                # 101st request should be rate limited
                assert response.status_code == 429

    def test_search_endpoint(self, client):
        """Test /search/ endpoint"""
        response = client.post('/api/v1/legal-graphrag/search/', {
            'query': 'gastos deducibles',
            'filters': {'naturaleza': 'Normativa'},
            'limit': 10
        }, format='json')

        assert response.status_code == 200
        data = response.json()
        assert 'results' in data['data']
```

---

## 7. User Acceptance Testing (UAT)

### 7.1 UAT Test Cases

**Test with 5 real artists (Elena, Carlos, Ana personas)**

| # | Persona | Query | Expected Outcome |
|---|---------|-------|------------------|
| 1 | Elena | "¿Puedo deducir gastos de mi estudio en casa?" | Cites IRPF Artículo 30, clear yes/no answer, explains requirements |
| 2 | Elena | "¿Qué IVA aplico al vender cuadros?" | Cites IVA law, explains 10% vs 21% distinction |
| 3 | Carlos | "¿Cómo tributan los royalties de Spotify?" | Cites IRPF, explains royalty taxation |
| 4 | Ana | "¿Qué subvenciones hay para asociaciones?" | Lists relevant grants (or admits no info), cites sources |
| 5 | All | "¿Existe la Ley Ficticia 999/2050?" | Admits "no information", doesn't invent |

### 7.2 UAT Metrics

**Success Criteria**:
- **Accuracy**: 80%+ answers cite correct legal source
- **Hallucination**: 0% invented laws/articles
- **Usefulness**: 70%+ users rate answer as "helpful"
- **Speed**: <5 seconds average response time

---

## 8. Performance Tests

```python
# apps/legal_graphrag/tests/test_performance.py

import pytest
import time

@pytest.mark.performance
class TestPerformance:
    def test_query_response_time(self, rag_engine):
        """Test that queries respond in <5 seconds"""
        query = "¿Puedo deducir gastos de formación?"

        start = time.time()
        result = rag_engine.answer_query(query)
        duration = time.time() - start

        assert duration < 5.0  # 5 seconds max

    def test_vector_search_speed(self, search_engine):
        """Test vector search is <500ms"""
        query = "gastos deducibles"

        start = time.time()
        results = search_engine.hybrid_search(query, limit=10)
        duration = (time.time() - start) * 1000  # ms

        assert duration < 500  # 500ms max
```

---

## 9. Test Data Management

### 9.1 Fixtures

```python
# apps/legal_graphrag/tests/fixtures.py

import pytest
from apps.legal_graphrag.models import CorpusSource, LegalDocument, DocumentChunk

@pytest.fixture
def p1_fiscal_sources(db):
    """Create P1 fiscal sources for testing"""
    sources = []

    # Ley IRPF
    source = CorpusSource.objects.create(
        prioridad='P1',
        naturaleza='Normativa',
        area_principal='Fiscal',
        titulo='Ley 35/2006 del IRPF',
        id_oficial='BOE-A-2006-20764',
        url_oficial='https://www.boe.es/eli/es/l/2006/11/28/35/con',
        tipo='Ley',
        nivel_autoridad='Ley',
        estado='ingested'
    )
    sources.append(source)

    # Add more sources...

    return sources
```

### 9.2 Test Database

```bash
# Run tests with separate test database
pytest --ds=ovra_backend.settings_test

# Or use in-memory SQLite for fast tests
pytest --ds=ovra_backend.settings_test --reuse-db
```

---

## 10. Running Tests

### 10.1 Run All Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=apps.legal_graphrag --cov-report=html

# Run specific test file
pytest apps/legal_graphrag/tests/test_artist_queries.py

# Run specific test
pytest apps/legal_graphrag/tests/test_artist_queries.py::TestArtistQueryScenarios::test_home_studio_deduction
```

### 10.2 Test Markers

```python
# Mark slow tests (>5s)
@pytest.mark.slow
def test_full_ingestion():
    pass

# Mark performance tests
@pytest.mark.performance
def test_response_time():
    pass

# Run only fast tests
pytest -m "not slow"

# Run only performance tests
pytest -m performance
```

---

## 11. Continuous Testing

### 11.1 Pre-Commit Hooks

```bash
# .git/hooks/pre-commit

#!/bin/bash
pytest apps/legal_graphrag/tests/ -m "not slow"

if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

### 11.2 GitHub Actions CI

```yaml
# .github/workflows/test.yml

name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-django pytest-cov

      - name: Run tests
        run: |
          pytest --cov=apps.legal_graphrag --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

---

**Document End** | Next: [08_MVP_SPRINT_PLAN.md](./08_MVP_SPRINT_PLAN.md)
