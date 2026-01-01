"""
Definitive Operational Memory Unit Tests

Tests for session-level state management with DB persistence.
"""

import pytest
from datetime import datetime
from apps.legal_graphrag.models import ChatSession
from apps.legal_graphrag.services.v1_1.operational_memory_v1_1 import (
    default_session_state,
    load_state,
    save_state,
    compute_state_diff,
    count_tokens,
    has_referential_marker,
    is_followup,
    infer_slot_fill,
    build_merged_query,
    build_context_block,
    compute_effective_area,
    reset_state_for_topic_change,
    update_state_after_answer,
)


# ========== Helper Tests ==========

class TestHelperFunctions:
    """Test utility functions"""

    def test_count_tokens(self):
        assert count_tokens("Hola mundo") == 2
        assert count_tokens("¿Qué gastos puedo deducir?") == 4
        assert count_tokens("Valencia") == 1

    def test_has_referential_marker(self):
        assert has_referential_marker("en relación a lo anterior") is True
        assert has_referential_marker("lo mismo") is True
        assert has_referential_marker("eso") is True
        assert has_referential_marker("¿Qué gastos puedo deducir?") is False

    def test_compute_state_diff(self):
        before = {"topic_lock": None, "pending_slots": []}
        after = {"topic_lock": "Fiscal", "pending_slots": ["location"]}

        diff = compute_state_diff(before, after)

        assert "topic_lock" in diff
        assert diff["topic_lock"]["before"] is None
        assert diff["topic_lock"]["after"] == "Fiscal"


# ========== State Management Tests ==========

class TestStateManagement:
    """Test state load/save with DB persistence"""

    @pytest.mark.django_db
    def test_load_state_defaults(self):
        """New session should get default state"""
        session = ChatSession.objects.create()
        state = load_state(session)

        assert state["topic_lock"] is None
        assert state["base_question"] is None
        assert state["pending_slots"] == []
        assert state["slot_values"] == {}
        assert state["turn_count"] == 0

    @pytest.mark.django_db
    def test_save_and_load_state(self):
        """State should persist across DB round-trip"""
        session = ChatSession.objects.create()

        state = load_state(session)
        state["topic_lock"] = "Fiscal"
        state["base_question"] = "¿Gastos deducibles?"
        state["pending_slots"] = ["location"]
        save_state(session, state)

        # Reload session
        session.refresh_from_db()
        state2 = load_state(session)

        assert state2["topic_lock"] == "Fiscal"
        assert state2["base_question"] == "¿Gastos deducibles?"
        assert state2["pending_slots"] == ["location"]


# ========== Follow-Up Detection Tests ==========

class TestFollowUpDetection:
    """Test follow-up query detection logic"""

    def test_slot_fill_detection(self):
        """Short reply with pending slots = slot_fill"""
        state = {
            "topic_lock": "Fiscal",
            "base_question": "¿Deducciones IRPF?",
            "pending_slots": ["location"],
            "slot_values": {},
        }

        is_fu, reason = is_followup("Valencia", state)

        assert is_fu is True
        assert reason == "slot_fill"

    def test_referential_detection(self):
        """Referential markers = referential"""
        state = {
            "topic_lock": "Fiscal",
            "base_question": "¿IVA autónomos?",
            "pending_slots": [],
            "slot_values": {},
        }

        is_fu, reason = is_followup("en relación a lo anterior", state)

        assert is_fu is True
        assert reason == "referential"

    def test_short_ambiguous_detection(self):
        """Very short query with base_question = short_ambiguous"""
        state = {
            "topic_lock": "Fiscal",
            "base_question": "¿Retenciones IRPF músicos?",
            "pending_slots": [],
            "slot_values": {},
        }

        is_fu, reason = is_followup("¿Y en Madrid?", state)

        assert is_fu is True
        assert reason == "short_ambiguous"

    def test_new_question_detection(self):
        """Long query = new_question"""
        state = {
            "topic_lock": "Fiscal",
            "base_question": "Previous question",
            "pending_slots": [],
            "slot_values": {},
        }

        is_fu, reason = is_followup("¿Cuáles son las obligaciones de IVA para servicios digitales?", state)

        assert is_fu is False
        assert reason == "new_question"


# ========== Slot Fill Logic Tests ==========

