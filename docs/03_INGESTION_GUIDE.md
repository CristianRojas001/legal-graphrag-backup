# Legal GraphRAG System - Ingestion Guide

## Document Information
- **Version**: 1.0 (MVP)
- **Last Updated**: 2025-12-11
- **Status**: Planning Phase
- **Related**: [02_DATA_MODEL.md](./02_DATA_MODEL.md) | [01_ARCHITECTURE.md](./01_ARCHITECTURE.md)

---

## 1. Ingestion Pipeline Overview

The ingestion pipeline transforms raw legal documents (HTML, PDF) from official sources (BOE, EUR-Lex, DGT) into searchable, embedded chunks stored in PostgreSQL.

### Pipeline Stages

```
┌────────────────────────────────────────────────────────────┐
│ STAGE 1: DISCOVERY                                         │
│ - Identify sources from corpus catalog (Excel)             │
│ - Check if already ingested                                │
│ - Prioritize P1 > P2 > P3                                  │
└────────────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────────┐
│ STAGE 2: FETCHING                                          │
│ - Route to appropriate connector (BOE, DOUE, DGT)          │
│ - HTTP GET to official URL                                 │
│ - Save raw HTML/PDF                                        │
│ - Extract basic metadata                                   │
└────────────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────────┐
│ STAGE 3: PARSING & NORMALIZATION                           │
│ - Parse document structure (articles, sections)            │
│ - Clean text (remove HTML tags, fix encoding)             │
│ - Extract citations and cross-references                   │
│ - Convert to canonical JSON format                         │
└────────────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────────┐
│ STAGE 4: CHUNKING                                          │
│ - Split into semantic units (article-level)                │
│ - Generate chunk labels ("Artículo 30.2")                  │
│ - Preserve document hierarchy in metadata                  │
└────────────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────────┐
│ STAGE 5: EMBEDDING GENERATION                              │
│ - Call Gemini API for each chunk                           │
│ - Generate 768-dim vectors                                 │
│ - Handle rate limits and retries                           │
└────────────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────────┐
│ STAGE 6: STORAGE                                           │
│ - Create LegalDocument record                              │
│ - Insert DocumentChunks with embeddings                    │
│ - Update CorpusSource status                               │
│ - Log results                                              │
└────────────────────────────────────────────────────────────┘
```

---

## 2. Source Connectors

### 2.1 BOE Connector (Spanish Official Bulletin)

**Purpose**: Fetch and parse documents from BOE.es

**Input**: BOE URL (e.g., `https://www.boe.es/eli/es/l/2006/11/28/35/con`)

**Output**: Structured document with articles

