"""
Legal GraphRAG Views
API endpoints for legal document search and chat.
"""

import ipaddress
import logging
from typing import Optional

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import ChatSession, ChatMessage, CorpusSource
from .serializers import (
    ChatRequestSerializer,
    SearchRequestSerializer,
    CorpusSourceSerializer,
)
from .services.legal_rag_engine import LegalRAGEngine
from .services.legal_search_engine import LegalSearchEngine

logger = logging.getLogger(__name__)


def _safe_ip(ip_value: Optional[str]) -> Optional[str]:
    """Return a valid IP string or None."""
    if not ip_value:
        return None
    try:
        ipaddress.ip_address(ip_value)
        return ip_value
    except ValueError:
        return None


def _get_client_ip(request) -> Optional[str]:
    """Extract client IP from headers in a safe way."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        candidate = forwarded.split(',')[0].strip()
        return _safe_ip(candidate)
    return _safe_ip(request.META.get('REMOTE_ADDR'))


def _get_or_create_session(session_id: Optional[str], request) -> ChatSession:
    """Reuse an existing session or create a new one for the request."""
    if session_id:
        existing = ChatSession.objects.filter(id=session_id).first()
        if existing:
            return existing

    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    return ChatSession.objects.create(
        user=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
        ip_address=_get_client_ip(request),
        user_agent=user_agent,
    )


def _persist_chat_messages(session: ChatSession, query: str, rag_result: dict, area_principal: Optional[str]) -> None:
    """Store user and assistant messages for the chat session."""
    try:
        ChatMessage.objects.create(
            session=session,
            role='user',
            content=query,
            metadata={'area_principal': area_principal},
        )
        ChatMessage.objects.create(
            session=session,
            role='assistant',
            content=rag_result.get('answer', ''),
            sources=rag_result.get('sources', []),
            metadata=rag_result.get('metadata', {}),
        )
    except Exception:
        # Do not fail the endpoint if persistence fails; just log it.
        logger.exception("Failed to persist chat messages for session %s", session.id)


def _is_greeting(query: str) -> bool:
    """Check if query is a casual greeting or chitchat."""
    greetings = [
        'hola', 'hello', 'hi', 'hey', 'buenos dias', 'buenas tardes', 'buenas noches',
        'como estas', 'que tal', 'como va', 'que pasa', 'como te va',
        'gracias', 'thanks', 'muchas gracias', 'ok', 'vale', 'de acuerdo',
        'adios', 'chao', 'hasta luego', 'nos vemos', 'bye',
    ]
    query_lower = query.lower().strip()
    return any(greeting in query_lower for greeting in greetings) and len(query_lower.split()) < 10


def _is_follow_up_question(query: str) -> bool:
    """Check if query is a follow-up question about previously retrieved data."""
    follow_up_patterns = [
        'y si', 'pero si', 'entonces', 'en ese caso', 'y como', 'y cuando', 'y donde',
        'y que', 'y cual', 'y quien', 'y cuanto', 'y por que',
        'puedes explicar', 'explica', 'me puedes decir', 'mas sobre', 'mas informacion',
        'por que', 'como se', 'donde dice', 'cual es', 'que significa',
        'en la fuente', 'en el documento', 'en la ley', 'en el articulo',
    ]
    query_lower = query.lower().strip()
    # Short queries with question words are likely follow-ups
    is_short_question = len(query_lower.split()) < 15 and any(q in query_lower for q in ['?', 'por que', 'como', 'cuando', 'donde', 'cual', 'quien', 'cuanto'])
    has_follow_up_pattern = any(pattern in query_lower for pattern in follow_up_patterns)
    return has_follow_up_pattern or (is_short_question and len(query_lower.split()) < 8)


def _get_conversation_context(session: ChatSession, limit: int = 5) -> str:
    """Retrieve recent conversation history for context."""
    try:
        recent_messages = ChatMessage.objects.filter(
            session=session
        ).order_by('-created_at')[:limit * 2]  # Get last N exchanges (user + assistant pairs)

        context_lines = []
        for msg in reversed(recent_messages):
            role_label = "Usuario" if msg.role == 'user' else "Asistente"
            context_lines.append(f"{role_label}: {msg.content[:500]}")

        return "\n\n".join(context_lines) if context_lines else ""
    except Exception as e:
        logger.error(f"Failed to retrieve conversation context: {str(e)}")
        return ""


@api_view(['POST'])
def chat_view(request):
    """
    Run the Legal RAG Engine and return an answer with citations.
    Detects casual greetings/chitchat and responds without searching.
    """
    serializer = ChatRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    query = data['query']

    session = _get_or_create_session(data.get('session_id'), request)

    # Check if this is a casual greeting/chitchat
    if _is_greeting(query):
        greeting_response = {
            'answer': '¡Hola! Soy tu asistente legal especializado en normativa para artistas y profesionales culturales en España. Puedo ayudarte con preguntas sobre:\n\n- **Fiscal**: IRPF, IVA, deducciones, retenciones\n- **Laboral**: Contratos, autónomos, Seguridad Social\n- **Propiedad Intelectual**: Derechos de autor, SGAE, licencias\n- **Subvenciones**: Ayudas, becas, convocatorias\n\n¿En qué puedo ayudarte hoy?',
            'sources': [],
            'metadata': {'greeting': True}
        }

        _persist_chat_messages(session, query, greeting_response, None)

        return Response({
            'session_id': str(session.id),
            'answer': greeting_response['answer'],
            'sources': [],
            'metadata': greeting_response['metadata'],
        }, status=status.HTTP_200_OK)

    # Check if this is a follow-up question (reference conversation context)
    is_follow_up = _is_follow_up_question(query)

    # For follow-up questions, use conversation context instead of new search
    if is_follow_up and session.messages.count() > 0:
        conversation_context = _get_conversation_context(session)

        # Use LLM to answer based on conversation history
        import google.generativeai as genai
        from django.conf import settings

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name='gemini-2.5-flash')

        follow_up_prompt = f"""Eres un asistente legal especializado. El usuario tiene una pregunta de seguimiento sobre una conversación anterior.

