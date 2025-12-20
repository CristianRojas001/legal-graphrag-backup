"""
DGT Connector - Fetches tax rulings from PETETE database
"""

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

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ArtistingLegalBot/1.0 (legal@artisting.es)'
        })

    def fetch(self, url: str) -> Dict:
        """
        Fetch DGT ruling

        DGT rulings are simpler than laws:
        - Single document (not divided into articles)
        - Has "consulta" and "contestación" sections
        """
        logger.info(f"Fetching DGT ruling: {url}")

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'

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

        # Title
        title_elem = soup.select_one('h1, .title')
        if title_elem:
            metadata['titulo'] = title_elem.text.strip()

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
