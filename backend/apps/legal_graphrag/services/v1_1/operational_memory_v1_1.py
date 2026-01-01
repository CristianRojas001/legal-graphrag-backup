"""
Operational Memory State Machine for V1.1

Deterministic session state management:
- Topic lock persistence
- Slot fill detection
- Follow-up query merging
- Context block generation
"""

import re
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List


# ========== Constants ==========

CONF_THRESHOLD_HIGH = 0.80  # For breaking topic lock (explicit topic change)
CONF_THRESHOLD_LOW = 0.55   # For normal classification
MAX_SLOT_FILL_TOKENS = 10   # Max tokens for slot-fill reply
MAX_SHORT_AMBIGUOUS_TOKENS = 6  # Max tokens for short ambiguous reply

REFERENTIAL_MARKERS = [
    r"\blo\s+anterior\b",
    r"\blo\s+mismo\b",
    r"\beso\b",
    r"\ben\s+relaci[oó]n\b",
    r"\bal\s+respecto\b",
    r"\bmi\s+caso\b",
    r"\bsobre\s+esto\b",
    r"\bla\s+pregunta\s+anterior\b",
    r"\blo\s+que\s+dijiste\b",
]


# ========== State Management ==========

def default_session_state() -> Dict[str, Any]:
    """
    Default session state structure.

    Returns:
        dict: Initial state with all required fields
    """
    return {
        "topic_lock": None,
        "base_question": None,
        "last_actionable_user_question": None,
        "pending_slots": [],
        "slot_values": {},
        "last_answer_brief": None,
        "turn_count": 0,
        "created_at": datetime.now().isoformat(),
    }


def load_state(session) -> Dict[str, Any]:
    """
    Load session state from database, merging with defaults.

    Args:
        session: ChatSession model instance

    Returns:
        dict: Complete state with all required fields
    """
    state = default_session_state()
    if session.session_state:
        state.update(session.session_state)
    return state


def save_state(session, state: Dict[str, Any]) -> None:
    """
    Save session state to database.

    Args:
        session: ChatSession model instance
        state: State dict to save
    """
    session.session_state = state
    session.save(update_fields=['session_state', 'updated_at'])


def compute_state_diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute what changed between two states.

    Args:
        before: Previous state
        after: New state

    Returns:
        dict: Diff showing before/after for changed fields
    """
    diff = {}
    for key in after:
        if before.get(key) != after[key]:
            diff[key] = {"before": before.get(key), "after": after[key]}
    return diff


# ========== Helper Functions ==========

def count_tokens(text: str) -> int:
    """
    Simple token count (split on whitespace + punctuation).

    Args:
        text: Input text

    Returns:
        int: Approximate token count
    """
    return len(re.findall(r'\w+', text))


def has_referential_marker(query: str) -> bool:
    """
    Check if query contains referential markers.

    Args:
        query: User query

    Returns:
        bool: True if referential markers detected
    """
    query_lower = query.lower()
    return any(re.search(pattern, query_lower, re.IGNORECASE) for pattern in REFERENTIAL_MARKERS)


def strip_html_comments(text: str) -> str:
    """
    Remove HTML comments from text.

    Args:
        text: Input text

    Returns:
        str: Text with HTML comments removed
    """
    return re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL).strip()


# ========== Follow-Up Detection ==========

def is_followup(query: str, state: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Determine if query is a follow-up to previous conversation.

    Args:
        query: Current user query
        state: Current session state

    Returns:
        tuple: (is_followup: bool, reason: str)
            Reasons: "slot_fill", "referential", "short_ambiguous", "new_question"
    """
    tokens = count_tokens(query)
    has_pending = len(state.get("pending_slots", [])) > 0
    has_base = state.get("base_question") is not None

    # Slot fill: short reply with pending slots
    if has_pending and tokens <= MAX_SLOT_FILL_TOKENS:
        return True, "slot_fill"

    # Referential: contains markers
    if has_referential_marker(query):
        return True, "referential"

    # Short ambiguous: very short with existing context
    if has_base and tokens <= MAX_SHORT_AMBIGUOUS_TOKENS:
        return True, "short_ambiguous"

    # Otherwise: new question
    return False, "new_question"


# ========== Slot Fill Logic ==========