```python
# apps/legal_graphrag/services/ingestion/boe_connector.py

import requests
from bs4 import BeautifulSoup
from typing import Dict, List
import logging

logger = logging.getLogger('apps.legal_graphrag.ingestion')

class BOEConnector:
    """
    Fetches and parses documents from BOE.es

    Supports:
    - Leyes (Laws)
    - Reales Decretos (Royal Decrees)
    - Órdenes (Orders)
    - Constitución (Constitution)
    """

    BASE_URL = 'https://www.boe.es'

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ArtistingLegalBot/1.0 (legal@artisting.es)'
        })

    def fetch(self, url: str) -> Dict:
        """
        Fetch BOE document from official URL

        Args:
            url: BOE document URL

        Returns:
            {
                'html': str,              # Raw HTML
                'content': str,           # Cleaned text
                'metadata': dict,         # Document metadata
                'structure': list         # Parsed structure
            }
        """
        logger.info(f"Fetching BOE document: {url}")

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract metadata
            metadata = self._extract_metadata(soup, url)

            # Parse structure (articles, sections)
            structure = self._parse_structure(soup)

            # Extract full text
            content = self._extract_content(soup)

            return {
                'html': response.text,
                'content': content,
                'metadata': metadata,
                'structure': structure
            }

        except requests.RequestException as e:
            logger.error(f"Failed to fetch BOE document: {e}")
            raise

    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract BOE-specific metadata"""
        metadata = {'url': url}

        # Publication date
        fecha_elem = soup.select_one('.fecha-publicacion, meta[name="DC.Date"]')
        if fecha_elem:
            metadata['fecha_publicacion'] = fecha_elem.get('content') or fecha_elem.text.strip()

        # Section
        seccion_elem = soup.select_one('.seccion')
        if seccion_elem:
            metadata['seccion'] = seccion_elem.text.strip()

        # Department
        dept_elem = soup.select_one('.departamento, .nombre-ministerio')
        if dept_elem:
            metadata['departamento'] = dept_elem.text.strip()

        # Title
        title_elem = soup.select_one('h1.titulo, .titulo-disposicion')
        if title_elem:
            metadata['titulo'] = title_elem.text.strip()

        # BOE identifier
        boe_id_elem = soup.select_one('meta[name="DC.identifier"]')
        if boe_id_elem:
            metadata['boe_id'] = boe_id_elem.get('content')

        return metadata

    def _parse_structure(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Parse document structure into articles/sections

        Returns:
            [
                {
                    'type': 'article',
                    'label': 'Artículo 30',
                    'number': 30,
                    'title': 'Gastos deducibles',
                    'text': 'Son gastos deducibles...',
                    'subsections': [...]
                },
                ...
            ]
        """
        structure = []

        # Look for article containers
        articles = soup.select('.articulo, article[id^="art"]')

        for idx, article_elem in enumerate(articles, 1):
            article_data = self._parse_article(article_elem, idx)
            if article_data:
                structure.append(article_data)

        # If no articles found, try alternative selectors
        if not structure:
            structure = self._parse_alternative_structure(soup)

        return structure

    def _parse_article(self, article_elem, position: int) -> Dict:
        """Parse a single article element"""
        # Extract article number/label
        label_elem = article_elem.select_one('.numero-articulo, .titulo-articulo, h3, h4')
        label = label_elem.text.strip() if label_elem else f"Artículo {position}"

        # Extract article title (if separate from number)
        title_elem = article_elem.select_one('.titulo')
        title = title_elem.text.strip() if title_elem else None

        # Extract article text (paragraphs)
        text_elems = article_elem.select('p, .parrafo')
        text = '\n\n'.join([p.get_text(strip=True) for p in text_elems if p.get_text(strip=True)])

        # Try to extract article number
        import re
        number_match = re.search(r'(\d+)', label)
        number = int(number_match.group(1)) if number_match else position

        return {
            'type': 'article',
            'label': label,
            'number': number,
            'title': title,
            'text': text,
            'position': position
        }

    def _parse_alternative_structure(self, soup: BeautifulSoup) -> List[Dict]:
        """Fallback parser for different BOE formats"""
        structure = []

        # Try heading-based parsing (h2, h3 as section markers)
        headings = soup.select('h2, h3, h4')

        for heading in headings:
            # Get text until next heading
            text_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                if sibling.name == 'p':
                    text_parts.append(sibling.get_text(strip=True))

            if text_parts:
                structure.append({
                    'type': 'section',
                    'label': heading.get_text(strip=True),
                    'text': '\n\n'.join(text_parts),
                    'position': len(structure) + 1
                })

        return structure

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract full document text"""
        content_div = soup.select_one('#textoBOE, .texto-disposicion, main')
        if content_div:
            return content_div.get_text(separator='\n\n', strip=True)
        return soup.get_text(separator='\n\n', strip=True)
```

### 2.2 DOUE Connector (EU Official Journal)

**Purpose**: Fetch and parse EU directives/regulations from EUR-Lex

