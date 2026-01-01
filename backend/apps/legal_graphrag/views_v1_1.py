"""
Legal GraphRAG Views V1.1
Orchestrator-driven multi-turn logic (feature-flagged).
"""

import copy
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import ChatMessage
from .serializers import ChatRequestSerializer
from .services.v1_1.legal_rag_engine_v1_1 import LegalRAGEngineV1_1
from .services.v1_1.intent_classifier import IntentClassifier
from .services.v1_1.orchestrator_v1_1 import (
    apply_state_patch,
    build_state_patch_from_answer,
    decide_turn,
    default_session_state,
    log_orchestrator_decision,
)
from .views import (
    _get_or_create_session,
    _get_or_create_session_with_meta,
    _persist_chat_messages,
    _is_greeting,
    _is_follow_up_question,
    _get_conversation_context,
)

logger = logging.getLogger(__name__)


def _compute_state_diff(before: dict, after: dict) -> dict:
    before_keys = set(before.keys())
    after_keys = set(after.keys())
    set_keys = [key for key in after_keys if before.get(key) != after.get(key)]
    cleared_keys = [key for key in before_keys if key not in after_keys]
    unchanged_keys = [key for key in after_keys if before.get(key) == after.get(key)]
    return {
        "set": sorted(set_keys),
        "cleared": sorted(cleared_keys),
        "unchanged": sorted(unchanged_keys),
    }


def _log_full_trace(trace_payload: dict) -> None:
    log_dir = Path(__file__).resolve().parents[3] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "trace_v1_1.jsonl"
    try:
        with open(log_file, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(trace_payload, ensure_ascii=False, default=str) + "\n"
            )
    except Exception:
        logger.exception("Failed to write full trace log")


def _persist_chat_messages_with_trace(session, query, rag_result, area_principal):
    trace = {
        "save_called": False,
        "save_success": False,
        "db_commit_success": False,
        "messages": [],
        "assistant_contains_cited_ids": False,
        "assistant_message_id": None,
        "user_message_id": None,
    }
    try:
        trace["save_called"] = True
        user_msg = ChatMessage.objects.create(
            session=session,
            role="user",
            content=query,
            metadata={"area_principal": area_principal},
        )
        assistant_msg = ChatMessage.objects.create(
            session=session,
            role="assistant",
            content=rag_result.get("answer", ""),
            sources=rag_result.get("sources", []),
            metadata=rag_result.get("metadata", {}),
        )
        trace["assistant_contains_cited_ids"] = "<!--CITED_IDS" in assistant_msg.content
        trace["assistant_message_id"] = str(assistant_msg.id)
        trace["user_message_id"] = str(user_msg.id)
        trace["messages"] = [
            {
                "id": str(user_msg.id),
                "role": "user",
                "session_id": str(session.id),
                "metadata_size": len(json.dumps(user_msg.metadata)) if user_msg.metadata else 0,
            },
            {
                "id": str(assistant_msg.id),
                "role": "assistant",
                "session_id": str(session.id),
                "metadata_size": len(json.dumps(assistant_msg.metadata)) if assistant_msg.metadata else 0,
            },
        ]
        trace["save_success"] = True
        trace["db_commit_success"] = True
    except Exception:
        logger.exception("Failed to persist chat messages for trace")
    return trace


def _classifier_matches(classifier: IntentClassifier, query: str) -> dict:
    normalized = classifier._normalize_text(query)
    matches = {}
    for area, keywords in classifier.normalized_area_keywords.items():
        matched = [kw for kw in keywords if kw in normalized]
        if matched:
            matches[area] = matched[:10]
    return matches


