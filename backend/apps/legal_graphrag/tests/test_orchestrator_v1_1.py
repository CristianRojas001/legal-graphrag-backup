from apps.legal_graphrag.services.v1_1.orchestrator_v1_1 import (
    decide_turn,
    default_session_state,
)


def test_thin_turn_followup_attaches_base_question():
    state = default_session_state()
    state["base_question"] = "Pregunta base sobre IRPF"
    state["topic_lock"] = "Fiscal"
    classifier = {"area": "Laboral", "confidence": 0.2}

    decision = decide_turn(state, "y eso?", classifier)

    assert decision.mode == "FOLLOWUP_REFERENTIAL"
    assert "Pregunta base" in (decision.merged_query or "")


def test_low_confidence_falls_back_to_topic_lock():
    state = default_session_state()
    state["topic_lock"] = "Fiscal"
    classifier = {"area": "Laboral", "confidence": 0.3}

    decision = decide_turn(state, "tengo dudas", classifier)

    assert decision.effective_area == "Fiscal"


def test_pending_slot_qualitative_keeps_period_pending():
    state = default_session_state()
    state["base_question"] = "Pregunta base"
    state["pending_slots"] = ["period"]
    classifier = {"area": "Fiscal", "confidence": 0.6}

    decision = decide_turn(state, "sin fecha concreta", classifier)

    assert decision.mode == "FOLLOWUP_SLOT_FILL"
    assert decision.state_patch["set"]["pending_slots"] == ["period"]
    assert decision.state_patch["set"]["slot_values"]["period"] == "sin fecha concreta"


def test_explicit_topic_change_breaks_lock():
    state = default_session_state()
    state["topic_lock"] = "Fiscal"
    classifier = {"area": "Propiedad Intelectual", "confidence": 0.9}

    decision = decide_turn(state, "Cambiando de tema: derechos de autor", classifier)

    assert decision.mode == "NEW_QUESTION"
    assert decision.effective_area == "Propiedad Intelectual"


def test_no_base_question_short_ambiguous_clarify():
    state = default_session_state()
    classifier = {"area": None, "confidence": 0.2}

    decision = decide_turn(state, "Valencia", classifier)

    assert decision.mode == "CLARIFY"
    assert decision.should_call_rag is False


def test_tax_net_turnover_slot_maps_ab():
    state = default_session_state()
    state["base_question"] = "Soy consejero/administrador. Que retencion aplica?"
    state["pending_slots"] = ["tax_net_turnover_bucket"]
    state["topic_lock"] = "Fiscal"
    classifier = {"area": "Fiscal", "confidence": 0.6}

    decision = decide_turn(state, "A", classifier)

    assert decision.mode == "FOLLOWUP_SLOT_FILL"
    slot_values = decision.state_patch["set"]["slot_values"]
    assert slot_values["tax_net_turnover_bucket"] == "GT_100K"
    assert decision.state_patch["set"]["pending_slots"] == []


def test_impresos_not_followup_referential():
    state = default_session_state()
    classifier = {"area": "Fiscal", "confidence": 0.5}

    decision = decide_turn(state, "Vendo libros impresos. Que IVA aplico?", classifier)

    assert decision.mode == "NEW_QUESTION"
