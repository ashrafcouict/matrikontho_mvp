import copy
from pathlib import Path

import pandas as pd
import streamlit as st

from modules.asr import transcribe_audio
from modules.llm_extractor import extract_symptoms
from modules.triage_engine import assess
from modules.advice_generator import advice_for
from modules.referral_sms import make_sms
from modules.database import (
    init_db,
    save_assessment,
    list_assessments,
    export_csv,
)

st.set_page_config(
    page_title="মাতৃকণ্ঠ | Matrikontho",
    page_icon="🌸",
    layout="centered",
)

init_db()

# Load the separate stylesheet. The app still runs if the CSS file is absent.
css_path = Path(__file__).parent / "assets" / "styles.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

# Session state
for key, default in {
    "transcript": "",
    "extraction": None,
    "result": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


SYMPTOM_LABELS = {
    "vaginal_bleeding": "যোনিপথে রক্তপাত",
    "bleeding": "রক্তপাত",
    "convulsions": "খিঁচুনি",
    "seizures": "খিঁচুনি",
    "severe_headache": "তীব্র মাথাব্যথা",
    "headache": "মাথাব্যথা",
    "blurred_vision": "চোখে ঝাপসা দেখা",
    "swelling": "মুখ বা হাত ফুলে যাওয়া",
    "facial_hand_swelling": "মুখ বা হাত ফুলে যাওয়া",
    "fever": "জ্বর",
    "reduced_fetal_movement": "শিশুর নড়াচড়া কমে যাওয়া",
    "abdominal_pain": "পেটে ব্যথা",
    "severe_abdominal_pain": "তীব্র পেটব্যথা",
    "breathing_difficulty": "শ্বাসকষ্ট",
    "difficulty_breathing": "শ্বাসকষ্ট",
    "high_fever": "উচ্চ জ্বর",
}

SEVERITY_LABELS = {
    "mild": "মৃদু",
    "moderate": "মাঝারি",
    "severe": "তীব্র",
    "unknown": "জানা যায়নি",
    "": "উল্লেখ নেই",
}


def humanize(value):
    """Make an internal enum readable without exposing raw model JSON."""
    if value is None or value == "":
        return "উল্লেখ নেই"
    text = str(value)
    return text.replace("_", " ").strip()


def symptom_label(symptom):
    name = symptom.get("name", "অন্যান্য সমস্যা")
    return SYMPTOM_LABELS.get(str(name).lower(), humanize(name))


def current_status(symptom):
    value = symptom.get("present")
    if value is True:
        return "উপস্থিত"
    if value is False:
        return "নেই (নিশ্চিত)"
    return "অনিশ্চিত / নিশ্চিত নয়"


def render_symptom_review(extraction):
    """Render editable, human-readable symptom cards; no raw JSON in the patient UI."""
    symptoms = extraction.get("symptoms") or []
    if not symptoms:
        st.info("এখনো নির্দিষ্ট কোনো লক্ষণ শনাক্ত হয়নি। আপনার বক্তব্য আবার যাচাই করুন।")
        return

    st.caption(
        "নিচের তথ্যগুলো আপনার বক্তব্য থেকে শনাক্ত করা হয়েছে। ভুল থাকলে সংশোধন করুন। "
        "‘অনিশ্চিত’ মানে লক্ষণটি নেই—এমন নয়।"
    )

    edited = copy.deepcopy(extraction)

    with st.form("confirm_extracted_information"):
        st.markdown("**আপনার বলা সমস্যাগুলো**")
        for index, symptom in enumerate(symptoms):
            label = symptom_label(symptom)
            st.markdown(f'<div class="symptom-name">{label}</div>', unsafe_allow_html=True)

            options = ["উপস্থিত", "নেই (নিশ্চিত)", "অনিশ্চিত / নিশ্চিত নয়"]
            default = current_status(symptom)
            selected = st.selectbox(
                f"{label} — অবস্থা",
                options,
                index=options.index(default),
                key=f"symptom_status_{index}",
                label_visibility="collapsed",
            )
            edited["symptoms"][index]["present"] = {
                "উপস্থিত": True,
                "নেই (নিশ্চিত)": False,
                "অনিশ্চিত / নিশ্চিত নয়": None,
            }[selected]

            severity = symptom.get("severity")
            if severity not in (None, ""):
                severity_label = SEVERITY_LABELS.get(str(severity).lower(), humanize(severity))
                st.caption(f"তীব্রতা: {severity_label}")

            duration = symptom.get("duration")
            if duration not in (None, ""):
                st.caption(f"সময়কাল: {humanize(duration)}")

            if symptom.get("evidence"):
                st.caption(f"আপনার বক্তব্য: “{symptom['evidence']}”")

            if index < len(symptoms) - 1:
                st.divider()

        submitted = st.form_submit_button(
            "তথ্য নিশ্চিত ও সংরক্ষণ করুন",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        st.session_state.extraction = edited
        st.session_state.result = None
        st.success("তথ্য আপডেট হয়েছে। এখন ঝুঁকি মূল্যায়ন করুন।")


# Header
st.markdown(
    """
    <section class="hero">
      <div class="hero-title">🌸 মাতৃকণ্ঠ</div>
      <div class="hero-tagline">আপনার কথা শুনি, ঝুঁকি বুঝি, সাহায্যের পথ দেখাই।</div>
      <div class="hero-subtitle">বাংলা কণ্ঠভিত্তিক মাতৃস্বাস্থ্য ঝুঁকি স্ক্রিনিং · Hackathon MVP</div>
    </section>
    """,
    unsafe_allow_html=True,
)

st.warning(
    "এটি পরীক্ষামূলক স্ক্রিনিং সহায়ক—রোগ নির্ণয় বা চিকিৎসার বিকল্প নয়। "
    "জরুরি সমস্যা হলে AI-এর উত্তরের অপেক্ষা না করে নিকটস্থ হাসপাতালে যান।"
)

tab1, tab2, tab3 = st.tabs(
    ["🎙️ নতুন মূল্যায়ন", "📋 স্বাস্থ্যকর্মী ড্যাশবোর্ড", "ℹ️ সীমাবদ্ধতা"]
)

with tab1:
    st.subheader("১. আপনার কথা বলুন")
    st.write("আসসালামু আলাইকুম। আমি মাতৃকণ্ঠ। আপনার শরীরের কোনো সমস্যা হচ্ছে? আমাকে বলুন।")

    pregnancy = st.selectbox(
        "আপনি কি বর্তমানে গর্ভবতী?",
        ["জানি না", "হ্যাঁ", "না"],
    )
    weeks = st.number_input(
        "গর্ভাবস্থার কত সপ্তাহ চলছে? জানা না থাকলে ০ দিন",
        min_value=0,
        max_value=45,
        value=0,
    )

    audio = st.audio_input("মাইক্রোফোনে কথা বলুন (সমর্থিত ব্রাউজারে)")
    uploaded = st.file_uploader(
        "অথবা অডিও ফাইল দিন",
        type=["wav", "mp3", "m4a", "ogg"],
    )

    if audio or uploaded:
        if st.button("অডিও থেকে লেখা তৈরি করুন"):
            with st.spinner("কথা থেকে লেখা তৈরি হচ্ছে..."):
                transcript, err = transcribe_audio(audio or uploaded)
                if err:
                    st.error(err)
                else:
                    st.session_state.transcript = transcript
                    st.success("ট্রান্সক্রিপশন তৈরি হয়েছে। নিচে যাচাই করুন।")

    st.session_state.transcript = st.text_area(
        "আপনার কথার লেখা (ভুল থাকলে সংশোধন করুন)",
        value=st.session_state.transcript,
        height=130,
        key="transcript_box",
    )

    if st.button("লেখা বিশ্লেষণ করুন", type="primary", use_container_width=True):
        if not st.session_state.transcript.strip():
            st.error("আগে কথা বলুন অথবা নিচে লিখুন।")
        else:
            with st.spinner("লক্ষণগুলো বোঝার চেষ্টা করছি..."):
                extraction = extract_symptoms(
                    st.session_state.transcript,
                    pregnancy_status={
                        "হ্যাঁ": "pregnant",
                        "না": "not_pregnant",
                        "জানি না": "unknown",
                    }[pregnancy],
                    gestational_age_weeks=int(weeks) if weeks else None,
                )
                st.session_state.extraction = extraction
                st.session_state.result = None

    if st.session_state.extraction:
        st.divider()
        st.subheader("২. শনাক্ত তথ্য যাচাই করুন")

        ext = st.session_state.extraction
        col1, col2 = st.columns(2)
        with col1:
            pregnancy_value = ext.get("pregnancy_status", "unknown")
            pregnancy_display = {
                "pregnant": "গর্ভবতী",
                "not_pregnant": "গর্ভবতী নন",
                "unknown": "জানা যায়নি",
            }.get(pregnancy_value, humanize(pregnancy_value))
            st.metric("গর্ভাবস্থার অবস্থা", pregnancy_display)
        with col2:
            gestational_age = ext.get("gestational_age_weeks")
            st.metric(
                "গর্ভকাল",
                f"{gestational_age} সপ্তাহ" if gestational_age else "জানা যায়নি",
            )

        render_symptom_review(ext)

        with st.expander("উন্নত তথ্য / ডিবাগ (শুধু ডেমো টিমের জন্য)"):
            st.json(st.session_state.extraction)
            st.caption("এই JSON অভ্যন্তরীণ ডিবাগের জন্য; রোগীকে দেখানোর প্রয়োজন নেই।")

        if st.button("ঝুঁকি মূল্যায়ন করুন", type="primary", use_container_width=True):
            st.session_state.result = assess(st.session_state.extraction)

    if st.session_state.result:
        res = st.session_state.result
        st.divider()
        st.subheader("৩. মূল্যায়নের ফল")

        risk_labels = {
            "HIGH": ("🔴", "উচ্চ ঝুঁকি"),
            "MEDIUM": ("🟠", "মাঝারি ঝুঁকি"),
            "LOW": ("🟢", "কম ঝুঁকি"),
            "INCOMPLETE": ("⚪", "তথ্য অসম্পূর্ণ"),
        }
        icon, bengali_risk = risk_labels.get(
            res.get("risk_level"),
            ("⚪", humanize(res.get("risk_level", "unknown"))),
        )
        st.markdown(
            f'<div class="risk-result"><div class="risk-level">{icon} {bengali_risk}</div>'
            f'<div class="risk-status">{humanize(res.get("assessment_status", ""))}</div></div>',
            unsafe_allow_html=True,
        )

        st.write(res.get("explanation", ""))
        triggered = res.get("triggered_symptoms") or []
        if triggered:
            st.write("**চিহ্নিত লক্ষণ:**", ", ".join(
                SYMPTOM_LABELS.get(str(item).lower(), humanize(item))
                for item in triggered
            ))

        st.markdown("### করণীয়")
        st.write(advice_for(res))

        if res.get("risk_level") == "HIGH":
            sms = make_sms(st.session_state.extraction, res)
            st.subheader("রেফারেল SMS (শুধু ড্রাফট)")
            st.code(sms)
            st.caption("এটি সিমুলেটেড SMS; কোনো বার্তা পাঠানো হয়নি।")

        if st.button("অ্যানোনিমাইজড রেকর্ড সংরক্ষণ করুন"):
            aid = save_assessment(
                st.session_state.extraction,
                res,
                advice_for(res),
            )
            st.success(f"রেকর্ড সংরক্ষিত: {aid}")


with tab2:
    st.subheader("স্বাস্থ্যকর্মী ড্যাশবোর্ড")
    records = list_assessments()
    if records:
        df = pd.DataFrame(records)
        a, b, c, d = st.columns(4)
        for col, level, label in zip(
            [a, b, c, d],
            ["HIGH", "MEDIUM", "LOW", "INCOMPLETE"],
            ["উচ্চ", "মাঝারি", "কম", "অসম্পূর্ণ"],
        ):
            col.metric(label, int((df["risk_level"] == level).sum()))
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "CSV ডাউনলোড",
            export_csv(),
            "matrikontho_cases.csv",
            "text/csv",
        )
    else:
        st.info("এখনো কোনো ডেমো মূল্যায়ন সংরক্ষিত হয়নি।")


with tab3:
    st.subheader("গুরুত্বপূর্ণ সীমাবদ্ধতা")
    st.markdown(
        """
- এটি **রোগ নির্ণয় করে না** এবং চিকিৎসা/ওষুধের পরামর্শ দেয় না।
- ঝুঁকির নিয়মগুলো প্রাথমিক ডেমো নিয়ম; WHO/DGHS-এর অনুমোদিত ক্লিনিক্যাল প্রোটোকল হিসেবে দাবি করা হচ্ছে না।
- বাস্তব ব্যবহারের আগে প্রসূতি ও জনস্বাস্থ্য বিশেষজ্ঞের পর্যালোচনা, স্থানীয় রেফারেল ডিরেক্টরি, নিরাপত্তা পরীক্ষা ও নৈতিক অনুমোদন দরকার।
- Whisper/LLM বন্ধ থাকলে টেক্সট-ভিত্তিক নিয়ম ও প্রশ্ন-পরিকল্পনার fallback চালু থাকে।
- ডেমোতে কেবল কাল্পনিক তথ্য ব্যবহার করুন।
"""
    )
