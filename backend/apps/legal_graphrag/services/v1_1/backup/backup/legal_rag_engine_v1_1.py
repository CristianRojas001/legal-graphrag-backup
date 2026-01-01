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
from apps.legal_graphrag.models import DocumentChunk
from django.db.models import Q

logger = logging.getLogger(__name__)

_RETRIEVAL_CACHE: "OrderedDict[tuple, dict]" = OrderedDict()
_RETRIEVAL_CACHE_MAX = 64


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
        expanded = expanded_queries
        if expanded is None:
            expanded = self.query_expander.expand(
                query,
                max_total=expansion_max_total,
                llm_variants=expansion_llm_variants,
            )
        if not expanded:
            expanded = [query]
        self.flow_logger.log_query_expansion(query, expanded)

        per_query_limit = max(per_query_limit, max_sources)
        combined: List[Dict[str, Any]] = []
        retrieval_debug = []
        if forced_sources:
            combined.extend(forced_sources)
        total_vector = 0
        total_lexical = 0

        # Step 3: Hybrid search
        for q in expanded:
            try:
                results, debug = self.search_engine.hybrid_search(
                    query=q,
                    limit=per_query_limit,
                    return_debug=True,
                )
                combined.extend(results)
                retrieval_debug.append({
                    "query": q,
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
            "\n\nCITACION OBLIGATORIA:\n"
            "Al final de tu respuesta, incluye un comentario HTML oculto con los IDs de documentos citados:\n\n"
            "<!--CITED_IDS: BOE-A-XXXX-XXXXX, BOE-A-YYYY-YYYYY -->\n\n"
            "Reglas:\n"
            "- Solo incluye document_id de fuentes que realmente citaste/usaste\n"
            "- Separa multiples IDs con comas\n"
            "- Usa el formato BOE-A-XXXX-XXXXX exacto (del campo document_id)\n"
            "- Si no citaste ninguna fuente, usa: <!--CITED_IDS: -->\n"
            "- Este comentario es invisible para el usuario pero critico para el sistema\n"
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
        logger.info("V1.1 RAG query: '%s'", query[:100])

        # Start flow logging
        self.flow_logger.start_query(query, session_id=session_id)

        # Step 0: Meta query bypass (before intent classification)
        if self._is_meta_query(query):
            logger.info("Meta query detected, bypassing retrieval")
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

        # Step 1: Intent classification
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

        # Step 8: Abstain check
        abstained = self._should_abstain(query, area_principal, sources)
        self.flow_logger.log_abstain_check(abstained, "low_evidence" if abstained else "sufficient_evidence")

        # Always build prompt and call model, even with low evidence
        # Pass abstained flag in trace for metadata, not for control flow
        prompt = self._build_hierarchical_prompt(query=query, sources=sources, area_principal=area_principal)
        if context_block:
            prompt += f"\n\nCONTEXTO CONVERSACIONAL:\n{context_block}\n"
        if question_type:
            prompt += f"\nQUESTION_TYPE: {question_type}\n"

        # Step 9: LLM generation
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

        answer_text, cited_ids, formatted_sources, postprocess_errors = self._postprocess_answer(
            answer_text=answer_text,
            sources=sources,
            abstained=abstained,
        )

        # Step 11: Judge
        judge_result = self.judge.judge(question=query, answer=answer_text, sources=sources)
        redo_performed = False
        if judge_result.get("verdict") == "REDO":
            redo_performed = True
            answer_text = self._retry_with_stricter_prompt(prompt, query, sources)
            answer_text, cited_ids, formatted_sources, postprocess_errors = self._postprocess_answer(
                answer_text=answer_text,
                sources=sources,
                abstained=abstained,
            )
            judge_result = self.judge.judge(question=query, answer=answer_text, sources=sources)

        if judge_result.get("verdict") == "REDO":
            answer_text = self._add_low_confidence_disclaimer(answer_text)

        self.flow_logger.log_judge(judge_result.get("verdict"), judge_result.get("reasons", []))

        # Step 12: Final answer logging
        is_helpful = len(answer_text) > 100  # Simple heuristic
        self.flow_logger.log_final_answer(len(answer_text), is_helpful, answer_text, cited_ids)

        # Write flow log to file
        self.flow_logger.finish_and_write()

        cited_count = sum(1 for source in formatted_sources if source.get("is_cited"))
        additional_count = max(len(formatted_sources) - cited_count, 0)

        debug_summary = {
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

        citations_instruction = ""
        if "CITACION OBLIGATORIA" in prompt:
            idx = prompt.find("CITACION OBLIGATORIA")
            citations_instruction = prompt[idx: idx + 800]

        chat_trace = {
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
        self._write_chat_trace(chat_trace)

        metadata = {
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
        if area_principal:
            priority_sources = len(sources.get('normativa', [])) + len(sources.get('doctrina', []))
            if priority_sources < 1:
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
