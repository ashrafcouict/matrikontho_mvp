"""Sidebar developer panel: raw extraction / triage data for debugging."""

import streamlit as st


def render_debug_sidebar() -> None:
    with st.sidebar:
        st.markdown("### 🔧 ডেভেলপার তথ্য")
        ext = st.session_state.get("extraction")
        result = st.session_state.get("result")
        if ext is None and result is None:
            st.caption("বিশ্লেষণ করার পর এখানে কাঁচা ডেটা দেখা যাবে।")
            return
        if ext is not None:
            with st.expander("লক্ষণ এক্সট্র্যাকশন (JSON)"):
                st.json(ext)
        if result is not None:
            with st.expander("ঝুঁকি মূল্যায়ন (JSON)"):
                st.json(result if isinstance(result, dict) else getattr(result, "__dict__", str(result)))