def infer_slot_fill(query: str, pending_slots: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Infer which slot a reply fills and extract value.

    Args:
        query: User reply
        pending_slots: List of pending slot names

    Returns:
        tuple: (slot_name: str|None, slot_value: str|None)
    """
    if not pending_slots:
        return None, None

    normalized = query.lower().strip()

    # Period detection (year)
    if re.search(r"\b(19|20)\d{2}\b", normalized):
        if "period" in pending_slots:
            return "period", query.strip()

    # Entity type detection
    entity_markers = ["autonomo", "autónomo", "sl", "s.l", "sociedad", "asociacion", "asociación"]
    if any(marker in normalized for marker in entity_markers):
        if "entity_type" in pending_slots:
            return "entity_type", query.strip()

    # Activity detection
    activity_markers = ["música", "pintura", "danza", "teatro", "escritor", "fotograf"]
    if any(marker in normalized for marker in activity_markers):
        if "activity" in pending_slots:
            return "activity", query.strip()

    # Location fallback (if pending and not matched above)
    if "location" in pending_slots:
        return "location", query.strip()

    # Default: fill first pending slot
    return pending_slots[0], query.strip()


# ========== Query Merging ==========

def build_merged_query(base_question: str, user_reply: str, state: Dict[str, Any]) -> str:
    """
    Build merged query from base question + user reply + slot values.

    Args:
        base_question: Original question
        user_reply: Current user reply
        state: Session state (for slot_values)

    Returns:
        str: Merged query
    """
    parts = [base_question]

    # Add slot values if any
    if state.get("slot_values"):
        slot_str = ", ".join(f"{k}: {v}" for k, v in state["slot_values"].items())
        parts.append(f"[Contexto: {slot_str}]")

    # Add current reply
    parts.append(user_reply)

    return " ".join(parts)


# ========== Context Block ==========

def build_context_block(state: Dict[str, Any]) -> str:
    """
    Build concise context block (<120 tokens) for RAG prompt.

    Only includes context when meaningful (non-empty slot_values OR topic_lock).

    Args:
        state: Session state

    Returns:
        str: Context block (empty if no meaningful context)
    """
    parts = []

    # Topic lock
    if state.get("topic_lock"):
        parts.append(f"Área: {state['topic_lock']}")

    # Slot values
    if state.get("slot_values"):
        slot_str = ", ".join(f"{k}={v}" for k, v in state["slot_values"].items())
        parts.append(f"Contexto del usuario: {slot_str}")

    # Last answer brief (if available)
    if state.get("last_answer_brief"):
        brief = state["last_answer_brief"][:80]
        parts.append(f"Tema previo: {brief}...")

    return "\n".join(parts) if parts else ""


# ========== Topic Lock Logic ==========

def compute_effective_area(
    area_detected: Optional[str],
    confidence: float,
    state: Dict[str, Any],
) -> Tuple[Optional[str], bool, str]:
    """
    Compute effective area with topic-lock fallback.

    Rules:
    1. High confidence + different area: break lock (explicit topic change)
    2. Low confidence + pending slots: keep lock (slot-fill mode)
    3. Medium confidence + same area: use classifier
    4. Low confidence + topic lock: use lock (fallback)
    5. No classifier + no lock: None

    Args:
        area_detected: Classifier output
        confidence: Classifier confidence
        state: Session state

    Returns:
        tuple: (effective_area: str|None, fallback_used: bool, reason: str)
    """
    topic_lock = state.get("topic_lock")
    has_pending = len(state.get("pending_slots", [])) > 0

    # High confidence classifier
    if area_detected and confidence >= CONF_THRESHOLD_HIGH:
        if topic_lock and area_detected != topic_lock:
            # Explicit topic change (but not during slot fill)
            if has_pending:
                return topic_lock, True, "slot_fill_mode_prevents_topic_change"
            else:
                return area_detected, False, "high_confidence_topic_change"
        else:
            return area_detected, False, "high_confidence_classifier"

    # Medium confidence classifier
    if area_detected and confidence >= CONF_THRESHOLD_LOW:
        if topic_lock and area_detected != topic_lock:
            # Ambiguous, keep lock
            return topic_lock, True, "medium_confidence_keep_lock"
        else:
            return area_detected, False, "medium_confidence_classifier"

    # Low/no confidence: fallback to lock if exists
    if topic_lock:
        return topic_lock, True, "low_confidence_fallback_to_lock"

    # No classifier, no lock
    return None, False, "no_area_detected_no_lock"


# ========== State Update Helpers ==========

def reset_state_for_topic_change(state: Dict[str, Any]) -> None:
    """
    Reset state when explicit topic change detected.

    Clears: base_question, pending_slots, slot_values
    Keeps: turn_count, created_at

    Args:
        state: State dict (mutated in place)
    """
    state["base_question"] = None
    state["last_actionable_user_question"] = None
    state["pending_slots"] = []
    state["slot_values"] = {}
    state["last_answer_brief"] = None
    # topic_lock will be updated by caller


def update_state_after_answer(
    state: Dict[str, Any],
    query: str,
    answer: str,
    effective_area: Optional[str],
) -> None:
    """
    Update state after successful answer generation.

    Args:
        state: State dict (mutated in place)
        query: User query
        answer: Assistant answer
        effective_area: Area used for this query
    """
    state["base_question"] = query
    state["last_actionable_user_question"] = query
    state["turn_count"] += 1

    # Update topic lock if area was determined
    if effective_area:
        state["topic_lock"] = effective_area

    # Store answer brief (first 200 chars, no HTML comments)
    clean_answer = strip_html_comments(answer)
    state["last_answer_brief"] = clean_answer[:200]
