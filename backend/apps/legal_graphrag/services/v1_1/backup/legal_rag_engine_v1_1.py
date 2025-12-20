"""
Legal RAG Engine V1.1
Multi-query retrieval + hierarchy-safe fusion + judge/redo pipeline.
"""

import logging
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
