# Day 2 - Ingestion Pipeline Testing Instructions

**For Codex**: This document contains all the testing instructions for the Day 2 ingestion pipeline implementation.

---

## Overview

The ingestion pipeline has been implemented with the following components:

1. **Connectors**: BOEConnector, DOUEConnector, DGTConnector
2. **Normalizer**: LegalDocumentNormalizer
3. **Embedding Service**: EmbeddingService (Gemini API)
4. **Celery Tasks**: `ingest_legal_source`, `ingest_all_p1_sources`
5. **Management Commands**: `ingest_source`, `ingest_all_p1`

Your job is to:
1. Write comprehensive tests for each component
2. Test the full ingestion pipeline with a sample source
3. Document any issues found
4. Verify the deliverable: "Ingestion pipeline can fetch, parse, and store 1 source (test with Constitution)"

---

## Test Plan

### Phase 1: Unit Tests

#### 1.1 Test BOE Connector

**File**: `apps/legal_graphrag/tests/test_boe_connector.py`

Create tests for:
- ✅ Fetching a valid BOE document (use Constitution: `https://www.boe.es/eli/es/c/1978/12/27/(1)/con`)
- ✅ Parsing document structure (articles)
- ✅ Extracting metadata (title, date, BOE ID)
- ✅ Handling HTTP errors (404, timeout)
- ✅ Fallback parsing when structure is not found

**Example test structure**:
```python
import pytest
from apps.legal_graphrag.services.ingestion.boe_connector import BOEConnector

class TestBOEConnector:
    def test_fetch_constitution(self):
        """Test fetching Spanish Constitution"""
        connector = BOEConnector()
        result = connector.fetch('https://www.boe.es/eli/es/c/1978/12/27/(1)/con')

        assert result is not None
        assert 'html' in result
        assert 'content' in result
        assert 'metadata' in result
        assert 'structure' in result
        assert len(result['structure']) > 0  # Should have articles

    def test_extract_metadata(self):
        """Test metadata extraction"""
        # ... implement test

    def test_parse_structure(self):
        """Test article parsing"""
        # ... implement test

    def test_http_error_handling(self):
        """Test error handling for invalid URLs"""
        # ... implement test
```

#### 1.2 Test DOUE Connector

**File**: `apps/legal_graphrag/tests/test_doue_connector.py`

Create tests for:
- ✅ Fetching a valid EUR-Lex document
- ✅ Parsing EU directive structure
- ✅ Extracting CELEX number
- ✅ Handling different document formats

#### 1.3 Test DGT Connector

**File**: `apps/legal_graphrag/tests/test_dgt_connector.py`

Create tests for:
- ✅ Fetching a DGT ruling (if URL available)
- ✅ Parsing consulta/contestacion sections
- ✅ Extracting ruling number from URL

**Note**: If you don't have access to a real DGT URL, use mocks.

#### 1.4 Test Normalizer

**File**: `apps/legal_graphrag/tests/test_normalizer.py`

Create tests for:
- ✅ Normalizing BOE document structure
- ✅ Normalizing DOUE document structure
- ✅ Creating fallback chunk when parsing fails
- ✅ Preserving metadata in chunks

**Example test**:
```python
import pytest
from apps.legal_graphrag.services.ingestion.normalizer import LegalDocumentNormalizer
from apps.legal_graphrag.models import CorpusSource

class TestLegalDocumentNormalizer:
    def test_normalize_boe_document(self):
        """Test normalizing a BOE document"""
        # Create mock source
        source = CorpusSource.objects.get(id_oficial='BOE-A-1978-31229')  # Constitution

        # Create mock raw_doc
        raw_doc = {
            'html': '<html>...</html>',
            'content': 'Full text...',
            'metadata': {'fecha_publicacion': '1978-12-29'},
            'structure': [
                {
                    'type': 'article',
                    'label': 'Artículo 1',
                    'text': 'España se constituye...',
                    'position': 1
                }
            ]
        }

        normalizer = LegalDocumentNormalizer()
        result = normalizer.normalize(raw_doc, source)

        assert result is not None
        assert result['titulo'] == source.titulo
        assert result['id_oficial'] == source.id_oficial
        assert len(result['chunks']) > 0
        assert result['chunks'][0]['type'] == 'article'

    def test_fallback_chunk_creation(self):
        """Test fallback when structure parsing fails"""
        # ... implement test
```