```python
# apps/legal_graphrag/services/ingestion/doue_connector.py

import requests
from bs4 import BeautifulSoup
from typing import Dict, List
import logging

logger = logging.getLogger('apps.legal_graphrag.ingestion')

class DOUEConnector:
    """
    Fetches and parses documents from EUR-Lex

    Supports:
    - EU Directives
    - EU Regulations
    - TFUE (Treaty on the Functioning of the EU)
    """

    BASE_URL = 'https://eur-lex.europa.eu'

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ArtistingLegalBot/1.0 (legal@artisting.es)',
            'Accept-Language': 'es'
        })

    def fetch(self, url: str) -> Dict:
        """
        Fetch EU document from EUR-Lex

        EUR-Lex provides multiple formats:
        - HTML: Human-readable
        - XML: Structured (preferred for parsing)
        - PDF: Archival

        We fetch HTML and parse structure
        """
        logger.info(f"Fetching DOUE document: {url}")

        try:
            # Ensure we get the HTML version
            if '/TXT/' not in url and '/AUTO/' not in url:
                url = url.replace('/legal-content/', '/legal-content/ES/TXT/')

            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')

            metadata = self._extract_metadata(soup, url)
            structure = self._parse_structure(soup)
            content = self._extract_content(soup)

            return {
                'html': response.text,
                'content': content,
                'metadata': metadata,
                'structure': structure
            }

        except requests.RequestException as e:
            logger.error(f"Failed to fetch DOUE document: {e}")
            raise

    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract EUR-Lex metadata"""
        metadata = {'url': url}

        # CELEX number (EU document identifier)
        celex_elem = soup.select_one('meta[name="CELEX"]')
        if celex_elem:
            metadata['celex'] = celex_elem.get('content')

        # Date of document
        date_elem = soup.select_one('.eli-date, meta[name="DC.date"]')
        if date_elem:
            metadata['fecha_documento'] = date_elem.get('content') or date_elem.text.strip()

        # Document type
        doctype_elem = soup.select_one('meta[name="DC.type"]')
        if doctype_elem:
            metadata['tipo'] = doctype_elem.get('content')

        return metadata

    def _parse_structure(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse EU document structure (articles)"""
        structure = []

        # EUR-Lex articles are in divs with class 'eli-subdivision'
        articles = soup.select('.eli-subdivision[data-type="article"], article')

        for idx, article in enumerate(articles, 1):
            article_data = self._parse_article(article, idx)
            if article_data:
                structure.append(article_data)

        return structure

    def _parse_article(self, article_elem, position: int) -> Dict:
        """Parse a single EU article"""
        # Article number
        num_elem = article_elem.select_one('.eli-title, .article-num')
        label = num_elem.text.strip() if num_elem else f"Artículo {position}"

        # Article text
        text_elem = article_elem.select_one('.eli-content, .article-text')
        text = text_elem.get_text(separator='\n\n', strip=True) if text_elem else article_elem.get_text(strip=True)

        return {
            'type': 'article',
            'label': label,
            'text': text,
            'position': position
        }

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract full text"""
        content_div = soup.select_one('.eli-main-content, #document-content, main')
        if content_div:
            return content_div.get_text(separator='\n\n', strip=True)
        return soup.get_text(separator='\n\n', strip=True)
```

### 2.3 DGT Connector (Tax Rulings - Doctrina)

**Purpose**: Fetch DGT tax rulings from PETETE database

```python
# apps/legal_graphrag/services/ingestion/dgt_connector.py

import requests
from bs4 import BeautifulSoup
from typing import Dict, List
import logging
import re

logger = logging.getLogger('apps.legal_graphrag.ingestion')

class DGTConnector:
    """
    Fetches DGT tax rulings from PETETE database

    URL format:
    https://petete.tributos.hacienda.gob.es/consultas/V0123-21
    """

    BASE_URL = 'https://petete.tributos.hacienda.gob.es'

    def fetch(self, url: str) -> Dict:
        """
        Fetch DGT ruling

        DGT rulings are simpler than laws:
        - Single document (not divided into articles)
        - Has "consulta" and "contestación" sections
        """
        logger.info(f"Fetching DGT ruling: {url}")

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            metadata = self._extract_metadata(soup, url)
            structure = self._parse_ruling(soup)
            content = self._extract_content(soup)

            return {
                'html': response.text,
                'content': content,
                'metadata': metadata,
                'structure': structure
            }

        except requests.RequestException as e:
            logger.error(f"Failed to fetch DGT ruling: {e}")
            raise

    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract DGT ruling metadata"""
        metadata = {'url': url}

        # Extract ruling number from URL
        match = re.search(r'/(V\d+-\d+)', url)
        if match:
            metadata['numero_consulta'] = match.group(1)

        # Date
        date_elem = soup.select_one('.fecha, .date')
        if date_elem:
            metadata['fecha'] = date_elem.text.strip()

        # Subject
        subject_elem = soup.select_one('.asunto, .subject')
        if subject_elem:
            metadata['asunto'] = subject_elem.text.strip()

        return metadata

    def _parse_ruling(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Parse DGT ruling structure

        Returns:
            [
                {
                    'type': 'consulta',
                    'label': 'Consulta',
                    'text': '...'
                },
                {
                    'type': 'contestacion',
                    'label': 'Contestación',
                    'text': '...'
                }
            ]
        """
        structure = []

        # Query section
        consulta_elem = soup.select_one('.consulta, #consulta')
        if consulta_elem:
            structure.append({
                'type': 'consulta',
                'label': 'Consulta',
                'text': consulta_elem.get_text(strip=True),
                'position': 1
            })

        # Response section
        contestacion_elem = soup.select_one('.contestacion, #contestacion')
        if contestacion_elem:
            structure.append({
                'type': 'contestacion',
                'label': 'Contestación',
                'text': contestacion_elem.get_text(strip=True),
                'position': 2
            })

        return structure

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract full ruling text"""
        main_content = soup.select_one('main, .content, #content')
        if main_content:
            return main_content.get_text(separator='\n\n', strip=True)
        return soup.get_text(separator='\n\n', strip=True)
```

