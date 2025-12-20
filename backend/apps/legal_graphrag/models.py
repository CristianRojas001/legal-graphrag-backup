"""
Legal GraphRAG Models
Database models for legal document ingestion, search, and chat.
"""

from django.db import models
from django.contrib.auth.models import User
from pgvector.django import VectorField
import uuid


class CorpusSource(models.Model):
    """Catalog of legal sources to ingest"""

    PRIORIDAD_CHOICES = [
        ('P1', 'P1 - Core'),
        ('P2', 'P2 - Important'),
        ('P3', 'P3 - Edge cases'),
    ]

    ESTADO_CHOICES = [
        ('pending', 'Pending'),
        ('ingesting', 'Ingesting'),
        ('ingested', 'Ingested'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]

    # Priority & Classification
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, db_index=True)
    naturaleza = models.CharField(max_length=50, db_index=True)
    area_principal = models.CharField(max_length=100, db_index=True, null=True, blank=True)

    # Document Metadata
    titulo = models.TextField()
    tipo = models.CharField(max_length=100, null=True, blank=True)
    ambito = models.CharField(max_length=50, null=True, blank=True)
    funcion_artisting = models.TextField(null=True, blank=True)

    # Official Identifiers
    id_oficial = models.CharField(max_length=100, unique=True)
    url_oficial = models.TextField()

    # Legal Context
    vigencia = models.TextField(null=True, blank=True)
    nivel_autoridad = models.CharField(max_length=50, null=True, blank=True)
    articulos_clave = models.TextField(null=True, blank=True)
    frecuencia_actualizacion = models.CharField(max_length=50, null=True, blank=True)

    # Ingestion Status
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pending', db_index=True)
    last_ingested_at = models.DateTimeField(null=True, blank=True)
    ingestion_error = models.TextField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'legal_corpus_sources'
        ordering = ['prioridad', 'area_principal', 'titulo']
        indexes = [
            models.Index(fields=['prioridad', 'estado']),
            models.Index(fields=['naturaleza', 'area_principal']),
        ]

    def __str__(self):
        return f"[{self.prioridad}] {self.titulo}"


class LegalDocument(models.Model):
    """Ingested legal document"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Foreign Key
    source = models.ForeignKey(CorpusSource, on_delete=models.CASCADE, related_name='documents')

    # Document Identity
    doc_title = models.TextField()
    doc_id_oficial = models.CharField(max_length=100, unique=True)
    url = models.TextField()

    # Content
    raw_html = models.TextField(null=True, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'legal_documents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source']),
            models.Index(fields=['doc_id_oficial']),
        ]

    def __str__(self):
        return f"{self.doc_title} ({self.doc_id_oficial})"


class DocumentChunk(models.Model):
    """Searchable chunk with embedding"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Foreign Key
    document = models.ForeignKey(LegalDocument, on_delete=models.CASCADE, related_name='chunks')

    # Chunk Identity
    chunk_type = models.CharField(max_length=50)  # article, section, etc.
    chunk_label = models.TextField(null=True, blank=True)

    # Content
    chunk_text = models.TextField()

    # Vector Embedding (pgvector)
    embedding = VectorField(dimensions=768)

    # Metadata
    metadata = models.JSONField(default=dict)

    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'legal_document_chunks'
        ordering = ['document', 'chunk_type']
        indexes = [
            models.Index(fields=['document']),
            models.Index(fields=['chunk_type']),
        ]

    def __str__(self):
        return f"{self.chunk_label or self.chunk_type} - {self.document.doc_title}"


class ChatSession(models.Model):
    """User chat session"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # User (nullable for anonymous)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='legal_chat_sessions')

    # Session Metadata
    session_title = models.TextField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'legal_chat_sessions'
        ordering = ['-updated_at']

    def __str__(self):
        return f"Session {self.id} - {self.created_at.strftime('%Y-%m-%d')}"


class ChatMessage(models.Model):
    """Individual chat message"""

    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Foreign Key
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')

    # Message Content
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()

    # Sources (for assistant messages)
    sources = models.JSONField(default=list)

    # Metadata
    metadata = models.JSONField(default=dict)

    # Feedback
    feedback_rating = models.IntegerField(null=True, blank=True, choices=[(1, 'Bad'), (5, 'Good')])
    feedback_comment = models.TextField(null=True, blank=True)

    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'legal_chat_messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        return f"[{self.role}] {self.content[:50]}"