def _normalize_text_basic(text: str) -> str:
    import unicodedata

    if not text:
        return ""
    lowered = text.lower()
    normalized = unicodedata.normalize("NFKD", lowered)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _build_memory_summary(
    base_question: str,
    slot_values: dict,
    user_texts: list,
    prior_summary: str,
) -> str:
    combined = " ".join([base_question or ""] + user_texts)
    normalized = _normalize_text_basic(combined)

    regions_map = {
        "espana": "Espana",
        "ue": "UE",
        "union europea": "UE",
        "francia": "Francia",
        "alemania": "Alemania",
        "portugal": "Portugal",
        "madrid": "Madrid",
        "valencia": "Valencia",
        "cataluna": "Cataluna",
        "andalucia": "Andalucia",
        "aragon": "Aragon",
        "galicia": "Galicia",
    }
    region_hits = []
    for token, label in regions_map.items():
        if token in normalized and label not in region_hits:
            region_hits.append(label)

    profile_hits = []
    if "autonomo" in normalized:
        profile_hits.append("autonomo")
    if "empresa" in normalized:
        profile_hits.append("empresa")
    if "particular" in normalized:
        profile_hits.append("particular")
    if "sociedad" in normalized or "sl" in normalized:
        if "sociedad" not in profile_hits:
            profile_hits.append("sociedad")

    constraints = []
    if "vat id" in normalized or "vatid" in normalized:
        constraints.append("cliente empresa con VAT ID (B2B)")
    elif "empresa" in normalized:
        constraints.append("cliente empresa (B2B)")
    if "particular" in normalized:
        constraints.append("cliente particular (B2C)")
    if "digital" in normalized:
        constraints.append("servicios digitales")
    if "artistico" in normalized or "artistica" in normalized:
        constraints.append("servicios artisticos")
    if "presencial" in normalized:
        constraints.append("servicios presenciales")

    lines = []
    if base_question:
        lines.append(f"- Tema/base: {base_question.strip()[:180]}")
    if region_hits:
        lines.append(f"- Jurisdiccion/region: {', '.join(region_hits)}")
    if profile_hits:
        lines.append(f"- Perfil/entidad: {', '.join(profile_hits)}")
    if constraints:
        lines.append(f"- Condiciones: {', '.join(constraints)}")
    if slot_values:
        slot_parts = [f"{key}={value}" for key, value in slot_values.items()]
        lines.append(f"- Slots confirmados: {', '.join(slot_parts)}")

    if not lines:
        return (prior_summary or "")[:600]

    summary = "\n".join(lines[:6])
    return summary[:600]


def _get_recent_messages(session, role: str, limit: int = 2) -> list:
    messages = (
        ChatMessage.objects.filter(session=session, role=role)
        .order_by("-created_at")
        .values_list("content", flat=True)[:limit]
    )
    return list(reversed(list(messages)))


def _build_full_trace(
    base_trace: dict,
    state_before: dict,
    state_after: dict,
    state_diff: dict,
    messages_trace: dict,
    classifier_result: dict,
    classifier_matches: dict,
    orchestrator_trace: dict,
    rag_result: dict,
    messages_before: int,
    messages_after: int,
    save_state_called: bool,
    save_state_success: bool,
    save_state_where: str,
    max_sources_requested: int,
    pending_extraction: dict = None,
    state_recovery: dict = None,
) -> dict:
    sources = rag_result.get("sources", []) if rag_result else []
    cited_ids = [src.get("id") for src in sources if src.get("is_cited")]
    additional_ids = [src.get("id") for src in sources if not src.get("is_cited")]
    metadata = rag_result.get("metadata", {}) if rag_result else {}

    return {
        **base_trace,
        "session": {
            "state_before": state_before,
            "state_after": state_after,
            "state_diff": state_diff,
            "save_state_called": save_state_called,
            "save_state_success": save_state_success,
            "save_state_where": save_state_where,
            "db_commit_success": save_state_success,
            "messages_before": messages_before,
            "messages_after": messages_after,
            "state_recovery": state_recovery or {},
        },
        "orchestrator": orchestrator_trace,
        "classifier": {
            "area_detected": classifier_result.get("area"),
            "confidence": classifier_result.get("confidence"),
            "scores": classifier_result.get("scores") or {},
            "matched_keywords": classifier_matches,
        },
        "rag": {
            "query_expansion": metadata.get("debug_summary", {}).get("query_expansion", {}).get("queries", []),
            "forced_area": metadata.get("forced_area"),
            "question_type": metadata.get("question_type"),
            "retrieval_params": {
                "max_sources_requested": max_sources_requested,
                "max_sources_returned": metadata.get("total_sources"),
                "area_principal": metadata.get("area_principal"),
            },
            "top_sources": [
                {
                    "id": src.get("id"),
                    "title": src.get("title"),
                    "score": src.get("relevance_score"),
                    "naturaleza": src.get("source_type"),
                }
                for src in sources[:5]
            ],
            "cited_ids": cited_ids,
            "additional_ids": additional_ids,
            "abstain": {
                "abstained": metadata.get("abstained"),
                "reason": metadata.get("abstain_reason"),
            },
        },
        "persistence": messages_trace,
        "pending_slots_extraction": pending_extraction or {},
    }


