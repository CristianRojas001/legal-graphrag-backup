"""
Legal RAG Engine V1.1
Multi-query retrieval + hierarchy-safe fusion + judge/redo pipeline.
"""

import copy
import concurrent.futures
import json
import logging
import re
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from django.conf import settings

from apps.legal_graphrag.services.legal_rag_engine import LegalRAGEngine
from apps.legal_graphrag.services.legal_search_engine import LegalSearchEngine
from apps.legal_graphrag.services.v1_1.query_expander_v1_1 import QueryExpanderV1_1
from apps.legal_graphrag.services.v1_1.judge_v1_1 import AnswerJudgeV1_1
from apps.legal_graphrag.services.v1_1.embedding_service import EmbeddingService
from apps.legal_graphrag.services.v1_1.authority_pack_v1_1 import (
    build_authority_sources,
    is_authority_question,
)
from apps.legal_graphrag.services.v1_1.flow_logger_v1_1 import FlowLoggerV1_1, format_source_snippet
from apps.legal_graphrag.services.v1_1.reference_resolver import ExactReferenceResolver
from apps.legal_graphrag.services.v1_1.tax_rate_resolver import (
    TaxRateResolver,
    sanitize_answer_percentages,
)
from apps.legal_graphrag.models import CorpusSource, DocumentChunk
from django.db.models import Q

logger = logging.getLogger(__name__)

_RETRIEVAL_CACHE: "OrderedDict[tuple, dict]" = OrderedDict()
_RETRIEVAL_CACHE_MAX = 64
_CORE_AREA_CACHE: Dict[str, Any] = {"timestamp": 0.0, "map": {}}


