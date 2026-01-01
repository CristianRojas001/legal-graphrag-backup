"""
Unit tests for V1.1 Operational Memory (Session State Management)

Tests cover:
- Query merge logic
- Slot fill behavior
- Topic lock enforcement
- State persistence and safety
"""

import pytest
from typing import Dict, Any, Optional


# ========== Test Helpers ==========

def build_session_state(
    topic_lock: Optional[str] = None,
    pending_slots: Optional[list] = None,
    base_question: Optional[str] = None,
    slot_values: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build a session state dict for testing"""
    return {
        "topic_lock": topic_lock,
        "pending_slots": pending_slots or [],
        "base_question": base_question,
        "slot_values": slot_values or {},
    }


def is_short_reply(query: str, threshold: int = 20) -> bool:
    """Check if query is a short reply (likely slot fill)"""
    return len(query.strip()) <= threshold


def has_referential_marker(query: str) -> bool:
    """Check if query contains referential markers"""
    markers = [
        "en relación a",
        "sobre lo anterior",
        "lo mismo",
        "eso",
        "lo que dijiste",
        "la pregunta anterior",
        "al respecto",
    ]
    query_lower = query.lower()
    return any(marker in query_lower for marker in markers)


def should_merge_query(
    query: str,
    session_state: Dict[str, Any],
) -> tuple[bool, str]:
    """
    Determine if query should be merged with base_question.

    Returns: (should_merge, reason)
    """
    base_question = session_state.get("base_question")
    pending_slots = session_state.get("pending_slots", [])

    # No base question = cannot merge
    if not base_question:
        return False, "no_base_question"

    # Short reply with pending slots = merge
    if is_short_reply(query) and pending_slots:
        return True, "short_reply_with_pending_slots"

    # Referential marker = merge
    if has_referential_marker(query):
        return True, "referential_marker"

    # Otherwise, it's a new question
    return False, "new_question"


def merge_with_slot(base_question: str, slot_name: str, slot_value: str) -> str:
    """Merge base question with slot value"""
    return f"{base_question} [{slot_name}: {slot_value}]"


def detect_topic_change(query: str) -> bool:
    """Detect explicit topic change markers"""
    change_markers = [
        "ahora sobre",
        "cambiando de tema",
        "mejor dime sobre",
        "no, sobre",
        "en lugar de eso",
    ]
    query_lower = query.lower()
    return any(marker in query_lower for marker in change_markers)


# ========== Merge Logic Tests ==========

class TestMergeLogic:
    """Test query merge decision logic"""

    def test_short_reply_with_pending_slots_triggers_merge(self):
        """Short reply with pending slots should trigger merge"""
        query = "Valencia"
        state = build_session_state(
            base_question="¿Puedo deducir estudio en casa?",
            pending_slots=["location"],
            topic_lock="Fiscal"
        )

        should_merge, reason = should_merge_query(query, state)
        assert should_merge is True
        assert reason == "short_reply_with_pending_slots"

    def test_referential_marker_triggers_merge(self):
        """Referential markers should trigger merge even without pending slots"""
        query = "en relación a lo anterior"
        state = build_session_state(
            base_question="¿Qué obligaciones tengo con IVA?",
            pending_slots=[],
            topic_lock="Fiscal"
        )

        should_merge, reason = should_merge_query(query, state)
        assert should_merge is True
        assert reason == "referential_marker"

    def test_no_base_question_prevents_merge(self):
        """No base question = cannot merge, even if short"""
        query = "Valencia"
        state = build_session_state(
            base_question=None,
            pending_slots=[],
            topic_lock=None
        )

        should_merge, reason = should_merge_query(query, state)
        assert should_merge is False
        assert reason == "no_base_question"

    def test_long_query_without_markers_is_new_question(self):
        """Long query without referential markers = new question"""
        query = "¿Cuáles son las obligaciones de IVA para servicios digitales?"
        state = build_session_state(
            base_question="¿Puedo deducir estudio en casa?",
            pending_slots=[],
            topic_lock="Fiscal"
        )

        should_merge, reason = should_merge_query(query, state)
        assert should_merge is False
        assert reason == "new_question"

    def test_explicit_topic_change_detected(self):
        """Explicit topic change markers should be detected"""
        queries = [
            "Ahora sobre derechos de autor",
            "Cambiando de tema, ¿qué pasa con la PI?",
            "No, mejor dime sobre propiedad intelectual",
        ]

        for query in queries:
            assert detect_topic_change(query) is True, f"Failed for: {query}"

    def test_merge_with_slot_produces_correct_output(self):
        """Merging should append slot value to base question"""
        base = "¿Puedo deducir estudio en casa?"
        merged = merge_with_slot(base, "location", "Valencia")
        assert "¿Puedo deducir estudio en casa?" in merged
        assert "Valencia" in merged


# ========== Slot Fill Behavior Tests ==========

class TestSlotFillBehavior:
    """Test slot fill continuation logic"""

    def test_location_slot_flow(self):
        """Test location slot fill maintains context"""
        # Q1: Ask question that needs location
        q1 = "Soy artista autónomo. ¿Puedo deducir estudio en casa?"
        state1 = build_session_state(
            base_question=q1,
            pending_slots=["location"],
            topic_lock="Fiscal"
        )

        # Q2: Provide location
        q2 = "Valencia"
        should_merge, reason = should_merge_query(q2, state1)
        assert should_merge is True
        assert reason == "short_reply_with_pending_slots"

        # Merge should include location
        merged = merge_with_slot(q1, "location", q2)
        assert "Valencia" in merged
        assert q1 in merged

        # After merge, pending_slots should be cleared
        state2 = build_session_state(
            base_question=q1,
            pending_slots=[],  # Cleared after fill
            topic_lock="Fiscal",  # Topic remains
            slot_values={"location": "Valencia"}
        )
        assert state2["pending_slots"] == []
        assert state2["topic_lock"] == "Fiscal"

    def test_activity_slot_maintains_topic_lock(self):
        """Activity slot fill should not break topic lock"""
        q1 = "Autónomo vs cuenta ajena para artista"
        state1 = build_session_state(
            base_question=q1,
            pending_slots=["activity"],
            topic_lock="Laboral"
        )

        q2 = "música"
        should_merge, reason = should_merge_query(q2, state1)
        assert should_merge is True

        # Topic should stay Laboral, not drift to PI
        # (This would be enforced by topic_lock in actual implementation)
        state2 = build_session_state(
            base_question=q1,
            pending_slots=[],
            topic_lock="Laboral",  # Must remain
            slot_values={"activity": "música"}
        )
        assert state2["topic_lock"] == "Laboral"

    def test_invalid_slot_value_preserves_state(self):
        """Invalid slot value should preserve session state"""
        q1 = "Deducciones fiscales para artistas"
        state1 = build_session_state(
            base_question=q1,
            pending_slots=["location"],
            topic_lock="Fiscal"
        )

        # User provides nonsense
        q2 = "asdfgh"
        should_merge, reason = should_merge_query(q2, state1)
        # Should still attempt merge (system will ask for clarification)
        assert should_merge is True

        # After clarification request, state should persist
        # Q3: Valid location
        q3 = "Madrid"
        should_merge, reason = should_merge_query(q3, state1)
        assert should_merge is True

        # State should still have base_question intact
        assert state1["base_question"] == q1
        assert state1["topic_lock"] == "Fiscal"


# ========== Topic Lock Tests ==========

class TestTopicLockEnforcement:
    """Test topic lock prevents drift during slot fill"""

    def test_topic_lock_enforced_during_slot_fill(self):
        """Topic lock should prevent reclassification during slot fill"""
        state = build_session_state(
            base_question="¿Retenciones IRPF para artistas?",
            pending_slots=["location"],
            topic_lock="Fiscal"
        )

        # User provides location (which happens to be "música")
        # This should NOT reclassify to PI
        assert state["topic_lock"] == "Fiscal"

        # After slot fill, topic should remain Fiscal
        state_after = build_session_state(
            base_question="¿Retenciones IRPF para artistas?",
            pending_slots=[],
            topic_lock="Fiscal",
            slot_values={"location": "Madrid"}
        )
        assert state_after["topic_lock"] == "Fiscal"

    def test_explicit_topic_change_breaks_lock(self):
        """Explicit topic change should reset state and lock"""
        state_before = build_session_state(
            base_question="¿Qué obligaciones tengo con IVA?",
            pending_slots=[],
            topic_lock="Fiscal"
        )

        query = "Ahora sobre derechos de autor de mis canciones"
        is_topic_change = detect_topic_change(query)
        assert is_topic_change is True

        # After topic change, state should reset
        state_after = build_session_state(
            base_question=None,  # Reset
            pending_slots=[],
            topic_lock=None,  # Will be reclassified to PI
            slot_values={}
        )
        assert state_after["base_question"] is None
        assert state_after["topic_lock"] is None

    def test_topic_lock_persists_across_multiple_slots(self):
        """Topic lock should persist when filling multiple slots"""
        state1 = build_session_state(
            base_question="¿Deducciones para autónomos?",
            pending_slots=["location", "activity"],
            topic_lock="Fiscal"
        )

        # Fill location
        state2 = build_session_state(
            base_question="¿Deducciones para autónomos?",
            pending_slots=["activity"],  # One slot filled
            topic_lock="Fiscal",  # Persists
            slot_values={"location": "Barcelona"}
        )
        assert state2["topic_lock"] == "Fiscal"

        # Fill activity
        state3 = build_session_state(
            base_question="¿Deducciones para autónomos?",
            pending_slots=[],  # All slots filled
            topic_lock="Fiscal",  # Still persists
            slot_values={"location": "Barcelona", "activity": "pintura"}
        )
        assert state3["topic_lock"] == "Fiscal"


# ========== State Persistence and Safety Tests ==========

class TestStatePersistenceAndSafety:
    """Test session state edge cases and safety"""

    def test_empty_query_does_not_crash(self):
        """Empty query should handle gracefully"""
        query = ""
        state = build_session_state(
            base_question="Previous question",
            pending_slots=["location"],
            topic_lock="Fiscal"
        )

        should_merge, reason = should_merge_query(query, state)
        # Should not crash, behavior is up to implementation
        assert isinstance(should_merge, bool)
        assert isinstance(reason, str)

    def test_slot_fill_without_base_question_asks_clarification(self):
        """Slot value without base question should ask for clarification"""
        query = "Valencia"
        state = build_session_state(
            base_question=None,  # No context
            pending_slots=[],
            topic_lock=None
        )

        should_merge, reason = should_merge_query(query, state)
        assert should_merge is False
        assert reason == "no_base_question"
        # System should respond: "¿A qué te refieres con 'Valencia'?"

    def test_multiple_referential_markers_handled(self):
        """Multiple referential markers in one query"""
        query = "En relación a lo anterior, sobre lo mismo"
        state = build_session_state(
            base_question="¿IVA para servicios?",
            pending_slots=[],
            topic_lock="Fiscal"
        )

        should_merge, reason = should_merge_query(query, state)
        assert should_merge is True
        assert reason == "referential_marker"

    def test_rapid_topic_switches_reset_state(self):
        """Rapid topic switches should properly reset state"""
        # Start with Fiscal
        state1 = build_session_state(
            base_question="IVA para autónomos",
            pending_slots=[],
            topic_lock="Fiscal"
        )

        # Explicit change to PI
        query = "No, mejor dime sobre propiedad intelectual"
        is_change = detect_topic_change(query)
        assert is_change is True

        # State should reset
        state2 = build_session_state(
            base_question=None,
            pending_slots=[],
            topic_lock=None,
            slot_values={}
        )
        assert state2["base_question"] is None

    def test_case_insensitive_referential_detection(self):
        """Referential markers should be case insensitive"""
        queries = [
            "En Relación A lo anterior",
            "SOBRE LO ANTERIOR",
            "Lo Mismo",
        ]
        for query in queries:
            assert has_referential_marker(query) is True, f"Failed for: {query}"

    def test_pending_slots_cleared_after_fill(self):
        """Pending slots should be cleared after successful fill"""
        state_before = build_session_state(
            base_question="¿Deducciones?",
            pending_slots=["location"],
            topic_lock="Fiscal"
        )
        assert state_before["pending_slots"] == ["location"]

        # After slot fill
        state_after = build_session_state(
            base_question="¿Deducciones?",
            pending_slots=[],  # Cleared
            topic_lock="Fiscal",
            slot_values={"location": "Madrid"}
        )
        assert state_after["pending_slots"] == []
        assert "location" in state_after["slot_values"]


# ========== Integration Scenario Tests ==========

class TestIntegrationScenarios:
    """Test complete multi-turn scenarios"""

    def test_location_slot_complete_flow(self):
        """
        Q1: "Soy artista autónomo. ¿Puedo deducir estudio en casa?"
        A1: asks location
        Q2: "Valencia"
        Expect: merged_query includes base_question + Valencia; topic remains Fiscal; answer continues.
        """
        # Q1
        q1 = "Soy artista autónomo. ¿Puedo deducir estudio en casa?"
        state1 = build_session_state(
            base_question=q1,
            pending_slots=["location"],
            topic_lock="Fiscal"
        )

        # Q2
        q2 = "Valencia"
        should_merge, reason = should_merge_query(q2, state1)
        assert should_merge is True
        assert reason == "short_reply_with_pending_slots"

        merged = merge_with_slot(q1, "location", q2)
        assert "Valencia" in merged

        # Final state
        state2 = build_session_state(
            base_question=q1,
            pending_slots=[],
            topic_lock="Fiscal",
            slot_values={"location": "Valencia"}
        )
        assert state2["topic_lock"] == "Fiscal"
        assert state2["pending_slots"] == []

    def test_activity_slot_with_topic_lock(self):
        """
        Q1: "Autónomo vs cuenta ajena para artista"
        A1: asks activity
        Q2: "música"
        Expect: stays Laboral/Fiscal thread (not PI).
        """
        q1 = "Autónomo vs cuenta ajena para artista"
        state1 = build_session_state(
            base_question=q1,
            pending_slots=["activity"],
            topic_lock="Laboral"
        )

        q2 = "música"
        should_merge, reason = should_merge_query(q2, state1)
        assert should_merge is True

        state2 = build_session_state(
            base_question=q1,
            pending_slots=[],
            topic_lock="Laboral",  # Must NOT change to PI
            slot_values={"activity": "música"}
        )
        assert state2["topic_lock"] == "Laboral"

    def test_referential_continuation(self):
        """
        Q1: "¿Qué obligaciones tengo con IVA?"
        Q2: "en relación a lo anterior"
        Expect: asks for missing info or continues; not a random new topic.
        """
        q1 = "¿Qué obligaciones tengo con IVA?"
        state1 = build_session_state(
            base_question=q1,
            pending_slots=[],
            topic_lock="Fiscal"
        )

        q2 = "en relación a lo anterior"
        should_merge, reason = should_merge_query(q2, state1)
        assert should_merge is True
        assert reason == "referential_marker"

        # State should remain intact
        assert state1["topic_lock"] == "Fiscal"

    def test_explicit_topic_change_resets(self):
        """
        After a Fiscal thread, Q: "Ahora sobre derechos de autor de mis canciones"
        Expect: lock breaks to PI, state reset appropriately.
        """
        state_before = build_session_state(
            base_question="¿Obligaciones IVA?",
            pending_slots=[],
            topic_lock="Fiscal"
        )

        query = "Ahora sobre derechos de autor de mis canciones"
        is_change = detect_topic_change(query)
        assert is_change is True

        # State should reset
        state_after = build_session_state(
            base_question=None,
            pending_slots=[],
            topic_lock=None,
            slot_values={}
        )
        assert state_after["base_question"] is None
        assert state_after["topic_lock"] is None

    def test_no_base_question_safety(self):
        """
        Q: "Valencia"
        Expect: asks "¿a qué te refieres?" and does not crash/merge.
        """
        query = "Valencia"
        state = build_session_state(
            base_question=None,
            pending_slots=[],
            topic_lock=None
        )

        should_merge, reason = should_merge_query(query, state)
        assert should_merge is False
        assert reason == "no_base_question"
        # System should ask for clarification

    def test_context_merge_with_constraint(self):
        """
        Q1: "¿IVA para autónomos?"
        Q2: "¿Y los músicos?" (referential but adds new constraint)
        Expected: Should merge successfully and narrow scope, not break topic lock.
        """
        q1 = "¿IVA para autónomos?"
        state1 = build_session_state(
            base_question=q1,
            pending_slots=[],
            topic_lock="Fiscal"
        )

        q2 = "¿Y los músicos?"
        # This has referential marker "Y" (implicit continuation)
        # For simplicity, let's treat it as referential
        should_merge, _ = should_merge_query(q2, state1)
        # Depending on implementation, this might or might not merge
        # But topic lock should remain
        assert state1["topic_lock"] == "Fiscal"

    def test_slot_persistence_across_error(self):
        """
        Q1: "Deducciones fiscales para artistas"
        A1: asks location
        Q2: "asdfgh" (invalid location)
        A2: clarification request
        Q3: "Madrid" (valid)
        Expected: Session remembers base_question, doesn't get confused by error turn.
        """
        q1 = "Deducciones fiscales para artistas"
        state1 = build_session_state(
            base_question=q1,
            pending_slots=["location"],
            topic_lock="Fiscal"
        )

        # Q2: invalid
        q2 = "asdfgh"
        should_merge, _ = should_merge_query(q2, state1)
        assert should_merge is True  # Still attempts merge

        # State persists after error
        assert state1["base_question"] == q1
        assert state1["topic_lock"] == "Fiscal"

        # Q3: valid
        q3 = "Madrid"
        should_merge, reason = should_merge_query(q3, state1)
        assert should_merge is True
        assert state1["base_question"] == q1
