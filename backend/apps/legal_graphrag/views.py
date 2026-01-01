"""
Legal GraphRAG Views
API endpoints for legal document search and chat.
"""

import hashlib
import ipaddress
import logging
import re
import uuid
from typing import Optional, List

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import AnswerFeedbackEvent, ChatSession, ChatMessage, CorpusSource
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


def _get_or_create_session_with_meta(session_id: Optional[str], request) -> tuple[ChatSession, str, bool]:
    """
    Reuse an existing session or create a new one for the request.
    Returns (session, lookup_method, is_new_session).
    """
    if session_id:
        existing = ChatSession.objects.filter(id=session_id).first()
        if existing:
            return existing, "session_id", False

    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    session = ChatSession.objects.create(
        user=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
        ip_address=_get_client_ip(request),
        user_agent=user_agent,
    )
    return session, "created_new", True


def _persist_chat_messages(session: ChatSession, query: str, rag_result: dict, area_principal: Optional[str]) -> dict:
    """Store user and assistant messages for the chat session."""
    try:
        user_msg = ChatMessage.objects.create(
            session=session,
            role='user',
            content=query,
            metadata={'area_principal': area_principal},
        )
        assistant_msg = ChatMessage.objects.create(
            session=session,
            role='assistant',
            content=rag_result.get('answer', ''),
            sources=rag_result.get('sources', []),
            metadata=rag_result.get('metadata', {}),
        )
        return {
            "user_message_id": str(user_msg.id),
            "assistant_message_id": str(assistant_msg.id),
        }
    except Exception:
        # Do not fail the endpoint if persistence fails; just log it.
        logger.exception("Failed to persist chat messages for session %s", session.id)
    return {}


def _is_greeting(query: str) -> bool:
    """Check if query is a casual greeting or chitchat."""
    token_greetings = {
        "hola", "hello", "hi", "hey", "gracias", "thanks", "ok", "vale",
        "adios", "chao", "bye",
    }
    phrase_greetings = [
        "buenos dias", "buenas tardes", "buenas noches",
        "como estas", "que tal", "como va", "que pasa", "como te va",
        "muchas gracias", "de acuerdo", "hasta luego", "nos vemos",
    ]
    query_lower = query.lower().strip()
    if len(query_lower.split()) >= 10:
        return False
    tokens = re.findall(r"\b\w+\b", query_lower)
    if any(token in token_greetings for token in tokens):
        return True
    return any(phrase in query_lower for phrase in phrase_greetings)


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


def _extract_para_afinar_questions(answer: str) -> List[str]:
    """Extract bullet questions from a 'Para afinar' section if present."""
    if not answer:
        return []

    lines = answer.splitlines()
    start_idx = None
    for idx, line in enumerate(lines):
        if "para afinar" in line.lower():
            start_idx = idx + 1
            break

    if start_idx is None:
        return []

    questions = []
    for line in lines[start_idx:]:
        stripped = line.strip()
        if not stripped:
            if questions:
                break
            continue
        if stripped.startswith("**"):
            break
        if stripped.startswith(("-", "•", "*")):
            questions.append(stripped.lstrip("-•* ").strip())

    return questions


def _derive_pending_slots(questions: List[str]) -> List[str]:
    """Map clarifying questions to simple slot categories."""
    slot_map = {
        "location": ["ccaa", "comunidad", "provincia", "ciudad", "municipio", "localidad", "donde"],
        "entity_type": ["autonomo", "autónomo", "sl", "s.l", "sociedad", "asociacion", "asociación", "empresa", "entidad"],
        "period": ["fecha", "fechas", "periodo", "período", "anio", "año", "ejercicio", "202"],
    }

    pending = []
    for question in questions:
        normalized = question.lower()
        for slot, tokens in slot_map.items():
            if any(token in normalized for token in tokens) and slot not in pending:
                pending.append(slot)
    return pending


def _build_pending_metadata(answer: str, pending_question: str, area_principal: Optional[str]) -> Optional[dict]:
    """Build metadata for slot-fill follow-ups based on 'Para afinar'."""
    questions = _extract_para_afinar_questions(answer)
    pending_slots = _derive_pending_slots(questions)
    if not pending_slots:
        return None

    return {
        "pending_slots": pending_slots,
        "pending_question": pending_question,
        "pending_topic": area_principal,
    }


