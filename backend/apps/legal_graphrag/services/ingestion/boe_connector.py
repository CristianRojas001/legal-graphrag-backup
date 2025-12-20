"""
BOE Connector - Fetches and parses documents from BOE.es
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List
import logging
import re

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

    def fetch(self, url: str, boe_id: str | None = None) -> Dict:
        """
        Fetch BOE document from official URL

        Args:
            url: BOE document URL (supports HTML and PDF)
            boe_id: Optional BOE identifier (e.g., BOE-A-1978-31229) used
                when the PDF URL does not include the ID

        Returns:
            {
                'html': str,              # Raw HTML (or empty for PDFs)
                'content': str,           # Cleaned text
                'metadata': dict,         # Document metadata
                'structure': list         # Parsed structure
            }
        """
        logger.info(f"Fetching BOE document: {url}")

        try:
            # Check if URL points to PDF
            if url.endswith('.pdf') or '/pdf/' in url.lower():
                logger.warning(f"PDF URL detected: {url}")
                logger.warning("PDF parsing not yet implemented. Converting to HTML URL...")

                # Try to convert PDF URL to HTML URL
                html_url = self._convert_pdf_to_html_url(url, boe_id=boe_id)
                if html_url:
                    logger.info(f"Converted to HTML URL: {html_url}")
                    url = html_url
                else:
                    raise ValueError(f"Cannot process PDF URL: {url}. Please provide HTML version of the document.")

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

    def _convert_pdf_to_html_url(self, pdf_url: str, boe_id: str | None = None) -> str:
        """
        Convert PDF URL to HTML URL

        Example:
        PDF:  https://www.boe.es/buscar/pdf/1978/BOE-A-1978-31229-consolidado.pdf
        HTML: https://www.boe.es/eli/es/c/1978/12/27/(1)/con

        Args:
            pdf_url: PDF URL

        Returns:
            HTML URL or None if conversion not possible
        """
        import re

        # Try to extract BOE ID from PDF URL (Pattern: BOE-A-YYYY-NNNNN)
        match = re.search(r'(BOE-A-\d{4}-\d+)', pdf_url)

        resolved_boe_id = None
        if match:
            resolved_boe_id = match.group(1)
        elif boe_id:
            # Fall back to provided BOE identifier (e.g., when PDF file name
            # lacks the BOE-A-* pattern, such as A29313-29424.pdf)
            resolved_boe_id = boe_id

        if not resolved_boe_id:
            return None

        # Try to construct ELI (European Legislation Identifier) URL
        # This is the canonical HTML format for BOE documents
        # Pattern: /eli/es/{type}/{year}/{month}/{day}/{number}/con

        # For now, we'll use the simpler BOE search URL which redirects to ELI
        html_url = f"https://www.boe.es/buscar/doc.php?id={resolved_boe_id}"

        logger.info(f"Converted PDF URL to HTML: {pdf_url} -> {html_url}")
        return html_url

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

        # Look for article headers (h5.articulo, h4.articulo, etc.)
        article_headers = soup.select('h5.articulo, h4.articulo, h3.articulo, .articulo, article[id^="art"]')

        if article_headers:
            # New structure: article headers with paragraph siblings
            for idx, header in enumerate(article_headers, 1):
                article_data = self._parse_article_with_siblings(header, idx)
                if article_data and article_data.get('text'):
                    structure.append(article_data)
        else:
            # Old structure: article containers with nested content
            articles = soup.select('article[id^="art"]')
            for idx, article_elem in enumerate(articles, 1):
                article_data = self._parse_article(article_elem, idx)
                if article_data:
                    structure.append(article_data)

        # If no articles found, try alternative selectors
        if not structure:
            structure = self._parse_alternative_structure(soup)

        return structure

    def _parse_article_with_siblings(self, header_elem, position: int) -> Dict:
        """
        Parse article where header and content are siblings

        Used for BOE doc.php format where:
        <h5 class="articulo">Artículo 1</h5>
        <p class="parrafo">Text 1...</p>
        <p class="parrafo">Text 2...</p>
        <h5 class="articulo">Artículo 2</h5>
        """
        # Get article label from header
        label = header_elem.get_text(strip=True)

        # Collect paragraph siblings until next article header
        text_parts = []
        for sibling in header_elem.find_next_siblings():
            # Stop at next article
            if sibling.name in ['h5', 'h4', 'h3'] and 'articulo' in sibling.get('class', []):
                break

            # Collect paragraph text
            if sibling.name == 'p' and 'parrafo' in sibling.get('class', []):
                text = sibling.get_text(strip=True)
                if text:
                    text_parts.append(text)

        # Join all paragraphs
        text = '\n\n'.join(text_parts)

        # Extract article number
        number_match = re.search(r'(\d+)', label)
        number = int(number_match.group(1)) if number_match else position

        return {
            'type': 'article',
            'label': label,
            'number': number,
            'title': None,
            'text': text,
            'position': position
        }

    def _parse_article(self, article_elem, position: int) -> Dict:
        """Parse a single article element (container format)"""
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
