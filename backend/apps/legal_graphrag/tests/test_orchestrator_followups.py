import pytest
from rest_framework.test import APIRequestFactory

from apps.legal_graphrag.views_v1_1 import chat_view_v1_1
from apps.legal_graphrag.services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1


@pytest.mark.django_db
def test_orchestrator_followups_with_memory_summary(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_V1_1", "1")
    monkeypatch.setenv("DEBUG_TRACE", "1")

    def fake_answer_query(self, query, area_principal=None, **kwargs):
        return {
            "answer": "Respuesta base.\n<!--CITED_IDS: -->",
            "sources": [],
            "metadata": {"area_principal": area_principal},
        }

    monkeypatch.setattr(LegalRAGEngineV1_1, "answer_query", fake_answer_query)

    factory = APIRequestFactory()

    request1 = factory.post(
        "/api/v1/legal-graphrag/v1_1/chat/",
        {
            "query": "Facturo a clientes de la UE. ¿Cuándo llevo IVA y cuándo no? (servicios digitales vs servicios artísticos presenciales)",
        },
        format="json",
        HTTP_X_DEVELOPER_DEBUG="1",
    )
    response1 = chat_view_v1_1(request1)
    session_id = response1.data["session_id"]
    assert response1.data["metadata"]["decision"]["mode"] == "NEW_QUESTION"

    request2 = factory.post(
        "/api/v1/legal-graphrag/v1_1/chat/",
        {"query": "por ejemplo?", "session_id": session_id},
        format="json",
        HTTP_X_DEVELOPER_DEBUG="1",
    )
    response2 = chat_view_v1_1(request2)
    decision2 = response2.data["metadata"]["decision"]
    assert decision2["mode"] != "CLARIFY"
    assert decision2.get("merged_query")
    trace2 = response2.data["metadata"]["developer_debug"]["orchestrator_trace"]
    assert trace2["decision"]["mode"].startswith("FOLLOWUP")
    assert trace2["decision"]["merged_query_preview"] is not None
    full_trace2 = response2.data["metadata"]["developer_debug"]["full_trace"]
    assert full_trace2["session"]["state_after"].get("memory_summary")

    request3 = factory.post(
        "/api/v1/legal-graphrag/v1_1/chat/",
        {"query": "dame un ejemplo de eso", "session_id": session_id},
        format="json",
        HTTP_X_DEVELOPER_DEBUG="1",
    )
    response3 = chat_view_v1_1(request3)
    decision3 = response3.data["metadata"]["decision"]
    assert decision3["mode"] != "CLARIFY"

    request4 = factory.post(
        "/api/v1/legal-graphrag/v1_1/chat/",
        {"query": "cliente empresa con VAT ID", "session_id": session_id},
        format="json",
        HTTP_X_DEVELOPER_DEBUG="1",
    )
    response4 = chat_view_v1_1(request4)
    assert response4.data["metadata"]["decision"]["mode"] != "CLARIFY"

    request5 = factory.post(
        "/api/v1/legal-graphrag/v1_1/chat/",
        {"query": "cliente particular en Francia", "session_id": session_id},
        format="json",
        HTTP_X_DEVELOPER_DEBUG="1",
    )
    response5 = chat_view_v1_1(request5)
    assert response5.data["metadata"]["decision"]["mode"] != "CLARIFY"


@pytest.mark.django_db
def test_orchestrator_followups_negative_control(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_V1_1", "1")

    factory = APIRequestFactory()
    request = factory.post(
        "/api/v1/legal-graphrag/v1_1/chat/",
        {"query": "por ejemplo?"},
        format="json",
        HTTP_X_DEVELOPER_DEBUG="1",
    )
    response = chat_view_v1_1(request)
    assert response.data["metadata"]["decision"]["mode"] == "CLARIFY"
