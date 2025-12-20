import time
import uuid

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.legal_graphrag.models import (
    ChatMessage,
    ChatSession,
    CorpusSource,
    DocumentChunk,
    LegalDocument,
)

pytestmark = pytest.mark.django_db


def source_defaults():
    return {
        'prioridad': 'P1',
        'naturaleza': 'Normativa',
        'area_principal': 'Fiscalidad',
        'titulo': 'Base Law',
        'tipo': 'Ley',
        'ambito': 'Nacional',
        'funcion_artisting': 'Cobertura general',
        'id_oficial': f"LAW-{uuid.uuid4()}",
        'url_oficial': 'https://example.com/law',
        'vigencia': 'Vigente',
        'nivel_autoridad': 'Alta',
        'articulos_clave': '1-3',
        'frecuencia_actualizacion': 'Anual',
    }


def create_source(**overrides):
    data = source_defaults()
    data.update(overrides)
    return CorpusSource.objects.create(**data)


def create_document(source=None, **overrides):
    source = source or create_source()
    data = {
        'doc_title': 'Test Document',
        'doc_id_oficial': f"DOC-{uuid.uuid4()}",
        'url': 'https://example.com/document',
        'raw_html': '<p>Test</p>',
    }
    data.update(overrides)
    return LegalDocument.objects.create(source=source, **data)


def sample_embedding(value=0.0):
    return [float(value)] * 768


def create_chunk(document=None, **overrides):
    document = document or create_document()
    data = {
        'chunk_type': 'article',
        'chunk_label': 'Article 1',
        'chunk_text': 'Example chunk text',
        'embedding': sample_embedding(),
    }
    data.update(overrides)
    return DocumentChunk.objects.create(document=document, **data)


def create_user(username='analyst'):
    return User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='password123',
    )


def create_session(user=None, **overrides):
    data = {
        'session_title': 'Compliance review',
        'ip_address': '127.0.0.1',
        'user_agent': 'pytest agent',
    }
    data.update(overrides)
    return ChatSession.objects.create(user=user, **data)


def create_message(session=None, **overrides):
    session = session or create_session()
    data = {
        'role': 'user',
        'content': 'How does this affect SMEs?',
    }
    data.update(overrides)
    return ChatMessage.objects.create(session=session, **data)


class TestCorpusSource:
    def test_create_corpus_source_with_all_fields(self):
        source = create_source(
            titulo='Test Law',
            tipo='Ley orgánica',
            ambito='Estatal',
            funcion_artisting='Cobertura base',
            vigencia='2024',
            nivel_autoridad='Alta',
            articulos_clave='1-10',
            frecuencia_actualizacion='Anual',
        )

        assert source.estado == 'pending'
        assert str(source) == '[P1] Test Law'

    def test_prioridad_choices_validation(self):
        data = source_defaults()
        data['prioridad'] = 'PX'
        source = CorpusSource(**data)

        with pytest.raises(ValidationError):
            source.full_clean()

    def test_estado_choices_validation(self):
        data = source_defaults()
        data['estado'] = 'unknown'
        source = CorpusSource(**data)

        with pytest.raises(ValidationError):
            source.full_clean()

    def test_id_oficial_is_unique(self):
        create_source(id_oficial='LAW-100')

        with pytest.raises(IntegrityError):
            create_source(id_oficial='LAW-100')

    def test_default_estado_is_pending(self):
        source = create_source()
        assert source.estado == 'pending'

    def test_ordering_by_prioridad_area_and_titulo(self):
        s1 = create_source(prioridad='P2', area_principal='B', titulo='Beta', id_oficial='ORDER-1')
        s2 = create_source(prioridad='P1', area_principal='C', titulo='Gamma', id_oficial='ORDER-2')
        s3 = create_source(prioridad='P1', area_principal='A', titulo='Alpha', id_oficial='ORDER-3')

        ordered_titles = list(CorpusSource.objects.values_list('titulo', flat=True))
        assert ordered_titles == [s3.titulo, s2.titulo, s1.titulo]


class TestLegalDocument:
    def test_create_document_and_str_representation(self):
        source = create_source()
        doc = create_document(source=source, doc_title='BOE summary', doc_id_oficial='DOC-1')

        assert doc.source == source
        assert str(doc) == 'BOE summary (DOC-1)'

    def test_uuid_primary_key_auto_generation(self):
        doc = create_document()
        assert isinstance(doc.id, uuid.UUID)

    def test_doc_id_oficial_uniqueness(self):
        create_document(doc_id_oficial='DOC-100')

        with pytest.raises(IntegrityError):
            create_document(doc_id_oficial='DOC-100')

    def test_metadata_default_is_dict(self):
        doc = create_document(doc_id_oficial='DOC-200')
        assert doc.metadata == {}

    def test_cascade_delete_with_source(self):
        doc = create_document()
        source = doc.source
        source.delete()

        assert not LegalDocument.objects.filter(id=doc.id).exists()


class TestDocumentChunk:
    def test_embedding_field_accepts_vector(self):
        embedding = sample_embedding(0.5)
        chunk = create_chunk(embedding=embedding)

        assert chunk.embedding == embedding

    def test_cascade_delete_with_document(self):
        doc = create_document()
        chunk = create_chunk(document=doc)
        doc.delete()

        assert not DocumentChunk.objects.filter(id=chunk.id).exists()

    def test_metadata_jsonfield_defaults_to_dict(self):
        chunk = create_chunk()
        assert chunk.metadata == {}

    def test_str_includes_label_and_document_title(self):
        doc = create_document(doc_title='Ley General Tributaria', doc_id_oficial='DOC-STR')
        chunk = create_chunk(document=doc, chunk_label='Artículo 5')

        assert str(chunk) == 'Artículo 5 - Ley General Tributaria'


class TestChatSession:
    def test_create_session_without_user(self):
        session = create_session()
        assert session.user is None

    def test_create_session_with_user(self):
        user = create_user('auditor')
        session = create_session(user=user, session_title='Auditor session')

        assert session.user == user
        assert session.session_title == 'Auditor session'

    def test_created_at_auto_set(self):
        session = create_session()
        assert session.created_at is not None

    def test_updated_at_auto_updates(self):
        session = create_session()
        original_updated_at = session.updated_at

        time.sleep(0.01)
        session.session_title = 'Updated session'
        session.save()
        session.refresh_from_db()

        assert session.updated_at > original_updated_at


class TestChatMessage:
    def test_create_user_message(self):
        session = create_session()
        message = create_message(session=session, role='user', content='Necesito ayuda')

        assert message.session == session
        assert message.sources == []

    def test_create_assistant_message_with_sources(self):
        session = create_session()
        message = create_message(
            session=session,
            role='assistant',
            content='Aquí tienes las fuentes',
            sources=[{'id': 'LAW-1', 'title': 'Constitución'}],
        )

        assert message.sources[0]['id'] == 'LAW-1'

    def test_role_validation_only_allows_user_or_assistant(self):
        session = create_session()
        message = ChatMessage(session=session, role='system', content='No permitido')

        with pytest.raises(ValidationError):
            message.full_clean()

    def test_sources_default_to_list(self):
        message = create_message(role='assistant')
        assert message.sources == []

    def test_feedback_rating_validation(self):
        session = create_session()
        message = ChatMessage(session=session, role='assistant', content='Hola', feedback_rating=3)

        with pytest.raises(ValidationError):
            message.full_clean()