---

## 3. Document Normalizer

**Purpose**: Convert different source formats into a canonical JSON structure

```python
# apps/legal_graphrag/services/ingestion/normalizer.py

from typing import Dict, List
import logging

logger = logging.getLogger('apps.legal_graphrag.ingestion')

class LegalDocumentNormalizer:
    """
    Normalizes legal documents from various sources into canonical format

    Canonical format:
    {
        "titulo": str,
        "id_oficial": str,
        "fecha_publicacion": str,
        "tipo": str,
        "naturaleza": str,
        "chunks": [
            {
                "type": "article",
                "label": "Artículo 30",
                "text": "...",
                "metadata": {...}
            }
        ],
        "metadata": {...}
    }
    """

    def normalize(self, raw_doc: Dict, source: 'CorpusSource') -> Dict:
        """
        Normalize document to canonical format

        Args:
            raw_doc: Output from connector (BOE, DOUE, DGT)
            source: CorpusSource instance

        Returns:
            Canonical document dict
        """
        logger.info(f"Normalizing document: {source.titulo}")

        # Extract chunks from structure
        chunks = self._normalize_chunks(
            raw_doc.get('structure', []),
            source
        )

        # If no structured chunks, create one chunk from full content
        if not chunks and raw_doc.get('content'):
            chunks = [self._create_fallback_chunk(raw_doc['content'], source)]

        # Build canonical metadata
        canonical_metadata = {
            **raw_doc.get('metadata', {}),
            'naturaleza': source.naturaleza,
            'area_principal': source.area_principal,
            'prioridad': source.prioridad,
            'nivel_autoridad': source.nivel_autoridad,
            'tipo': source.tipo,
            'ambito': source.ambito,
        }

        return {
            'titulo': source.titulo,
            'id_oficial': source.id_oficial,
            'fecha_publicacion': raw_doc.get('metadata', {}).get('fecha_publicacion'),
            'tipo': source.tipo,
            'naturaleza': source.naturaleza,
            'chunks': chunks,
            'metadata': canonical_metadata
        }

    def _normalize_chunks(self, structure: List[Dict], source: 'CorpusSource') -> List[Dict]:
        """Normalize chunks from parsed structure"""
        chunks = []

        for chunk_data in structure:
            chunk = {
                'type': chunk_data.get('type', 'section'),
                'label': chunk_data.get('label', ''),
                'text': chunk_data.get('text', ''),
                'metadata': {
                    'naturaleza': source.naturaleza,
                    'area_principal': source.area_principal,
                    'prioridad': source.prioridad,
                    'nivel_autoridad': source.nivel_autoridad,
                    'tipo': source.tipo,
                    'ambito': source.ambito,
                    'doc_title': source.titulo,
                    'doc_id_oficial': source.id_oficial,
                    'url': source.url_oficial,
                    'position': chunk_data.get('position', chunk_data.get('number')),
                }
            }

            # Add title if exists
            if chunk_data.get('title'):
                chunk['metadata']['title'] = chunk_data['title']

            chunks.append(chunk)

        return chunks

    def _create_fallback_chunk(self, content: str, source: 'CorpusSource') -> Dict:
        """Create single chunk from full content when parsing fails"""
        logger.warning(f"Creating fallback chunk for {source.titulo}")

        return {
            'type': 'full_text',
            'label': source.titulo,
            'text': content,
            'metadata': {
                'naturaleza': source.naturaleza,
                'area_principal': source.area_principal,
                'prioridad': source.prioridad,
                'nivel_autoridad': source.nivel_autoridad,
                'tipo': source.tipo,
                'ambito': source.ambito,
                'doc_title': source.titulo,
                'doc_id_oficial': source.id_oficial,
                'url': source.url_oficial,
                'position': 1,
                'is_fallback': True
            }
        }
```