@api_view(["POST"])
def chat_view_v1_1(request):
    """
    V1.1 chat endpoint with orchestrator-based routing (optional).
    """
    orchestrator_enabled = os.getenv("ORCHESTRATOR_V1_1", "1") == "1"
    debug_enabled = request.headers.get("X-Developer-Debug") == "1"
    trace_enabled = debug_enabled and os.getenv("DEBUG_TRACE", "0") == "1"
    request_id = str(uuid.uuid4())
    request_timestamp = datetime.now().isoformat()

    serializer = ChatRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    query = data["query"]

    session, lookup_method, is_new_session = _get_or_create_session_with_meta(
        data.get("session_id"), request
    )
    messages_before = session.messages.count()

    # STALENESS DETECTION: Clear state if session is stale
    # This prevents old conversation context from bleeding into new topics
    state_raw = session.session_state or default_session_state()

    # Check for session staleness (30+ minutes of inactivity)
    from django.utils import timezone
    state_cleared_reason = None

    if session.updated_at:
        now = timezone.now()
        time_since_update = now - session.updated_at

        # If session hasn't been used in 30+ minutes, clear state
        if time_since_update > timedelta(minutes=30):
            old_topic_lock = state_raw.get('topic_lock')  # Save before clearing
            old_base_question = state_raw.get('base_question')
            state_raw = default_session_state()
            state_cleared_reason = f"stale_session_inactive_{int(time_since_update.total_seconds() / 60)}min"
            logger.info(
                f"[Session Staleness] Cleared stale session state. "
                f"Session {session.id} inactive for {time_since_update}. "
                f"Old state had topic_lock={old_topic_lock}, base_question={old_base_question[:50] if old_base_question else None}"
            )

    state = copy.deepcopy(state_raw)
    recovery_info = {"applied": False, "fields": [], "state_cleared": state_cleared_reason}

    if not state.get("base_question") or not state.get("last_actionable_user_question"):
        last_user = ChatMessage.objects.filter(session=session, role="user").order_by("-created_at").first()
        if last_user:
            if not state.get("base_question"):
                state["base_question"] = last_user.content
                recovery_info["fields"].append("base_question")
            if not state.get("last_actionable_user_question"):
                state["last_actionable_user_question"] = last_user.content
                recovery_info["fields"].append("last_actionable_user_question")

    last_assistant_for_recovery = ChatMessage.objects.filter(session=session, role="assistant").order_by("-created_at").first()
    if last_assistant_for_recovery and not state.get("topic_lock"):
        meta = last_assistant_for_recovery.metadata or {}
        decision = meta.get("decision") or {}
        recovered_area = decision.get("effective_area") or meta.get("area_principal")
        if recovered_area:
            state["topic_lock"] = recovered_area
            recovery_info["fields"].append("topic_lock")

    if recovery_info["fields"]:
        recovery_info["applied"] = True

    recent_user_messages = _get_recent_messages(session, "user", limit=2)
    recent_assistant_messages = _get_recent_messages(session, "assistant", limit=2)

    base_trace = {
        "request_id": request_id,
        "timestamp": request_timestamp,
        "endpoint": request.path,
        "engine_version": "v1_1",
        "session_id_received": data.get("session_id"),
        "user_id_received": str(request.user.id) if getattr(request, "user", None) and request.user.is_authenticated else None,
        "ip": request.META.get("REMOTE_ADDR"),
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
        "chat_session_db_id": str(session.id),
        "chat_session_lookup_method": lookup_method,
        "is_new_session": is_new_session,
    }

    if _is_greeting(query):
        greeting_response = {
            "answer": "Hola! Soy tu asistente legal. Puedo ayudarte con temas fiscales, laborales, propiedad intelectual y subvenciones.",
            "sources": [],
            "metadata": {"greeting": True, "version": "v1_1"},
        }
        messages_trace = {}
        message_ids = {}
        if trace_enabled:
            messages_trace = _persist_chat_messages_with_trace(session, query, greeting_response, None)
            message_ids = {
                "assistant_message_id": messages_trace.get("assistant_message_id"),
                "user_message_id": messages_trace.get("user_message_id"),
            }
        else:
            message_ids = _persist_chat_messages(session, query, greeting_response, None)
        if message_ids:
            greeting_response.setdefault("metadata", {})
            greeting_response["metadata"].update(message_ids)

        if trace_enabled:
            state_before = session.session_state or {}
            state_after = state_before
            full_trace = _build_full_trace(
                base_trace=base_trace,
                state_before=state_raw,
                state_after=state_after,
                state_diff=_compute_state_diff(state_raw, state_after),
                messages_trace=messages_trace,
                classifier_result={"area": None, "confidence": 0.0, "scores": {}},
                classifier_matches={},
                orchestrator_trace={
                    "decision": {"mode": "GREETING", "reason": "greeting"},
                    "signals": {},
                    "thresholds": {},
                    "rejections": [],
                    "state_after": state_after,
                    "state_diff": {},
                },
                rag_result=greeting_response,
                messages_before=messages_before,
                messages_after=session.messages.count(),
                save_state_called=False,
                save_state_success=False,
                save_state_where="greeting",
                max_sources_requested=data.get("max_sources", 10),
                pending_extraction={"ran": False, "written": False},
                state_recovery=recovery_info,
            )
            greeting_response["metadata"]["developer_debug"] = {
                "full_trace": full_trace,
            }
            _log_full_trace(full_trace)

        return Response(
            {
                "session_id": str(session.id),
                "answer": greeting_response["answer"],
                "sources": [],
                "metadata": greeting_response["metadata"],
            },
            status=status.HTTP_200_OK,
        )

    if orchestrator_enabled:
        last_assistant = ChatMessage.objects.filter(
            session=session,
            role="assistant",
        ).order_by("-created_at").first()
        last_assistant_text = last_assistant.content if last_assistant else None

        classifier = IntentClassifier()
        classifier_result = classifier.classify_with_confidence(query)
        classifier_matches = _classifier_matches(classifier, query)

        router_context = {
            "memory_summary": (state.get("memory_summary") or "")[:600],
            "base_question": (state.get("base_question") or ""),
            "recent_user_messages": recent_user_messages,
            "recent_assistant_messages": recent_assistant_messages,
            "current_user_text": query,
        }

        decision = decide_turn(
            session_state=state,
            user_text=query,
            classifier_result=classifier_result,
            last_assistant_text=last_assistant_text,
            router_context=router_context,
        )

        if decision.mode == "CLARIFY":
            clarify_text = "Podrias dar un poco mas de contexto para poder ayudarte?"
            response_payload = {
                "session_id": str(session.id),
                "answer": clarify_text,
                "sources": [],
                "metadata": {
                    "version": "v1_1",
                    "orchestrator": True,
                    "decision": decision.__dict__,
                    "clarify": True,
                },
            }
            new_state = apply_state_patch(state, decision.state_patch)
            session.session_state = new_state
            session.save(update_fields=["session_state", "updated_at"])
            if debug_enabled:
                decision.trace["session_id"] = str(session.id)
                decision.trace["turn_index"] = state.get("turn_count", 0)
                decision.trace["state_after"] = {
                    "topic_lock": new_state.get("topic_lock"),
                    "pending_slots": new_state.get("pending_slots"),
                    "turn_count": new_state.get("turn_count"),
                }
                decision.trace["state_diff"] = {
                    "set": list(decision.state_patch.get("set", {}).keys()),
                    "cleared": decision.state_patch.get("unset", []),
                    "unchanged": ["topic_lock", "base_question"] if state.get("topic_lock") or state.get("base_question") else [],
                }
                response_payload["metadata"]["developer_debug"] = {
                    "orchestrator_trace": decision.trace,
                }
            log_orchestrator_decision(str(session.id), decision, state, new_state)
            messages_trace = {}
            message_ids = {}
            if trace_enabled:
                messages_trace = _persist_chat_messages_with_trace(session, query, response_payload, classifier_result.get("area"))
                message_ids = {
                    "assistant_message_id": messages_trace.get("assistant_message_id"),
                    "user_message_id": messages_trace.get("user_message_id"),
                }
                full_trace = _build_full_trace(
                    base_trace=base_trace,
                    state_before=state_raw,
                    state_after=new_state,
                    state_diff=_compute_state_diff(state_raw, new_state),
                    messages_trace=messages_trace,
                    classifier_result=classifier_result,
                    classifier_matches=classifier_matches,
                    orchestrator_trace=decision.trace,
                    rag_result=response_payload,
                    messages_before=messages_before,
                    messages_after=session.messages.count(),
                    save_state_called=True,
                    save_state_success=True,
                    save_state_where="clarify",
                    max_sources_requested=data.get("max_sources", 10),
                    pending_extraction={"ran": False, "written": False},
                    state_recovery=recovery_info,
                )
                response_payload.setdefault("metadata", {})
                response_payload["metadata"].setdefault("developer_debug", {})
                response_payload["metadata"]["developer_debug"]["full_trace"] = full_trace
                _log_full_trace(full_trace)
            else:
                message_ids = _persist_chat_messages(session, query, response_payload, classifier_result.get("area"))
            if message_ids:
                response_payload.setdefault("metadata", {})
                response_payload["metadata"].update(message_ids)
            return Response(response_payload, status=status.HTTP_200_OK)

        if decision.mode == "META":
            engine = LegalRAGEngineV1_1()
            answer_text = engine._build_meta_response()
            response_payload = {
                "session_id": str(session.id),
                "answer": answer_text,
                "sources": [],
                "metadata": {
                    "version": "v1_1",
                    "orchestrator": True,
                    "decision": decision.__dict__,
                    "meta": True,
                },
            }
            new_state = apply_state_patch(state, decision.state_patch)
            session.session_state = new_state
            session.save(update_fields=["session_state", "updated_at"])
            if debug_enabled:
                decision.trace["session_id"] = str(session.id)
                decision.trace["turn_index"] = state.get("turn_count", 0)
                decision.trace["state_after"] = {
                    "topic_lock": new_state.get("topic_lock"),
                    "pending_slots": new_state.get("pending_slots"),
                    "turn_count": new_state.get("turn_count"),
                }
                decision.trace["state_diff"] = {
                    "set": list(decision.state_patch.get("set", {}).keys()),
                    "cleared": decision.state_patch.get("unset", []),
                    "unchanged": ["topic_lock", "base_question"] if state.get("topic_lock") or state.get("base_question") else [],
                }
                response_payload["metadata"]["developer_debug"] = {
                    "orchestrator_trace": decision.trace,
                }
            log_orchestrator_decision(str(session.id), decision, state, new_state)
            messages_trace = {}
            message_ids = {}
            if trace_enabled:
                messages_trace = _persist_chat_messages_with_trace(session, query, response_payload, classifier_result.get("area"))
                message_ids = {
                    "assistant_message_id": messages_trace.get("assistant_message_id"),
                    "user_message_id": messages_trace.get("user_message_id"),
                }
                full_trace = _build_full_trace(
                    base_trace=base_trace,
                    state_before=state_raw,
                    state_after=new_state,
                    state_diff=_compute_state_diff(state_raw, new_state),
                    messages_trace=messages_trace,
                    classifier_result=classifier_result,
                    classifier_matches=classifier_matches,
                    orchestrator_trace=decision.trace,
                    rag_result=response_payload,
                    messages_before=messages_before,
                    messages_after=session.messages.count(),
                    save_state_called=True,
                    save_state_success=True,
                    save_state_where="meta",
                    max_sources_requested=data.get("max_sources", 10),
                    pending_extraction={"ran": False, "written": False},
                    state_recovery=recovery_info,
                )
                response_payload.setdefault("metadata", {})
                response_payload["metadata"].setdefault("developer_debug", {})
                response_payload["metadata"]["developer_debug"]["full_trace"] = full_trace
                _log_full_trace(full_trace)
            else:
                message_ids = _persist_chat_messages(session, query, response_payload, classifier_result.get("area"))
            if message_ids:
                response_payload.setdefault("metadata", {})
                response_payload["metadata"].update(message_ids)
            return Response(response_payload, status=status.HTTP_200_OK)

        engine = LegalRAGEngineV1_1()
        try:
            rag_result = engine.answer_query(
                query=decision.merged_query or query,
                area_principal=decision.effective_area,
                forced_area=decision.forced_area,
                max_sources=data.get("max_sources", 10),
                question_type=decision.question_type,
                context_block=decision.context_block,
                session_id=str(session.id),
                trace_context={
                    "case_id": data.get("case_id"),
                    "turn": data.get("turn"),
                    "area": decision.effective_area,
                    "user_text": query,
                    "session_id": str(session.id),
                    "router_decision": decision.__dict__,
                    "intent_classifier": classifier_result,
                },
            )
        except Exception:
            logger.exception("V1.1 RAG generation failed (orchestrator)")
            return Response({"detail": "Failed to generate answer"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        pending_patch = build_state_patch_from_answer(rag_result.get("answer", ""))
        rag_result.setdefault("metadata", {})
        rag_result["metadata"].update({
            "orchestrator": True,
            "decision": decision.__dict__,
        })
        pending_slots = []
        pending_from_answer = pending_patch.get("set", {}).get("pending_slots") if pending_patch else None
        if pending_from_answer:
            pending_slots.extend(pending_from_answer)
        pending_from_meta = rag_result.get("metadata", {}).get("pending_slots") or []
        if pending_from_meta:
            pending_slots.extend(pending_from_meta)
        if pending_slots:
            pending_patch = {
                "set": {"pending_slots": list(dict.fromkeys(pending_slots))},
                "unset": [],
                "append": {},
            }

        new_state = apply_state_patch(state, decision.state_patch)
        if pending_patch.get("set"):
            new_state = apply_state_patch(new_state, pending_patch, increment_turn=False)
        new_state["last_answer_brief"] = (rag_result.get("answer") or "")[:300]
        new_state["memory_summary"] = _build_memory_summary(
            base_question=new_state.get("base_question") or new_state.get("last_actionable_user_question") or "",
            slot_values=new_state.get("slot_values") or {},
            user_texts=recent_user_messages + [query],
            prior_summary=new_state.get("memory_summary") or "",
        )

        session.session_state = new_state
        session.save(update_fields=["session_state", "updated_at"])
        if debug_enabled:
            decision.trace["session_id"] = str(session.id)
            decision.trace["turn_index"] = state.get("turn_count", 0)
            decision.trace["state_after"] = {
                "topic_lock": new_state.get("topic_lock"),
                "pending_slots": new_state.get("pending_slots"),
                "turn_count": new_state.get("turn_count"),
            }
            decision.trace["state_diff"] = {
                "set": list(decision.state_patch.get("set", {}).keys()),
                "cleared": decision.state_patch.get("unset", []),
                "pending_set": list(pending_patch.get("set", {}).keys()) if pending_patch else [],
                "unchanged": ["topic_lock", "base_question"] if state.get("topic_lock") or state.get("base_question") else [],
            }
            rag_result["metadata"]["developer_debug"] = {
                "orchestrator_trace": decision.trace,
            }
        log_orchestrator_decision(str(session.id), decision, state, new_state)
        messages_trace = {}
        message_ids = {}
        if trace_enabled:
            messages_trace = _persist_chat_messages_with_trace(session, query, rag_result, decision.effective_area)
            message_ids = {
                "assistant_message_id": messages_trace.get("assistant_message_id"),
                "user_message_id": messages_trace.get("user_message_id"),
            }
            full_trace = _build_full_trace(
                base_trace=base_trace,
                state_before=state_raw,
                state_after=new_state,
                state_diff=_compute_state_diff(state_raw, new_state),
                messages_trace=messages_trace,
                classifier_result=classifier_result,
                classifier_matches=classifier_matches,
                orchestrator_trace=decision.trace,
                rag_result=rag_result,
                messages_before=messages_before,
                messages_after=session.messages.count(),
                save_state_called=True,
                save_state_success=True,
                save_state_where="orchestrator",
                max_sources_requested=data.get("max_sources", 10),
                pending_extraction={
                    "ran": True,
                    "written": bool(pending_patch.get("set")) if pending_patch else False,
                },
                state_recovery=recovery_info,
            )
            rag_result.setdefault("metadata", {})
            rag_result["metadata"].setdefault("developer_debug", {})
            rag_result["metadata"]["developer_debug"]["full_trace"] = full_trace
            _log_full_trace(full_trace)
        else:
            message_ids = _persist_chat_messages(session, query, rag_result, decision.effective_area)
        if message_ids:
            rag_result.setdefault("metadata", {})
            rag_result["metadata"].update(message_ids)

        response_payload = {
            "session_id": str(session.id),
            "answer": rag_result.get("answer", ""),
            "sources": rag_result.get("sources", []),
            "metadata": rag_result.get("metadata", {}),
        }
        return Response(response_payload, status=status.HTTP_200_OK)

    # Legacy path (orchestrator disabled)
    is_follow_up = _is_follow_up_question(query)
    if is_follow_up and session.messages.count() > 0:
        conversation_context = _get_conversation_context(session)
        import google.generativeai as genai
        from django.conf import settings

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name="gemini-2.5-flash")
        follow_up_prompt = (
            "You are a legal assistant. Answer based only on the conversation history.\n\n"
            f"History:\n{conversation_context}\n\n"
            f"User question: {query}\n"
        )
        try:
            response = model.generate_content(follow_up_prompt)
            follow_up_answer = response.text
        except Exception:
            logger.exception("V1.1 follow-up LLM failed")
            follow_up_answer = "Disculpa, hubo un error al procesar tu pregunta de seguimiento."

        follow_up_result = {
            "answer": follow_up_answer,
            "sources": [],
            "metadata": {"follow_up": True, "used_conversation_context": True, "version": "v1_1"},
        }
        message_ids = _persist_chat_messages(session, query, follow_up_result, None)
        if message_ids:
            follow_up_result.setdefault("metadata", {})
            follow_up_result["metadata"].update(message_ids)
        return Response(
            {
                "session_id": str(session.id),
                "answer": follow_up_result["answer"],
                "sources": [],
                "metadata": follow_up_result["metadata"],
            },
            status=status.HTTP_200_OK,
        )

    engine = LegalRAGEngineV1_1()
    try:
        rag_result = engine.answer_query(
            query=query,
            area_principal=data.get("area_principal") or None,
            max_sources=data.get("max_sources", 10),
            session_id=str(session.id),
        )
    except Exception:
        logger.exception("V1.1 RAG generation failed")
        return Response({"detail": "Failed to generate answer"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    message_ids = _persist_chat_messages(session, query, rag_result, data.get("area_principal"))
    if message_ids:
        rag_result.setdefault("metadata", {})
        rag_result["metadata"].update(message_ids)

    response_payload = {
        "session_id": str(session.id),
        "answer": rag_result.get("answer", ""),
        "sources": rag_result.get("sources", []),
        "metadata": rag_result.get("metadata", {}),
    }
    return Response(response_payload, status=status.HTTP_200_OK)
