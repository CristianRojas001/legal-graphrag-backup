"""
Legal Document Normalizer - Converts different source formats into canonical JSON structure
"""

from typing import Dict, List, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from apps.legal_graphrag.models import CorpusSource

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