---

## 4. Embedding Service

**Purpose**: Generate vector embeddings using Gemini API

```python
# apps/legal_graphrag/services/embedding_service.py

import google.generativeai as genai
from django.conf import settings
from typing import List
import logging
import time

logger = logging.getLogger('apps.legal_graphrag.ingestion')

class EmbeddingService:
    """
    Generates embeddings using Gemini text-embedding-004

    Specs:
    - Model: text-embedding-004
    - Dimensions: 768
    - Max input: 2048 tokens (~8000 chars)
    - Rate limit: 1500 requests/day (free tier)
    """

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model_name = 'models/text-embedding-004'

    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for text

        Args:
            text: Input text (max 8000 chars recommended)

        Returns:
            List of 768 floats
        """
        # Truncate if too long
        if len(text) > 8000:
            logger.warning(f"Text truncated from {len(text)} to 8000 chars")
            text = text[:8000]

        try:
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_document"  # Optimize for retrieval
            )

            return result['embedding']

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    def embed_batch(self, texts: List[str], delay_ms: int = 100) -> List[List[float]]:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of input texts
            delay_ms: Delay between requests (rate limiting)

        Returns:
            List of embeddings
        """
        embeddings = []

        for idx, text in enumerate(texts):
            logger.info(f"Embedding chunk {idx + 1}/{len(texts)}")

            embedding = self.embed(text)
            embeddings.append(embedding)

            # Rate limiting
            if idx < len(texts) - 1:
                time.sleep(delay_ms / 1000)

        return embeddings
```

---

## 5. Celery Tasks

**Purpose**: Orchestrate async ingestion pipeline

