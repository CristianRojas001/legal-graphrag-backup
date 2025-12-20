"""
Legal GraphRAG Admin Configuration
Django admin interface for managing legal documents and chat.
"""

from django.contrib import admin
from .models import CorpusSource, LegalDocument, DocumentChunk, ChatSession, ChatMessage


@admin.register(CorpusSource)
class CorpusSourceAdmin(admin.ModelAdmin):
    list_display = ['prioridad', 'titulo', 'naturaleza', 'area_principal', 'estado', 'last_ingested_at']
    list_filter = ['prioridad', 'naturaleza', 'area_principal', 'estado']
    search_fields = ['titulo', 'id_oficial', 'url_oficial']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['prioridad', 'area_principal', 'titulo']

    fieldsets = (
        ('Priority & Classification', {
            'fields': ('prioridad', 'naturaleza', 'area_principal')
        }),
        ('Document Info', {
            'fields': ('titulo', 'tipo', 'ambito', 'funcion_artisting')
        }),
        ('Official IDs', {
            'fields': ('id_oficial', 'url_oficial')
        }),
        ('Legal Context', {
            'fields': ('vigencia', 'nivel_autoridad', 'articulos_clave', 'frecuencia_actualizacion')
        }),
        ('Ingestion Status', {
            'fields': ('estado', 'last_ingested_at', 'ingestion_error')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ['doc_title', 'doc_id_oficial', 'source', 'created_at']
    list_filter = ['created_at', 'source__prioridad', 'source__naturaleza']
    search_fields = ['doc_title', 'doc_id_oficial', 'url']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['source']

    fieldsets = (
        ('Document Identity', {
            'fields': ('id', 'source', 'doc_title', 'doc_id_oficial', 'url')
        }),
        ('Content', {
            'fields': ('raw_html', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ['chunk_label', 'chunk_type', 'document', 'created_at']
    list_filter = ['chunk_type', 'created_at']
    search_fields = ['chunk_label', 'chunk_text', 'document__doc_title']
    readonly_fields = ['id', 'created_at']
    raw_id_fields = ['document']

    fieldsets = (
        ('Chunk Info', {
            'fields': ('id', 'document', 'chunk_type', 'chunk_label')
        }),
        ('Content', {
            'fields': ('chunk_text', 'embedding', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'session_title', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['id', 'session_title', 'user__username']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['user']

    fieldsets = (
        ('Session Info', {
            'fields': ('id', 'user', 'session_title')
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['role', 'session', 'content_preview', 'feedback_rating', 'created_at']
    list_filter = ['role', 'created_at', 'feedback_rating']
    search_fields = ['content', 'session__id']
    readonly_fields = ['id', 'created_at']
    raw_id_fields = ['session']

    fieldsets = (
        ('Message Info', {
            'fields': ('id', 'session', 'role', 'content')
        }),
        ('Sources & Metadata', {
            'fields': ('sources', 'metadata')
        }),
        ('Feedback', {
            'fields': ('feedback_rating', 'feedback_comment')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'
