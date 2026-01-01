"""
Flow Logger for V1.1 - Logs every step of the RAG pipeline to identify bottlenecks
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

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

        # Operational memory state tracking
        self._previous_session_state = None
        self._forced_area_used = False
        self._forced_area_value = None

    def start_query(self, query: str, session_id: str = None):
        """Start logging a new query"""
        self.current_flow = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "query": query,
            "steps": {}
        }

    def log_step(self, step_name: str, data: Dict[str, Any]):
        """Log a pipeline step"""
        self.current_flow["steps"][step_name] = data

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
            "preview_first_200": preview[:200] if preview else None,
            "preview_first_1000": preview[:1000] if preview else None,
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

    def log_final_answer(self, length: int, is_helpful: bool, preview: str, cited_ids: Any = None):
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
            "preview_first_300": preview[:300],
            "preview_first_1000": preview[:1000],
            "cited_ids": list(cited_ids) if cited_ids else [],
        })

    def log_sources_final(self, sources: List[Dict[str, Any]], cited_ids: Any = None):
        """Log final sources with scores and cited flag"""
        cited_set = set(cited_ids or [])
        top_sources = []
        for src in sources[:10]:
            top_sources.append({
                "id": src.get("id"),
                "title": (src.get("title") or "")[:120],
                "source_type": src.get("source_type"),
                "relevance_score": src.get("relevance_score"),
                "is_cited": src.get("is_cited") or (src.get("id") in cited_set),
                "label": src.get("label"),
            })

        self.log_step("13_sources_final", {
            "count": len(sources),
            "top_sources": top_sources,
            "cited_ids": list(cited_set),
        })

    # ========== Operational Memory Logging ==========

    def set_forced_area(self, area_value: str):
        """Mark that area was forced (topic lock)"""
        self._forced_area_used = True
        self._forced_area_value = area_value

    def log_opmem_merge_attempt(
        self,
        merge_attempted: bool,
        merge_success: bool,
        reason: str,
        base_question: Optional[str] = None,
        user_reply: Optional[str] = None,
        merged_query: Optional[str] = None,
        slot_filled: Optional[str] = None,
        slot_value: Optional[str] = None,
        pending_slots_before: Optional[List[str]] = None,
        pending_slots_after: Optional[List[str]] = None,
        topic_lock_before: Optional[str] = None,
        topic_lock_after: Optional[str] = None,
    ):
        """
        Log query merge attempts with structured payload.

        Event: opmem_merge_attempt

        Args:
            merge_attempted: Whether merge was attempted
            merge_success: Whether merge succeeded
            reason: Why merge happened (e.g., "short_reply_with_pending_slots", "referential_marker", "no_base_question")
            base_question: Original question (first 200 chars)
            user_reply: Current user reply (first 200 chars)
            merged_query: Result of merge (first 300 chars)
            slot_filled: Name of slot filled (e.g., "location")
            slot_value: Value provided (first 60 chars)
            pending_slots_before: Slots pending before merge
            pending_slots_after: Slots pending after merge
            topic_lock_before: Topic lock before merge
            topic_lock_after: Topic lock after merge
        """
        log_data = {
            "merge_attempted": merge_attempted,
            "merge_success": merge_success,
            "reason": reason,
        }

        # Add previews if provided
        if base_question is not None:
            log_data["base_question_preview"] = base_question[:200]
        if user_reply is not None:
            log_data["user_reply_preview"] = user_reply[:200]
        if merged_query is not None:
            log_data["merged_query_preview"] = merged_query[:300]

        # Add slot data
        if slot_filled is not None:
            log_data["slot_filled"] = slot_filled
        if slot_value is not None:
            log_data["slot_value_preview"] = slot_value[:60]

        # Add state transitions
        if pending_slots_before is not None:
            log_data["pending_slots_before"] = pending_slots_before
        if pending_slots_after is not None:
            log_data["pending_slots_after"] = pending_slots_after
        if topic_lock_before is not None:
            log_data["topic_lock_before"] = topic_lock_before
        if topic_lock_after is not None:
            log_data["topic_lock_after"] = topic_lock_after

        self.log_step("opmem_merge_attempt", log_data)

    def log_opmem_state_changed(
        self,
        event_type: str,
        session_state_snapshot: Optional[Dict[str, Any]] = None,
        diff: Optional[Dict[str, Any]] = None,
    ):
        """
        Log operational memory state changes.

        Event: opmem_state_changed

        Args:
            event_type: Type of change (e.g., "slot_filled", "topic_lock_set", "state_reset", "pending_slots_updated")
            session_state_snapshot: Snapshot of current state (topic_lock, pending_slots, slot_values keys)
            diff: What changed
        """
        log_data = {"event_type": event_type}

        if session_state_snapshot is not None:
            # Only include key fields, not full chat history
            snapshot = {}
            if "topic_lock" in session_state_snapshot:
                snapshot["topic_lock"] = session_state_snapshot["topic_lock"]
            if "pending_slots" in session_state_snapshot:
                snapshot["pending_slots"] = session_state_snapshot["pending_slots"]
            if "base_question" in session_state_snapshot:
                # Preview only
                base_q = session_state_snapshot["base_question"]
                snapshot["base_question_preview"] = (base_q[:200] if base_q else None)
            if "slot_values" in session_state_snapshot:
                # Preview slot values (first 60 chars each)
                slot_vals = session_state_snapshot["slot_values"]
                if isinstance(slot_vals, dict):
                    snapshot["slot_values_preview"] = {
                        k: (v[:60] if isinstance(v, str) else v)
                        for k, v in slot_vals.items()
                    }

            log_data["session_state"] = snapshot

        if diff is not None:
            log_data["diff"] = diff

        self.log_step("opmem_state_changed", log_data)

    def finalize_with_forced_area(self):
        """Add forced_area tracking to final flow before writing"""
        if "steps" not in self.current_flow:
            self.current_flow["steps"] = {}

        self.current_flow["steps"]["opmem_forced_area"] = {
            "used_forced_area": self._forced_area_used,
            "forced_area_value": self._forced_area_value,
        }

    def finish_and_write(self):
        """Write the complete flow to file"""
        # Add forced area tracking
        self.finalize_with_forced_area()

        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(self.current_flow, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to write flow log: {e}")

        # Reset forced area tracking
        self._forced_area_used = False
        self._forced_area_value = None


def format_source_snippet(source: Dict[str, Any]) -> Dict[str, str]:
    """Format a source for logging"""
    return {
        "id": source.get("document_id", "")[:50],
        "title": source.get("document_title", "")[:80],
        "naturaleza": source.get("source_naturaleza", ""),
        "score": round(source.get("rrf_score", source.get("similarity", 0)), 3),
        "text_preview": (source.get("chunk_text", "") or "")[:100]
    }
