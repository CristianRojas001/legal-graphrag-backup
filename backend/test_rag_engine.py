"""
Smoke tests for Legal RAG Engine
Runs a few common artist queries through the RAG pipeline and checks that answers/sources are returned.
"""

import logging
import os
import sys
import django
import pytest

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')
django.setup()

from apps.legal_graphrag.services.legal_rag_engine import LegalRAGEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "query,area",
    [
        ("¿Puedo deducir gastos de home studio en el IRPF?", "Fiscal"),
        ("¿Qué IVA aplico si vendo un cuadro a una empresa?", "Fiscal"),
        ("¿Cómo registro mis derechos de autor?", "Propiedad Intelectual"),
        ("¿Necesito darme de alta como autónomo si soy artista?", "Laboral"),
        ("¿Qué es el mecenazgo cultural?", None),
    ],
)
def test_rag_query_smoke(query: str, area: str | None):
    """Smoke test: RAG returns an answer and sources for common artist queries."""
    engine = LegalRAGEngine()
    result = engine.answer_query(query=query, area_principal=area)

    assert result is not None
    assert isinstance(result.get("answer"), str)
    assert isinstance(result.get("sources"), list)
    # Ensure some content is returned
    assert len(result["answer"]) > 10
    # Allow zero sources if none are found, but ensure key exists
    assert "sources" in result