#### 1.5 Test Embedding Service

**File**: `apps/legal_graphrag/tests/test_embedding_service.py`

Create tests for:
- ✅ Generating embeddings for text
- ✅ Handling text truncation (>8000 chars)
- ✅ Batch embedding generation
- ✅ API error handling

**Important**: Use mocks for Gemini API to avoid consuming quota:

```python
import pytest
from unittest.mock import patch, MagicMock
from apps.legal_graphrag.services.embedding_service import EmbeddingService

class TestEmbeddingService:
    @patch('google.generativeai.embed_content')
    def test_embed_text(self, mock_embed):
        """Test embedding generation"""
        # Mock Gemini API response
        mock_embed.return_value = {
            'embedding': [0.1] * 768
        }

        service = EmbeddingService()
        result = service.embed('Test text')

        assert len(result) == 768
        assert all(isinstance(x, float) for x in result)

    @patch('google.generativeai.embed_content')
    def test_text_truncation(self, mock_embed):
        """Test truncation of long texts"""
        mock_embed.return_value = {'embedding': [0.1] * 768}

        service = EmbeddingService()
        long_text = 'A' * 10000  # Longer than 8000 chars
        result = service.embed(long_text)

        # Should still work (truncated)
        assert len(result) == 768
```

---

### Phase 2: Integration Tests

#### 2.1 Test Full Ingestion Pipeline

**File**: `apps/legal_graphrag/tests/test_ingestion_pipeline.py`

Create an end-to-end test that:
1. Takes a CorpusSource (Constitution)
2. Runs the full ingestion pipeline
3. Verifies database records were created

**Important**: This test will consume Gemini API quota, so:
- Run it sparingly
- Consider mocking the embedding service

**Example test**:
```python
import pytest
from django.test import TransactionTestCase
from apps.legal_graphrag.models import CorpusSource, LegalDocument, DocumentChunk
from apps.legal_graphrag.tasks import ingest_legal_source

class TestIngestionPipeline(TransactionTestCase):
    def test_ingest_constitution(self):
        """
        Test full ingestion pipeline with Spanish Constitution

        This test:
        1. Fetches Constitution from BOE
        2. Parses articles
        3. Generates embeddings
        4. Stores in database
        """
        # Get Constitution source
        source = CorpusSource.objects.get(id_oficial='BOE-A-1978-31229')

        # Run ingestion (synchronously, not via Celery)
        result = ingest_legal_source(source.id)

        # Verify result
        assert result['status'] == 'success'
        assert result['chunks_created'] > 0

        # Verify database records
        source.refresh_from_db()
        assert source.estado == 'ingested'
        assert source.last_ingested_at is not None

        # Verify document created
        doc = LegalDocument.objects.get(source=source)
        assert doc is not None
        assert doc.doc_title == source.titulo
        assert doc.raw_html is not None

        # Verify chunks created
        chunks = DocumentChunk.objects.filter(document=doc)
        assert chunks.count() > 0

        # Verify embeddings
        for chunk in chunks:
            assert chunk.embedding is not None
            assert len(chunk.embedding) == 768

        print(f"\n✓ Successfully ingested {source.titulo}")
        print(f"  - Document ID: {doc.id}")
        print(f"  - Chunks created: {chunks.count()}")
```

---

### Phase 3: Management Command Tests

#### 3.1 Test `ingest_source` Command

**File**: `apps/legal_graphrag/tests/test_management_commands.py`

Test the management command:

```python
import pytest
from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from apps.legal_graphrag.models import CorpusSource

class TestManagementCommands(TestCase):
    def test_ingest_source_by_id(self):
        """Test ingesting source by ID"""
        source = CorpusSource.objects.first()

        out = StringIO()
        call_command('ingest_source', str(source.id), '--sync', stdout=out)

        output = out.getvalue()
        assert 'Ingesting:' in output
        assert '✓ Ingested:' in output

    def test_ingest_source_by_id_oficial(self):
        """Test ingesting source by id_oficial"""
        out = StringIO()
        call_command('ingest_source', 'BOE-A-1978-31229', '--sync', stdout=out)

        output = out.getvalue()
        assert 'Ingesting:' in output

    def test_ingest_source_not_found(self):
        """Test error when source not found"""
        out = StringIO()
        call_command('ingest_source', 'INVALID-ID', stdout=out)

        output = out.getvalue()
        assert 'Source not found' in output
```

