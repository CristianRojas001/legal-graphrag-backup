"""
Flow Logger for V1.1 - Logs every step of the RAG pipeline to identify bottlenecks
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class FlowLoggerV1_1:
    """Logs the complete flow of a query through the V1.1 pipeline"""

    def __init__(self, log_dir: str = None):
        if log_dir is None:
            # Default to backend/logs/
            log_dir = Path(__file__).resolve().parents[4] / "logs"
        else:
            log_dir = Path(log_dir)

        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = log_dir / "query_flow_v1_1.jsonl"
        self.current_flow = {}

    def start_query(self, query: str):
        """Start logging a new query"""
        self.current_flow = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "steps": {}
        }

    def log_step(self, step_name: str, data: Dict[str, Any]):
        """Log a pipeline step"""
        self.current_flow["steps"][step_name] = data

    def finish_and_write(self):
        """Write the complete flow to file"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(self.current_flow, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to write flow log: {e}")

    # Helper methods for common logging patterns

    def log_intent_classification(self, area: str, confidence: float):
        """Log intent classifier output"""
        self.log_step("1_intent_classification", {
            "area_detected": area,
            "confidence": confidence
        })

    def log_query_expansion(self, original: str, expanded: List[str]):
        """Log query expander output"""
        self.log_step("2_query_expansion", {
            "original_query": original,
            "expanded_count": len(expanded),
            "expanded_queries": expanded
        })

    def log_hybrid_search_aggregate(self, total_vector: int, total_lexical: int, total_fused: int):
        """Log aggregated hybrid search results"""
        self.log_step("3_hybrid_search", {
            "total_vector_results": total_vector,
            "total_lexical_results": total_lexical,
            "total_fused_results": total_fused
        })

    def log_bucket_split(self, normativa: int, doctrina: int, jurisprudencia: int,
                        top_5_snippets: List[Dict[str, str]]):
        """Log bucket split after naturaleza classification"""
        self.log_step("4_bucket_split", {
            "normativa_count": normativa,
            "doctrina_count": doctrina,
            "jurisprudencia_count": jurisprudencia,
            "top_5_sources": top_5_snippets
        })

    def log_dedup_rank(self, before_counts: Dict[str, int], after_counts: Dict[str, int],
                       top_scores: Dict[str, List[float]]):
        """Log dedup and ranking results"""
        self.log_step("5_dedup_rank", {
            "before_dedup": before_counts,
            "after_dedup": after_counts,
            "top_scores_per_bucket": top_scores
        })

    def log_area_filter(self, before_counts: Dict[str, int], after_counts: Dict[str, int],
                       dropped_count: int, top_5_after: List[Dict[str, str]]):
        """Log area filter results - KEY STEP to identify if this is killing sources"""
        self.log_step("6_area_filter", {
            "before_filter": before_counts,
            "after_filter": after_counts,
            "total_dropped": dropped_count,
            "drop_percentage": round(dropped_count / sum(before_counts.values()) * 100, 1) if sum(before_counts.values()) > 0 else 0,
            "top_5_after_filter": top_5_after
        })

    def log_authority_pack(self, is_authority_question: bool, pack_added: bool,
                          pack_count: int, final_counts: Dict[str, int]):
        """Log authority pack injection"""
        self.log_step("7_authority_pack", {
            "is_authority_question": is_authority_question,
            "pack_added": pack_added,
            "pack_sources_count": pack_count,
            "final_source_counts": final_counts
        })

    def log_abstain_check(self, should_abstain: bool, reason: str = None):
        """Log abstain check result"""
        self.log_step("8_abstain_check", {
            "should_abstain": should_abstain,
            "reason": reason
        })

    def log_llm_response(self, response_length: int, preview: str, error: str = None):
        """Log LLM generation result"""
        self.log_step("9_llm_response", {
            "success": error is None,
            "error": error,
            "response_length_chars": response_length,
            "preview_first_200": preview[:200] if preview else None
        })

    def log_validation(self, answer_changed: bool, before_length: int, after_length: int):
        """Log validation result"""
        self.log_step("10_validation", {
            "answer_changed": answer_changed,
            "before_length": before_length,
            "after_length": after_length,
            "note": "DISABLED in v1.1 - only citation cleanup"
        })

    def log_judge(self, verdict: str, reasons: List[str]):
        """Log judge result"""
        self.log_step("11_judge", {
            "verdict": verdict,
            "reasons": reasons,
            "note": "DISABLED in v1.1"
        })

    def log_final_answer(self, length: int, is_helpful: bool, preview: str):
        """Log final answer characteristics"""
        unhelpful_phrases = [
            "no puedo afirmar",
            "no hay información",
            "no se encontraron fuentes",
            "no tengo información"
        ]
        contains_unhelpful = any(phrase in preview.lower() for phrase in unhelpful_phrases)

        self.log_step("12_final_answer", {
            "length_chars": length,
            "appears_helpful": is_helpful and not contains_unhelpful,
            "contains_unhelpful_phrases": contains_unhelpful,
            "preview_first_300": preview[:300]
        })


def format_source_snippet(source: Dict[str, Any]) -> Dict[str, str]:
    """Format a source for logging"""
    return {
        "id": source.get("document_id", "")[:50],
        "title": source.get("document_title", "")[:80],
        "naturaleza": source.get("source_naturaleza", ""),
        "score": round(source.get("rrf_score", source.get("similarity", 0)), 3),
        "text_preview": (source.get("chunk_text", "") or "")[:100]
    }
