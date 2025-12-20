"""
DOUE Connector - Fetches and parses documents from EUR-Lex
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List
import logging
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

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
            # Normalize URL to Spanish HTML/TXT (avoid PDF)
            url = self._normalize_url(url)

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

    def _normalize_url(self, url: str) -> str:
        """
        Force Spanish HTML/TXT URLs and auto-convert PDF links to TXT to avoid binary ingest.
        """
        parsed = urlparse(url)
        path_lower = parsed.path.lower()

        # If it's a PDF link (explicit PDF path or .pdf)
        if '/pdf/' in path_lower or path_lower.endswith('.pdf'):
            query = parse_qs(parsed.query)
            celex = None
            if 'uri' in query:
                # uri can be ['CELEX:32010L0013']
                for v in query.get('uri', []):
                    if v.upper().startswith('CELEX:'):
                        celex = v
                        break
            # If CELEX not found in query, try to extract from path fragments
            if not celex:
                parts = path_lower.split(':')
                if len(parts) > 1 and parts[-1]:
                    celex_candidate = parts[-1].split('/')[0]
                    if celex_candidate:
                        celex = f"CELEX:{celex_candidate}"

            if celex:
                logger.info(f"PDF URL detected; converting to Spanish TXT using {celex}")
                new_query = urlencode({'uri': celex})
                new_path = parsed.path.lower().replace('/pdf/', '/txt/').replace('/PDF/', '/TXT/')
                # Ensure ES language in path
                if '/legal-content/' in new_path and '/txt/' in new_path and '/es/' not in new_path:
                    new_path = new_path.replace('/legal-content/', '/legal-content/ES/')
                rebuilt = parsed._replace(path=new_path, query=new_query)
                return urlunparse(rebuilt)
            else:
                logger.warning("PDF URL without CELEX, keeping original (may fail parsing)")
                return url

        # For non-PDF, ensure Spanish TXT view
        if '/legal-content/' in path_lower and '/txt/' not in path_lower and '/auto/' not in path_lower:
            new_path = parsed.path.replace('/legal-content/', '/legal-content/ES/TXT/')
            parsed = parsed._replace(path=new_path)
        elif '/legal-content/' in path_lower and '/txt/' in path_lower and '/es/' not in path_lower:
            new_path = parsed.path.replace('/legal-content/', '/legal-content/ES/')
            parsed = parsed._replace(path=new_path)

        return urlunparse(parsed)

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

        # Title
        title_elem = soup.select_one('h1, .title')
        if title_elem:
            metadata['titulo'] = title_elem.text.strip()

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
