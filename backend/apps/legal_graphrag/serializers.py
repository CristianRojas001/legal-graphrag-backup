"""
Legal GraphRAG Serializers
DRF serializers for API endpoints.
"""

from rest_framework import serializers

from .models import CorpusSource


class ChatRequestSerializer(serializers.Serializer):
    """Validate chat requests sent to the RAG engine."""

    query = serializers.CharField()
    area_principal = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    session_id = serializers.UUIDField(required=False)
    max_sources = serializers.IntegerField(required=False, min_value=1, max_value=15, default=10)


class SearchRequestSerializer(serializers.Serializer):
    """Validate search requests for hybrid search."""

    query = serializers.CharField()
    limit = serializers.IntegerField(required=False, min_value=1, max_value=25, default=10)


class CorpusSourceSerializer(serializers.ModelSerializer):
    """Serialize corpus sources for listing endpoints."""

    class Meta:
        model = CorpusSource
        fields = [
            'id',
            'prioridad',
            'naturaleza',
            'area_principal',
            'titulo',
            'tipo',
            'ambito',
            'funcion_artisting',
            'id_oficial',
            'url_oficial',
            'vigencia',
            'nivel_autoridad',
            'estado',
            'last_ingested_at',
        ]