class LegalRAGEngineV1_1(LegalRAGEngine):
    """
    V1.1 pipeline:
    - Expand query (deterministic + limited LLM variants)
    - Retrieve per query
    - Fuse + dedup per hierarchy bucket
    - Generate answer
    - Judge and optional redo (no new retrieval)
    """

    def __init__(self):
        super().__init__()
        self.search_engine = LegalSearchEngine()
        self.query_expander = QueryExpanderV1_1(self.model)
        self.judge = AnswerJudgeV1_1(self.model)
        self.flow_logger = FlowLoggerV1_1()  # Flow logging
        self.reference_resolver = ExactReferenceResolver()
        self._semantic_match_threshold = getattr(settings, "RAG_SEMANTIC_THRESHOLD", 0.7)
        self._semantic_match_enabled = getattr(settings, "RAG_SEMANTIC_MATCH_ENABLED", False)
        self._semantic_embedding_cache: "OrderedDict[str, List[float]]" = OrderedDict()
        self._semantic_cache_max = 256
        self._area_filter_enabled = getattr(settings, "RAG_AREA_FILTER_ENABLED", True)
        self._core_areas = {"Fiscal", "Laboral", "Propiedad Intelectual"}
        self._core_area_aliases = self._build_core_area_aliases()
        self._core_area_cache_ttl = getattr(settings, "RAG_CORE_AREA_CACHE_TTL", 300)
        self._area_filter_fallback_min = getattr(settings, "RAG_AREA_FILTER_FALLBACK_MIN_RESULTS", 6)
        self._judge_enabled = getattr(settings, "RAG_JUDGE_ENABLED", False)  # Disable by default for speed
        self.tax_resolver = TaxRateResolver()
        self._last_allowed_percentages: List[int] = []
        self._non_tax_percent_allowlist = self._load_non_tax_percent_allowlist()
        self.embedding_service = None
        if self._semantic_match_enabled and getattr(settings, "GEMINI_API_KEY", ""):
            self.embedding_service = EmbeddingService()

        # Meta query patterns (capability/help questions)
        self._meta_patterns = [
            r"\bqu[eé]\s+puedes?\s+hacer\b",
            r"\bc[oó]mo\s+puedes?\s+ayudar\b",
            r"\bc[oó]mo\s+funciona\s+(este\s+chat|esto)\b",
            r"\bpor\s+qu[eé]\s+(no\s+)?respondiste\b",
            r"\bpor\s+qu[eé]\s+te\s+abstuviste\b",
            r"\bqu[eé]\s+es\s+rag\b",
            r"\bwhat\s+can\s+you\s+do\b",
            r"\bhow\s+(can|do)\s+you\s+(help|work)\b",
            r"\bhow\s+does\s+this\s+(chat|work)\b",
        ]

    def _write_chat_trace(self, payload: Dict[str, Any]) -> None:
        log_dir = Path(__file__).resolve().parents[5] / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "chat_trace_v1_1.jsonl"
        try:
            with open(log_file, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("Failed to write chat trace")

    def _is_meta_query(self, query: str) -> bool:
        """
        Detect meta/capability questions that should not trigger legal retrieval.

        Examples:
        - "What can you do?"
        - "¿Qué puedes hacer?"
        - "How does this chat work?"
        - "Why did you abstain?"
        """
        query_lower = query.lower()
        for pattern in self._meta_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return True
        return False

    def _is_sensitive_internal_query(self, query: str) -> bool:
        if not query:
            return False
        normalized = self._normalize_text(query)
        patterns = [
            "api key",
            "apikey",
            "token",
            "credentials",
            "password",
            "secreto",
            "secret",
            "infraestructura",
            "infrastructure",
            "servidor",
            "server",
            "base de datos",
            "database",
            "endpoint interno",
            "internal endpoint",
            "security",
            "seguridad interna",
            "configuracion",
            "config",
        ]
        return any(term in normalized for term in patterns)

    def _build_sensitive_response(self) -> str:
        return (
            "Lo siento, no puedo ayudar con detalles internos de infraestructura, "
            "seguridad o configuracion. Si tienes una consulta legal, dime el caso "
            "concreto y te ayudo."
        )

    def _build_meta_response(self) -> str:
        """
        Build a helpful response for meta/capability questions without citing legal sources.
        """
        return """Soy un asistente especializado en normativa legal española, centrado en:

**Áreas principales:**
- **Fiscal**: IRPF, IVA, retenciones, impuestos, Ley General Tributaria
- **Laboral**: Seguridad Social, autónomos (RETA), contratos, cotizaciones
- **Propiedad Intelectual**: Derechos de autor, licencias, SGAE, CEDRO

**Cómo puedo ayudarte:**
1. Respondo preguntas concretas sobre normativa, doctrina administrativa y jurisprudencia española
2. Cito las fuentes legales específicas que respaldan cada respuesta
3. Si no tengo evidencia suficiente, te lo indico claramente y te ayudo a reformular la pregunta

**Para obtener mejores respuestas:**
- Formula preguntas específicas sobre un tema legal concreto
- Incluye contexto relevante (actividad, situación, fechas)
- Si buscas normativa específica, menciona la ley o el BOE si lo conoces

**Ejemplos de preguntas útiles:**
- "¿Qué retenciones de IRPF aplican a artistas autónomos?"
- "¿Cuál es el tipo de IVA para servicios culturales?"
- "¿Qué derechos tienen los autores sobre obras musicales?"

¿Sobre qué tema legal te gustaría que te ayude?"""

    def _build_core_area_aliases(self) -> Dict[str, str]:
        aliases: Dict[str, str] = {}
        raw_aliases = getattr(settings, "RAG_CORE_AREA_ALIASES", {})
        if not isinstance(raw_aliases, dict):
            return aliases
        for raw_key, raw_value in raw_aliases.items():
            if not raw_key or not raw_value:
                continue
            normalized_key = self._normalize_text(str(raw_key))
            if not normalized_key:
                continue
            aliases[normalized_key] = str(raw_value)
        return aliases

    def _infer_core_area(self, area_value: Optional[str]) -> str:
        if not area_value:
            return "Other"
        normalized = self._normalize_text(area_value)
        if not normalized:
            return "Other"
        alias = self._core_area_aliases.get(normalized)
        if alias in self._core_areas:
            return alias
        if "fiscal" in normalized:
            return "Fiscal"
        if (
            "laboral" in normalized
            or "seguridad social" in normalized
            or "prevencion de riesgos laborales" in normalized
        ):
            return "Laboral"
        if (
            "propiedad intelectual" in normalized
            or normalized.startswith("pi ")
            or normalized.startswith("pi ue")
            or normalized == "pi"
        ):
            return "Propiedad Intelectual"
        return "Other"

    def _get_core_area_map(self) -> Dict[str, List[str]]:
        now = time.time()
        cache = _CORE_AREA_CACHE
        if cache.get("map") and now - cache.get("timestamp", 0) < self._core_area_cache_ttl:
            return cache["map"]

        area_values = list(
            CorpusSource.objects.exclude(area_principal__isnull=True)
            .exclude(area_principal__exact="")
            .values_list("area_principal", flat=True)
            .distinct()
        )

        area_map: Dict[str, List[str]] = {core: [] for core in self._core_areas}
        for value in area_values:
            core_area = self._infer_core_area(value)
            if core_area in area_map:
                area_map[core_area].append(value)

        for core_area in self._core_areas:
            if core_area not in area_map:
                area_map[core_area] = []
            if core_area not in area_map[core_area]:
                area_map[core_area].append(core_area)

        cache["timestamp"] = now
        cache["map"] = area_map
        return area_map

    def _get_area_filter_values(
        self,
        area_principal: Optional[str],
    ) -> Tuple[Optional[str], Optional[List[str]]]:
        if not self._area_filter_enabled or not area_principal:
            return None, None
        core_area = area_principal if area_principal in self._core_areas else self._infer_core_area(area_principal)
        if core_area not in self._core_areas:
            return None, None
        area_map = self._get_core_area_map()
        values = area_map.get(core_area) or [core_area]
        return core_area, values

    def _is_rate_only_tax_query(self, query: str) -> bool:
        if not self._is_rate_seeking_query(query):
            return False
        normalized = self._normalize_text(query)
        disqualifiers = [
            "como",
            "aplica",
            "aplicacion",
            "requisito",
            "requisitos",
            "exencion",
            "exento",
            "factura",
            "modelo",
            "declaracion",
            "plazo",
            "obligacion",
            "deduc",
            "base imponible",
            "calcular",
            "caso",
            "procedimiento",
            "documentacion",
        ]
        if any(token in normalized for token in disqualifiers):
            return False
        token_count = len(re.findall(r"\w+", normalized))
        return token_count <= 12

    def _build_tax_sources(self, tax_context: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        entries: List[Dict[str, Any]] = []
        for key, label in (("iva", "IVA"), ("irpf", "IRPF")):
            item = tax_context.get(key)
            if not item or item.get("status") != "ok":
                continue
            refs = item.get("refs") or []
            ref = refs[0] if refs else {}
            rate = int(item.get("rate_percent"))
            rule_id = item.get("rule_id") or f"{label}_RATE"
            doc_id = f"AEAT-{label}-RESOLVER"
            entries.append({
                "rank": 0,
                "chunk_id": f"tax-{rule_id}",
                "chunk_label": f"AEAT {label} {rate}%",
                "chunk_text": f"AEAT {label}: tipo aplicable {rate}%.",
                "chunk_type": "tax_rate",
                "similarity": 1.0,
                "document_title": ref.get("label", f"AEAT {label}"),
                "document_id": doc_id,
                "document_url": ref.get("url", ""),
                "source_title": "AEAT",
                "source_priority": "P1",
                "source_naturaleza": "Doctrina administrativa",
                "metadata": {"tax_resolver": True, "rule_id": rule_id},
                "search_method": "tax_resolver",
                "rrf_score": 9999,
            })

        return {"normativa": [], "doctrina": entries, "jurisprudencia": []}

    def _inject_tax_sources(
        self,
        sources: Dict[str, List[Dict[str, Any]]],
        tax_context: Dict[str, Any],
    ) -> Dict[str, List[Dict[str, Any]]]:
        if not tax_context or tax_context.get("status") != "ok":
            return sources
        tax_sources = self._build_tax_sources(tax_context)
        existing_ids = {item.get("document_id") for bucket in sources.values() for item in bucket}
        for item in tax_sources.get("doctrina", []):
            if item.get("document_id") not in existing_ids:
                sources.setdefault("doctrina", []).append(item)
        return sources

    def _build_tax_rate_answer(self, query: str, tax_context: Dict[str, Any]) -> str:
        parts = []
        iva = tax_context.get("iva")
        irpf = tax_context.get("irpf")
        if iva and iva.get("status") == "ok":
            parts.append(f"El tipo de IVA aplicable es {int(iva.get('rate_percent'))}%.")
        if irpf and irpf.get("status") == "ok":
            parts.append(f"La retencion de IRPF aplicable es {int(irpf.get('rate_percent'))}%.")

        if not parts:
            return "No puedo determinar una tasa con la informacion disponible."

        cited_ids = []
        if iva and iva.get("status") == "ok":
            cited_ids.append("AEAT-IVA-RESOLVER")
        if irpf and irpf.get("status") == "ok":
            cited_ids.append("AEAT-IRPF-RESOLVER")

        answer = " ".join(parts)
        if cited_ids:
            answer += f"\n\n<!--CITED_IDS: {', '.join(cited_ids)} -->"
        return answer

    def _load_non_tax_percent_allowlist(self) -> List[int]:
        raw = getattr(settings, "RAG_NON_TAX_PERCENT_ALLOWLIST", [])
        if isinstance(raw, (list, tuple)):
            values = raw
        elif isinstance(raw, str):
            values = [item.strip() for item in raw.split(",") if item.strip()]
        else:
            return []
        parsed = []
        for value in values:
            try:
                parsed.append(int(value))
            except (TypeError, ValueError):
                continue
        return parsed

    def _build_tax_slot_prompt(self, query: str) -> str:
        return (
            "Extrae intentos fiscales en JSON estricto. No incluyas numeros ni porcentajes.\n"
            "Devuelve SOLO un objeto JSON con este esquema:\n"
            "{\n"
            "  \"needs_tax\": true/false,\n"
            "  \"taxes\": [\"IVA\",\"IRPF\"],\n"
            "  \"iva\": {\n"
            "    \"topic\": \"entradas_cultura|servicios_artistas|libros_prensa|general|unknown\",\n"
            "    \"keywords\": [\"...\"]\n"
            "  },\n"
            "  \"irpf\": {\n"
            "    \"income_type\": \"actividad_profesional|consejero_administrador|cesion_derecho_imagen|capital_inmobiliario_arrendamiento_urbano|unknown\",\n"
            "    \"new_activity\": true/false/null,\n"
            "    \"net_turnover_bucket\": \"GT_100K|LT_100K|null\"\n"
            "  }\n"
            "}\n"
            f"Pregunta: {query}\n"
        )

    def _extract_query_keyword_candidates(self, normalized_query: str, max_terms: int = 40) -> List[str]:
        if not normalized_query:
            return []
        tokens = [token for token in normalized_query.split() if len(token) > 2]
        terms = list(tokens)
        for size in (2, 3, 4):
            for idx in range(len(tokens) - size + 1):
                terms.append(" ".join(tokens[idx : idx + size]))
        seen = set()
        result = []
        for term in terms:
            if term in seen:
                continue
            seen.add(term)
            result.append(term)
            if len(result) >= max_terms:
                break
        return result

    def _merge_keywords(self, primary: List[str], secondary: List[str], max_terms: int = 40) -> List[str]:
        merged = []
        seen = set()
        for word in (primary or []) + (secondary or []):
            normalized = self._normalize_text(str(word))
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
            if len(merged) >= max_terms:
                break
        return merged

    def _apply_tax_slot_overrides(self, query: str, intent: Dict[str, Any]) -> None:
        if not query:
            return
        matches = re.findall(
            r"\b(tax_[a-z_]+|net_turnover_bucket|new_activity|income_type)\s*=\s*([A-Za-z0-9_]+)\b",
            query,
            flags=re.IGNORECASE,
        )
        if not matches:
            return

        irpf_overrides: Dict[str, Any] = {}
        for raw_key, raw_value in matches:
            key = raw_key.lower()
            value = raw_value
            value_lower = raw_value.lower()
            if key in {"tax_net_turnover_bucket", "net_turnover_bucket"}:
                bucket = value.upper()
                if bucket in {"GT_100K", "LT_100K"}:
                    irpf_overrides["net_turnover_bucket"] = bucket
            elif key in {"tax_new_activity", "new_activity"}:
                if value_lower in {"true", "si", "sí", "a"}:
                    irpf_overrides["new_activity"] = True
                elif value_lower in {"false", "no", "b"}:
                    irpf_overrides["new_activity"] = False
            elif key in {"tax_irpf_income_type", "income_type"}:
                if value_lower in {"actividad_profesional", "profesional", "a"} or "actividad" in value_lower:
                    irpf_overrides["income_type"] = "actividad_profesional"
                elif value_lower in {"consejero_administrador", "consejero", "administrador", "b"}:
                    irpf_overrides["income_type"] = "consejero_administrador"

        if irpf_overrides:
            intent["needs_tax"] = True
            if "IRPF" not in intent["taxes"]:
                intent["taxes"].append("IRPF")
            intent.setdefault("irpf", {})
            intent["irpf"].update(irpf_overrides)

    def _extract_tax_intent(self, query: str) -> Dict[str, Any]:
        intent = {
            "needs_tax": False,
            "taxes": [],
            "iva": {"topic": "unknown", "keywords": []},
            "irpf": {"income_type": "unknown", "new_activity": None, "net_turnover_bucket": None},
        }
        if not query:
            return intent

        if self.model:
            prompt = self._build_tax_slot_prompt(query)
            try:
                response = self.model.generate_content(prompt)
                raw = response.text or ""
            except Exception:
                logger.exception("Tax slot extraction failed")
                raw = ""

            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            payload = None
            if match:
                try:
                    payload = json.loads(match.group(0))
                except Exception:
                    payload = None

            if isinstance(payload, dict):
                intent["needs_tax"] = bool(payload.get("needs_tax", intent["needs_tax"]))
                taxes = payload.get("taxes")
                if isinstance(taxes, list):
                    intent["taxes"] = taxes
                iva_payload = payload.get("iva")
                if isinstance(iva_payload, dict):
                    intent["iva"] = iva_payload
                irpf_payload = payload.get("irpf")
                if isinstance(irpf_payload, dict):
                    intent["irpf"] = irpf_payload

        normalized = self._normalize_text(query)
        if any(token in normalized for token in ["iva", "irpf", "retencion", "retenciones", "tipo impositivo"]):
            intent["needs_tax"] = True
            if "iva" in normalized and "IVA" not in intent["taxes"]:
                intent["taxes"].append("IVA")
            if "irpf" in normalized and "IRPF" not in intent["taxes"]:
                intent["taxes"].append("IRPF")
            if "IVA" in intent["taxes"] and not (intent.get("iva") or {}).get("keywords"):
                words = [token for token in normalized.split() if len(token) > 2]
                intent["iva"]["keywords"] = words[:12]
            if "iva" in normalized and "irpf" not in normalized:
                intent["taxes"] = ["IVA"]
            elif "irpf" in normalized and "iva" not in normalized:
                intent["taxes"] = ["IRPF"]

        if "IVA" in (intent.get("taxes") or []):
            query_terms = self._extract_query_keyword_candidates(normalized)
            intent.setdefault("iva", {"topic": "unknown", "keywords": []})
            current = intent["iva"].get("keywords") or []
            intent["iva"]["keywords"] = self._merge_keywords(current, query_terms)

        self._apply_tax_slot_overrides(query, intent)
        return intent

    def _run_tax_pipeline(self, query: str) -> Optional[Dict[str, Any]]:
        intent = self._extract_tax_intent(query)
        if not intent.get("needs_tax"):
            return None

        taxes = intent.get("taxes") or []
        result = {
            "status": "not_applicable",
            "allowed_rates": [],
            "iva": None,
            "irpf": None,
            "clarifying_question": None,
            "intent": intent,
        }

        if "IVA" in taxes:
            iva_result = self.tax_resolver.resolve_iva(intent.get("iva") or {})
            result["iva"] = iva_result
            if iva_result.get("status") == "ok":
                result["allowed_rates"].append(int(iva_result.get("rate_percent")))
        if "IRPF" in taxes:
            irpf_result = self.tax_resolver.resolve_irpf(intent.get("irpf") or {})
            result["irpf"] = irpf_result
            if irpf_result.get("status") == "ok":
                result["allowed_rates"].append(int(irpf_result.get("rate_percent")))

        if any(entry and entry.get("status") == "needs_clarification" for entry in [result.get("iva"), result.get("irpf")]):
            result["status"] = "needs_clarification"
            clarifications = []
            for entry in [result.get("iva"), result.get("irpf")]:
                if entry and entry.get("status") == "needs_clarification":
                    clarifications.append(entry.get("clarifying_question"))
            result["clarifying_question"] = " ".join([text for text in clarifications if text])
            return result

        if result["allowed_rates"]:
            result["status"] = "ok"
            return result

        return None

    def _build_tax_pending_slots(self, tax_context: Optional[Dict[str, Any]]) -> List[str]:
        if not tax_context or tax_context.get("status") != "needs_clarification":
            return []
        pending: List[str] = []
        irpf = tax_context.get("irpf") or {}
        if irpf.get("status") == "needs_clarification":
            missing = irpf.get("missing_fields") or []
            if "income_type" in missing:
                pending.append("tax_irpf_income_type")
            if "net_turnover_bucket" in missing:
                pending.append("tax_net_turnover_bucket")
            if "new_activity" in missing:
                pending.append("tax_new_activity")
        return pending

    def _build_tax_context_prompt(self, tax_context: Dict[str, Any]) -> str:
        if not tax_context or tax_context.get("status") != "ok":
            return ""
        lines = [
            "\n\nTAX_RATE_RESOLVER:",
            "- Usa SOLO los porcentajes siguientes (no inventes otros).",
        ]
        iva = tax_context.get("iva")
        if iva and iva.get("status") == "ok":
            lines.append(f"- IVA: {int(iva.get('rate_percent'))}% (rule_id={iva.get('rule_id')})")
        irpf = tax_context.get("irpf")
        if irpf and irpf.get("status") == "ok":
            lines.append(f"- IRPF: {int(irpf.get('rate_percent'))}% (rule_id={irpf.get('rule_id')})")
        lines.append("- Si falta informacion, pide aclaracion y no des porcentajes.")
        return "\n".join(lines)

    def _split_by_naturaleza(self, results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        buckets = {"normativa": [], "doctrina": [], "jurisprudencia": []}
        for result in results:
            naturaleza = result.get("source_naturaleza", "")
            if naturaleza == "Normativa":
                buckets["normativa"].append(result)
            elif naturaleza == "Doctrina administrativa":
                buckets["doctrina"].append(result)
            elif naturaleza == "Jurisprudencia":
                buckets["jurisprudencia"].append(result)
        return buckets

    def _build_retrieval_plan(
        self,
        query: str,
        intent_confidence: float,
        router_decision: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        token_count = len(re.findall(r"\w+", query or ""))
        mode = (router_decision or {}).get("mode") if router_decision else None
        is_follow_up = mode in {"FOLLOWUP_SLOT_FILL", "FOLLOWUP_REFERENTIAL"}
        simple = token_count <= 8

        if is_follow_up or simple or intent_confidence >= 0.7:
            return {
                "max_total": 2,
                "llm_variants": 0,
                "per_query_limit": 8,
                "mode": "light",
            }
        if intent_confidence < 0.5:
            return {
                "max_total": 4,
                "llm_variants": 1,
                "per_query_limit": 12,
                "mode": "balanced",
            }
        return {
            "max_total": 2,
            "llm_variants": 0,
            "per_query_limit": 8,
            "mode": "light",
        }

    def _cache_get(self, key: tuple) -> Optional[Dict[str, Any]]:
        payload = _RETRIEVAL_CACHE.get(key)
        if not payload:
            return None
        _RETRIEVAL_CACHE.move_to_end(key)
        return copy.deepcopy(payload)

    def _cache_set(self, key: tuple, payload: Dict[str, Any]) -> None:
        _RETRIEVAL_CACHE[key] = copy.deepcopy(payload)
        _RETRIEVAL_CACHE.move_to_end(key)
        while len(_RETRIEVAL_CACHE) > _RETRIEVAL_CACHE_MAX:
            _RETRIEVAL_CACHE.popitem(last=False)

    def _add_authority_minipack(
        self,
        area_principal: Optional[str],
        query: str,
        sources: Dict[str, List[Dict[str, Any]]],
        reason: str,
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
        if not area_principal:
            return sources, {"added": False}

        mini_pack_ids = {
            "Fiscal": ["BOE-A-2006-20764", "BOE-A-1992-28740", "BOE-A-2003-23186"],
            "Laboral": ["BOE-A-2015-11430", "BOE-A-2015-11724", "BOE-A-1985-17303"],
            "Propiedad Intelectual": ["BOE-A-1996-8930"],
        }.get(area_principal, [])
        if not mini_pack_ids:
            return sources, {"added": False}

        added = []
        for doc_id in mini_pack_ids:
            found = any(
                item.get("document_id") == doc_id
                for bucket in sources.values()
                for item in bucket
            )
            if found:
                continue
            chunk = self._fetch_doc_chunk_by_id(doc_id)
            if not chunk:
                continue
            sources.setdefault("normativa", []).append(chunk)
            added.append(doc_id)

        return sources, {"added": bool(added), "reason": reason, "doc_ids": added}

    def _filter_sources_by_area(
        self,
        area_principal: Optional[str],
        sources: Dict[str, List[Dict[str, Any]]],
        query: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        filtered = super()._filter_sources_by_area(area_principal, sources, query)
        if area_principal != "Laboral":
            return filtered
        target_ids = {"BOE-A-1985-17303", "BOE-A-2022-4583"}
        for bucket, items in sources.items():
            for item in items:
                if item.get("document_id") in target_ids and item not in filtered.get(bucket, []):
                    filtered.setdefault(bucket, []).append(item)
        return filtered

    def _dedup_and_rank(
        self,
        buckets: Dict[str, List[Dict[str, Any]]],
        limits: Dict[str, int],
    ) -> Dict[str, List[Dict[str, Any]]]:
        deduped: Dict[str, Dict[Tuple[str, str], Dict[str, Any]]] = {
            "normativa": {},
            "doctrina": {},
            "jurisprudencia": {},
        }

        for bucket, items in buckets.items():
            for item in items:
                key = (item.get("document_id", ""), item.get("chunk_label", ""))
                score = item.get("rrf_score", item.get("similarity", 0))
                existing = deduped[bucket].get(key)
                if not existing or score > existing.get("_score", 0):
                    item["_score"] = score
                    deduped[bucket][key] = item

        ranked: Dict[str, List[Dict[str, Any]]] = {"normativa": [], "doctrina": [], "jurisprudencia": []}
        for bucket, items in deduped.items():
            sorted_items = sorted(items.values(), key=lambda x: x.get("_score", 0), reverse=True)
            ranked[bucket] = sorted_items[: limits.get(bucket, 0)]
        return ranked

    def _retrieve_hierarchical_sources_v1_1(
        self,
        query: str,
        area_principal: Optional[str],
        max_sources: int,
        expansion_max_total: int,
        expansion_llm_variants: int,
        per_query_limit: int,
        session_id: Optional[str],
        intent_confidence: float,
        router_decision: Optional[Dict[str, Any]],
        expanded_queries: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
        cache_key = (
            session_id or "",
            area_principal or "",
            self._normalize_text(query),
            expansion_max_total,
            expansion_llm_variants,
            per_query_limit,
        )
        cached = self._cache_get(cache_key)
        if cached:
            cached["trace"]["cache"] = {"hit": True, "key": cache_key}
            return cached["sources"], cached["trace"]

        forced_sources = self.reference_resolver.resolve(query)
        forced_ids = sorted({src.get("document_id") for src in forced_sources if src.get("document_id")})

        # Step 2: Query expansion
        t_expand_start = time.time()
        expanded = expanded_queries
        if expanded is None:
            expanded = self.query_expander.expand(
                query,
                max_total=expansion_max_total,
                llm_variants=expansion_llm_variants,
            )
        if not expanded:
            expanded = [query]
        logger.info("  - Query expansion took %.2fs (%d queries)", time.time() - t_expand_start, len(expanded))
        self.flow_logger.log_query_expansion(query, expanded)

        per_query_limit = max(per_query_limit, max_sources)
        combined: List[Dict[str, Any]] = []
        retrieval_debug = []
        if forced_sources:
            combined.extend(forced_sources)
        total_vector = 0
        total_lexical = 0
        primary_results = 0
        fallback_results = 0
        fallback_triggered = False
        fallback_reason = None
        core_area, area_filter_values = self._get_area_filter_values(area_principal)

        # Step 3: Hybrid search
        t_hybrid_start = time.time()
        # OPTIMIZATION: Apply area filter at DB level if enabled
        search_area_filter = area_filter_values if self._area_filter_enabled else None
        for q in expanded:
            try:
                results, debug = self.search_engine.hybrid_search(
                    query=q,
                    limit=per_query_limit,
                    return_debug=True,
                    area_filter=search_area_filter,
                )
                combined.extend(results)
                primary_results += len(results)
                retrieval_debug.append({
                    "query": q,
                    "pass": "primary",
                    "bm25_topK": [
                        {"id": item.get("document_id"), "score": item.get("fts_rank", 0.0)}
                        for item in (debug.get("lexical_results") or [])[:20]
                    ],
                    "vector_topK": [
                        {"id": item.get("document_id"), "score": item.get("similarity", 0.0)}
                        for item in (debug.get("vector_results") or [])[:20]
                    ],
                    "fused_topK": [
                        {
                            "id": item.get("document_id"),
                            "score": item.get("rrf_score", item.get("similarity", 0.0)),
                            "source": "rrf",
                        }
                        for item in (debug.get("fused_results") or [])[:20]
                    ],
                })
                # Rough estimate - each query contributes to both
                total_vector += len(results)
                total_lexical += len(results)
            except Exception:
                logger.exception("V1.1 retrieval failed for query: %s", q)
        if area_filter_values:
            min_results = max(self._area_filter_fallback_min, 1)
            if primary_results < min_results:
                fallback_triggered = True
                fallback_reason = "low_primary_results"

        if fallback_triggered:
            for q in expanded:
                try:
                    results, debug = self.search_engine.hybrid_search(
                        query=q,
                        limit=per_query_limit,
                        return_debug=True,
                        area_filter=None,
                    )
                    combined.extend(results)
                    fallback_results += len(results)
                    retrieval_debug.append({
                        "query": q,
                        "pass": "fallback",
                        "bm25_topK": [
                            {"id": item.get("document_id"), "score": item.get("fts_rank", 0.0)}
                            for item in (debug.get("lexical_results") or [])[:20]
                        ],
                        "vector_topK": [
                            {"id": item.get("document_id"), "score": item.get("similarity", 0.0)}
                            for item in (debug.get("vector_results") or [])[:20]
                        ],
                        "fused_topK": [
                            {
                                "id": item.get("document_id"),
                                "score": item.get("rrf_score", item.get("similarity", 0.0)),
                                "source": "rrf",
                            }
                            for item in (debug.get("fused_results") or [])[:20]
                        ],
                    })
                    total_vector += len(results)
                    total_lexical += len(results)
                except Exception:
                    logger.exception("V1.1 fallback retrieval failed for query: %s", q)
        logger.info("  - Hybrid search (%d queries) took %.2fs", len(expanded), time.time() - t_hybrid_start)

        combined = self._apply_reference_boost(combined, query)
        self.flow_logger.log_hybrid_search_aggregate(total_vector, total_lexical, len(combined))

        # Step 4: Bucket split
        buckets = self._split_by_naturaleza(combined)
        flat_all = []
        for bucket in buckets.values():
            flat_all.extend(bucket)
        top_5_raw = [format_source_snippet(s) for s in flat_all[:5]]
        self.flow_logger.log_bucket_split(
            len(buckets["normativa"]),
            len(buckets["doctrina"]),
            len(buckets["jurisprudencia"]),
            top_5_raw
        )

        # Step 5: Dedup and rank
        authority_question = is_authority_question(query)
        limits = {"normativa": 8, "doctrina": 1, "jurisprudencia": 1} if authority_question else {
            "normativa": 5, "doctrina": 3, "jurisprudencia": 2
        }
        before_dedup = {k: len(v) for k, v in buckets.items()}
        fused = self._dedup_and_rank(buckets, limits)
        after_dedup = {k: len(v) for k, v in fused.items()}
        top_scores = {}
        for bucket, items in fused.items():
            scores = [item.get("rrf_score", item.get("similarity", 0)) for item in items]
            top_scores[bucket] = sorted(scores, reverse=True)[:5]
        self.flow_logger.log_dedup_rank(before_dedup, after_dedup, top_scores)

        counts_pre_filter = {k: len(v) for k, v in fused.items()}

        if area_principal == "Laboral":
            normalized_query = self._normalize_text(query)
            if "contrato" in normalized_query or "artista" in normalized_query:
                target_ids = {"BOE-A-1985-17303", "BOE-A-2022-4583"}
                existing_ids = {item.get("document_id") for item in fused.get("normativa", [])}
                for item in buckets.get("normativa", []):
                    doc_id = item.get("document_id")
                    if doc_id in target_ids and doc_id not in existing_ids:
                        fused["normativa"].append(item)
                        existing_ids.add(doc_id)
                preferred_terms = ["contrato", "temporal", "duracion", "artista", "relacion laboral"]
                for doc_id in target_ids:
                    if doc_id not in existing_ids:
                        direct_item = self._fetch_doc_chunk_by_id(doc_id, preferred_terms=preferred_terms)
                        if direct_item:
                            fused["normativa"].append(direct_item)
                            existing_ids.add(doc_id)

        # Step 6: Area filter - KEY BOTTLENECK
        filtered = self._filter_sources_by_area(area_principal, fused, query)
        counts_post_filter = {k: len(v) for k, v in filtered.items()}
        dropped = sum(counts_pre_filter.values()) - sum(counts_post_filter.values())
        flat_filtered = []
        for bucket in filtered.values():
            flat_filtered.extend(bucket)
        top_5_filtered = [format_source_snippet(s) for s in flat_filtered[:5]]
        self.flow_logger.log_area_filter(counts_pre_filter, counts_post_filter, dropped, top_5_filtered)

        token_count = len(re.findall(r"\w+", query or ""))
        weak_retrieval = sum(counts_post_filter.values()) < 2
        short_query = token_count <= 6
        normalized_query = self._normalize_text(query)
        generic_query = any(token in normalized_query for token in ["como funciona", "que es", "que diferencia"])
        mini_pack_reason = None
        if short_query:
            mini_pack_reason = "short_query"
        elif weak_retrieval:
            mini_pack_reason = "weak_retrieval"
        elif generic_query:
            mini_pack_reason = "generic_query"

        mini_pack_info = {"added": False}
        if mini_pack_reason:
            filtered, mini_pack_info = self._add_authority_minipack(
                area_principal=area_principal,
                query=query,
                sources=filtered,
                reason=mini_pack_reason,
            )

        # Step 7: Authority pack
        authority_added = False
        authority_count = 0
        if authority_question:
            authority_sources = build_authority_sources(query, area_principal)
            authority_count = sum(len(v) for v in authority_sources.values())
            if authority_count:
                authority_added = True
                for bucket, items in authority_sources.items():
                    filtered[bucket].extend(items)
                filtered = self._dedup_and_rank(filtered, limits)

        final_counts = {k: len(v) for k, v in filtered.items()}
        self.flow_logger.log_authority_pack(authority_question, authority_added, authority_count, final_counts)

        top_scores: Dict[str, List[float]] = {}
        for bucket, items in filtered.items():
            scores = [item.get("rrf_score", item.get("similarity", 0)) for item in items]
            top_scores[bucket] = sorted(scores, reverse=True)[:3]

        context_docs = {}
        for bucket, items in filtered.items():
            for item in items:
                doc_id = item.get("document_id")
                if not doc_id:
                    continue
                entry = context_docs.setdefault(doc_id, {
                    "id": doc_id,
                    "title": item.get("document_title"),
                    "p_level": item.get("source_priority"),
                    "authority_rank": item.get("source_naturaleza"),
                    "chunk_ids": [],
                })
                chunk_id = item.get("chunk_id")
                if chunk_id and chunk_id not in entry["chunk_ids"]:
                    entry["chunk_ids"].append(chunk_id)

        trace = {
            "expanded_queries": expanded,
            "reference_resolver": {
                "forced_count": len(forced_sources),
                "forced_ids": forced_ids,
            },
            "retrieval_plan": {
                "max_total": expansion_max_total,
                "llm_variants": expansion_llm_variants,
                "per_query_limit": per_query_limit,
                "intent_confidence": intent_confidence,
                "router_mode": (router_decision or {}).get("mode") if router_decision else None,
            },
            "area_filter": {
                "enabled": self._area_filter_enabled,
                "requested_area": area_principal,
                "core_area": core_area,
                "values": area_filter_values or [],
                "primary_results": primary_results,
                "fallback_triggered": fallback_triggered,
                "fallback_reason": fallback_reason,
                "fallback_results": fallback_results,
            },
            "authority_question": authority_question,
            "authority_pack_added": authority_added,
            "authority_pack_count": authority_count,
            "authority_minipack": mini_pack_info,
            "retrieval_counts": {
                "combined_results": len(combined),
                "fused_pre_filter": counts_pre_filter,
                "post_filter": counts_post_filter,
                "dropped_sources": dropped,
            },
            "retrieval_debug": retrieval_debug,
            "post_filter_topK": [
                {
                    "id": item.get("document_id"),
                    "score": item.get("rrf_score", item.get("similarity", 0.0)),
                }
                for bucket in filtered.values()
                for item in bucket[:20]
            ],
            "top_scores": top_scores,
            "final_context_docs": list(context_docs.values()),
            "cache": {"hit": False, "key": cache_key},
        }
        self._cache_set(cache_key, {"sources": filtered, "trace": trace, "timestamp": time.time()})
        return filtered, trace

    def _apply_reference_boost(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        if not results or not query:
            return results

        normalized_query = self._normalize_text(query)
        boe_ids = re.findall(r"\bBOE-A-\d{4}-\d+\b", query, flags=re.IGNORECASE)
        boe_ids = {boe_id.upper() for boe_id in boe_ids}

        law_titles = re.findall(r"\b(?:Ley|Real Decreto)\s+\d+/\d{4}\b", query, flags=re.IGNORECASE)
        law_titles_norm = [self._normalize_text(title) for title in law_titles]

        article_match = re.search(
            r"\bart(?:\.|iculo)?\s*(\d+(?:\.\d+)*)(?:\s*[ªº])?\b",
            query,
            flags=re.IGNORECASE,
        )
        article_number = article_match.group(1) if article_match else None
        article_base = article_number.split(".")[0] if article_number else None
        labor_artist_boost = "contrato artist" in normalized_query or "artista" in normalized_query
        amortizacion_boost = "amortiz" in normalized_query

        for result in results:
            boost = 0.0
            doc_id = (result.get("document_id") or "").upper()
            doc_title = self._normalize_text(result.get("document_title", ""))
            chunk_label = self._normalize_text(result.get("chunk_label", ""))

            if boe_ids and doc_id in boe_ids:
                boost += 5.0
            if law_titles_norm and any(title in doc_title for title in law_titles_norm):
                boost += 2.0
            if article_base and f"articulo {article_base}" in chunk_label:
                boost += 1.5
            if labor_artist_boost and doc_id in {"BOE-A-1985-17303", "BOE-A-2022-4583"}:
                boost += 6.0
            if amortizacion_boost and doc_id == "BOE-A-2006-20764":
                boost += 2.0

            base_score = result.get("rrf_score")
            if base_score is None:
                base_score = result.get("similarity", 0.0)

            result["rrf_score"] = base_score + boost
            result["boost_score"] = boost

        return results

    def _fetch_doc_chunk_by_id(
        self,
        doc_id: str,
        preferred_terms: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not doc_id:
            return None
        qs = DocumentChunk.objects.filter(document__doc_id_oficial=doc_id).select_related(
            "document",
            "document__source",
        )
        chunk = None
        if preferred_terms:
            term_filter = Q()
            for term in preferred_terms:
                term_filter |= Q(chunk_text__icontains=term) | Q(chunk_label__icontains=term)
            chunk = qs.filter(term_filter).first()
        if chunk is None:
            chunk = qs.first()
        if not chunk:
            return None
        return {
            "rank": 1,
            "chunk_id": str(chunk.id),
            "chunk_label": chunk.chunk_label or chunk.chunk_type,
            "chunk_text": chunk.chunk_text,
            "chunk_type": chunk.chunk_type,
            "similarity": 0.0,
            "document_title": chunk.document.doc_title,
            "document_id": chunk.document.doc_id_oficial,
            "document_url": chunk.document.url,
            "source_title": chunk.document.source.titulo,
            "source_priority": chunk.document.source.prioridad,
            "source_naturaleza": chunk.document.source.naturaleza,
            "metadata": chunk.metadata,
            "search_method": "direct",
            "rrf_score": 10.0,
        }

    def _build_hierarchical_prompt(
        self,
        query: str,
        sources: Dict[str, List[Dict[str, Any]]],
        area_principal: Optional[str]
    ) -> str:
        prompt = super()._build_hierarchical_prompt(query, sources, area_principal)

        prompt = re.sub(
            r"\n\*\*Fundamento:\*\*.*?\n\n\*\*En la pr",
            "\n\n**En la pr",
            prompt,
            flags=re.DOTALL,
        )

        prompt = prompt.replace(
            "5. No incluyas listas de \"Fuentes utilizadas\" con fuentes que no citaste en Fundamento",
            "5. No incluyas listas de \"Fuentes utilizadas\"; la UI maneja las tarjetas",
        )

        prompt = re.sub(
            r"FORMATO RESPUESTA \(EVIDENCE-BACKED\):.*?\n\*\*En la pr",
            "FORMATO RESPUESTA (EVIDENCE-BACKED):\n"
            "- [Responde directamente usando solo fuentes RELEVANT]\n\n"
            "**En la pr",
            prompt,
            flags=re.DOTALL,
        )

        prompt += (
            "\n\nEJEMPLOS DE RESPUESTAS CORRECTAS:\n\n"
            "Ejemplo 1 - Respuesta con evidencia clara:\n"
            "---\n"
            "Usuario: \"¿Cuál es el tipo de IVA para servicios culturales?\"\n\n"
            "Respuesta:\n"
            "Los servicios culturales tributan al tipo reducido del 10% en el IVA. Según el artículo 91.Uno.2.4º de la Ley 37/1992 del IVA, se aplica este tipo a las prestaciones de servicios relacionadas con exposiciones y ferias de carácter comercial.\n\n"
            "<!--CITED_IDS: BOE-A-1992-28740 -->\n"
            "---\n\n"
            "Ejemplo 2 - Respuesta citando múltiples fuentes:\n"
            "---\n"
            "Usuario: \"¿Qué retenciones aplican a artistas autónomos?\"\n\n"
            "Respuesta:\n"
            "Los artistas en régimen de autónomos están sujetos a una retención del 15% sobre sus rendimientos profesionales, según el artículo 101.5.a) de la Ley 35/2006 del IRPF. Durante los tres primeros años de actividad, la retención se reduce al 7%, conforme al artículo 101.5.b) del mismo texto legal.\n\n"
            "<!--CITED_IDS: BOE-A-2006-20764 -->\n"
            "---\n\n"
            "Ejemplo 3 - Abstención por falta de evidencia:\n"
            "---\n"
            "Usuario: \"¿Cuánto cuesta registrar un nombre artístico en España?\"\n\n"
            "Respuesta:\n"
            "Lo siento, no dispongo de información específica sobre los costes de registro de nombres artísticos en la documentación legal consultada. Esta información probablemente requiere consultar las tasas oficiales de la Oficina Española de Patentes y Marcas (OEPM) o del Registro Civil.\n\n"
            "<!--CITED_IDS: -->\n"
            "---\n\n"
            "AHORA RESPONDE LA PREGUNTA DEL USUARIO SIGUIENDO ESTOS EJEMPLOS:\n"
        )

        prompt += (
            "\n\n⚠️ CITACION OBLIGATORIA - REQUISITO CRITICO:\n"
            "DEBES citar TODAS las fuentes que uses en tu respuesta. NO EXCEPCIONES.\n\n"
            "Al final de tu respuesta, SIEMPRE incluye este comentario HTML con los IDs citados:\n"
            "<!--CITED_IDS: BOE-A-XXXX-XXXXX, BOE-A-YYYY-YYYYY -->\n\n"
            "Reglas ESTRICTAS:\n"
            "- Si mencionas una ley, reglamento o concepto de una fuente → DEBES citarla\n"
            "- Incluye SOLO los document_id de fuentes que realmente usaste\n"
            "- Separa multiples IDs con comas (ej: BOE-A-2006-20764, BOE-A-1992-28740)\n"
            "- Si NO puedes citar fuentes especificas, NO respondas (abstente)\n"
            "- El comentario es invisible al usuario pero OBLIGATORIO para el sistema\n\n"
            "✅ CORRECTO: Respuesta basada en fuentes + <!--CITED_IDS: BOE-A-... -->\n"
            "❌ INCORRECTO: Respuesta sin <!--CITED_IDS: ... --> o con IDs vacios\n"
        )

        return prompt

    def _extract_cited_ids(self, answer: str) -> set:
        """
        Extract cited document IDs from HTML comment and/or [ID: ...] markers.
        """
        if not answer:
            return set()

        cited_ids = set()

        html_comment_match = re.search(
            r"<!--\s*CITED_IDS:\s*(.*?)\s*-->",
            answer,
            re.IGNORECASE,
        )
        if html_comment_match:
            ids_str = html_comment_match.group(1).strip()
            if ids_str:
                cited_ids.update(
                    doc_id.strip()
                    for doc_id in ids_str.split(",")
                    if doc_id.strip()
                )

        if not cited_ids:
            cited_ids.update(re.findall(r"\[ID:\s*([^\]]+)\]", answer))
            cited_ids = {cid.strip() for cid in cited_ids if cid.strip()}

        if cited_ids:
            logger.info("Extracted %d cited IDs: %s", len(cited_ids), cited_ids)
        return cited_ids

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        if not self.embedding_service or not text:
            return None
        cache_key = self._normalize_text(text)[:500]
        cached = self._semantic_embedding_cache.get(cache_key)
        if cached is not None:
            self._semantic_embedding_cache.move_to_end(cache_key)
            return cached
        try:
            embedding = self.embedding_service.embed(cache_key)
        except Exception:
            logger.exception("V1.1 semantic embedding failed")
            return None
        self._semantic_embedding_cache[cache_key] = embedding
        self._semantic_embedding_cache.move_to_end(cache_key)
        while len(self._semantic_embedding_cache) > self._semantic_cache_max:
            self._semantic_embedding_cache.popitem(last=False)
        return embedding

    def _source_matches_tokens_semantic(
        self,
        source: Dict[str, Any],
        tokens: List[str],
    ) -> bool:
        if not tokens:
            return False
        if not self._semantic_match_enabled or not self.embedding_service:
            return self._source_matches_tokens(source, tokens)

        source_text = self._normalize_text(
            (source.get("chunk_text", "") or "")
            + " "
            + (source.get("chunk_label", "") or "")
        )
        if not source_text:
            return False

        long_tokens = []
        for token in tokens:
            if len(token) <= 4:
                if token in source_text:
                    return True
            else:
                long_tokens.append(token)

        if not long_tokens:
            return False

        source_embedding = self._get_embedding(source_text[:500])
        if not source_embedding:
            return False

        for token in long_tokens:
            token_embedding = self._get_embedding(token)
            if not token_embedding:
                continue
            similarity = self._cosine_similarity(source_embedding, token_embedding)
            if similarity >= self._semantic_match_threshold:
                return True

        return False

    def _extract_citations_from_answer(
        self,
        answer: str,
        sources: Dict[str, List[Dict[str, Any]]],
    ) -> set:
        if not answer:
            return set()

        cited_ids = set()
        answer_norm = self._normalize_text(answer)

        for bucket in sources.values():
            for chunk in bucket:
                doc_id = chunk.get("document_id")
                if not doc_id:
                    continue
                if doc_id in answer:
                    cited_ids.add(doc_id)
                    continue
                title = chunk.get("document_title", "")
                label = chunk.get("chunk_label", "")
                title_norm = self._normalize_text(title) if title else ""
                label_norm = self._normalize_text(label) if label else ""
                if (title_norm and title_norm in answer_norm) or (label_norm and label_norm in answer_norm):
                    cited_ids.add(doc_id)

        return cited_ids

    def _resolve_cited_ids(
        self,
        answer: str,
        sources: Dict[str, List[Dict[str, Any]]],
    ) -> set:
        cited_ids = self._extract_cited_ids(answer)
        if cited_ids:
            return cited_ids
        return self._extract_citations_from_answer(answer, sources)

    def _ensure_citation_comment(self, answer: str, cited_ids: set) -> str:
        if not answer:
            return answer

        new_comment = "<!--CITED_IDS: -->"
        if cited_ids:
            new_comment = f"<!--CITED_IDS: {', '.join(sorted(cited_ids))} -->"

        if re.search(r"<!--\s*CITED_IDS:\s*.*?\s*-->", answer, re.IGNORECASE):
            return re.sub(
                r"<!--\s*CITED_IDS:\s*.*?\s*-->",
                new_comment,
                answer,
                flags=re.IGNORECASE,
            )

        return answer.rstrip() + f"\n\n{new_comment}"

    def _retry_with_stricter_prompt(
        self,
        prompt: str,
        query: str,
        sources: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        if not self.model:
            return self._generate_fallback_answer(query, sources)

        stricter_prompt = (
            prompt
            + "\n\nINSTRUCCIONES EXTRA:\n"
            + "- Responde SOLO con afirmaciones apoyadas por las fuentes.\n"
            + "- Si falta evidencia, usa Two-Lane Mode o abstente.\n"
            + "- No inventes hechos ni tasas.\n"
        )
        try:
            response = self.model.generate_content(stricter_prompt)
            return response.text or ""
        except Exception:
            logger.exception("V1.1 strict retry failed")
            return self._generate_fallback_answer(query, sources)

    def _add_low_confidence_disclaimer(self, answer: str) -> str:
        disclaimer = (
            "\n\nNota: la evidencia recuperada no respalda plenamente esta respuesta. "
            "Si puedes aportar mÇ­s contexto o una referencia concreta, puedo afinarla."
        )
        return (answer or "").rstrip() + disclaimer

    def _postprocess_answer(
        self,
        answer_text: str,
        sources: Dict[str, List[Dict[str, Any]]],
        abstained: bool,
        allowed_percentages: Optional[List[int]] = None,
    ) -> Tuple[str, set, List[Dict[str, Any]], List[str]]:
        postprocess_errors = []
        before_validation = answer_text
        try:
            allowed_ids = {src.get('document_id', '') for group in sources.values() for src in group if src.get('document_id')}
            def drop_bad_id(match):
                doc_id = match.group(1).strip()
                return match.group(0) if doc_id in allowed_ids else ""
            answer_text = re.sub(r"\[ID:\s*([^\]]+)\]", drop_bad_id, answer_text)
        except Exception:
            logger.exception("V1.1 citation cleanup failed")
            postprocess_errors.append("citation_cleanup_failed")

        try:
            allowed = allowed_percentages or []
            sanitized = sanitize_answer_percentages(
                answer_text,
                allowed,
                non_tax_allowlist=self._non_tax_percent_allowlist,
            )
            if sanitized.get("changed"):
                answer_text = sanitized.get("text", answer_text)
                postprocess_errors.append("tax_percent_sanitized")
        except Exception:
            logger.exception("V1.1 tax percentage validation failed")
            postprocess_errors.append("tax_percent_validation_failed")

        self.flow_logger.log_validation(answer_text != before_validation, len(before_validation), len(answer_text))

        cited_ids = set()
        try:
            cited_ids = self._resolve_cited_ids(answer_text, sources)
            answer_text = self._ensure_citation_comment(answer_text, cited_ids)
        except Exception:
            logger.exception("V1.1 cited ID resolution failed")
            postprocess_errors.append("cited_resolution_failed")

        try:
            answer_text = self._attach_citations(answer_text, sources)
        except Exception:
            logger.exception("V1.1 citation attachment failed")
            postprocess_errors.append("citation_failed")

        try:
            cited_ids = self._extract_cited_ids(answer_text)
        except Exception:
            logger.exception("V1.1 cited ID extraction failed")
            cited_ids = set()
            postprocess_errors.append("cited_extraction_failed")

        try:
            formatted_sources = self._format_sources(sources, cited_ids)
        except Exception:
            logger.exception("V1.1 source formatting failed")
            formatted_sources = []
            postprocess_errors.append("format_sources_failed")

        try:
            self.flow_logger.log_sources_final(formatted_sources, cited_ids)
        except Exception:
            logger.exception("V1.1 flow logging sources failed")

        return answer_text, cited_ids, formatted_sources, postprocess_errors

    def _classify_intent_v1_1(
        self,
        query: str,
        area_principal: Optional[str],
        forced_area: Optional[str],
        trace_context: Optional[Dict[str, Any]],
    ) -> Tuple[
        Optional[str],
        Optional[str],
        float,
        Optional[Dict[str, Any]],
        Optional[Dict[str, Any]],
        Optional[List[str]],
        Dict[str, Any],
    ]:
        router_decision = (trace_context or {}).get("router_decision") if trace_context else None
        intent_area = None
        intent_confidence = 0.0
        intent_scores = None
        expanded_queries = None
        tentative_plan = None

        if forced_area:
            area_principal = forced_area
            intent_area = forced_area
            intent_confidence = 1.0
            logger.info("Using forced area: %s", area_principal)
            self.flow_logger.log_intent_classification(area_principal, 1.0)
        elif area_principal is None:
            tentative_plan = self._build_retrieval_plan(
                query=query,
                intent_confidence=0.6,
                router_decision=router_decision,
            )
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                intent_future = executor.submit(
                    self.intent_classifier.classify_with_confidence, query
                )
                expansion_future = executor.submit(
                    self.query_expander.expand,
                    query,
                    max_total=tentative_plan["max_total"],
                    llm_variants=tentative_plan["llm_variants"],
                )
                area_classification = intent_future.result()
                expanded_queries = expansion_future.result()

            area_principal = area_classification.get("area")
            intent_area = area_principal
            intent_confidence = area_classification.get("confidence", 0.0)
            intent_scores = area_classification.get("scores")
            self.flow_logger.log_intent_classification(area_principal, intent_confidence)
        else:
            intent_area = area_principal
            intent_confidence = 1.0
            logger.info("Using pre-classified area: %s", area_principal)
            self.flow_logger.log_intent_classification(area_principal, 1.0)

        retrieval_plan = self._build_retrieval_plan(
            query=query,
            intent_confidence=intent_confidence,
            router_decision=router_decision,
        )
        if expanded_queries is not None and tentative_plan is not None:
            if (
                tentative_plan["max_total"] != retrieval_plan["max_total"]
                or tentative_plan["llm_variants"] != retrieval_plan["llm_variants"]
            ):
                expanded_queries = self.query_expander.expand(
                    query,
                    max_total=retrieval_plan["max_total"],
                    llm_variants=retrieval_plan["llm_variants"],
                )

        return (
            area_principal,
            intent_area,
            intent_confidence,
            intent_scores,
            router_decision,
            expanded_queries,
            retrieval_plan,
        )

    def _build_prompt_v1_1(
        self,
        query: str,
        sources: Dict[str, List[Dict[str, Any]]],
        area_principal: Optional[str],
        context_block: Optional[str],
        question_type: Optional[str],
    ) -> str:
        prompt = self._build_hierarchical_prompt(
            query=query,
            sources=sources,
            area_principal=area_principal,
        )
        if context_block:
            prompt += f"\n\nCONTEXTO CONVERSACIONAL:\n{context_block}\n"
        if question_type:
            prompt += f"\nQUESTION_TYPE: {question_type}\n"
        return prompt

    def _generate_answer_v1_1(
        self,
        prompt: str,
        query: str,
        sources: Dict[str, List[Dict[str, Any]]],
    ) -> Tuple[str, str]:
        try:
            response = self.model.generate_content(prompt)
            answer_text = response.text
            raw_completion = answer_text
            self.flow_logger.log_llm_response(len(answer_text), answer_text)
        except Exception as e:
            logger.exception("V1.1 LLM generation failed")
            answer_text = self._generate_fallback_answer(query, sources)
            raw_completion = answer_text
            self.flow_logger.log_llm_response(len(answer_text), answer_text, error=str(e))
        return answer_text, raw_completion

    def _build_debug_summary_v1_1(
        self,
        intent_area: Optional[str],
        intent_confidence: float,
        intent_scores: Optional[Dict[str, Any]],
        trace: Dict[str, Any],
        abstained: bool,
        cited_ids: set,
        formatted_sources: List[Dict[str, Any]],
        postprocess_errors: List[str],
    ) -> Dict[str, Any]:
        cited_count = sum(1 for source in formatted_sources if source.get("is_cited"))
        additional_count = max(len(formatted_sources) - cited_count, 0)
        return {
            "intent": {
                "area_detected": intent_area,
                "confidence": intent_confidence,
                "scores": intent_scores,
            },
            "retrieval_plan": trace.get("retrieval_plan"),
            "authority_minipack": trace.get("authority_minipack"),
            "reference_resolver": trace.get("reference_resolver"),
            "query_expansion": {
                "count": len(trace.get("expanded_queries") or []),
                "queries": (trace.get("expanded_queries") or [])[:5],
            },
            "retrieval": trace.get("retrieval_counts"),
            "dedup_rank": {
                "before": trace.get("retrieval_counts", {}).get("fused_pre_filter"),
                "after": trace.get("retrieval_counts", {}).get("post_filter"),
                "top_scores": trace.get("top_scores"),
            },
            "area_filter": {
                "before": trace.get("retrieval_counts", {}).get("fused_pre_filter"),
                "after": trace.get("retrieval_counts", {}).get("post_filter"),
                "dropped": trace.get("retrieval_counts", {}).get("dropped_sources"),
                "core_area": (trace.get("area_filter") or {}).get("core_area"),
                "values": (trace.get("area_filter") or {}).get("values"),
                "fallback_triggered": (trace.get("area_filter") or {}).get("fallback_triggered"),
                "fallback_reason": (trace.get("area_filter") or {}).get("fallback_reason"),
            },
            "authority_pack": {
                "is_authority_question": trace.get("authority_question"),
                "added": trace.get("authority_pack_added"),
                "count": trace.get("authority_pack_count"),
            },
            "abstain": {
                "abstained": abstained,
            },
            "citations": {
                "cited_ids": sorted(cited_ids),
                "cited_count": cited_count,
                "additional_count": additional_count,
            },
            "sources_preview": [
                {
                    "id": src.get("id"),
                    "title": src.get("title"),
                    "label": src.get("label"),
                    "score": src.get("relevance_score"),
                    "is_cited": src.get("is_cited"),
                }
                for src in formatted_sources[:5]
            ],
            "postprocess_errors": postprocess_errors if postprocess_errors else [],
        }

    def _build_chat_trace_v1_1(
        self,
        trace_context: Optional[Dict[str, Any]],
        query: str,
        session_id: Optional[str],
        intent_area: Optional[str],
        intent_confidence: float,
        intent_scores: Optional[Dict[str, Any]],
        trace: Dict[str, Any],
        prompt: str,
        sources: Dict[str, List[Dict[str, Any]]],
        raw_completion: str,
        cited_ids: set,
        abstained: bool,
        answer_text: str,
        postprocess_errors: List[str],
    ) -> Dict[str, Any]:
        citations_instruction = ""
        if "CITACION OBLIGATORIA" in prompt:
            idx = prompt.find("CITACION OBLIGATORIA")
            citations_instruction = prompt[idx: idx + 800]

        return {
            "orchestrator_input": {
                "case_id": (trace_context or {}).get("case_id"),
                "turn": (trace_context or {}).get("turn"),
                "area": (trace_context or {}).get("area") or intent_area,
                "user_text": (trace_context or {}).get("user_text") or query,
                "session_id": (trace_context or {}).get("session_id") or session_id,
                "router_decision": (trace_context or {}).get("router_decision"),
                "intent_classifier": {
                    "area_detected": intent_area,
                    "confidence": intent_confidence,
                    "scores": intent_scores,
                },
            },
            "retrieval": {
                "plan": trace.get("retrieval_plan"),
                "cache": trace.get("cache"),
                "expanded_query": trace.get("expanded_queries"),
                "bm25_topK": [item for entry in trace.get("retrieval_debug", []) for item in entry.get("bm25_topK", [])],
                "vector_topK": [item for entry in trace.get("retrieval_debug", []) for item in entry.get("vector_topK", [])],
                "fused_topK": [item for entry in trace.get("retrieval_debug", []) for item in entry.get("fused_topK", [])],
                "after_filters": trace.get("post_filter_topK"),
                "final_selected_context": trace.get("final_context_docs"),
                "filters": trace.get("retrieval_counts"),
            },
            "prompt": {
                "system_prompt_id": "hierarchical_prompt_v1_1",
                "user_prompt": prompt,
                "context_length_chars": sum(len(item.get("chunk_text") or "") for bucket in sources.values() for item in bucket),
                "citations_instructions": citations_instruction,
            },
            "model_output": {
                "raw_text": raw_completion,
                "extracted_citations": sorted(cited_ids),
                "abstain": {
                    "abstained": abstained,
                    "min_token_matches": getattr(self, "_min_token_matches", None),
                    "min_strict_matches": getattr(self, "_min_strict_matches", None),
                },
                "final_response": answer_text,
            },
            "post_processing": {
                "postprocess_errors": postprocess_errors,
            },
        }

    def _build_metadata_v1_1(
        self,
        area_principal: Optional[str],
        question_type: Optional[str],
        forced_area: Optional[str],
        abstained: bool,
        judge_result: Dict[str, Any],
        redo_performed: bool,
        sources: Dict[str, List[Dict[str, Any]]],
        formatted_sources: List[Dict[str, Any]],
        cited_ids: set,
        trace: Dict[str, Any],
        postprocess_errors: List[str],
        debug_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        cited_count = sum(1 for source in formatted_sources if source.get("is_cited"))
        additional_count = max(len(formatted_sources) - cited_count, 0)
        return {
            "version": "v1_1",
            "area_principal": area_principal,
            "model": self.model.model_name,
            "normativa_count": len(sources.get("normativa", [])),
            "doctrina_count": len(sources.get("doctrina", [])),
            "jurisprudencia_count": len(sources.get("jurisprudencia", [])),
            "total_sources": len(formatted_sources),
            "cited_count": cited_count,
            "additional_count": additional_count,
            "cited_ids": sorted(cited_ids),
            "question_type": question_type,
            "forced_area": forced_area,
            "abstained": abstained,
            "judge": judge_result,
            "redo_performed": redo_performed,
            "expanded_queries": trace.get("expanded_queries"),
            "authority_question": trace.get("authority_question"),
            "authority_pack_added": trace.get("authority_pack_added"),
            "authority_pack_count": trace.get("authority_pack_count"),
            "authority_minipack": trace.get("authority_minipack"),
            "retrieval_counts": trace.get("retrieval_counts"),
            "top_scores": trace.get("top_scores"),
            "postprocess_errors": postprocess_errors if postprocess_errors else None,
            "debug_summary": debug_summary,
        }

    def answer_query(
        self,
        query: str,
        area_principal: Optional[str] = None,
        max_sources: int = 10,
        forced_area: Optional[str] = None,
        question_type: Optional[str] = None,
        context_block: Optional[str] = None,
        session_id: Optional[str] = None,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        t_total_start = time.time()
        logger.info("V1.1 RAG query: '%s'", query[:100])

        # Start flow logging
        self.flow_logger.start_query(query, session_id=session_id)

        if self._is_sensitive_internal_query(query):
            answer_text = self._build_sensitive_response()
            self.flow_logger.log_intent_classification("restricted", 1.0)
            self.flow_logger.log_final_answer(len(answer_text), True, answer_text)
            self.flow_logger.finish_and_write()
            return {
                "answer": answer_text,
                "sources": [],
                "metadata": {
                    "version": "v1_1",
                    "area_principal": "restricted",
                    "model": self.model.model_name,
                    "normativa_count": 0,
                    "doctrina_count": 0,
                    "jurisprudencia_count": 0,
                    "total_sources": 0,
                    "abstained": False,
                    "restricted_query": True,
                },
            }

        # Step 0: Meta query bypass (before intent classification)
        t_meta_start = time.time()
        if self._is_meta_query(query):
            logger.info("Meta query detected, bypassing retrieval (%.2fs)", time.time() - t_meta_start)
            answer_text = self._build_meta_response()
            self.flow_logger.log_intent_classification("meta", 1.0)
            self.flow_logger.log_final_answer(len(answer_text), True, answer_text)
            self.flow_logger.finish_and_write()

            return {
                "answer": answer_text,
                "sources": [],
                "metadata": {
                    "version": "v1_1",
                    "area_principal": "meta",
                    "model": self.model.model_name,
                    "normativa_count": 0,
                    "doctrina_count": 0,
                    "jurisprudencia_count": 0,
                    "total_sources": 0,
                    "abstained": False,
                    "is_meta_query": True,
                },
            }

        router_decision = (trace_context or {}).get("router_decision") if trace_context else None

        # Step 1: Intent classification + query expansion
        t_intent_start = time.time()
        (
            area_principal,
            intent_area,
            intent_confidence,
            intent_scores,
            router_decision,
            expanded_queries,
            retrieval_plan,
        ) = self._classify_intent_v1_1(
            query=query,
            area_principal=area_principal,
            forced_area=forced_area,
            trace_context=trace_context,
        )
        t_intent_elapsed = time.time() - t_intent_start
        logger.info("Stage 1 (Intent+Expansion) took %.2fs", t_intent_elapsed)

        # Step 2: Retrieval
        t_retrieval_start = time.time()
        sources, trace = self._retrieve_hierarchical_sources_v1_1(
            query=query,
            area_principal=area_principal,
            max_sources=max_sources,
            expansion_max_total=retrieval_plan["max_total"],
            expansion_llm_variants=retrieval_plan["llm_variants"],
            per_query_limit=retrieval_plan["per_query_limit"],
            session_id=session_id,
            intent_confidence=intent_confidence,
            router_decision=router_decision,
            expanded_queries=expanded_queries,
        )
        t_retrieval_elapsed = time.time() - t_retrieval_start
        logger.info("Stage 2 (Retrieval) took %.2fs", t_retrieval_elapsed)

        # Step 3: Abstain check
        t_abstain_start = time.time()
        abstained = self._should_abstain(query, area_principal, sources)
        logger.info("Stage 3 (Abstain check) took %.2fs", time.time() - t_abstain_start)
        self.flow_logger.log_abstain_check(abstained, "low_evidence" if abstained else "sufficient_evidence")

        tax_context = self._run_tax_pipeline(query)
        self._last_allowed_percentages = tax_context.get("allowed_rates", []) if tax_context else []
        if tax_context and tax_context.get("status") == "needs_clarification":
            answer_text = tax_context.get("clarifying_question") or "Puedes aclarar un poco mas?"
            self.flow_logger.log_final_answer(len(answer_text), True, answer_text)
            self.flow_logger.finish_and_write()
            pending_slots = self._build_tax_pending_slots(tax_context)
            metadata = {
                "version": "v1_1",
                "area_principal": area_principal,
                "model": self.model.model_name,
                "normativa_count": 0,
                "doctrina_count": 0,
                "jurisprudencia_count": 0,
                "total_sources": 0,
                "abstained": False,
                "tax_resolution": tax_context,
            }
            if pending_slots:
                metadata["pending_slots"] = pending_slots
            return {
                "answer": answer_text,
                "sources": [],
                "metadata": metadata,
            }

        deterministic_tax = False
        if tax_context and tax_context.get("status") == "ok":
            deterministic_tax = self._is_rate_only_tax_query(query)
            if deterministic_tax:
                sources = self._build_tax_sources(tax_context)
                abstained = False
            else:
                sources = self._inject_tax_sources(sources, tax_context)

        # Step 4: Prompt building
        t_prompt_start = time.time()
        if deterministic_tax:
            prompt = "DETERMINISTIC_TAX_RESPONSE"
        else:
            prompt = self._build_prompt_v1_1(
                query=query,
                sources=sources,
                area_principal=area_principal,
                context_block=context_block,
                question_type=question_type,
            )
            if tax_context and tax_context.get("status") == "ok":
                prompt += self._build_tax_context_prompt(tax_context)
        logger.info("Stage 4 (Prompt building) took %.2fs", time.time() - t_prompt_start)

        # Step 5: LLM generation
        t_llm_start = time.time()
        if deterministic_tax:
            answer_text = self._build_tax_rate_answer(query, tax_context)
            raw_completion = answer_text
            self.flow_logger.log_llm_response(len(answer_text), answer_text)
        else:
            answer_text, raw_completion = self._generate_answer_v1_1(
                prompt=prompt,
                query=query,
                sources=sources,
            )
        t_llm_elapsed = time.time() - t_llm_start
        logger.info("Stage 5 (LLM generation) took %.2fs", t_llm_elapsed)

        # Step 6: Post-processing
        t_postprocess_start = time.time()
        answer_text, cited_ids, formatted_sources, postprocess_errors = self._postprocess_answer(
            answer_text=answer_text,
            sources=sources,
            abstained=abstained,
            allowed_percentages=self._last_allowed_percentages,
        )
        logger.info("Stage 6 (Post-processing) took %.2fs", time.time() - t_postprocess_start)

        # Step 7: Judge + optional redo (DISABLED BY DEFAULT for performance)
        t_judge_start = time.time()
        redo_performed = False

        if self._judge_enabled:
            judge_result = self.judge.judge(question=query, answer=answer_text, sources=sources)
            if judge_result.get("verdict") == "REDO":
                redo_performed = True
                answer_text = self._retry_with_stricter_prompt(prompt, query, sources)
                answer_text, cited_ids, formatted_sources, postprocess_errors = self._postprocess_answer(
                    answer_text=answer_text,
                    sources=sources,
                    abstained=abstained,
                    allowed_percentages=self._last_allowed_percentages,
                )
                judge_result = self.judge.judge(question=query, answer=answer_text, sources=sources)

            if judge_result.get("verdict") == "REDO":
                answer_text = self._add_low_confidence_disclaimer(answer_text)
        else:
            # Judge disabled - skip for performance (saves 15-25s per request)
            judge_result = {"verdict": "SKIPPED", "reasons": ["Judge disabled for performance"]}
            logger.info("Judge skipped (disabled for performance)")

        t_judge_elapsed = time.time() - t_judge_start
        logger.info("Stage 7 (Judge%s) took %.2fs", " + redo" if redo_performed else "", t_judge_elapsed)

        self.flow_logger.log_judge(judge_result.get("verdict"), judge_result.get("reasons", []))

        # Step 12: Final answer logging
        is_helpful = len(answer_text) > 100  # Simple heuristic
        self.flow_logger.log_final_answer(len(answer_text), is_helpful, answer_text, cited_ids)

        # Write flow log to file
        self.flow_logger.finish_and_write()

        # Step 8: Build response metadata
        t_metadata_start = time.time()
        debug_summary = self._build_debug_summary_v1_1(
            intent_area=intent_area,
            intent_confidence=intent_confidence,
            intent_scores=intent_scores,
            trace=trace,
            abstained=abstained,
            cited_ids=cited_ids,
            formatted_sources=formatted_sources,
            postprocess_errors=postprocess_errors,
        )

        chat_trace = self._build_chat_trace_v1_1(
            trace_context=trace_context,
            query=query,
            session_id=session_id,
            intent_area=intent_area,
            intent_confidence=intent_confidence,
            intent_scores=intent_scores,
            trace=trace,
            prompt=prompt,
            sources=sources,
            raw_completion=raw_completion,
            cited_ids=cited_ids,
            abstained=abstained,
            answer_text=answer_text,
            postprocess_errors=postprocess_errors,
        )
        self._write_chat_trace(chat_trace)

        metadata = self._build_metadata_v1_1(
            area_principal=area_principal,
            question_type=question_type,
            forced_area=forced_area,
            abstained=abstained,
            judge_result=judge_result,
            redo_performed=redo_performed,
            sources=sources,
            formatted_sources=formatted_sources,
            cited_ids=cited_ids,
            trace=trace,
            postprocess_errors=postprocess_errors,
            debug_summary=debug_summary,
        )
        if tax_context:
            metadata["tax_resolution"] = tax_context
        logger.info("Stage 8 (Build metadata) took %.2fs", time.time() - t_metadata_start)

        t_total_elapsed = time.time() - t_total_start
        logger.info("TOTAL RAG pipeline took %.2fs (Intent: %.2fs, Retrieval: %.2fs, LLM: %.2fs, Judge: %.2fs)",
                    t_total_elapsed, t_intent_elapsed, t_retrieval_elapsed, t_llm_elapsed, t_judge_elapsed)

        return {
            "answer": answer_text,
            "sources": formatted_sources,
            "metadata": metadata,
        }

    def _is_rate_seeking_query(self, query: str) -> bool:
        """
        Detect if query is asking for specific rates/percentages.

        Examples of rate-seeking queries:
        - "¿Cuál es el tipo de IVA...?"
        - "¿Qué porcentaje...?"
        - "¿Cuánto es el IVA...?"
        """
        norm_query = self._normalize_text(query)
        rate_patterns = [
            r"\btipo\b",
            r"\bporcentaje\b",
            r"\bcuanto\s+(es|tiene|aplica)\b",
            r"\btasa\b",
            r"%",
            r"\brate\b",
        ]
        return any(re.search(pattern, norm_query, re.IGNORECASE) for pattern in rate_patterns)

    def _should_abstain(
        self,
        query: str,
        area_principal: Optional[str],
        sources: Dict[str, List[Dict[str, Any]]]
    ) -> bool:
        """
        Override to relax IVA hard-abstain for non-rate questions.

        Key change: Only enforce IVA-token hard requirement when query is rate-seeking.
        This prevents abstaining on conceptual IVA questions (obligations, exemptions, etc.)
        when sources don't contain numeric/rate evidence.
        """
        total_sources = sum(len(v) for v in sources.values())
        if total_sources == 0:
            return True

        # Build tokens to check
        tokens: List[str] = []
        strict_tokens: List[str] = []
        if area_principal and area_principal in self._area_tokens:
            tokens.extend([self._normalize_text(t) for t in self._area_tokens[area_principal]])
            strict_tokens.extend([self._normalize_text(t) for t in self._area_required_terms.get(area_principal, [])])
            strict_tokens.extend([self._normalize_text(t) for t in self._area_law_hints.get(area_principal, [])])
        else:
            # fallback: use extracted keywords from query
            tokens.extend([self._normalize_text(t) for t in self.intent_classifier.extract_keywords(query)])

        if not tokens:
            return False  # nothing to match against

        def count_matches(token_list: List[str]) -> int:
            count = 0
            for group in sources.values():
                for src in group:
                    if self._source_matches_tokens_semantic(src, token_list):
                        count += 1
            return count

        # Strict: require minimum matches on law/required tokens when area is known
        if strict_tokens:
            strict_matches = count_matches(strict_tokens)
            if strict_matches < self._min_strict_matches:
                norm_query = self._normalize_text(query)
                if area_principal == "Laboral" and any(token in norm_query for token in ["contrato", "artista", "artistas"]):
                    pass
                else:
                    return True

        # If the area is known and we have zero normativa/doctrina, abstain (likely off-topic)
        # RELAXED THRESHOLD: Only abstain if <1 priority sources AND <2 total sources
        # This allows answering with jurisprudencia or FAQ sources if relevant
        if area_principal:
            priority_sources = len(sources.get('normativa', [])) + len(sources.get('doctrina', []))
            if priority_sources < 1 and total_sources < 2:
                return True

            # MODIFIED: Only enforce IVA-token hard requirement for rate-seeking queries
            norm_query = self._normalize_text(query)
            if "iva" in norm_query and self._is_rate_seeking_query(query):
                # Rate-seeking IVA query: require IVA/rate tokens in sources
                iva_tokens = ["iva", "impuesto sobre el valor añadido", "tipo impositivo"]
                if not any(
                    self._source_matches_tokens_semantic(
                        src,
                        [self._normalize_text(t) for t in iva_tokens],
                    )
                    for grp in sources.values()
                    for src in grp
                ):
                    return True

        token_matches = count_matches(tokens)
        return token_matches < self._min_token_matches

    def _validate_answer(
        self,
        answer: str,
        sources: Dict[str, List[Dict[str, Any]]],
        area_principal: Optional[str],
        query: str,
    ) -> str:
        """
        Override to fix numeric validation logic.

        Key change: Only block answers that make UNSUPPORTED numeric claims.
        Do NOT block answers that have no numbers just because sources don't include rates.

        Rule:
        - If answer contains a numeric claim (rate/%/tipo), require support
        - If answer has no numbers, do not abstain just because sources don't include rate patterns
        """
        if not answer:
            return answer

        allowed_ids = {src.get('document_id', '') for group in sources.values() for src in group if src.get('document_id')}
        source_text = " ".join([src.get('chunk_text', '') for group in sources.values() for src in group])
        norm_source_text = self._normalize_text(source_text)

        # Check if answer contains any numeric rate claims
        found_rates = re.findall(r"(\d+(?:[.,]\d+)?)\s*(?:%|por ciento|por 100)", answer)

        if found_rates:
            # Answer makes numeric claims - validate each one
            if area_principal == "Fiscal" or "iva" in self._normalize_text(query):
                allowed_rates = {"0", "4", "5", "10", "21", "0.0", "4.0", "5.0", "10.0", "21.0"}
                for rate in found_rates:
                    rate_clean = rate.replace(",", ".").rstrip(".")
                    # Check if rate is in allowed list
                    if rate_clean not in allowed_rates:
                        logger.warning(f"Unsupported rate {rate_clean} not in allowed rates, abstaining")
                        return self._build_abstain_answer(query)
                    # Check if rate appears in sources
                    pattern_rate = rf"{re.escape(rate_clean)}\s*(%|por ciento|por 100)"
                    if not (re.search(pattern_rate, source_text, flags=re.IGNORECASE) or re.search(pattern_rate, norm_source_text, flags=re.IGNORECASE)):
                        logger.warning(f"Rate {rate_clean} not found in sources, abstaining")
                        return self._build_abstain_answer(query)
        # REMOVED: Don't abstain if answer has no rates (even if sources don't have rates either)
        # This was the key fix - answers without numeric claims are fine regardless of source content

        # Remove citations with IDs not in allowed_ids
        def drop_bad_id(match: re.Match) -> str:
            doc_id = match.group(1).strip()
            return match.group(0) if doc_id in allowed_ids else ""

        answer = re.sub(r"\[ID:\s*([^\]]+)\]", drop_bad_id, answer)
        return answer

    def _attach_citations(self, answer: str, sources: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Validate cited IDs and clean invalid IDs from the HTML comment.
        """
        if not answer:
            return answer

        allowed_ids = {
            src.get("document_id", "")
            for group in sources.values()
            for src in group
            if src.get("document_id")
        }

        html_comment_match = re.search(
            r"<!--\s*CITED_IDS:\s*(.*?)\s*-->",
            answer,
            re.IGNORECASE,
        )
        if not html_comment_match:
            return answer.strip()

        ids_str = html_comment_match.group(1).strip()
        comment_ids = set()
        if ids_str:
            comment_ids = {
                doc_id.strip()
                for doc_id in ids_str.split(",")
                if doc_id.strip()
            }

        valid_ids = comment_ids & allowed_ids
        invalid_ids = comment_ids - allowed_ids
        if invalid_ids:
            logger.warning("Removing invalid cited IDs: %s", invalid_ids)

        new_comment = f"<!--CITED_IDS: {', '.join(sorted(valid_ids))} -->"
        if not valid_ids:
            new_comment = "<!--CITED_IDS: -->"

        answer = re.sub(
            r"<!--\s*CITED_IDS:\s*.*?\s*-->",
            new_comment,
            answer,
            flags=re.IGNORECASE,
        )

        return answer.strip()

    def _format_sources(
        self,
        sources: Dict[str, List[Dict[str, Any]]],
        cited_ids: Optional[set] = None,
    ) -> List[Dict[str, Any]]:
        """
        Format sources for API response and mark cited sources.
        """
        if cited_ids is None:
            cited_ids = set()

        formatted = []

        for naturaleza, chunks in sources.items():
            for chunk in chunks:
                doc_id = chunk.get("document_id", "")
                formatted.append({
                    "id": doc_id,
                    "title": chunk.get("document_title", ""),
                    "url": chunk.get("document_url", ""),
                    "source_type": chunk.get("source_naturaleza", ""),
                    "relevance_score": chunk.get("similarity", chunk.get("rrf_score", 0)),
                    "excerpt": chunk.get("chunk_text", "")[:300],
                    "label": chunk.get("chunk_label", chunk.get("chunk_type", "Sin etiqueta")),
                    "source_title": chunk.get("source_title", ""),
                    "source_priority": chunk.get("source_priority", ""),
                    "chunk_type": chunk.get("chunk_type", ""),
                    "is_cited": doc_id in cited_ids if doc_id else False,
                })

        formatted.sort(
            key=lambda item: (not item.get("is_cited", False), -(item.get("relevance_score") or 0))
        )

        return formatted
