from apps.legal_graphrag.services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1


def _engine():
    return LegalRAGEngineV1_1.__new__(LegalRAGEngineV1_1)


def test_extract_cited_ids_html_comment():
    engine = _engine()
    answer = "Texto\n<!--CITED_IDS: BOE-A-2007-12345, BOE-A-1992-28740 -->"
    ids = engine._extract_cited_ids(answer)
    assert ids == {"BOE-A-2007-12345", "BOE-A-1992-28740"}


def test_extract_cited_ids_empty_comment():
    engine = _engine()
    answer = "Texto\n<!--CITED_IDS: -->"
    ids = engine._extract_cited_ids(answer)
    assert ids == set()


def test_extract_cited_ids_fallback_markers():
    engine = _engine()
    answer = "Texto con [ID: BOE-A-2007-12345] y [ID: BOE-A-1992-28740]"
    ids = engine._extract_cited_ids(answer)
    assert ids == {"BOE-A-2007-12345", "BOE-A-1992-28740"}


def test_extract_cited_ids_no_comment_or_markers():
    engine = _engine()
    answer = "Texto sin citas"
    ids = engine._extract_cited_ids(answer)
    assert ids == set()


def test_format_sources_marks_cited_and_orders_first():
    engine = _engine()
    sources = {
        "normativa": [
            {
                "document_id": "BOE-A-2007-12345",
                "document_title": "Ley X",
                "document_url": "https://example.com/x",
                "source_naturaleza": "Normativa",
                "rrf_score": 0.2,
                "chunk_text": "Texto X",
                "chunk_label": "Art 1",
            },
            {
                "document_id": "BOE-A-1992-28740",
                "document_title": "Ley Y",
                "document_url": "https://example.com/y",
                "source_naturaleza": "Normativa",
                "rrf_score": 0.9,
                "chunk_text": "Texto Y",
                "chunk_label": "Art 2",
            },
        ]
    }
    cited_ids = {"BOE-A-2007-12345"}

    formatted = engine._format_sources(sources, cited_ids)

    assert formatted[0]["id"] == "BOE-A-2007-12345"
    assert formatted[0]["is_cited"] is True
    assert formatted[1]["id"] == "BOE-A-1992-28740"
    assert formatted[1]["is_cited"] is False
