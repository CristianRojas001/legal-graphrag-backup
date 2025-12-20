"""
Legal RAG Engine V1.1
Multi-query retrieval + hierarchy-safe fusion + judge/redo pipeline.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple

from apps.legal_graphrag.services.legal_rag_engine import LegalRAGEngine
from apps.legal_graphrag.services.legal_search_engine import LegalSearchEngine
from apps.legal_graphrag.services.v1_1.query_expander_v1_1 import QueryExpanderV1_1
from apps.legal_graphrag.services.v1_1.judge_v1_1 import AnswerJudgeV1_1
from apps.legal_graphrag.services.v1_1.authority_pack_v1_1 import (
    build_authority_sources,
    is_authority_question,
)
from apps.legal_graphrag.services.v1_1.flow_logger_v1_1 import FlowLoggerV1_1, format_source_snippet

logger = logging.getLogger(__name__)


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
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
        # Step 2: Query expansion
        expanded = self.query_expander.expand(query, max_total=8)
        if not expanded:
            expanded = [query]
        self.flow_logger.log_query_expansion(query, expanded)

        per_query_limit = max(10, max_sources * 2)
        combined: List[Dict[str, Any]] = []
        total_vector = 0
        total_lexical = 0

        # Step 3: Hybrid search
        for q in expanded:
            try:
                results = self.search_engine.hybrid_search(query=q, limit=per_query_limit)
                combined.extend(results)
                # Rough estimate - each query contributes to both
                total_vector += len(results)
                total_lexical += len(results)
            except Exception:
                logger.exception("V1.1 retrieval failed for query: %s", q)

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

        # Step 6: Area filter - KEY BOTTLENECK
        filtered = self._filter_sources_by_area(area_principal, fused, query)
        counts_post_filter = {k: len(v) for k, v in filtered.items()}
        dropped = sum(counts_pre_filter.values()) - sum(counts_post_filter.values())
        flat_filtered = []
        for bucket in filtered.values():
            flat_filtered.extend(bucket)
        top_5_filtered = [format_source_snippet(s) for s in flat_filtered[:5]]
        self.flow_logger.log_area_filter(counts_pre_filter, counts_post_filter, dropped, top_5_filtered)

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

        trace = {
            "expanded_queries": expanded,
            "authority_question": authority_question,
            "authority_pack_added": authority_added,
            "authority_pack_count": authority_count,
            "retrieval_counts": {
                "combined_results": len(combined),
                "fused_pre_filter": counts_pre_filter,
                "post_filter": counts_post_filter,
            },
            "top_scores": top_scores,
        }
        return filtered, trace

    def answer_query(
        self,
        query: str,
        area_principal: Optional[str] = None,
        max_sources: int = 10,
    ) -> Dict[str, Any]:
        logger.info("V1.1 RAG query: '%s'", query[:100])

        # Start flow logging
        self.flow_logger.start_query(query)

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

        # Step 1: Intent classification
        if area_principal is None:
            area_classification = self.intent_classifier.classify_with_confidence(query)
            area_principal = area_classification.get("area")
            confidence = area_classification.get("confidence", 0.0)
            self.flow_logger.log_intent_classification(area_principal, confidence)
        else:
            logger.info("Using pre-classified area: %s", area_principal)
            self.flow_logger.log_intent_classification(area_principal, 1.0)

        sources, trace = self._retrieve_hierarchical_sources_v1_1(
            query=query, area_principal=area_principal, max_sources=max_sources
        )

        # Step 8: Abstain check
        abstained = self._should_abstain(query, area_principal, sources)
        self.flow_logger.log_abstain_check(abstained, "low_evidence" if abstained else "sufficient_evidence")

        # Always build prompt and call model, even with low evidence
        # Pass abstained flag in trace for metadata, not for control flow
        prompt = self._build_hierarchical_prompt(query=query, sources=sources, area_principal=area_principal)

        # Step 9: LLM generation
        try:
            response = self.model.generate_content(prompt)
            answer_text = response.text
            self.flow_logger.log_llm_response(len(answer_text), answer_text)
        except Exception as e:
            logger.exception("V1.1 LLM generation failed")
            answer_text = self._generate_fallback_answer(query, sources)
            self.flow_logger.log_llm_response(len(answer_text), answer_text, error=str(e))

        # Make post-processing non-fatal
        postprocess_errors = []
        # Step 10: Validation (DISABLED - only citation cleanup)
        before_validation = answer_text
        try:
            allowed_ids = {src.get('document_id', '') for group in sources.values() for src in group if src.get('document_id')}
            import re
            def drop_bad_id(match):
                doc_id = match.group(1).strip()
                return match.group(0) if doc_id in allowed_ids else ""
            answer_text = re.sub(r"\[ID:\s*([^\]]+)\]", drop_bad_id, answer_text)
        except Exception:
            logger.exception("V1.1 citation cleanup failed")
            postprocess_errors.append("citation_cleanup_failed")

        self.flow_logger.log_validation(answer_text != before_validation, len(before_validation), len(answer_text))

        try:
            answer_text = self._attach_citations(answer_text, sources)
        except Exception:
            logger.exception("V1.1 citation attachment failed")
            postprocess_errors.append("citation_failed")

        try:
            formatted_sources = self._format_sources(sources)
        except Exception:
            logger.exception("V1.1 source formatting failed")
            formatted_sources = []
            postprocess_errors.append("format_sources_failed")

        # Step 11: Judge (DISABLED)
        judge_result = {"verdict": "PASS", "reasons": ["judge_disabled_v1.1"]}
        redo_performed = False
        self.flow_logger.log_judge(judge_result["verdict"], judge_result["reasons"])

        # Step 12: Final answer logging
        is_helpful = len(answer_text) > 100  # Simple heuristic
        self.flow_logger.log_final_answer(len(answer_text), is_helpful, answer_text)

        # Write flow log to file
        self.flow_logger.finish_and_write()

        metadata = {
            "version": "v1_1",
            "area_principal": area_principal,
            "model": self.model.model_name,
            "normativa_count": len(sources.get("normativa", [])),
            "doctrina_count": len(sources.get("doctrina", [])),
            "jurisprudencia_count": len(sources.get("jurisprudencia", [])),
            "total_sources": len(formatted_sources),
            "abstained": abstained,
            "judge": judge_result,
            "redo_performed": redo_performed,
            "expanded_queries": trace.get("expanded_queries"),
            "authority_question": trace.get("authority_question"),
            "authority_pack_added": trace.get("authority_pack_added"),
            "authority_pack_count": trace.get("authority_pack_count"),
            "retrieval_counts": trace.get("retrieval_counts"),
            "top_scores": trace.get("top_scores"),
            "postprocess_errors": postprocess_errors if postprocess_errors else None,
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
                    if self._source_matches_tokens(src, token_list):
                        count += 1
            return count

        # Strict: require minimum matches on law/required tokens when area is known
        if strict_tokens:
            strict_matches = count_matches(strict_tokens)
            if strict_matches < self._min_strict_matches:
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
                if not any(self._source_matches_tokens(src, [self._normalize_text(t) for t in iva_tokens]) for grp in sources.values() for src in grp):
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
        Append ONLY cited sources to the answer.
        If no citations exist in the answer, do not append "Fuentes utilizadas".

        This fixes the "citation confetti" problem where all retrieved sources
        were listed even when not cited in the answer.
        """
        if not answer:
            return answer

        # Extract cited IDs from the answer text
        cited_ids = set(re.findall(r"\[ID:\s*([^\]]+)\]", answer))
        cited_ids = {cid.strip() for cid in cited_ids if cid.strip()}

        if not cited_ids:
            # Do not append a source list if nothing was cited
            return answer.strip()

        # Build lookup for retrieved sources
        flat: List[Dict[str, Any]] = []
        for group in sources.values():
            flat.extend(group)
        by_id = {c.get("document_id", ""): c for c in flat if c.get("document_id")}

        lines = [answer.strip(), "", "**Fuentes utilizadas**:"]
        for cid in cited_ids:
            chunk = by_id.get(cid)
            if not chunk:
                continue
            title = chunk.get("document_title", "")
            label = chunk.get("chunk_label", "")
            lines.append(f"- [ID: {cid}] {title} - {label}")

        # If none of the cited IDs were found in sources, omit the block
        if len(lines) == 3:  # Only header, no actual sources added
            return answer.strip()

        return "\n".join(lines)
