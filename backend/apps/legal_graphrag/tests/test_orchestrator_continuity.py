import pytest
from rest_framework.test import APIRequestFactory

from apps.legal_graphrag.views_v1_1 import chat_view_v1_1
from apps.legal_graphrag.services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1


@pytest.mark.django_db
def test_orchestrator_continuity_conversation(monkeypatch):
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

    # Turn 1
    request1 = factory.post(
        "/api/v1/legal-graphrag/v1_1/chat/",
        {"query": "Facturo a clientes de la UE. ¿Cuándo llevo IVA y cuándo no?"},
        format="json",
        HTTP_X_DEVELOPER_DEBUG="1",
    )
    response1 = chat_view_v1_1(request1)
    session_id = response1.data["session_id"]
    decision1 = response1.data["metadata"]["decision"]
    assert decision1["mode"] == "NEW_QUESTION"
    assert decision1["effective_area"] == "Fiscal"

    # Turn 2
    request2 = factory.post(
        "/api/v1/legal-graphrag/v1_1/chat/",
        {"query": "por ejemplo?", "session_id": session_id},
        format="json",
        HTTP_X_DEVELOPER_DEBUG="1",
    )
    response2 = chat_view_v1_1(request2)
    decision2 = response2.data["metadata"]["decision"]
    assert decision2["mode"] != "CLARIFY"
    assert decision2["mode"] in {"FOLLOWUP_REFERENTIAL", "FOLLOWUP_SLOT_FILL"}

    trace2 = response2.data["metadata"]["developer_debug"]["full_trace"]
    assert trace2["chat_session_db_id"] == session_id
    assert trace2["orchestrator"]["thread_status"] != "no_thread"

    # Turn 3
    request3 = factory.post(
        "/api/v1/legal-graphrag/v1_1/chat/",
        {"query": "y si el cliente es empresa con VAT ID?", "session_id": session_id},
        format="json",
        HTTP_X_DEVELOPER_DEBUG="1",
    )
    response3 = chat_view_v1_1(request3)
    decision3 = response3.data["metadata"]["decision"]
    assert decision3["mode"] != "CLARIFY"
