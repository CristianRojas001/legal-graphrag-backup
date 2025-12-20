import re

from apps.legal_graphrag.services.legal_rag_engine import LegalRAGEngine


def _fake_source(doc_id: str, text: str):
    return {"document_id": doc_id, "chunk_text": text}


def test_validator_abstains_on_unsupported_rate():
    engine = LegalRAGEngine()
    sources = {"normativa": [_fake_source("DOC-1", "Artículo 90 LIVA sin tipos")] }
    answer = "El tipo aplicable es 15% según la ley."

    validated = engine._validate_answer(answer, sources, area_principal="Fiscal", query="IVA concierto")

    assert "No tengo información" in validated  # abstain fallback


def test_validator_allows_supported_rate_and_id():
    engine = LegalRAGEngine()
    sources = {"normativa": [_fake_source("DOC-IVA", "El tipo general del IVA es del 21% (art. 90).")]}
    answer = "El tipo general del IVA es 21% [ID: DOC-IVA]"

    validated = engine._validate_answer(answer, sources, area_principal="Fiscal", query="IVA general")

    # ID remains and answer not replaced by abstain
    assert "[ID: DOC-IVA]" in validated
    assert "No tengo información" not in validated


def test_validator_rejects_rate_not_in_sources_text():
    engine = LegalRAGEngine()
    sources = {"normativa": [_fake_source("DOC-IVA", "El tipo general del IVA es del 21% (art. 90).")]}
    answer = "El tipo general del IVA es 10% [ID: DOC-IVA]"

    validated = engine._validate_answer(answer, sources, area_principal="Fiscal", query="IVA general")

    assert "No tengo información" in validated  # abstain fallback
