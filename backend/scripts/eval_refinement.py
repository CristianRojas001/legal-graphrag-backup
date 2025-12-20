"""
Evaluation runner for refinement scenarios.

Runs a fixed set of artist-focused queries against the chat API and writes
JSON/Markdown reports with latency, answers, and source counts.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional
import urllib.request
import urllib.error


# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8")


SCENARIOS: List[str] = [
    # Fiscal / IVA / IRPF
    "¿Puedo deducir gastos de home studio en IRPF como músico autónomo?",
    "¿Qué retención de IRPF aplica a facturas por actuaciones en directo?",
    "¿Qué IVA corresponde a entradas de un concierto pequeño?",
    "¿Qué tipo de IVA aplica a clases particulares de música?",
    "¿Qué IVA aplica a la venta de merchandising en un concierto?",
    "¿Qué IVA aplica al alquiler de una sala para conciertos?",
    "¿Qué pasa con el IVA en servicios culturales prestados a una ONG?",
    "¿Cómo facturo un bolo a un cliente de otro país de la UE? ¿IVA o inversión del sujeto pasivo?",
    "¿Puedo deducir gastos de desplazamiento y dietas en una gira?",
    "¿Puedo deducir el alquiler de un local de ensayo en IRPF?",
    "¿Cómo declaro royalties de streaming en IRPF?",
    "¿Hay deducciones por mecenazgo cultural para donantes?",
    "¿Hay requisitos especiales de facturación para venta online de merchandising?",
    "¿Aplica el derecho de desistimiento a la venta online de merchandising?",
    "¿Cómo reclamo si se cancela un concierto y ya vendí entradas (consumo)?",
    # Laboral / Seguridad Social
    "¿Necesito darme de alta en autónomos para actuar esporádicamente?",
    "¿Cómo cotiza un músico autónomo en el RETA?",
    "¿Cuándo aplica relación laboral especial de artistas?",
    "¿Cómo se cotizan los bolos ocasionales según la reforma de artistas?",
    "¿Puedo compatibilizar paro con actuaciones puntuales?",
    # Propiedad Intelectual
    "¿Cuánto dura la protección de derechos de autor de una canción en España?",
    "¿Cuántos años duran los derechos conexos de intérpretes o ejecutantes?",
    "¿Cómo debo ceder derechos de uso de una obra musical en un contrato?",
    "¿Cómo licencio una canción para un anuncio (sincronización)?",
    "¿Necesito registrar mi canción en el Registro de Propiedad Intelectual para tener protección?",
    "¿Puedo usar un sampler de otra canción sin licencia?",
    "¿Qué pasa si toco una versión (cover) en directo, necesito autorización?",
    "¿Qué derechos tengo al subir mi música a plataformas online?",
    "¿Qué obligaciones hay de depósito legal al editar un disco físico?",
    "¿Cómo protejo datos personales al vender entradas online (LOPDGDD/Comercio electrónico)?",
]


@dataclass
class ScenarioResult:
    query: str
    latency_ms: Optional[int] = None
    answer: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


def run_scenario(api_url: str, query: str, timeout: int) -> ScenarioResult:
    payload = json.dumps({"query": query}).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    req = urllib.request.Request(api_url, data=payload, headers=headers, method="POST")
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        latency_ms = int((time.time() - start) * 1000)
        return ScenarioResult(
            query=query,
            latency_ms=latency_ms,
            answer=data.get("answer", ""),
            sources=data.get("sources", [])
            or data.get("metadata", {}).get("sources", [])
            or [],
        )
    except Exception as e:
        return ScenarioResult(query=query, error=str(e))


def write_json(results: List[ScenarioResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(r) for r in results]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown(results: List[ScenarioResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("# Refinement Scenario Results")
    lines.append("")
    lines.append(f"- Total: {len(results)}")
    lines.append("")
    lines.append("| # | Query | Latency (ms) | Sources | Error |")
    lines.append("|---|-------|--------------|---------|-------|")
    for idx, r in enumerate(results, 1):
        lat = r.latency_ms if r.latency_ms is not None else ""
        src_cnt = len(r.sources) if r.sources else 0
        err = r.error or ""
        q_short = r.query.replace("|", "\\|")
        lines.append(f"| {idx} | {q_short} | {lat} | {src_cnt} | {err} |")
    lines.append("")
    lines.append("## Snippets")
    lines.append("")
    for idx, r in enumerate(results, 1):
        lines.append(f"### {idx}. {r.query}")
        if r.error:
            lines.append(f"- Error: {r.error}")
        else:
            lat = r.latency_ms if r.latency_ms is not None else "n/a"
            src_cnt = len(r.sources) if r.sources else 0
            lines.append(f"- Latency: {lat} ms")
            lines.append(f"- Sources: {src_cnt}")
            snippet = (r.answer or "").replace("\n", " ")
            lines.append(f"- Answer (snippet): {snippet[:400]}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run refinement scenarios against the chat API.")
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000/api/v1/legal-graphrag/chat/",
        help="Chat API URL",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Request timeout in seconds (per scenario)",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("../docs/Refinement/scenario_eval_latest.json"),
        help="Path to write JSON results",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=Path("../docs/Refinement/scenario_eval_latest.md"),
        help="Path to write Markdown summary",
    )
    args = parser.parse_args()

    results: List[ScenarioResult] = []
    for q in SCENARIOS:
        res = run_scenario(args.api_url, q, args.timeout)
        results.append(res)
        status = "OK" if res.error is None else f"ERR: {res.error}"
        print(f"[{status}] {q}")

    write_json(results, args.out_json)
    write_markdown(results, args.out_md)
    print(f"\nWrote JSON: {args.out_json}")
    print(f"Wrote Markdown: {args.out_md}")


if __name__ == "__main__":
    main()
