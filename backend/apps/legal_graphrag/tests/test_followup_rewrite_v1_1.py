from apps.legal_graphrag.services.v1_1.orchestrator_v1_1 import decide_turn, default_session_state


def test_followup_example_rewrite():
    state = default_session_state()
    state["base_question"] = "Base question sobre IVA"
    state["last_actionable_user_question"] = "Base question sobre IVA"
    state["topic_lock"] = "Fiscal"
    classifier = {"area": "Fiscal", "confidence": 0.6, "scores": {"Fiscal": 1}}

    decision = decide_turn(state, "por ejemplo?", classifier)

    assert decision.mode in {"FOLLOWUP_REFERENTIAL", "FOLLOWUP_SLOT_FILL"}
    assert decision.merged_query is not None
    assert "Solicitud: ejemplos" in decision.merged_query


def test_followup_example_with_base_question():
    state = default_session_state()
    state["base_question"] = "Base question sobre IRPF"
    state["last_actionable_user_question"] = "Base question sobre IRPF"
    state["topic_lock"] = "Fiscal"
    classifier = {"area": None, "confidence": 0.1, "scores": {}}

    decision = decide_turn(state, "dame un ejemplo", classifier)

    assert decision.mode in {"FOLLOWUP_REFERENTIAL", "FOLLOWUP_SLOT_FILL"}
    assert decision.merged_query is not None
    assert "Base question" in decision.merged_query