---

### Phase 4: Manual Testing

After running automated tests, perform manual testing:

#### 4.1 Test Single Source Ingestion (Constitution)

```bash
# Navigate to backend directory
cd "d:\IT workspace\Legal GraphRAG\backend"

# Activate virtual environment (if using one)
# source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run ingestion synchronously
python manage.py ingest_source BOE-A-1978-31229 --sync
```

**Expected output**:
```
Ingesting: Constitución Española
INFO ... Starting ingestion: Constitución Española
INFO ... Fetched X chunks
INFO ... Created document: 1
INFO ... Created chunk 1: Artículo 1
INFO ... Created chunk 2: Artículo 2
...
INFO ... ✓ Ingestion complete: Constitución Española (X chunks)
✓ Ingested: X chunks
```

#### 4.2 Verify Database Records

```bash
python manage.py shell
```

```python
from apps.legal_graphrag.models import CorpusSource, LegalDocument, DocumentChunk

# Check source status
source = CorpusSource.objects.get(id_oficial='BOE-A-1978-31229')
print(f"Status: {source.estado}")
print(f"Last ingested: {source.last_ingested_at}")

# Check document
doc = LegalDocument.objects.get(source=source)
print(f"Document ID: {doc.id}")
print(f"Title: {doc.doc_title}")

# Check chunks
chunks = DocumentChunk.objects.filter(document=doc)
print(f"Chunks count: {chunks.count()}")

# Inspect first chunk
first_chunk = chunks.first()
print(f"\nFirst chunk:")
print(f"  Label: {first_chunk.chunk_label}")
print(f"  Type: {first_chunk.chunk_type}")
print(f"  Text preview: {first_chunk.chunk_text[:200]}...")
print(f"  Embedding dimensions: {len(first_chunk.embedding)}")
```

**Expected output**:
```
Status: ingested
Last ingested: 2025-12-12 XX:XX:XX
Document ID: 1
Title: Constitución Española
Chunks count: 169
First chunk:
  Label: Artículo 1
  Type: article
  Text preview: 1. España se constituye en un Estado social y democrático...
  Embedding dimensions: 768
```

#### 4.3 Test Celery Task (Async)

**Prerequisites**:
1. Redis must be running
2. Celery worker must be running

```bash
# Terminal 1: Start Redis (if not running)
redis-server

# Terminal 2: Start Celery worker
cd "d:\IT workspace\Legal GraphRAG\backend"
celery -A ovra_backend worker -l info

# Terminal 3: Queue ingestion task
python manage.py ingest_source 2  # Use a different source ID
```

**Expected behavior**:
- Terminal 3 shows: "✓ Queued: Task ID abc123..."
- Terminal 2 (Celery) shows ingestion logs
- Check task status:

```python
from celery.result import AsyncResult

result = AsyncResult('abc123')  # Use actual task ID
print(f"Status: {result.status}")
print(f"Result: {result.result}")
```

---

### Phase 5: Error Handling Tests

Create tests for error scenarios:

#### 5.1 Invalid URL (404)

```python
def test_fetch_invalid_url(self):
    """Test handling of 404 errors"""
    connector = BOEConnector()

    with pytest.raises(requests.RequestException):
        connector.fetch('https://www.boe.es/invalid-url-12345')
```

#### 5.2 Network Timeout

```python
@patch('requests.Session.get')
def test_network_timeout(self, mock_get):
    """Test handling of network timeouts"""
    mock_get.side_effect = requests.Timeout()

    connector = BOEConnector()
    with pytest.raises(requests.Timeout):
        connector.fetch('https://www.boe.es/some-url')
```

#### 5.3 Gemini API Error

```python
@patch('google.generativeai.embed_content')
def test_api_error(self, mock_embed):
    """Test handling of API errors"""
    mock_embed.side_effect = Exception('API quota exceeded')

    service = EmbeddingService()
    with pytest.raises(Exception):
        service.embed('Test text')
```

---

## Running Tests

### Run All Tests

