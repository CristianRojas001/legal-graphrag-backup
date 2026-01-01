import pytest
from rest_framework.test import APIRequestFactory

from apps.legal_graphrag.models import AnswerFeedbackEvent, ChatMessage, ChatSession
from apps.legal_graphrag.views import feedback_view


@pytest.mark.django_db
def test_feedback_vote_requires_value():
    factory = APIRequestFactory()
    request = factory.post(
        "/api/v1/legal-graphrag/feedback/",
        {"message_id": "msg-1", "event_type": "vote"},
        format="json",
    )
    response = feedback_view(request)
    assert response.status_code == 400


@pytest.mark.django_db
def test_feedback_invalid_event_type():
    factory = APIRequestFactory()
    request = factory.post(
        "/api/v1/legal-graphrag/feedback/",
        {"message_id": "msg-1", "event_type": "other"},
        format="json",
    )
    response = feedback_view(request)
    assert response.status_code == 400


@pytest.mark.django_db
def test_feedback_vote_inserts_row():
    session = ChatSession.objects.create()
    assistant = ChatMessage.objects.create(
        session=session,
        role="assistant",
        content="Respuesta",
    )

    factory = APIRequestFactory()
    request = factory.post(
        "/api/v1/legal-graphrag/feedback/",
        {
            "message_id": str(assistant.id),
            "event_type": "vote",
            "vote_value": 1,
            "session_id": str(session.id),
            "conversation_id": str(session.id),
        },
        format="json",
    )
    response = feedback_view(request)

    assert response.status_code in {200, 201}
    assert AnswerFeedbackEvent.objects.filter(
        message_id=str(assistant.id),
        event_type="vote",
        vote_value=1,
    ).exists()


@pytest.mark.django_db
def test_feedback_copy_inserts_row():
    session = ChatSession.objects.create()
    assistant = ChatMessage.objects.create(
        session=session,
        role="assistant",
        content="Respuesta",
    )

    factory = APIRequestFactory()
    request = factory.post(
        "/api/v1/legal-graphrag/feedback/",
        {
            "message_id": str(assistant.id),
            "event_type": "copy",
            "session_id": str(session.id),
            "conversation_id": str(session.id),
        },
        format="json",
    )
    response = feedback_view(request)

    assert response.status_code == 201
    assert AnswerFeedbackEvent.objects.filter(
        message_id=str(assistant.id),
        event_type="copy",
    ).exists()
