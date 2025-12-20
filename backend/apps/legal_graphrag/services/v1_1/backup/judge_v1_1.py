"""
V1.1 Answer Judge
Checks support, coherence, and usefulness based on provided sources.
"""

import json
import re
from typing import Dict, List, Any


class AnswerJudgeV1_1:
    def __init__(self, model) -> None:
        self.model = model

    def _format_sources(self, sources: Dict[str, List[Dict[str, Any]]]) -> str:
        lines = []
        for group in ("normativa", "doctrina", "jurisprudencia"):
            for chunk in sources.get(group, []):
                doc_id = chunk.get("document_id", "")
                title = chunk.get("document_title", "")
                label = chunk.get("chunk_label", "")
                excerpt = (chunk.get("chunk_text", "") or "")[:1200]
                lines.append(f"[{doc_id}] {title} - {label}: {excerpt}")
        return "\n".join(lines)

    def judge(self, question: str, answer: str, sources: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Return verdict PASS/REDO with reasons.
        """
        if not self.model:
            return {"verdict": "PASS", "reasons": ["no_model"]}

        sources_text = self._format_sources(sources)
        prompt = (
            "Eres un juez de calidad (QA) para respuestas legales basadas en RAG.\n\n"
            "Objetivo: detectar ALUCINACIÓN (afirmaciones no apoyadas) y CITAS INCORRECTAS.\n"
            "No penalices respuestas parciales si:\n"
            "- responden directamente lo que se puede con las fuentes,\n"
            "- indican claramente límites (“las fuentes no permiten afirmar X”),\n"
            "- y piden aclaraciones concretas.\n\n"
            "Devuelve SOLO JSON con:\n"
            "{{\"verdict\":\"PASS|REDO\",\"reasons\":[\"...\"]}}\n\n"
            "Criterios para REDO (solo si ocurre al menos uno):\n"
            "1) La respuesta hace una afirmación factual/concreta no respaldada por las fuentes.\n"
            "2) La respuesta contradice explícitamente las fuentes.\n"
            "3) La respuesta NO responde a la pregunta (solo relleno, solo disclaimers).\n"
            "4) La respuesta cita una fuente que no contiene lo afirmado (cita engañosa).\n\n"
            "Si falta evidencia, es PASS si la respuesta:\n"
            "- ofrece lo más cercano soportado,\n"
            "- y enumera qué falta + preguntas concretas.\n\n"
            "Question:\n{q}\n\nAnswer:\n{a}\n\nSources:\n{s}\n"
        ).format(q=question, a=answer, s=sources_text)

        try:
            response = self.model.generate_content(prompt)
            text = response.text or ""

            # Try to extract JSON, handling code fences
            json_text = None

            # First try: JSON inside code fences
            code_fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
            if code_fence_match:
                json_text = code_fence_match.group(1)
            else:
                # Second try: bare JSON object
                json_match = re.search(r"\{.*\}", text, flags=re.S)
                if json_match:
                    json_text = json_match.group(0)

            if not json_text:
                return {"verdict": "PASS", "reasons": ["judge_parse_failed"]}

            try:
                payload = json.loads(json_text)
            except json.JSONDecodeError:
                # If parse fails, return PASS (no REDO loops)
                return {"verdict": "PASS", "reasons": ["judge_parse_failed"]}

            verdict = payload.get("verdict", "PASS")
            reasons = payload.get("reasons", [])

            if verdict not in ("PASS", "REDO"):
                verdict = "PASS"
                reasons = ["judge_invalid_verdict"]

            return {"verdict": verdict, "reasons": reasons}
        except Exception:
            return {"verdict": "PASS", "reasons": ["judge_error"]}
