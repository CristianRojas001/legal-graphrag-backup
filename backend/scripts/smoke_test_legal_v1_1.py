import os
import json

import django


def main() -> None:
    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        os.environ["DJANGO_SETTINGS_MODULE"] = "ovra_backend.settings"
    django.setup()

    from apps.legal_graphrag.services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1

    engine = LegalRAGEngineV1_1()

    queries = [
        "¿Cuál es la norma con mayor rango jurídico en España?",
        "¿Puede un reglamento contradecir una ley?",
        "¿La Ley 39/2015 se aplica a una asociación cultural privada?",
        "¿Qué diferencia hay entre ley orgánica y ley ordinaria?",
        "¿Qué es doctrina administrativa en este sistema?",
        "¿Qué norma prevalece si hay conflicto entre una ley y un real decreto?",
        "¿Qué significa jerarquía normativa en España?",
        "¿Se aplica la Ley 39/2015 a un artista autónomo?",
        "¿Qué fuentes del derecho son P1 según este sistema?",
        "¿Qué rango tiene la Constitución en la jerarquía normativa?",
    ]

    for idx, q in enumerate(queries, 1):
        result = engine.answer_query(query=q, area_principal=None, max_sources=10)
        sources = result.get("sources", [])
        metadata = result.get("metadata", {})

        print("=" * 90)
        print(f"{idx}. {q}")
        print("-" * 90)
        print(result.get("answer", "").strip())
        print("-" * 90)
        print("metadata:", json.dumps({
            "expanded_queries": metadata.get("expanded_queries"),
            "authority_pack_added": metadata.get("authority_pack_added"),
            "authority_pack_count": metadata.get("authority_pack_count"),
            "retrieval_counts": metadata.get("retrieval_counts"),
            "top_scores": metadata.get("top_scores"),
            "judge": metadata.get("judge"),
            "redo_performed": metadata.get("redo_performed"),
            "abstained": metadata.get("abstained"),
        }, ensure_ascii=False, indent=2))
        print("top_sources:", [s.get("id") for s in sources[:5]])


if __name__ == "__main__":
    main()
