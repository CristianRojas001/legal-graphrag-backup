"""
Ad-hoc harness for testing the IntentClassifier against the MVP test plan.
"""

import time
from pathlib import Path
from typing import Dict, List, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT_DIR))

from apps.legal_graphrag.services.intent_classifier import IntentClassifier


def run_basic(classifier: IntentClassifier) -> Dict[str, Tuple[int, int]]:
    sections = {
        "Fiscal": [
            "Puedo deducir gastos de mi home studio?",
            "Como declaro el IVA como artista?",
            "Que retenciones de IRPF aplican a musicos?",
            "Cuales son los gastos deducibles en Hacienda?",
            "Tengo que pagar impuestos por mecenazgo?",
        ],
        "Laboral": [
            "Como me doy de alta como autonomo?",
            "Que cotizacion de Seguridad Social tengo que pagar?",
            "Puedo contratar a un empleado siendo artista autonomo?",
            "Que pasa si me dan de baja en la Seguridad Social?",
            "Cuando tengo que afiliarme al RETA?",
        ],
        "Propiedad Intelectual": [
            "Como registro mis derechos de autor?",
            "Que hace la SGAE con mis royalties?",
            "Puedo denunciar por plagio de mi obra?",
            "Cuanto tiempo duran los derechos de autor?",
            "Necesito licencia para usar una cancion en mi video?",
        ],
    }

    summary: Dict[str, Tuple[int, int]] = {}
    print("=== BASIC FUNCTIONALITY ===")
    for area, queries in sections.items():
        hits = 0
        for query in queries:
            predicted = classifier.classify_area(query)
            hits += predicted == area
            print(f"[{area}] {query} -> {predicted}")
        summary[area] = (hits, len(queries))
    print()
    return summary


def run_edge_cases(classifier: IntentClassifier) -> Dict[str, List[bool]]:
    ambiguous_queries = [
        {
            "query": "Tengo que declarar los ingresos de mi contrato como autonomo?",
            "possible": ["Fiscal", "Laboral"],
        },
        {
            "query": "Como tributan los derechos de autor en el IRPF?",
            "possible": ["Fiscal", "Propiedad Intelectual"],
        },
        {
            "query": "Necesito licencia para abrir un estudio de grabacion?",
            "possible": ["Administrativo", "Laboral"],
        },
    ]
    unclear_queries = [
        "Donde esta la oficina de Hacienda mas cercana?",
        "Que hora es?",
        "Hola, como estas?",
        "Cual es la capital de Espana?",
        "Puedo comprar pan en la tienda?",
    ]
    edge_inputs = ["", "   ", "?", "¿?", "123456", "a" * 1000]

    print("=== EDGE CASES ===")
    ambiguous_results: List[bool] = []
    for test in ambiguous_queries:
        result = classifier.classify_with_confidence(test["query"])
        ok = result["area"] in test["possible"] if result["area"] else False
        ambiguous_results.append(ok)
        print(
            f"{test['query']} -> {result['area']} ({result['confidence']:.2f}) "
            f"expected {test['possible']} :: {'PASS' if ok else 'CHECK'}"
        )

    unclear_results: List[bool] = []
    for query in unclear_queries:
        area = classifier.classify_area(query)
        ok = area is None
        unclear_results.append(ok)
        print(f"{query} -> {area} :: {'PASS' if ok else 'WEAK'}")

    edge_results: List[bool] = []
    for query in edge_inputs:
        try:
            area = classifier.classify_area(query)
            edge_results.append(True)
            print(f"{query[:30]}... -> {area} :: PASS")
        except Exception as exc:  # pragma: no cover - defensive
            edge_results.append(False)
            print(f"{query[:30]}... -> FAIL ({exc})")
    print()

    return {
        "ambiguous": ambiguous_results,
        "unclear": unclear_results,
        "edge_inputs": edge_results,
    }


def run_keyword_extraction(classifier: IntentClassifier) -> List[bool]:
    print("=== KEYWORD EXTRACTION ===")
    tests = [
        {
            "query": "Como puedo deducir los gastos de mi estudio?",
            "expected": ["como", "puedo", "deducir", "gastos", "estudio"],
        },
        {
            "query": "Que retenciones de IRPF aplican?",
            "expected": ["retenciones", "irpf", "aplican"],
        },
        {
            "query": "Dar de alta en Seguridad Social",
            "expected": ["alta", "seguridad", "social"],
        },
    ]
    results: List[bool] = []
    for test in tests:
        extracted = classifier.extract_keywords(test["query"])
        missing = [k for k in test["expected"] if k not in extracted]
        ok = not missing
        results.append(ok)
        status = "PASS" if ok else "MISSING " + ", ".join(missing)
        print(f"{test['query']} -> {extracted} :: {status}")
    print()
    return results


