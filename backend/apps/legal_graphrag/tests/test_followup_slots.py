from apps.legal_graphrag.views import (
    _build_pending_metadata,
    _infer_slot_from_reply,
    _is_slot_fill_reply,
    _merge_pending_question,
)


def test_build_pending_metadata_from_para_afinar():
    answer = (
        "Respuesta base.\n\n"
        "**Para afinar:**\n"
        "- ¿En qué CCAA o ciudad?\n"
        "- ¿Eres autónomo o sociedad?\n"
        "- ¿En qué año?\n"
    )
    metadata = _build_pending_metadata(answer, "Pregunta original", "Fiscal")

    assert metadata is not None
    assert "pending_slots" in metadata
    assert "location" in metadata["pending_slots"]
    assert "entity_type" in metadata["pending_slots"]
    assert "period" in metadata["pending_slots"]


def test_slot_fill_reply_detection_and_merge():
    pending_slots = ["location", "period"]
    reply = "Valencia"

    assert _is_slot_fill_reply(reply, pending_slots) is True

    slot_name = _infer_slot_from_reply(reply, pending_slots)
    merged = _merge_pending_question("Pregunta original", slot_name, reply)

    assert "Contexto adicional" in merged
    assert "Valencia" in merged