def _infer_slot_from_reply(reply: str, pending_slots: List[str]) -> str:
    """Infer which slot a short reply likely fills."""
    normalized = reply.lower().strip()
    if re.search(r"\b(19|20)\d{2}\b", normalized):
        return "period"
    if any(token in normalized for token in ["autonomo", "autónomo", "sl", "s.l", "sociedad", "asociacion", "asociación"]):
        return "entity_type"
    if "location" in pending_slots:
        return "location"
    return pending_slots[0] if pending_slots else "context"


def _is_slot_fill_reply(reply: str, pending_slots: List[str]) -> bool:
    """Detect short replies meant to fill pending slots."""
    if not pending_slots:
        return False
    tokens = reply.strip().split()
    return len(tokens) <= 8 and "?" not in reply


def _merge_pending_question(pending_question: str, slot_name: str, reply: str) -> str:
    """Merge a short reply into the previous question for retrieval."""
    return f"{pending_question}\nContexto adicional: {slot_name}={reply}"


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

        message_ids = _persist_chat_messages(session, query, greeting_response, None)
        if message_ids:
            greeting_response.setdefault('metadata', {})
            greeting_response['metadata'].update(message_ids)

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

        message_ids = _persist_chat_messages(session, query, follow_up_result, None)
        if message_ids:
            follow_up_result.setdefault('metadata', {})
            follow_up_result['metadata'].update(message_ids)

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

    message_ids = _persist_chat_messages(session, query, rag_result, data.get('area_principal'))
    if message_ids:
        rag_result.setdefault('metadata', {})
        rag_result['metadata'].update(message_ids)

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


@api_view(['POST'])
def feedback_view(request):
    """
    Persist feedback events for assistant answers.
    """
    payload = request.data or {}
    message_id = payload.get('message_id')
    event_type = payload.get('event_type')
    vote_value = payload.get('vote_value')
    conversation_id = payload.get('conversation_id')
    answer_text = payload.get('answer_text')
    session_id = payload.get('session_id')

    if not isinstance(message_id, str) or not message_id.strip():
        return Response({'error': 'message_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    if event_type not in {'vote', 'copy'}:
        return Response({'error': 'event_type must be vote or copy'}, status=status.HTTP_400_BAD_REQUEST)
    if event_type == 'vote' and vote_value not in (-1, 1):
        return Response({'error': 'vote_value must be 1 or -1'}, status=status.HTTP_400_BAD_REQUEST)

    message = ChatMessage.objects.filter(id=message_id).select_related('session').first()
    if message and not conversation_id:
        conversation_id = str(message.session.id)
    if not session_id:
        session_id = request.COOKIES.get('legal_feedback_session_id')
    if not session_id:
        session_id = str(uuid.uuid4())

    user_id = None
    if getattr(request, 'user', None) and request.user.is_authenticated:
        user_id = str(request.user.id)

    answer_hash = None
    if isinstance(answer_text, str) and answer_text.strip():
        answer_hash = hashlib.sha256(answer_text.encode('utf-8')).hexdigest()

    route = request.path

    if event_type == 'vote':
        filter_kwargs = {'event_type': 'vote', 'message_id': message_id}
        if session_id:
            filter_kwargs['session_id'] = session_id
        elif conversation_id:
            filter_kwargs['conversation_id'] = conversation_id

        existing = AnswerFeedbackEvent.objects.filter(**filter_kwargs).first()
        if existing:
            existing.vote_value = vote_value
            existing.answer_hash = answer_hash or existing.answer_hash
            existing.route = route
            existing.user_id = user_id or existing.user_id
            existing.conversation_id = conversation_id or existing.conversation_id
            existing.session_id = session_id or existing.session_id
            existing.save(update_fields=[
                'vote_value',
                'answer_hash',
                'route',
                'user_id',
                'conversation_id',
                'session_id',
            ])
            response = Response({'ok': True}, status=status.HTTP_200_OK)
        else:
            AnswerFeedbackEvent.objects.create(
                user_id=user_id,
                session_id=session_id,
                conversation_id=conversation_id,
                message_id=message_id,
                answer_hash=answer_hash,
                event_type='vote',
                vote_value=vote_value,
                route=route,
            )
            response = Response({'ok': True}, status=status.HTTP_201_CREATED)
    else:
        AnswerFeedbackEvent.objects.create(
            user_id=user_id,
            session_id=session_id,
            conversation_id=conversation_id,
            message_id=message_id,
            answer_hash=answer_hash,
            event_type='copy',
            vote_value=None,
            route=route,
        )
        response = Response({'ok': True}, status=status.HTTP_201_CREATED)

    if 'legal_feedback_session_id' not in request.COOKIES:
        response.set_cookie(
            'legal_feedback_session_id',
            session_id,
            httponly=True,
            samesite='Lax',
        )
    return response