```bash
cd "d:\IT workspace\Legal GraphRAG\backend"
pytest apps/legal_graphrag/tests/ -v
```

### Run Specific Test File

```bash
pytest apps/legal_graphrag/tests/test_boe_connector.py -v
```

### Run with Coverage

```bash
pytest apps/legal_graphrag/tests/ --cov=apps.legal_graphrag --cov-report=html
```

Open `htmlcov/index.html` to see coverage report.

---

## Test Data Requirements

Before running tests, ensure:

1. ✅ Database is set up with migrations applied
2. ✅ Corpus sources are imported (70 sources)
3. ✅ Constitution source exists (id_oficial='BOE-A-1978-31229')
4. ✅ Gemini API key is configured in `.env`
5. ✅ Redis is running (for Celery tests)

**Verify**:
```bash
python manage.py shell
```

```python
from apps.legal_graphrag.models import CorpusSource

# Check corpus sources
print(f"Total sources: {CorpusSource.objects.count()}")  # Should be 70

# Check Constitution
constitution = CorpusSource.objects.get(id_oficial='BOE-A-1978-31229')
print(f"Constitution: {constitution.titulo}")
```

---

## Success Criteria

Day 2 is complete when:

- [x] All unit tests pass (BOE, DOUE, DGT connectors, normalizer, embedding service)
- [x] Integration test passes (full pipeline with Constitution)
- [x] Management commands work (`ingest_source`, `ingest_all_p1`)
- [x] Manual test successful: Constitution ingested with >0 chunks
- [x] Database verification: LegalDocument and DocumentChunks created with embeddings
- [x] Logs generated in `backend/logs/ingestion.log`
- [x] No errors or warnings (except expected ones)

---

## Deliverable Verification

**Day 2 Deliverable**: "Ingestion pipeline can fetch, parse, and store 1 source (test with Constitution)"

**How to verify**:

1. Run:
   ```bash
   python manage.py ingest_source BOE-A-1978-31229 --sync
   ```

2. Check database:
   ```python
   from apps.legal_graphrag.models import LegalDocument, DocumentChunk

   doc = LegalDocument.objects.get(doc_id_oficial='BOE-A-1978-31229')
   chunks = DocumentChunk.objects.filter(document=doc)

   print(f"✓ Document created: {doc.doc_title}")
   print(f"✓ Chunks created: {chunks.count()}")
   print(f"✓ Sample chunk: {chunks.first().chunk_label}")
   ```

3. If all above succeed → **Day 2 is complete! ✅**

---

## Troubleshooting

### Issue: "No module named 'google.generativeai'"

**Solution**:
```bash
pip install google-generativeai
```

### Issue: "Gemini API key not found"

**Solution**:
Check `.env` file has:
```
GEMINI_API_KEY=your_api_key_here
```

### Issue: "Connection refused" (Redis)

**Solution**:
Start Redis:
```bash
redis-server
```

### Issue: BOE parsing returns empty structure

**Solution**:
This is expected for some documents. The normalizer will create a fallback chunk. Check logs for warning:
```
WARNING ... Creating fallback chunk for [document name]
```

### Issue: "Task not found" (Celery)

**Solution**:
Make sure Celery worker is running:
```bash
celery -A ovra_backend worker -l info
```

---

## Notes for Codex

- **Mock external APIs**: Use `unittest.mock` or `pytest-mock` to mock BOE, EUR-Lex, DGT, and Gemini API calls in unit tests
- **Use fixtures**: Create pytest fixtures for common test data (CorpusSource, raw documents)
- **Test isolation**: Each test should be independent. Use `TransactionTestCase` for tests that modify the database
- **Skip slow tests**: Mark integration tests with `@pytest.mark.slow` so they can be skipped:
  ```python
  @pytest.mark.slow
  def test_full_ingestion():
      # ...
  ```

  Run fast tests only: `pytest -m "not slow"`

- **Document findings**: If you find bugs or issues, document them clearly with:
  - What you expected
  - What actually happened
  - Steps to reproduce
  - Suggested fix (if any)

---

## Next Steps (Day 3)

After Day 2 testing is complete and deliverable verified:

1. Move to Day 3: Embeddings & Search
2. Ingest all P1 sources (37 sources)
3. Implement search engine

---

**Good luck, Codex! 🚀**