**Historial de conversación:**
{conversation_context}

**Nueva pregunta del usuario:** {query}

**Instrucciones:**
- Responde basándote SOLO en la información del historial de conversación anterior
- Si la pregunta requiere nueva información legal que NO está en el historial, indícalo claramente
- Mantén el mismo formato profesional y las advertencias legales

Responde de forma directa y concisa."""

        try:
            response = model.generate_content(follow_up_prompt)
            follow_up_answer = response.text
        except Exception as e:
            logger.error(f"Follow-up LLM failed: {str(e)}")
            follow_up_answer = "Disculpa, hubo un error al procesar tu pregunta de seguimiento. ¿Podrías reformularla?"

        follow_up_result = {
            'answer': follow_up_answer,
            'sources': [],
            'metadata': {'follow_up': True, 'used_conversation_context': True}
        }

        _persist_chat_messages(session, query, follow_up_result, None)

        return Response({
            'session_id': str(session.id),
            'answer': follow_up_result['answer'],
            'sources': [],
            'metadata': follow_up_result['metadata'],
        }, status=status.HTTP_200_OK)

    # Otherwise, run full RAG pipeline
    engine = LegalRAGEngine()
    try:
        rag_result = engine.answer_query(
            query=query,
            area_principal=data.get('area_principal') or None,
            max_sources=data.get('max_sources', 10),
        )
    except Exception:
        logger.exception("RAG generation failed")
        return Response({'detail': 'Failed to generate answer'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    _persist_chat_messages(session, query, rag_result, data.get('area_principal'))

    response_payload = {
        'session_id': str(session.id),
        'answer': rag_result.get('answer', ''),
        'sources': rag_result.get('sources', []),
        'metadata': rag_result.get('metadata', {}),
    }
    return Response(response_payload, status=status.HTTP_200_OK)


@api_view(['POST'])
def search_view(request):
    """
    Expose hybrid search results for a query.
    """
    serializer = SearchRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    engine = LegalSearchEngine()
    results = engine.hybrid_search(query=data['query'], limit=data.get('limit', 10))

    return Response(
        {
            'count': len(results),
            'results': results,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
def sources_view(request):
    """
    List corpus sources with optional filtering.
    """
    qs = CorpusSource.objects.all().order_by('prioridad', 'titulo')

    prioridad = request.query_params.get('prioridad')
    if prioridad:
        qs = qs.filter(prioridad=prioridad)

    naturaleza = request.query_params.get('naturaleza')
    if naturaleza:
        qs = qs.filter(naturaleza=naturaleza)

    area = request.query_params.get('area_principal')
    if area:
        qs = qs.filter(area_principal=area)

    estado = request.query_params.get('estado')
    if estado:
        qs = qs.filter(estado=estado)

    serializer = CorpusSourceSerializer(qs, many=True)
    return Response(
        {
            'count': len(serializer.data),
            'results': serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
def health_view(request):
    """
    Health check endpoint for monitoring.
    """
    from django.db import connection

    try:
        # Test database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        db_status = "unhealthy"

    # Check corpus source count
    try:
        source_count = CorpusSource.objects.count()
        ingested_count = CorpusSource.objects.filter(estado='ingested').count()
    except Exception:
        source_count = 0
        ingested_count = 0

    health_data = {
        'status': 'healthy' if db_status == 'healthy' else 'degraded',
        'database': db_status,
        'corpus': {
            'total_sources': source_count,
            'ingested_sources': ingested_count,
        },
        'version': '1.0.0',
    }

    response_status = status.HTTP_200_OK if db_status == 'healthy' else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(health_data, status=response_status)