def run_utilities(classifier: IntentClassifier) -> Dict[str, bool]:
    print("=== UTILITY METHODS ===")
    areas = classifier.get_all_areas()
    expected_areas = [
        "Fiscal",
        "Laboral",
        "Propiedad Intelectual",
        "Contabilidad",
        "Subvenciones",
        "Societario",
        "Administrativo",
    ]
    missing = [a for a in expected_areas if a not in areas]
    extra = [a for a in areas if a not in expected_areas]
    print(f"Areas: {areas}")
    print(f"Missing: {missing} Extra: {extra}")

    keywords_count = {area: len(classifier.get_keywords_for_area(area)) for area in ["Fiscal", "Laboral"]}
    invalid = classifier.get_keywords_for_area("InvalidArea")
    print(f"Keywords per area: {keywords_count}")
    print(f"Invalid area keywords: {invalid}")
    print()

    return {
        "areas_ok": not missing and not extra,
        "keywords_ok": keywords_count["Fiscal"] > 0 and keywords_count["Laboral"] > 0 and invalid == [],
    }


def run_confidence(classifier: IntentClassifier) -> Dict[str, List[bool]]:
    print("=== CONFIDENCE SCORING ===")
    clear_queries = [
        "Puedo deducir gastos de IVA en mi declaracion de IRPF?",
        "Como me doy de alta como trabajador autonomo?",
        "Donde registro mis derechos de autor musicales?",
    ]
    ambiguous_low = [
        "Que documentos necesito?",
        "Cuales son mis obligaciones?",
        "Donde tengo que ir?",
    ]

    clear_results: List[bool] = []
    for query in clear_queries:
        res = classifier.classify_with_confidence(query)
        ok = res["confidence"] > 0.5
        clear_results.append(ok)
        print(f"{query} -> {res} :: {'HIGH' if ok else 'LOW'}")

    low_results: List[bool] = []
    for query in ambiguous_low:
        res = classifier.classify_with_confidence(query)
        ok = res["confidence"] < 0.5 or res["area"] is None
        low_results.append(ok)
        print(f"{query} -> {res} :: {'LOW' if ok else 'HIGH'}")
    print()

    return {"high": clear_results, "low": low_results}


def run_performance(classifier: IntentClassifier) -> Dict[str, float]:
    print("=== PERFORMANCE ===")
    perf_queries = [
        "Puedo deducir gastos de mi home studio?",
        "Como me doy de alta como autonomo?",
        "Donde registro mis derechos de autor?",
    ] * 100
    start = time.perf_counter()
    for query in perf_queries:
        classifier.classify_area(query)
    elapsed = time.perf_counter() - start
    avg_ms = elapsed / len(perf_queries) * 1000
    print(f"Total queries: {len(perf_queries)}")
    print(f"Total time: {elapsed:.4f}s")
    print(f"Avg per query: {avg_ms:.4f}ms")
    print(f"QPS: {len(perf_queries)/elapsed:.0f}")
    print()
    return {"elapsed": elapsed, "avg_ms": avg_ms}


def run_real_world(classifier: IntentClassifier) -> float:
    print("=== REAL-WORLD QUERIES ===")
    real_queries = [
        ("Puedo deducir el alquiler de mi estudio de musica?", "Fiscal"),
        ("Cuanto IVA tengo que cobrar por un concierto?", "Fiscal"),
        ("Debo hacer retencion de IRPF en facturas?", "Fiscal"),
        ("Puedo estar en el paro y ser autonomo a la vez?", "Laboral"),
        ("Cuanto cuesta la cuota de autonomos para artistas?", "Laboral"),
        ("Necesito contratar a musicos con contrato?", "Laboral"),
        ("Como cobro derechos de autor de Spotify?", "Propiedad Intelectual"),
        ("Puedo usar una foto de internet en mi disco?", "Propiedad Intelectual"),
        ("Que hago si alguien copia mi cancion?", "Propiedad Intelectual"),
        ("Hay ayudas para grabar un disco en 2025?", "Subvenciones"),
        ("Como solicito una beca del Ministerio de Cultura?", "Subvenciones"),
        ("Necesito licencia de actividad para dar clases?", "Administrativo"),
    ]
    correct = 0
    for query, expected in real_queries:
        area = classifier.classify_area(query)
        correct += area == expected
        print(f"{query} -> {area} (expected {expected})")
    accuracy = correct / len(real_queries) * 100
    print(f"Accuracy: {accuracy:.1f}% ({correct}/{len(real_queries)})")
    print()
    return accuracy


def main() -> None:
    classifier = IntentClassifier()
    summary = {
        "basic": run_basic(classifier),
        "edge_cases": run_edge_cases(classifier),
        "keywords": run_keyword_extraction(classifier),
        "utilities": run_utilities(classifier),
        "confidence": run_confidence(classifier),
        "performance": run_performance(classifier),
        "real_world_accuracy": run_real_world(classifier),
    }
    print("=== SUMMARY (raw data) ===")
    print(summary)


if __name__ == "__main__":
    main()
