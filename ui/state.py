"""Session state: defaults, resets, and callbacks that edit the extraction."""

import streamlit as st

from ui.constants import SYMPTOM_LABELS


def _defaults():
    return {
        "transcript": "",
        "transcript_box": "",
        "extraction": None,
        "result": None,
        "assessment_saved": False,
        "saved_assessment_id": None,
        "last_context_key": None,
        "asked_keys": [],
        "ext_version": 0,
        "sms_sent": False,
        "sms_sent_at": None,
    }


def init_state() -> None:
    for key, value in _defaults().items():
        st.session_state.setdefault(key, value)


def clear_result() -> None:
    """Drop the assessment so it must be re-run after any input change."""
    st.session_state["result"] = None
    st.session_state["assessment_saved"] = False
    st.session_state["saved_assessment_id"] = None
    st.session_state["sms_sent"] = False
    st.session_state["sms_sent_at"] = None


def reset_analysis() -> None:
    """Start over from a new transcript."""
    clear_result()
    st.session_state["extraction"] = None
    st.session_state["asked_keys"] = []
    st.session_state["ext_version"] += 1  # fresh widget keys for the chips


def _sync_symptom_list(ext: dict) -> None:
    free_text = [s for s in ext.get("symptoms") or [] if s not in SYMPTOM_LABELS]
    ext["symptoms"] = [f for f in SYMPTOM_LABELS if ext.get(f) is True] + free_text


def on_chips_change(widget_key: str) -> None:
    """Chip toggled: selected = present, deselected (was present) = denied."""
    ext = st.session_state["extraction"]
    selected = set(st.session_state.get(widget_key) or [])
    for field in SYMPTOM_LABELS:
        if field in selected:
            ext[field] = True
        elif ext.get(field) is True:
            ext[field] = False
    ext["user_confirmed"] = True
    _sync_symptom_list(ext)
    clear_result()


def answer_follow_up(key: str, value) -> None:
    """Record a হ্যাঁ/না/জানি না answer and apply it to the extraction."""
    ext = st.session_state["extraction"]
    st.session_state["asked_keys"].append(key)
    ext.setdefault("follow_up_answers", {})[key] = value
    if key in SYMPTOM_LABELS and value is not None:
        ext[key] = value
        ext["user_confirmed"] = True
        _sync_symptom_list(ext)
        st.session_state["ext_version"] += 1  # re-render chips with new defaults
        clear_result()


def mark_sms_unsent() -> None:
    st.session_state["sms_sent"] = False
    st.session_state["sms_sent_at"] = None
