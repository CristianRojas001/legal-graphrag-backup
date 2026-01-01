"""
Conversation orchestrator for v1.1.
Determines turn mode, stable topic, and deterministic query rewriting.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


DEFAULT_SCHEMA_VERSION = 1
SHORT_TOKEN_LIMIT = 6
SLOTFILL_TOKEN_LIMIT = 10
CONF_FOLLOW_CLASSIFIER = 0.55
CONF_BREAK_TOPIC_LOCK = 0.80
CANDIDATE_MODES = [
    "FOLLOWUP_SLOT_FILL",
    "FOLLOWUP_REFERENTIAL",
    "NEW_QUESTION",
    "CLARIFY",
    "META",
]


@dataclass
class TurnDecision:
    mode: str
    reason: str
    effective_area: Optional[str]
    forced_area: Optional[str]
    question_type: str
    base_question: Optional[str]
    merged_query: Optional[str]
    context_block: Optional[str]
    state_patch: Dict[str, Any]
    should_call_rag: bool
    trace: Dict[str, Any]


def default_session_state() -> Dict[str, Any]:
    return {
        "schema_version": DEFAULT_SCHEMA_VERSION,
        "turn_count": 0,
        "topic_lock": None,
        "base_question": None,
        "last_actionable_user_question": None,
        "pending_slots": [],
        "slot_values": {},
        "last_answer_brief": None,
        "memory_summary": "",
    }


def decide_turn(
    session_state: Dict[str, Any],
    user_text: str,
    classifier_result: Dict[str, Any],
    last_assistant_text: Optional[str] = None,
    router_context: Optional[Dict[str, Any]] = None,
) -> TurnDecision:
    state = session_state or default_session_state()
    normalized_text = _normalize_text(user_text)
    tokens = _tokenize(user_text)
    base_question = state.get("base_question")
    memory_summary = (state.get("memory_summary") or "").strip()
    pending_slots = state.get("pending_slots") or []
    topic_lock = state.get("topic_lock")
    classifier_area = classifier_result.get("area")
    classifier_confidence = classifier_result.get("confidence", 0.0)
    classifier_scores = classifier_result.get("scores", {})
    candidate_modes = list(CANDIDATE_MODES)
    llm_trace = _default_llm_trace()

    if _is_meta_query(normalized_text):
        trace = _build_orchestrator_trace(
            user_text=user_text,
            tokens=tokens,
            classifier_area=classifier_area,
            classifier_confidence=classifier_confidence,
            classifier_scores=classifier_scores,
            state_before=state,
            last_assistant_text=last_assistant_text,
            signals=_build_signals(
                tokens=tokens,
                pending_slots=pending_slots,
                referential_hit=False,
                referential_matches=[],
                explicit_topic_change=False,
                topic_lock=topic_lock,
            ),
            candidate_modes=candidate_modes,
            decision={"mode": "META", "reason": "meta_query"},
            rejections=[],
            router_context=router_context,
            llm_trace=llm_trace,
        )
        return TurnDecision(
            mode="META",
            reason="meta_query",
            effective_area=None,
            forced_area=None,
            question_type="unknown",
            base_question=None,
            merged_query=None,
            context_block=None,
            state_patch=_empty_patch(),
            should_call_rag=False,
            trace=trace,
        )


    explicit_topic_change = _is_explicit_topic_change(normalized_text)
    effective_area = _select_effective_area(classifier_area, classifier_confidence, topic_lock)

    referential_matches = _referential_matches(normalized_text)
    referential_hit = bool(referential_matches)

    base_context = base_question or memory_summary
    is_follow_up = _is_follow_up(
        normalized_text,
        tokens,
        pending_slots,
        base_context,
    )
    if topic_lock and not explicit_topic_change:
        if is_follow_up or len(tokens) <= SHORT_TOKEN_LIMIT or classifier_confidence < CONF_BREAK_TOPIC_LOCK:
            effective_area = topic_lock

    if not is_follow_up and len(tokens) <= 2 and classifier_confidence < 0.55 and not _looks_like_question(normalized_text):
        trace = _build_orchestrator_trace(
            user_text=user_text,
            tokens=tokens,
            classifier_area=classifier_area,
            classifier_confidence=classifier_confidence,
            classifier_scores=classifier_scores,
            state_before=state,
            last_assistant_text=last_assistant_text,
            signals=_build_signals(
                tokens=tokens,
                pending_slots=pending_slots,
                referential_hit=referential_hit,
                referential_matches=referential_matches,
                explicit_topic_change=explicit_topic_change,
                topic_lock=topic_lock,
            ),
            candidate_modes=candidate_modes,
            decision={"mode": "CLARIFY", "reason": "short_ambiguous"},
            rejections=["NEW_QUESTION rejected: short_ambiguous"],
            router_context=router_context,
            llm_trace=llm_trace,
        )
        return TurnDecision(
            mode="CLARIFY",
            reason="short_ambiguous",
            effective_area=effective_area,
            forced_area=topic_lock,
            question_type="unknown",
            base_question=None,
            merged_query=None,
            context_block=None,
            state_patch=_empty_patch(),
            should_call_rag=False,
            trace=trace,
        )

    if is_follow_up and not base_question and not state.get("last_actionable_user_question") and not memory_summary:
        trace = _build_orchestrator_trace(
            user_text=user_text,
            tokens=tokens,
            classifier_area=classifier_area,
            classifier_confidence=classifier_confidence,
            classifier_scores=classifier_scores,
            state_before=state,
            last_assistant_text=last_assistant_text,
            signals=_build_signals(
                tokens=tokens,
                pending_slots=pending_slots,
                referential_hit=referential_hit,
                referential_matches=referential_matches,
                explicit_topic_change=explicit_topic_change,
                topic_lock=topic_lock,
            ),
            candidate_modes=candidate_modes,
            decision=None,
            rejections=["FOLLOWUP_REFERENTIAL rejected: no_base_question"],
            router_context=router_context,
            llm_trace=llm_trace,
        )
        return TurnDecision(
            mode="CLARIFY",
            reason="no_base_question",
            effective_area=effective_area,
            forced_area=topic_lock,
            question_type="unknown",
            base_question=None,
            merged_query=None,
            context_block=None,
            state_patch=_empty_patch(),
            should_call_rag=False,
            trace=trace,
        )

    llm_decision, llm_trace = _call_llm_router(router_context, classifier_result)
    if llm_decision:
        mode = llm_decision.get("mode") or "NEW_QUESTION"
        reason = llm_decision.get("reason") or "llm_router"
        merged_query_llm = llm_decision.get("rewritten_query")
    else:
        merged_query_llm = None
        mode, reason = _classify_follow_up(normalized_text, tokens, pending_slots, base_context, is_follow_up)

    if explicit_topic_change and not pending_slots and classifier_confidence >= 0.80:
        mode = "NEW_QUESTION"
        reason = "explicit_topic_change"

    forced_area = _select_forced_area(mode, classifier_confidence, topic_lock, effective_area)
    question_type = _classify_question_type(effective_area, normalized_text)

    merged_query, context_block, slot_patch = _rewrite_query(
        mode,
        state,
        user_text,
        question_type,
        pending_slots,
    )
    if merged_query_llm:
        merged_query = merged_query_llm

    state_patch = _build_state_patch(
        mode=mode,
        reason=reason,
        state=state,
        user_text=user_text,
        effective_area=effective_area,
        classifier_confidence=classifier_confidence,
        explicit_topic_change=explicit_topic_change,
        slot_patch=slot_patch,
    )

    decision_payload = {
        "mode": mode,
        "reason": reason,
        "effective_area": effective_area,
        "forced_area_used": bool(forced_area),
        "forced_area_value": forced_area,
        "question_type": question_type,
        "merged_query_preview": (merged_query or "")[:180] if merged_query else None,
    }

    signals = _build_signals(
        tokens=tokens,
        pending_slots=pending_slots,
        referential_hit=referential_hit,
        referential_matches=referential_matches,
        explicit_topic_change=explicit_topic_change,
        topic_lock=topic_lock,
    )
    rejections = _build_rejections(
        selected_mode=mode,
        signals=signals,
        pending_slots=pending_slots,
        classifier_confidence=classifier_confidence,
        topic_lock=topic_lock,
    )
    trace = _build_orchestrator_trace(
        user_text=user_text,
        tokens=tokens,
        classifier_area=classifier_area,
        classifier_confidence=classifier_confidence,
        classifier_scores=classifier_scores,
        state_before=state,
        last_assistant_text=last_assistant_text,
        signals=signals,
        candidate_modes=candidate_modes,
        decision=decision_payload,
        rejections=rejections,
        router_context=router_context,
        llm_trace=llm_trace,
    )

    return TurnDecision(
        mode=mode,
        reason=reason,
        effective_area=effective_area,
        forced_area=forced_area,
        question_type=question_type,
        base_question=base_question,
        merged_query=merged_query,
        context_block=context_block,
        state_patch=state_patch,
        should_call_rag=(mode not in {"META", "CLARIFY"}),
        trace=trace,
    )


def apply_state_patch(state: Dict[str, Any], patch: Dict[str, Any], increment_turn: bool = True) -> Dict[str, Any]:
    next_state = {**state}
    for key, value in patch.get("set", {}).items():
        next_state[key] = value
    for key in patch.get("unset", []):
        next_state.pop(key, None)
    for key, values in patch.get("append", {}).items():
        next_state.setdefault(key, [])
        next_state[key].extend(values)

    if increment_turn:
        next_state["turn_count"] = int(next_state.get("turn_count", 0)) + 1
    next_state.setdefault("schema_version", DEFAULT_SCHEMA_VERSION)
    return next_state


def build_state_patch_from_answer(answer: str) -> Dict[str, Any]:
    questions = _extract_para_afinar_questions(answer)
    pending_slots = _derive_pending_slots(questions)
    if not pending_slots:
        return _empty_patch()

    return {
        "set": {
            "pending_slots": pending_slots,
        },
        "unset": [],
        "append": {},
    }


def log_orchestrator_decision(session_id: str, decision: TurnDecision, state_before: Dict[str, Any], state_after: Dict[str, Any]) -> None:
    log_dir = Path(__file__).resolve().parents[4] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "orchestrator_v1_1.jsonl"
    payload = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "decision": asdict(decision),
        "state_before": _summarize_state(state_before),
        "state_after": _summarize_state(state_after),
    }
    try:
        with open(log_file, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("Failed to write orchestrator log")


def _summarize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "turn_count": state.get("turn_count"),
        "topic_lock": state.get("topic_lock"),
        "base_question": (state.get("base_question") or "")[:200],
        "pending_slots": state.get("pending_slots"),
        "slot_values": state.get("slot_values"),
        "memory_summary": (state.get("memory_summary") or "")[:200],
    }


def _empty_patch() -> Dict[str, Any]:
    return {"set": {}, "unset": [], "append": {}}


def _default_llm_trace() -> Dict[str, Any]:
    return {
        "enabled": False,
        "used": False,
        "model": None,
        "error": None,
        "decision": None,
        "raw_preview": None,
    }


def _call_llm_router(
    router_context: Optional[Dict[str, Any]],
    classifier_result: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    trace = _default_llm_trace()
    if os.getenv("ORCHESTRATOR_LLM", "0") != "1":
        return None, trace
    if not router_context:
        return None, trace

    from django.conf import settings

    api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not api_key:
        trace["error"] = "missing_api_key"
        return None, trace

    trace["enabled"] = True
    model_name = os.getenv("ORCHESTRATOR_LLM_MODEL", "gemini-2.0-flash-lite")
    trace["model"] = model_name

    prompt = _build_llm_router_prompt(router_context, classifier_result)
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content(prompt)
        raw_text = response.text or ""
        trace["raw_preview"] = raw_text[:400]
        parsed = _parse_llm_json(raw_text)
        if not parsed:
            trace["error"] = "parse_failed"
            return None, trace

        mode = parsed.get("mode")
        reason = parsed.get("reason") or "llm_router"
        rewritten_query = parsed.get("rewritten_query") or None
        allowed_modes = {"NEW_QUESTION", "FOLLOWUP_SLOT_FILL", "FOLLOWUP_REFERENTIAL", "CLARIFY", "META"}
        if mode not in allowed_modes:
            trace["error"] = "invalid_mode"
            return None, trace

        decision = {
            "mode": mode,
            "reason": reason,
            "rewritten_query": rewritten_query,
        }
        trace["used"] = True
        trace["decision"] = decision
        return decision, trace
    except Exception as exc:
        trace["error"] = f"llm_error:{exc.__class__.__name__}"
        return None, trace


def _build_llm_router_prompt(
    router_context: Dict[str, Any],
    classifier_result: Dict[str, Any],
) -> str:
    context_payload = {
        "memory_summary": router_context.get("memory_summary"),
        "base_question": router_context.get("base_question"),
        "recent_user_messages": router_context.get("recent_user_messages"),
        "recent_assistant_messages": router_context.get("recent_assistant_messages"),
        "current_user_text": router_context.get("current_user_text"),
        "classifier": {
            "area_detected": classifier_result.get("area"),
            "confidence": classifier_result.get("confidence"),
            "scores": classifier_result.get("scores") or {},
        },
    }
    return (
        "You are a routing agent for a legal assistant. "
        "Decide how to route the current user message.\n"
        "Return ONLY valid JSON with keys: mode, reason, rewritten_query.\n"
        "Allowed modes: NEW_QUESTION, FOLLOWUP_SLOT_FILL, FOLLOWUP_REFERENTIAL, CLARIFY, META.\n"
        "Rules:\n"
        "- If base_question or memory_summary indicates an active topic, short vague messages "
        "like 'por ejemplo?' or 'dame un ejemplo' must be FOLLOWUP_REFERENTIAL.\n"
        "- If there is no base_question and no memory_summary, and the message is vague, use CLARIFY.\n"
        "- If you pick a FOLLOWUP mode, provide rewritten_query that restates the full question "
        "using base_question or memory_summary.\n"
        "- Keep reason short.\n\n"
        f"CONTEXT:\n{json.dumps(context_payload, ensure_ascii=False)}\n"
    )


def _parse_llm_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    snippet = text[start : end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        return None


def _normalize_text(text: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    normalized = re.sub(r"[^a-z0-9\s]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _tokenize(text: str) -> List[str]:
    return [tok for tok in re.split(r"\s+", text.strip()) if tok]


def _is_meta_query(normalized_text: str) -> bool:
    meta_tokens = [
        "que puedes hacer",
        "como puedes ayudar",
        "como funciona",
        "que es rag",
        "porque no respondiste",
        "por que no respondiste",
        "que fuentes usas",
        "que fuentes",
    ]
    return any(token in normalized_text for token in meta_tokens)


def _is_explicit_topic_change(normalized_text: str) -> bool:
    return any(marker in normalized_text for marker in ["cambiando de tema", "ahora sobre", "otro tema"])


def _looks_like_question(normalized_text: str) -> bool:
    question_tokens = ["que", "como", "cuando", "donde", "por que", "puedo", "debo", "necesito"]
    return any(token in normalized_text for token in question_tokens)


def _referential_matches(normalized_text: str) -> List[str]:
    referential_terms = ["lo anterior", "eso", "ese caso", "mi caso", "en relacion", "lo de antes", "sobre esto"]
    matches = []
    for term in referential_terms:
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, normalized_text):
            matches.append(term)
    return matches


def _build_signals(
    tokens: List[str],
    pending_slots: List[str],
    referential_hit: bool,
    referential_matches: List[str],
    explicit_topic_change: bool,
    topic_lock: Optional[str],
) -> Dict[str, Any]:
    token_count = len(tokens)
    return {
        "short_message": {"value": token_count <= SHORT_TOKEN_LIMIT, "token_count": token_count},
        "pending_slots_present": bool(pending_slots),
        "slot_fill_candidate": bool(pending_slots) and token_count <= SLOTFILL_TOKEN_LIMIT,
        "referential_hit": referential_hit,
        "referential_matches": referential_matches,
        "thin_turn": token_count <= SHORT_TOKEN_LIMIT,
        "explicit_topic_change": explicit_topic_change,
        "topic_lock_available": bool(topic_lock),
    }


def _build_rejections(
    selected_mode: str,
    signals: Dict[str, Any],
    pending_slots: List[str],
    classifier_confidence: float,
    topic_lock: Optional[str],
) -> List[str]:
    rejections = []
    if selected_mode != "FOLLOWUP_SLOT_FILL":
        if not pending_slots:
            rejections.append("FOLLOWUP_SLOT_FILL rejected: pending_slots_empty")
        elif not signals.get("slot_fill_candidate"):
            rejections.append("FOLLOWUP_SLOT_FILL rejected: slot_fill_candidate=false")
    if selected_mode != "FOLLOWUP_REFERENTIAL":
        if not signals.get("referential_hit"):
            rejections.append("FOLLOWUP_REFERENTIAL rejected: referential_hit=false")
        elif not signals.get("thin_turn"):
            rejections.append("FOLLOWUP_REFERENTIAL rejected: thin_turn=false")
    if selected_mode != "NEW_QUESTION":
        if signals.get("thin_turn") and signals.get("topic_lock_available"):
            rejections.append("NEW_QUESTION rejected: thin_turn + topic_lock_available")
    if not topic_lock:
        rejections.append("topic_lock_fallback skipped: no_topic_lock")
    elif classifier_confidence >= CONF_FOLLOW_CLASSIFIER:
        rejections.append("topic_lock_fallback skipped: classifier_confidence_high=true")
    return rejections


def _build_orchestrator_trace(
    user_text: str,
    tokens: List[str],
    classifier_area: Optional[str],
    classifier_confidence: float,
    classifier_scores: Dict[str, Any],
    state_before: Dict[str, Any],
    last_assistant_text: Optional[str],
    signals: Dict[str, Any],
    candidate_modes: List[str],
    decision: Optional[Dict[str, Any]],
    rejections: List[str],
    router_context: Optional[Dict[str, Any]] = None,
    llm_trace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    pending_slots = state_before.get("pending_slots") or []
    thread_status = "no_thread"
    if pending_slots:
        thread_status = "slot_fill_active"
    elif state_before.get("base_question") or state_before.get("topic_lock") or state_before.get("memory_summary"):
        thread_status = "active_thread"

    return {
        "thread_status": thread_status,
        "candidate_modes": candidate_modes,
        "inputs": {
            "user_text_preview": user_text[:120],
            "token_count": len(tokens),
            "classifier": {
                "area_detected": classifier_area,
                "confidence": classifier_confidence,
                "scores": classifier_scores or {},
            },
            "last_assistant": {
                "answer_preview": (last_assistant_text or "")[:120],
                "had_para_afinar": bool(last_assistant_text and "para afinar" in last_assistant_text.lower()),
            },
        },
        "state_before": {
            "topic_lock": state_before.get("topic_lock"),
            "base_question_preview": (state_before.get("base_question") or "")[:120],
            "last_actionable_preview": (state_before.get("last_actionable_user_question") or "")[:120],
            "pending_slots": pending_slots,
            "slot_values_keys": list((state_before.get("slot_values") or {}).keys()),
            "last_answer_brief_preview": (state_before.get("last_answer_brief") or "")[:120],
            "memory_summary_preview": (state_before.get("memory_summary") or "")[:160],
        },
        "router_inputs": router_context or {},
        "llm_router": llm_trace or {},
        "signals": signals,
        "thresholds": {
            "conf_follow_classifier": CONF_FOLLOW_CLASSIFIER,
            "conf_break_topic_lock": CONF_BREAK_TOPIC_LOCK,
            "short_token_limit": SHORT_TOKEN_LIMIT,
            "slotfill_token_limit": SLOTFILL_TOKEN_LIMIT,
        },
        "decision": decision,
        "rejections": rejections,
        "state_after": None,
        "state_diff": None,
    }


def _select_effective_area(classifier_area: Optional[str], confidence: float, topic_lock: Optional[str]) -> Optional[str]:
    if classifier_area and confidence >= 0.55:
        return classifier_area
    if topic_lock:
        return topic_lock
    return None


def _select_forced_area(mode: str, confidence: float, topic_lock: Optional[str], effective_area: Optional[str]) -> Optional[str]:
    if mode in {"FOLLOWUP_SLOT_FILL", "FOLLOWUP_REFERENTIAL"} and topic_lock:
        return topic_lock
    if confidence < 0.55 and topic_lock:
        return topic_lock
    return effective_area


def _is_follow_up(normalized_text: str, tokens: List[str], pending_slots: List[str], base_question: Optional[str]) -> bool:
    if pending_slots and len(tokens) <= SLOTFILL_TOKEN_LIMIT:
        return True
    if _referential_matches(normalized_text):
        return True
    if base_question and (len(tokens) <= SHORT_TOKEN_LIMIT or "y eso" in normalized_text):
        return True
    return False


def _classify_follow_up(
    normalized_text: str,
    tokens: List[str],
    pending_slots: List[str],
    base_question: Optional[str],
    is_follow_up: bool,
) -> Tuple[str, str]:
    if not is_follow_up:
        return "NEW_QUESTION", "new_question"

    if pending_slots and len(tokens) <= 10:
        return "FOLLOWUP_SLOT_FILL", "slot_fill"

    return "FOLLOWUP_REFERENTIAL", "referential"


def _classify_question_type(area: Optional[str], normalized_text: str) -> str:
    if area != "Fiscal":
        return "unknown"

    if any(token in normalized_text for token in ["deducible", "gasto", "factura", "afectacion", "afectacion"]):
        return "deducibles"
    if any(token in normalized_text for token in ["declaro", "declarar", "ingreso", "cobro", "actuacion"]):
        return "declarar_ingresos"
    if any(token in normalized_text for token in ["retencion", "modelo 111", "modelo 130", "retenciones"]):
        return "facturacion_retenciones"
    if any(token in normalized_text for token in ["amortizacion", "amortizar", "bien de inversion"]):
        return "amortizacion"
    if any(token in normalized_text for token in ["iva", "exento", "repercutir"]):
        return "iva"

    return "unknown"


def _rewrite_query(
    mode: str,
    state: Dict[str, Any],
    user_text: str,
    question_type: str,
    pending_slots: List[str],
) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    slot_patch: Dict[str, Any] = {"filled_slot": None, "slot_values": None, "pending_slots": None}
    if mode == "NEW_QUESTION":
        return None, None, slot_patch

    base = state.get("base_question") or state.get("last_actionable_user_question") or (state.get("memory_summary") or "").strip()
    if not base:
        return None, None, slot_patch

    slot_values = state.get("slot_values", {}).copy()
    pending = list(pending_slots)

    if mode == "FOLLOWUP_SLOT_FILL":
        slot_name = _infer_slot_fill(user_text, pending)
        slot_values[slot_name] = _map_tax_slot_value(slot_name, user_text)
        if slot_name in pending:
            if slot_name == "period" and not re.search(r"\b(19|20)\d{2}\b", user_text):
                pass
            else:
                pending = [slot for slot in pending if slot != slot_name]

        slot_patch = {
            "filled_slot": slot_name,
            "slot_values": slot_values,
            "pending_slots": pending,
        }

    slot_summary = _format_slot_summary(slot_values)

    normalized = _normalize_text(user_text)
    context_block = slot_summary if slot_summary else None
    if mode in {"FOLLOWUP_SLOT_FILL", "FOLLOWUP_REFERENTIAL"} and _is_example_request(normalized):
        merged_query = f"{base}\nSolicitud: ejemplos concretos relacionados con la pregunta base."
        if slot_summary:
            merged_query += f"\nContexto adicional: {slot_summary}"
        merged_query = _apply_question_type_anchors(merged_query, question_type)
        return merged_query, context_block, slot_patch
    merged_query = f"{base}\nAclaracion: {user_text.strip()}"
    if slot_summary:
        merged_query += f"\nContexto adicional: {slot_summary}"

    merged_query = _apply_question_type_anchors(merged_query, question_type)

    return merged_query, context_block, slot_patch


def _apply_question_type_anchors(merged_query: str, question_type: str) -> str:
    anchors = {
        "declarar_ingresos": "IRPF actividad economica ingresos obligacion declarar",
        "deducibles": "gastos deducibles afectacion justificantes facturas",
        "amortizacion": "amortizacion coeficientes vida util estimacion directa",
    }
    anchor = anchors.get(question_type)
    if anchor:
        return f"{merged_query}\nTerminos clave: {anchor}"
    return merged_query


def _format_slot_summary(slot_values: Dict[str, Any]) -> str:
    parts = []
    for key, value in slot_values.items():
        parts.append(f"{key}={value}")
    return ", ".join(parts)


def _map_tax_slot_value(slot_name: str, raw_value: str) -> Any:
    if not raw_value:
        return raw_value
    normalized = _normalize_text(raw_value)
    if slot_name == "tax_net_turnover_bucket":
        if normalized in {"a", "si", "sí"}:
            return "GT_100K"
        if normalized in {"b", "no"}:
            return "LT_100K"
    if slot_name == "tax_new_activity":
        if normalized in {"a", "si", "sí"}:
            return True
        if normalized in {"b", "no"}:
            return False
    if slot_name == "tax_irpf_income_type":
        if normalized in {"a", "actividad profesional", "profesional"} or "actividad" in normalized:
            return "actividad_profesional"
        if normalized in {"b", "consejero", "administrador"} or "consejero" in normalized or "administrador" in normalized:
            return "consejero_administrador"
    return raw_value.strip()

def _build_state_patch(
    mode: str,
    reason: str,
    state: Dict[str, Any],
    user_text: str,
    effective_area: Optional[str],
    classifier_confidence: float,
    explicit_topic_change: bool,
    slot_patch: Dict[str, Any],
) -> Dict[str, Any]:
    patch = _empty_patch()
    if mode == "NEW_QUESTION":
        patch["set"].update({
            "base_question": user_text,
            "last_actionable_user_question": user_text,
            "pending_slots": [],
            "slot_values": {},
        })
        if effective_area and (classifier_confidence >= 0.55 or explicit_topic_change):
            patch["set"]["topic_lock"] = effective_area
    elif mode in {"FOLLOWUP_SLOT_FILL", "FOLLOWUP_REFERENTIAL"}:
        if state.get("base_question"):
            patch["set"]["last_actionable_user_question"] = state.get("base_question")
        if slot_patch.get("slot_values") is not None:
            patch["set"]["slot_values"] = slot_patch["slot_values"]
        if slot_patch.get("pending_slots") is not None:
            patch["set"]["pending_slots"] = slot_patch["pending_slots"]

    return patch


def _extract_para_afinar_questions(answer: str) -> List[str]:
    if not answer:
        return []

    lines = answer.splitlines()
    start_idx = None
    for idx, line in enumerate(lines):
        if "para afinar" in line.lower():
            start_idx = idx + 1
            break

    if start_idx is None:
        return []

    questions = []
    for line in lines[start_idx:]:
        stripped = line.strip()
        if not stripped:
            if questions:
                break
            continue
        if stripped.startswith("**"):
            break
        if stripped.startswith(("-", "•", "*")):
            questions.append(stripped.lstrip("-•* ").strip())

    return questions


def _derive_pending_slots(questions: List[str]) -> List[str]:
    slot_map = {
        "location": ["ccaa", "comunidad", "provincia", "ciudad", "municipio", "localidad", "donde"],
        "entity_type": ["autonomo", "autónomo", "sl", "s.l", "sociedad", "asociacion", "asociación", "empresa", "entidad"],
        "period": ["fecha", "fechas", "periodo", "período", "anio", "año", "ejercicio", "202"],
    }

    pending = []
    for question in questions:
        normalized = _normalize_text(question)
        for slot, tokens in slot_map.items():
            if any(token in normalized for token in tokens) and slot not in pending:
                pending.append(slot)
    return pending


def _infer_slot_fill(reply: str, pending_slots: List[str]) -> str:
    normalized = _normalize_text(reply)
    if re.search(r"\b(19|20)\d{2}\b", normalized):
        return "period"
    if any(token in normalized for token in ["autonomo", "autónomo", "sl", "s.l", "sociedad", "asociacion", "asociación"]):
        return "entity_type"
    if "location" in pending_slots:
        return "location"
    return pending_slots[0] if pending_slots else "context"


def _is_example_request(normalized_text: str) -> bool:
    example_terms = ["por ejemplo", "dame un ejemplo", "dame ejemplos", "ejemplo", "ejemplos"]
    return any(term in normalized_text for term in example_terms)