class TestSlotFillLogic:
    """Test slot fill inference and extraction"""

    def test_location_slot_inference(self):
        """Location slot should be inferred"""
        slot, value = infer_slot_fill("Madrid", ["location"])

        assert slot == "location"
        assert value == "Madrid"

    def test_period_slot_inference(self):
        """Year detection = period slot"""
        slot, value = infer_slot_fill("2024", ["period", "location"])

        assert slot == "period"
        assert value == "2024"

    def test_activity_slot_inference(self):
        """Activity keywords detected"""
        slot, value = infer_slot_fill("música", ["activity", "location"])

        assert slot == "activity"
        assert value == "música"

    def test_entity_type_inference(self):
        """Entity type keywords detected"""
        slot, value = infer_slot_fill("autónomo", ["entity_type"])

        assert slot == "entity_type"
        assert value == "autónomo"

    def test_no_pending_slots(self):
        """No pending slots = None"""
        slot, value = infer_slot_fill("Valencia", [])

        assert slot is None
        assert value is None


# ========== Query Merging Tests ==========

class TestQueryMerging:
    """Test query merging logic"""

    def test_build_merged_query_simple(self):
        """Simple merge without slot values"""
        state = {"slot_values": {}}
        merged = build_merged_query("¿Gastos deducibles?", "en relación a lo anterior", state)

        assert "¿Gastos deducibles?" in merged
        assert "en relación a lo anterior" in merged

    def test_build_merged_query_with_slots(self):
        """Merge includes slot values"""
        state = {"slot_values": {"location": "Valencia", "activity": "música"}}
        merged = build_merged_query("¿Deducciones IRPF?", "¿Y Madrid?", state)

        assert "¿Deducciones IRPF?" in merged
        assert "Valencia" in merged
        assert "música" in merged
        assert "¿Y Madrid?" in merged


# ========== Context Block Tests ==========

class TestContextBlock:
    """Test context block generation"""

    def test_context_block_empty_state(self):
        """Empty state = no context"""
        state = {"topic_lock": None, "slot_values": {}, "last_answer_brief": None}
        context = build_context_block(state)

        assert context == ""

    def test_context_block_with_topic_lock(self):
        """Topic lock included"""
        state = {"topic_lock": "Fiscal", "slot_values": {}, "last_answer_brief": None}
        context = build_context_block(state)

        assert "Fiscal" in context

    def test_context_block_with_slot_values(self):
        """Slot values included"""
        state = {"topic_lock": None, "slot_values": {"location": "Madrid"}, "last_answer_brief": None}
        context = build_context_block(state)

        assert "Madrid" in context

    def test_context_block_complete(self):
        """Full context"""
        state = {
            "topic_lock": "Fiscal",
            "slot_values": {"location": "Valencia"},
            "last_answer_brief": "Las deducciones fiscales para autónomos...",
        }
        context = build_context_block(state)

        assert "Fiscal" in context
        assert "Valencia" in context
        assert "deducciones fiscales" in context.lower()


# ========== Topic Lock Fallback Tests ==========

class TestTopicLockFallback:
    """Test effective area computation with fallback"""

    def test_high_confidence_classifier(self):
        """High confidence = use classifier"""
        state = {"topic_lock": None, "pending_slots": []}
        area, fallback, reason = compute_effective_area("Fiscal", 0.85, state)

        assert area == "Fiscal"
        assert fallback is False
        assert reason == "high_confidence_classifier"

    def test_low_confidence_fallback_to_lock(self):
        """Low confidence + topic lock = use lock (CRITICAL)"""
        state = {"topic_lock": "Fiscal", "pending_slots": []}
        area, fallback, reason = compute_effective_area(None, 0.0, state)

        assert area == "Fiscal"
        assert fallback is True
        assert reason == "low_confidence_fallback_to_lock"

    def test_high_confidence_topic_change(self):
        """High confidence different area = break lock"""
        state = {"topic_lock": "Fiscal", "pending_slots": []}
        area, fallback, reason = compute_effective_area("PI", 0.85, state)

        assert area == "PI"
        assert fallback is False
        assert reason == "high_confidence_topic_change"

    def test_slot_fill_mode_prevents_topic_change(self):
        """High confidence + pending slots = keep lock (don't break during slot fill)"""
        state = {"topic_lock": "Laboral", "pending_slots": ["activity"]}
        area, fallback, reason = compute_effective_area("PI", 0.85, state)

        assert area == "Laboral"  # Lock preserved
        assert fallback is True
        assert reason == "slot_fill_mode_prevents_topic_change"

    def test_medium_confidence_keep_lock(self):
        """Medium confidence different area = keep lock"""
        state = {"topic_lock": "Fiscal", "pending_slots": []}
        area, fallback, reason = compute_effective_area("Laboral", 0.60, state)

        assert area == "Fiscal"
        assert fallback is True
        assert reason == "medium_confidence_keep_lock"

    def test_no_classifier_no_lock(self):
        """No classifier + no lock = None"""
        state = {"topic_lock": None, "pending_slots": []}
        area, fallback, reason = compute_effective_area(None, 0.0, state)

        assert area is None
        assert fallback is False
        assert reason == "no_area_detected_no_lock"


