import pytest
from rest_framework.test import APIRequestFactory

from apps.legal_graphrag.models import ChatSession
from apps.legal_graphrag.views_v1_1 import chat_view_v1_1
from apps.legal_graphrag.services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1


@pytest.mark.django_db
def test_orchestrator_merged_query_used(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_V1_1", "1")

    session = ChatSession.objects.create(session_state={
        "schema_version": 1,
        "turn_count": 1,
        "topic_lock": "Fiscal",
        "base_question": "Pregunta base sobre IRPF",
        "last_actionable_user_question": "Pregunta base sobre IRPF",
        "pending_slots": ["location"],
        "slot_values": {},
        "last_answer_brief": None,
    })

    captured = {}

    def fake_answer_query(
        self,
        query,
        area_principal=None,
        max_sources=10,
        forced_area=None,
        question_type=None,
        context_block=None,
        session_id=None,
        trace_context=None,
        **kwargs,
    ):
        captured["query"] = query
        captured["forced_area"] = forced_area
        return {"answer": "ok", "sources": [], "metadata": {}}

    monkeypatch.setattr(LegalRAGEngineV1_1, "answer_query", fake_answer_query)

    factory = APIRequestFactory()
    request = factory.post("/v1_1/chat/", {"query": "Valencia", "session_id": str(session.id)}, format="json")
    response = chat_view_v1_1(request)

    assert response.status_code == 200
    assert "Pregunta base" in captured["query"]
    assert "Contexto adicional" in captured["query"]
    assert captured["forced_area"] == "Fiscal"
