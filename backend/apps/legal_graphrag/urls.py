"""
Legal GraphRAG URL Configuration
"""

from django.urls import path

from .views import chat_view, search_view, sources_view, health_view
from .views_v1_1 import chat_view_v1_1

app_name = 'legal_graphrag'

urlpatterns = [
    path('chat/', chat_view, name='chat'),
    path('v1_1/chat/', chat_view_v1_1, name='chat-v1-1'),
    path('search/', search_view, name='search'),
    path('sources/', sources_view, name='sources'),
    path('health/', health_view, name='health'),
]
