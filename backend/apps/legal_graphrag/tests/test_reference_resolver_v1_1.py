import pytest

from apps.legal_graphrag.models import LegalDocument
from apps.legal_graphrag.services.v1_1.reference_resolver import ExactReferenceResolver


@pytest.mark.django_db
def test_resolver_boe_article_10():
    if not LegalDocument.objects.filter(doc_id_oficial="BOE-A-1978-31229").exists():
        pytest.skip("Constitution not ingested")

    resolver = ExactReferenceResolver()
    results = resolver.resolve("BOE-A-1978-31229 articulo 10")

    assert any(
        r.get("document_id") == "BOE-A-1978-31229"
        and "Artículo 10" in (r.get("chunk_label") or "")
        for r in results
    )


@pytest.mark.django_db
def test_resolver_constitucion_articulo_149():
    if not LegalDocument.objects.filter(doc_id_oficial="BOE-A-1978-31229").exists():
        pytest.skip("Constitution not ingested")

    resolver = ExactReferenceResolver()
    results = resolver.resolve("Constitución española artículo 149")

    assert any(
        r.get("document_id") == "BOE-A-1978-31229"
        and "Artículo 149" in (r.get("chunk_label") or "")
        for r in results
    )


@pytest.mark.django_db
def test_resolver_ley_article_if_present():
    if not LegalDocument.objects.filter(doc_title__icontains="Ley 38/2003").exists():
        pytest.skip("Ley 38/2003 not ingested")

    resolver = ExactReferenceResolver()
    results = resolver.resolve("Ley 38/2003 articulo 14")

    assert any(
        "Ley 38/2003" in (r.get("document_title") or "")
        and "Artículo 14" in (r.get("chunk_label") or "")
        for r in results
    )
