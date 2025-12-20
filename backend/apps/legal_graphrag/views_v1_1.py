"""
Legal GraphRAG Views V1.1
Separate entry point for multi-query + judge pipeline.
"""

import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import ChatMessage
from .serializers import ChatRequestSerializer
from .services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1
from .views import (
    _get_or_create_session,
    _persist_chat_messages,
    _is_greeting,
    _is_follow_up_question,
    _get_conversation_context,
)

logger = logging.getLogger(__name__)


@api_view(["POST"])
def chat_view_v1_1(request):
    """
    V1.1 chat endpoint with multi-query retrieval and judge/redo.
    """
    serializer = ChatRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    query = data["query"]

    session = _get_or_create_session(data.get("session_id"), request)

    if _is_greeting(query):
        greeting_response = {
            "answer": "Hola! Soy tu asistente legal. Puedo ayudarte con temas fiscales, laborales, propiedad intelectual y subvenciones.",
            "sources": [],
            "metadata": {"greeting": True, "version": "v1_1"},
        }
        _persist_chat_messages(session, query, greeting_response, None)
        return Response(
            {
                "session_id": str(session.id),
                "answer": greeting_response["answer"],
                "sources": [],
                "metadata": greeting_response["metadata"],
            },
            status=status.HTTP_200_OK,
        )

    is_follow_up = _is_follow_up_question(query)
    if is_follow_up and session.messages.count() > 0:
        conversation_context = _get_conversation_context(session)
        # Keep follow-up logic aligned with V1.0
        import google.generativeai as genai
        from django.conf import settings

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name="gemini-2.5-flash")
        follow_up_prompt = (
            "You are a legal assistant. Answer based only on the conversation history.\n\n"
            f"History:\n{conversation_context}\n\n"
            f"User question: {query}\n"
        )
        try:
            response = model.generate_content(follow_up_prompt)
            follow_up_answer = response.text
        except Exception:
            logger.exception("V1.1 follow-up LLM failed")
            follow_up_answer = "Disculpa, hubo un error al procesar tu pregunta de seguimiento."

        follow_up_result = {
            "answer": follow_up_answer,
            "sources": [],
            "metadata": {"follow_up": True, "used_conversation_context": True, "version": "v1_1"},
        }
        _persist_chat_messages(session, query, follow_up_result, None)
        return Response(
            {
                "session_id": str(session.id),
                "answer": follow_up_result["answer"],
                "sources": [],
                "metadata": follow_up_result["metadata"],
            },
            status=status.HTTP_200_OK,
        )

    engine = LegalRAGEngineV1_1()
    try:
        rag_result = engine.answer_query(
            query=query,
            area_principal=data.get("area_principal") or None,
            max_sources=data.get("max_sources", 10),
        )
    except Exception:
        logger.exception("V1.1 RAG generation failed")
        return Response({"detail": "Failed to generate answer"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    _persist_chat_messages(session, query, rag_result, data.get("area_principal"))

    response_payload = {
        "session_id": str(session.id),
        "answer": rag_result.get("answer", ""),
        "sources": rag_result.get("sources", []),
        "metadata": rag_result.get("metadata", {}),
    }
    return Response(response_payload, status=status.HTTP_200_OK)