# ========== State Update Tests ==========

class TestStateUpdates:
    """Test state update helpers"""

    def test_reset_state_for_topic_change(self):
        """Topic change resets context but keeps turn_count"""
        state = {
            "topic_lock": "Fiscal",
            "base_question": "Old question",
            "pending_slots": ["location"],
            "slot_values": {"location": "Madrid"},
            "turn_count": 3,
            "created_at": "2025-01-01",
        }

        reset_state_for_topic_change(state)

        assert state["base_question"] is None
        assert state["pending_slots"] == []
        assert state["slot_values"] == {}
        assert state["turn_count"] == 3  # Preserved
        assert state["created_at"] == "2025-01-01"  # Preserved

    def test_update_state_after_answer(self):
        """State updated after successful answer"""
        state = {
            "base_question": None,
            "topic_lock": None,
            "turn_count": 0,
            "last_answer_brief": None,
        }

        query = "¿Deducciones IRPF autónomos?"
        answer = "Las deducciones fiscales para autónomos permiten..."
        effective_area = "Fiscal"

        update_state_after_answer(state, query, answer, effective_area)

        assert state["base_question"] == query
        assert state["last_actionable_user_question"] == query
        assert state["topic_lock"] == "Fiscal"
        assert state["turn_count"] == 1
        assert "deducciones fiscales" in state["last_answer_brief"].lower()


# ========== Integration Scenarios ==========

class TestIntegrationScenarios:
    """Complete multi-turn scenarios"""

    @pytest.mark.django_db
    def test_location_slot_complete_flow(self):
        """
        Turn 1: Base question with pending location
        Turn 2: Provide location
        Expected: Slot filled, topic lock maintained
        """
        session = ChatSession.objects.create()

        # Turn 1
        state = load_state(session)
        state["base_question"] = "¿Deducciones IRPF autónomos?"
        state["topic_lock"] = "Fiscal"
        state["pending_slots"] = ["location"]
        save_state(session, state)

        # Turn 2
        session.refresh_from_db()
        state = load_state(session)

        is_fu, reason = is_followup("Valencia", state)
        assert is_fu is True
        assert reason == "slot_fill"

        slot, value = infer_slot_fill("Valencia", state["pending_slots"])
        assert slot == "location"
        assert value == "Valencia"

        # Update state
        state["slot_values"][slot] = value
        state["pending_slots"].remove(slot)
        save_state(session, state)

        # Verify persistence
        session.refresh_from_db()
        final_state = load_state(session)
        assert final_state["slot_values"]["location"] == "Valencia"
        assert final_state["pending_slots"] == []
        assert final_state["topic_lock"] == "Fiscal"

    @pytest.mark.django_db
    def test_topic_lock_prevents_drift(self):
        """
        Turn 1: Fiscal query establishes lock
        Turn 2: Ambiguous query with low confidence
        Expected: Fallback to Fiscal (no drift to IVA/etc)
        """
        session = ChatSession.objects.create()

        # Turn 1
        state = load_state(session)
        state["topic_lock"] = "Fiscal"
        state["base_question"] = "¿Gastos deducibles IRPF músico?"
        save_state(session, state)

        # Turn 2: Classifier returns null/low confidence
        session.refresh_from_db()
        state = load_state(session)

        area, fallback, reason = compute_effective_area(None, 0.0, state)

        assert area == "Fiscal"  # ✅ Lock prevents drift
        assert fallback is True
        assert reason == "low_confidence_fallback_to_lock"

    @pytest.mark.django_db
    def test_explicit_topic_change_breaks_lock(self):
        """
        Turn 1: Fiscal context
        Turn 2: High-confidence PI question
        Expected: Lock broken, state reset
        """
        session = ChatSession.objects.create()

        # Turn 1
        state = load_state(session)
        state["topic_lock"] = "Fiscal"
        state["base_question"] = "¿IVA autónomos?"
        save_state(session, state)

        # Turn 2: High confidence different area
        session.refresh_from_db()
        state = load_state(session)

        area, fallback, reason = compute_effective_area("PI", 0.85, state)

        assert area == "PI"  # ✅ Lock broken
        assert fallback is False
        assert reason == "high_confidence_topic_change"

        # Reset state
        reset_state_for_topic_change(state)
        assert state["base_question"] is None
        assert state["pending_slots"] == []
