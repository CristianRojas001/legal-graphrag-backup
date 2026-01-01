import os

import pytest
from rest_framework.test import APIRequestFactory

from apps.legal_graphrag.views_v1_1 import chat_view_v1_1


def _skip_if_missing():
    if os.getenv("RUN_EVAL_REGRESSIONS") != "1":
        pytest.skip("RUN_EVAL_REGRESSIONS not enabled")
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")


@pytest.mark.django_db
def test_eval_regression_f08():
    _skip_if_missing()
    factory = APIRequestFactory()
    request = factory.post(
        "/api/v1/legal-graphrag/v1_1/chat/",
        {
            "query": "Soy fotógrafo y compro equipo caro. ¿Cómo funciona la amortización y en qué casos me conviene?",
            "case_id": "F08",
            "turn": 1,
        },
        format="json",
        HTTP_X_DEVELOPER_DEBUG="1",
    )
    response = chat_view_v1_1(request)
    assert response.status_code == 200
    meta = response.data.get("metadata") or {}
    assert meta.get("abstained") is False
    cited = set(meta.get("cited_ids") or [])
    assert "BOE-A-2006-20764" in cited
    assert response.data.get("answer")


@pytest.mark.django_db
def test_eval_regression_l14():
    _skip_if_missing()
    factory = APIRequestFactory()
    request = factory.post(
        "/api/v1/legal-graphrag/v1_1/chat/",
        {
            "query": "¿Cuándo un contrato artístico puede ser temporal y qué límites hay?",
            "case_id": "L14",
            "turn": 1,
        },
        format="json",
        HTTP_X_DEVELOPER_DEBUG="1",
    )
    response = chat_view_v1_1(request)
    assert response.status_code == 200
    meta = response.data.get("metadata") or {}
    assert meta.get("abstained") is False
    cited = set(meta.get("cited_ids") or [])
    assert cited.intersection({"BOE-A-1985-17303", "BOE-A-2022-4583"})
    assert response.data.get("answer")


@pytest.mark.django_db
def test_eval_regression_p29():
    _skip_if_missing()
    factory = APIRequestFactory()
    request = factory.post(
        "/api/v1/legal-graphrag/v1_1/chat/",
        {
            "query": "Si subo un vídeo con música de terceros, ¿qué riesgos tengo (Content ID vs infracción)?",
            "case_id": "P29",
            "turn": 1,
        },
        format="json",
        HTTP_X_DEVELOPER_DEBUG="1",
    )
    response = chat_view_v1_1(request)
    assert response.status_code == 200
    meta = response.data.get("metadata") or {}
    assert meta.get("abstained") is False
    cited = set(meta.get("cited_ids") or [])
    sources = response.data.get("sources") or []
    source_ids = {src.get("id") for src in sources if src.get("id")}
    if "CELEX:32001L0029" in source_ids:
        assert cited.intersection({"BOE-A-1996-8930", "CELEX:32001L0029"})
    else:
        assert "BOE-A-1996-8930" in cited
        answer = (response.data.get("answer") or "").lower()
        assert "directiva" in answer
    assert response.data.get("answer")
