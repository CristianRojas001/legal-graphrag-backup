"""
Exact reference resolver for v1.1.
Detects explicit legal references and pulls targeted chunks directly from DB.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Q

from apps.legal_graphrag.models import CorpusSource, LegalDocument, DocumentChunk


class ExactReferenceResolver:
    """
    Resolve exact references (BOE IDs, law titles, article numbers) to chunks.
    """

    BOE_ID_PATTERN = re.compile(r"\bBOE-A-\d{4}-\d+\b", re.IGNORECASE)
    LAW_PATTERN = re.compile(
        r"\b(Ley|Real Decreto|Real Decreto Legislativo|Ley Organica)\s+\d+/\d{4}\b",
        re.IGNORECASE,
    )
    ECLI_PATTERN = re.compile(r"\bECLI:ES:[A-Z]+:\d{4}:\d+\b", re.IGNORECASE)
    ARTICLE_PATTERN = re.compile(
        r"\bart(?:\.|iculo)?\s*(\d+(?:\.\d+)*)(?:\s*[ªº])?\b",
        re.IGNORECASE,
    )

    def __init__(self):
        self.alias_map = {
            "constitucion": "BOE-A-1978-31229",
            "constitucion espanola": "BOE-A-1978-31229",
            "constitucion espanol": "BOE-A-1978-31229",
        }

    def resolve(self, query: str) -> List[Dict[str, Any]]:
        """
        Return forced sources derived from explicit references in the query.
        """
        if not query:
            return []

        boe_id, law_title, article_number, ecli = self._parse_references(query)
        document = self._resolve_document(boe_id, law_title, ecli, query)
        if not document:
            return []

        chunks = self._resolve_chunks(document, article_number, query)
        return [self._format_forced_chunk(chunk) for chunk in chunks]

    def _parse_references(
        self,
        query: str,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        boe_match = self.BOE_ID_PATTERN.search(query or "")
        boe_id = boe_match.group(0).upper() if boe_match else None

        ecli_match = self.ECLI_PATTERN.search(query or "")
        ecli = ecli_match.group(0).upper() if ecli_match else None

        law_match = self.LAW_PATTERN.search(query or "")
        law_title = law_match.group(0) if law_match else None

        article_match = self.ARTICLE_PATTERN.search(query or "")
        article_number = article_match.group(1) if article_match else None

        if not boe_id:
            normalized = self._normalize_text(query)
            for alias, canonical in self.alias_map.items():
                if alias in normalized:
                    boe_id = canonical
                    break

        return boe_id, law_title, article_number, ecli

    def _resolve_document(
        self,
        boe_id: Optional[str],
        law_title: Optional[str],
        ecli: Optional[str],
        query: str,
    ) -> Optional[LegalDocument]:
        if boe_id:
            doc = LegalDocument.objects.filter(doc_id_oficial__iexact=boe_id).first()
            if doc:
                return doc
            source = CorpusSource.objects.filter(id_oficial__iexact=boe_id).first()
            if source:
                return LegalDocument.objects.filter(source=source).first()

        if ecli:
            doc = LegalDocument.objects.filter(doc_id_oficial__iexact=ecli).first()
            if doc:
                return doc
            source = CorpusSource.objects.filter(id_oficial__iexact=ecli).first()
            if source:
                return LegalDocument.objects.filter(source=source).first()

        if law_title:
            return LegalDocument.objects.filter(doc_title__icontains=law_title).first()

        normalized = self._normalize_text(query)
        for alias, canonical in self.alias_map.items():
            if alias in normalized:
                return LegalDocument.objects.filter(doc_id_oficial__iexact=canonical).first()

        return None

    def _resolve_chunks(
        self,
        document: LegalDocument,
        article_number: Optional[str],
        query: str,
    ) -> List[DocumentChunk]:
        if article_number:
            base_article = article_number.split(".")[0]
            label_variants = [
                f"Artículo {base_article}",
                f"Articulo {base_article}",
                f"Art. {base_article}",
            ]
            article_filter = Q()
            for label in label_variants:
                article_filter |= Q(chunk_label__icontains=label)

            matches = list(
                DocumentChunk.objects.filter(document=document)
                .filter(article_filter)
                .order_by("chunk_label")[:5]
            )
            if matches:
                return matches

        overview = self._resolve_overview_chunks(document, query)
        if overview:
            return overview

        return list(
            DocumentChunk.objects.filter(document=document)
            .order_by("chunk_label")[:3]
        )

    def _resolve_overview_chunks(self, document: LegalDocument, query: str) -> List[DocumentChunk]:
        label_hints = [
            "Artículo 1",
            "Artículo 2",
            "Artículo 3",
            "Artículo 4",
            "Artículo 5",
            "Artículo 10",
            "Objeto",
            "Ámbito",
            "Ambito",
        ]

        label_filter = Q()
        for label in label_hints:
            label_filter |= Q(chunk_label__icontains=label)

        matches = list(
            DocumentChunk.objects.filter(document=document)
            .filter(label_filter)
            .order_by("chunk_label")[:5]
        )
        if matches:
            return matches

        normalized_query = self._normalize_text(query)
        if normalized_query:
            keyword_filter = Q(chunk_text__icontains=normalized_query[:40])
            return list(
                DocumentChunk.objects.filter(document=document)
                .filter(keyword_filter)
                .order_by("chunk_label")[:3]
            )

        return []

    @staticmethod
    def _format_forced_chunk(chunk: DocumentChunk) -> Dict[str, Any]:
        return {
            "rank": 0,
            "chunk_id": str(chunk.id),
            "chunk_label": chunk.chunk_label or chunk.chunk_type,
            "chunk_text": chunk.chunk_text,
            "chunk_type": chunk.chunk_type,
            "document_title": chunk.document.doc_title,
            "document_id": chunk.document.doc_id_oficial,
            "document_url": chunk.document.url,
            "source_title": chunk.document.source.titulo,
            "source_priority": chunk.document.source.prioridad,
            "source_naturaleza": chunk.document.source.naturaleza,
            "metadata": chunk.metadata,
            "search_method": "forced_reference",
            "rrf_score": 9999,
            "similarity": 1.0,
            "forced": True,
        }

    @staticmethod
    def _normalize_text(text: str) -> str:
        import unicodedata

        normalized = unicodedata.normalize("NFKD", text.lower())
        normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        normalized = re.sub(r"[^a-z0-9\s]+", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()
