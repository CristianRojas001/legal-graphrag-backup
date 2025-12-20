"""
Quick demo of citation confetti fixes
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')
django.setup()

from apps.legal_graphrag.services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1
import re


def demo_meta_query():
    """Demo: Meta query returns clean response with 0 sources"""
    print("\n" + "="*80)
    print("DEMO 1: Meta Query - No Citation Confetti")
    print("="*80)

    engine = LegalRAGEngineV1_1()
    result = engine.answer_query(query="Que puedes hacer?")

    print(f"\nQuery: 'Que puedes hacer?'")
    print(f"Total sources: {result['metadata']['total_sources']}")
    print(f"Is meta query: {result['metadata'].get('is_meta_query', False)}")
    print(f"\nAnswer preview:")
    print(result['answer'][:500] + "...")


def demo_citation_accuracy():
    """Demo: Only cited sources appear in Fuentes utilizadas"""
    print("\n" + "="*80)
    print("DEMO 2: Citation Accuracy - Only Cited Sources Listed")
    print("="*80)

    engine = LegalRAGEngineV1_1()
    result = engine.answer_query(query="Que es el IVA?")

    answer = result['answer']
    cited_ids = set(re.findall(r"\[ID:\s*([^\]]+)\]", answer))
    has_fuentes = "**Fuentes utilizadas**:" in answer

    print(f"\nQuery: 'Que es el IVA?'")
    print(f"Total sources retrieved: {result['metadata']['total_sources']}")
    print(f"Citations in answer: {len(cited_ids)}")
    print(f"Has 'Fuentes utilizadas': {has_fuentes}")

    if has_fuentes:
        fuentes_section = answer.split("**Fuentes utilizadas**:")[1] if "**Fuentes utilizadas**:" in answer else ""
        fuentes_ids = set(re.findall(r"\[ID:\s*([^\]]+)\]", fuentes_section))
        print(f"IDs in 'Fuentes utilizadas': {len(fuentes_ids)}")
        print(f"Accuracy: {len(fuentes_ids) == len(cited_ids) and fuentes_ids == cited_ids}")


def demo_iva_conceptual():
    """Demo: IVA conceptual question works without rate evidence"""
    print("\n" + "="*80)
    print("DEMO 3: IVA Conceptual - No Over-Abstaining")
    print("="*80)

    engine = LegalRAGEngineV1_1()
    result = engine.answer_query(query="Que obligaciones tiene un autonomo con el IVA?")

    print(f"\nQuery: 'Que obligaciones tiene un autonomo con el IVA?'")
    print(f"Abstained: {result['metadata']['abstained']}")
    print(f"Answer length: {len(result['answer'])} chars")
    print(f"Total sources: {result['metadata']['total_sources']}")

    # Check for rate claims
    found_rates = re.findall(r"(\d+)\s*%", result['answer'])
    print(f"Rate claims in answer: {found_rates if found_rates else 'None'}")
    print(f"\nAnswer preview:")
    print(result['answer'][:400] + "...")


if __name__ == '__main__':
    demo_meta_query()
    demo_citation_accuracy()
    demo_iva_conceptual()
    print("\n" + "="*80)
    print("All demos completed successfully!")
    print("="*80 + "\n")