```python
# apps/legal_graphrag/tasks.py

from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger('apps.legal_graphrag.ingestion')

@shared_task(bind=True, max_retries=3)
def ingest_legal_source(self, source_id: int):
    """
    Celery task: Ingest a single legal source

    Args:
        source_id: ID of CorpusSource to ingest

    Returns:
        dict: Ingestion results
    """
    from apps.legal_graphrag.models import CorpusSource, LegalDocument, DocumentChunk
    from apps.legal_graphrag.services.ingestion.boe_connector import BOEConnector
    from apps.legal_graphrag.services.ingestion.doue_connector import DOUEConnector
    from apps.legal_graphrag.services.ingestion.dgt_connector import DGTConnector
    from apps.legal_graphrag.services.ingestion.normalizer import LegalDocumentNormalizer
    from apps.legal_graphrag.services.embedding_service import EmbeddingService

    try:
        # Get source
        source = CorpusSource.objects.get(id=source_id)
        source.estado = 'ingesting'
        source.save()

        logger.info(f"Starting ingestion: {source.titulo}")

        # STAGE 1: Fetch document
        connector = get_connector(source)
        raw_doc = connector.fetch(source.url_oficial)

        logger.info(f"Fetched {len(raw_doc.get('structure', []))} chunks")

        # STAGE 2: Normalize
        normalizer = LegalDocumentNormalizer()
        normalized = normalizer.normalize(raw_doc, source)

        # STAGE 3: Create document record
        doc = LegalDocument.objects.create(
            source=source,
            doc_title=normalized['titulo'],
            doc_id_oficial=source.id_oficial,
            url=source.url_oficial,
            raw_html=raw_doc['html'],
            metadata=normalized['metadata']
        )

        logger.info(f"Created document: {doc.id}")

        # STAGE 4: Generate embeddings and create chunks
        embedding_service = EmbeddingService()
        chunks_created = 0

        for chunk in normalized['chunks']:
            # Generate embedding
            embedding = embedding_service.embed(chunk['text'])

            # Create chunk
            DocumentChunk.objects.create(
                document=doc,
                chunk_type=chunk['type'],
                chunk_label=chunk['label'],
                chunk_text=chunk['text'],
                embedding=embedding,
                metadata=chunk['metadata']
            )

            chunks_created += 1
            logger.info(f"Created chunk {chunks_created}: {chunk['label']}")

        # STAGE 5: Update source status
        source.estado = 'ingested'
        source.last_ingested_at = timezone.now()
        source.ingestion_error = None
        source.save()

        logger.info(f"✓ Ingestion complete: {source.titulo} ({chunks_created} chunks)")

        return {
            'source_id': source_id,
            'source_title': source.titulo,
            'chunks_created': chunks_created,
            'status': 'success'
        }

    except Exception as e:
        logger.error(f"Ingestion failed for source {source_id}: {e}")

        # Update source status
        try:
            source = CorpusSource.objects.get(id=source_id)
            source.estado = 'failed'
            source.ingestion_error = str(e)
            source.save()
        except:
            pass

        # Retry task
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task
def ingest_all_p1_sources():
    """
    Batch task: Ingest all P1 priority sources

    Usage:
        from apps.legal_graphrag.tasks import ingest_all_p1_sources
        ingest_all_p1_sources.delay()
    """
    from apps.legal_graphrag.models import CorpusSource

    p1_sources = CorpusSource.objects.filter(
        prioridad='P1',
        estado='pending'
    ).order_by('area_principal', 'titulo')

    logger.info(f"Queueing {p1_sources.count()} P1 sources for ingestion")

    for source in p1_sources:
        ingest_legal_source.delay(source.id)

    return f"Queued {p1_sources.count()} sources"


@shared_task
def update_source(source_id: int):
    """
    Update an existing source (re-ingest)

    Use case: Law has been updated, need to re-fetch
    """
    from apps.legal_graphrag.models import CorpusSource, LegalDocument

    source = CorpusSource.objects.get(id=source_id)

    # Delete old document and chunks (cascade)
    LegalDocument.objects.filter(source=source).delete()

    # Reset source status
    source.estado = 'pending'
    source.save()

    # Re-ingest
    ingest_legal_source.delay(source_id)


def get_connector(source: 'CorpusSource'):
    """Factory function to get appropriate connector"""
    from apps.legal_graphrag.services.ingestion.boe_connector import BOEConnector
    from apps.legal_graphrag.services.ingestion.doue_connector import DOUEConnector
    from apps.legal_graphrag.services.ingestion.dgt_connector import DGTConnector

    url = source.url_oficial.lower()

    if 'boe.es' in url:
        return BOEConnector()
    elif 'eur-lex.europa.eu' in url:
        return DOUEConnector()
    elif 'petete.tributos.hacienda.gob.es' in url or 'dgt' in url:
        return DGTConnector()
    else:
        # Default to BOE connector
        logger.warning(f"Unknown source type for {url}, using BOE connector")
        return BOEConnector()
```

---

## 6. Management Commands

```python
# apps/legal_graphrag/management/commands/ingest_source.py

from django.core.management.base import BaseCommand
from apps.legal_graphrag.models import CorpusSource
from apps.legal_graphrag.tasks import ingest_legal_source

class Command(BaseCommand):
    help = 'Ingest a legal source by ID or id_oficial'

    def add_arguments(self, parser):
        parser.add_argument('identifier', type=str, help='Source ID or id_oficial')
        parser.add_argument('--sync', action='store_true', help='Run synchronously (not via Celery)')

    def handle(self, *args, **options):
        identifier = options['identifier']

        # Try to get source by ID or id_oficial
        try:
            if identifier.isdigit():
                source = CorpusSource.objects.get(id=int(identifier))
            else:
                source = CorpusSource.objects.get(id_oficial=identifier)
        except CorpusSource.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Source not found: {identifier}'))
            return

        self.stdout.write(f'Ingesting: {source.titulo}')

        if options['sync']:
            # Run synchronously (for testing)
            result = ingest_legal_source(source.id)
            self.stdout.write(self.style.SUCCESS(f'✓ Ingested: {result["chunks_created"]} chunks'))
        else:
            # Queue as Celery task
            task = ingest_legal_source.delay(source.id)
            self.stdout.write(self.style.SUCCESS(f'✓ Queued: Task ID {task.id}'))
```

```python
# apps/legal_graphrag/management/commands/ingest_all_p1.py

from django.core.management.base import BaseCommand
from apps.legal_graphrag.tasks import ingest_all_p1_sources

class Command(BaseCommand):
    help = 'Ingest all P1 priority sources'

    def handle(self, *args, **options):
        result = ingest_all_p1_sources.delay()
        self.stdout.write(self.style.SUCCESS(f'✓ {result}'))
```

