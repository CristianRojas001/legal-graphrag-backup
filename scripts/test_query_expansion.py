"""Test query expansion for failing cases"""
import sys
sys.path.insert(0, 'D:\\IT workspace\\Legal GraphRAG\\backend')

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')

import django
django.setup()

from apps.legal_graphrag.services.v1_1.query_expander_v1_1 import QueryExpanderV1_1
import google.generativeai as genai
from django.conf import settings

# Initialize
genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel(model_name=settings.GEMINI_CHAT_MODEL)
expander = QueryExpanderV1_1(model)

# Test failing queries
TEST_QUERIES = [
    "Facturo a una empresa española como artista. ¿Debo aplicar retención? ¿De qué depende?",
    "¿Puedo deducir dietas y desplazamientos si voy a actuar fuera de mi ciudad?",
    "Soy ilustradora y trabajo desde casa. ¿Puedo deducir parte del alquiler y suministros?",
    "¿Cómo se suelen valorar los criterios en convocatorias culturales?",
]

print("=" * 80)
print("QUERY EXPANSION TEST")
print("=" * 80)

for query in TEST_QUERIES:
    print(f"\nOriginal: {query}")
    print(f"Expanded queries:")

    expanded = expander.expand(query, max_total=6, llm_variants=2)
    for i, exp_query in enumerate(expanded, 1):
        print(f"  {i}. {exp_query}")
    print()