---

## 7. Usage Examples

### 7.1 Ingest a Single Source

```bash
# Via management command (recommended)
python manage.py ingest_source BOE-A-1978-31229

# Or by ID
python manage.py ingest_source 1

# Synchronously (for debugging)
python manage.py ingest_source 1 --sync
```

### 7.2 Ingest All P1 Sources

```bash
python manage.py ingest_all_p1
```

### 7.3 Programmatically

```python
from apps.legal_graphrag.models import CorpusSource
from apps.legal_graphrag.tasks import ingest_legal_source

# Get source
source = CorpusSource.objects.get(id_oficial='BOE-A-1978-31229')

# Queue ingestion task
task = ingest_legal_source.delay(source.id)
print(f"Task ID: {task.id}")

# Check task status
from celery.result import AsyncResult
result = AsyncResult(task.id)
print(f"Status: {result.status}")
print(f"Result: {result.result}")
```

### 7.4 Monitor Progress

```python
from apps.legal_graphrag.models import CorpusSource

# Check ingestion status
for source in CorpusSource.objects.filter(prioridad='P1'):
    print(f"{source.estado:12} | {source.titulo}")

# Count chunks
from apps.legal_graphrag.models import DocumentChunk
print(f"Total chunks: {DocumentChunk.objects.count()}")
```

---

## 8. Error Handling

### 8.1 Common Errors

**HTTP 404 (Page Not Found)**:
- URL changed or document removed
- Mark source as `skipped`, manual review needed

**Parsing Failed (No Structure)**:
- Fallback to full-text chunk
- Log warning, manual inspection recommended

**Embedding API Error (Rate Limit)**:
- Celery retries with exponential backoff
- Consider caching embeddings

**Database Error**:
- Transaction rollback
- Source status remains `ingesting`, can retry

### 8.2 Retry Strategy

```python
# In tasks.py

@shared_task(bind=True, max_retries=3)
def ingest_legal_source(self, source_id: int):
    try:
        # ... ingestion logic ...
        pass
    except Exception as e:
        # Retry with exponential backoff
        # Retry 1: 60s delay
        # Retry 2: 120s delay
        # Retry 3: 180s delay
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
```

---

## 9. Performance Optimization

### 9.1 Batch Processing

```python
@shared_task
def ingest_sources_batch(source_ids: List[int]):
    """
    Ingest multiple sources in parallel

    Uses Celery group for parallelism
    """
    from celery import group

    job = group(ingest_legal_source.s(sid) for sid in source_ids)
    result = job.apply_async()

    return f"Queued {len(source_ids)} sources"
```

### 9.2 Embedding Cache

```python
# Cache embeddings to avoid re-generation
from django.core.cache import cache

class EmbeddingService:
    def embed(self, text: str) -> List[float]:
        # Generate cache key
        import hashlib
        cache_key = f"embed:{hashlib.md5(text.encode()).hexdigest()}"

        # Check cache
        cached = cache.get(cache_key)
        if cached:
            return cached

        # Generate embedding
        embedding = genai.embed_content(...)['embedding']

        # Cache for 30 days
        cache.set(cache_key, embedding, timeout=60*60*24*30)

        return embedding
```

### 9.3 Database Optimization

```sql
-- Vacuum and analyze after bulk inserts
VACUUM ANALYZE legal_document_chunks;

-- Reindex vector index
REINDEX INDEX idx_chunks_embedding;
```

---

## 10. Monitoring & Logging

### 10.1 Celery Monitoring

```bash
# View active tasks
celery -A ovra_backend inspect active

# View stats
celery -A ovra_backend inspect stats

# Purge queue
celery -A ovra_backend purge
```

### 10.2 Logging Strategy

```python
# In settings.py

LOGGING = {
    'version': 1,
    'handlers': {
        'ingestion_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/ingestion.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
        },
    },
    'loggers': {
        'apps.legal_graphrag.ingestion': {
            'handlers': ['ingestion_file'],
            'level': 'INFO',
        },
    },
}
```

---

**Document End** | Next: [04_RETRIEVAL_GUIDE.md](./04_RETRIEVAL_GUIDE.md)
