import inspect
from pathlib import Path

import pandas as pd
import streamlit as st

from modules.advice_generator import advice_for
from modules.asr import transcribe_audio
from modules.conversation import next_question
from modules.database import (
    export_csv,
    init_db,
    list_assessments,
    save_assessment,
)
from modules.llm_extractor import extract_symptoms
from modules.referral_sms import make_sms
from modules.triage_engine import assess


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="মাতৃকণ্ঠ | Matrikontho",
    page_icon="🌸",
    layout="centered",
)

# Initialize database
init_db()


# =========================================================
# 2. LOAD CUSTOM CSS
# =========================================================

def load_stylesheet() -> None:
    base_dir = Path(__file__).parent
    candidate_paths = [
        base_dir / "assets" / "styles.css",
        base_dir / "style.css",
    ]

    for css_path in candidate_paths:
        if css_path.exists():
            css_content = css_path.read_text(encoding="utf-8")
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
            return

    st.warning(
        "CSS ফাইল পাওয়া যায়নি। "
        "assets/styles.css অথবা style.css ফাইলটি রাখুন।"
    )


load_stylesheet()


# =========================================================
# 3. HELPERS & SESSION STATE
# =========================================================

def call_with_optional_context(func, *args, context=None, extraction=None):
    """Call module functions with extra context only if their signature supports it."""
    sig = inspect.signature(func)
    params = sig.parameters
    accepts_kwargs = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
    )

    kwargs = {}
    if context is not None and (accepts_kwargs or "context" in params):
        kwargs["context"] = context
    if extraction is not None and (accepts_kwargs or "extraction" in params):
        kwargs["extraction"] = extraction

    return func(*args, **kwargs)


def reset_analysis_state() -> None:
    st.session_state["extraction"] = None
    st.session_state["result"] = None
    st.session_state["assessment_saved"] = False
    st.session_state["saved_assessment_id"] = None


defaults = {
    "transcript": "",
    "transcript_box": "",
    "extraction": None,
    "result": None,
    "assessment_saved": False,
    "saved_assessment_id": None,
    "last_context_key": None,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# 4. HEADER
# =========================================================

st.markdown(
    """
    <div class="hero">
        <div class="hero-brand">
            <span class="hero-flower" aria-hidden="true">🌸</span>
            <span class="hero-title">মাতৃকণ্ঠ</span>
        </div>
        <div class="hero-tagline">
            আপনার কথা শুনি, ঝুঁকি বুঝি, সাহায্যের পথ দেখাই
        </div>
        <div class="hero-subtitle">
            Bangla Voice-based Maternal Risk Screener · Hackathon MVP
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.warning(
    "এটি পরীক্ষামূলক স্ক্রিনিং সহায়ক—রোগ নির্ণয় "
    "বা চিকিৎসার বিকল্প নয়। জরুরি সমস্যা হলে "
    "AI-এর উত্তরের অপেক্ষা না করে হাসপাতালে যান।"
)


# =========================================================
# 5. TABS
# =========================================================

tab1, tab2, tab3 = st.tabs(
    [
        "🎙️ নতুন মূল্যায়ন",
        "📋 স্বাস্থ্যকর্মী ড্যাশবোর্ড",
        "ℹ️ সীমাবদ্ধতা",
    ]
)


# =========================================================
# TAB 1: NEW ASSESSMENT
# =========================================================

with tab1:

    st.subheader("১. আপনার কথা বলুন")

    st.write(
        "আসসালামু আলাইকুম। আমি মাতৃকণ্ঠ। "
        "আপনার শরীরের কোনো সমস্যা হচ্ছে? আমাকে বলুন।"
    )

    # -----------------------------------------------------
    # PREGNANCY INFORMATION
    # -----------------------------------------------------

    pregnancy = st.selectbox(
        "আপনি কি বর্তমানে গর্ভবতী?",
        ["জানি না", "হ্যাঁ", "না"],
        key="pregnancy_status",
    )

    weeks = st.number_input(
        "গর্ভাবস্থার কত সপ্তাহ চলছে? জানা না থাকলে ০ দিন",
        min_value=0,
        max_value=45,
        value=0,
        step=1,
        key="gestational_weeks",
    )

    pregnancy_status = {
        "হ্যাঁ": "pregnant",
        "না": "not_pregnant",
        "জানি না": "unknown",
    }[pregnancy]

    normalized_weeks = int(weeks) if weeks else None
    case_context = {
        "pregnancy_status": pregnancy_status,
        "gestational_weeks": normalized_weeks,
    }

    current_context_key = (pregnancy_status, normalized_weeks)
    if (
        st.session_state["last_context_key"] is not None
        and st.session_state["last_context_key"] != current_context_key
        and (
            st.session_state["extraction"] is not None
            or st.session_state["result"] is not None
        )
    ):
        reset_analysis_state()
        st.info(
            "গর্ভাবস্থার তথ্য পরিবর্তিত হয়েছে। নতুন তথ্য অনুযায়ী আবার বিশ্লেষণ ও মূল্যায়ন করুন।"
        )
    st.session_state["last_context_key"] = current_context_key

    # -----------------------------------------------------
    # AUDIO INPUT
    # -----------------------------------------------------

    st.markdown("#### 🎙️ অডিও ইনপুট")

    audio = st.audio_input(
        "মাইক্রোফোনে কথা বলুন",
        key="recorded_audio",
    )

    uploaded = st.file_uploader(
        "অথবা অডিও ফাইল আপলোড করুন",
        type=["wav", "mp3", "m4a", "ogg"],
        key="uploaded_audio",
    )

    selected_audio = None
    if audio is not None and uploaded is not None:
        audio_source = st.radio(
            "কোন অডিও উৎস থেকে লেখা তৈরি করবেন?",
            ["আপলোড করা ফাইল", "মাইক্রোফোন রেকর্ডিং"],
            horizontal=True,
            key="audio_source_choice",
        )
        selected_audio = uploaded if audio_source == "আপলোড করা ফাইল" else audio
    elif uploaded is not None:
        selected_audio = uploaded
    elif audio is not None:
        selected_audio = audio

    if selected_audio is not None:

        if st.button(
            "অডিও থেকে লেখা তৈরি করুন",
            width="stretch",
        ):

            with st.spinner("বাংলা কথা শনাক্ত করা হচ্ছে..."):

                transcription = transcribe_audio(selected_audio)

            if transcription.get("success"):

                recognized_text = transcription.get("text", "").strip()

                if recognized_text:

                    st.session_state["transcript_box"] = recognized_text
                    st.session_state["transcript"] = recognized_text
                    reset_analysis_state()

                    st.success(
                        "ট্রান্সক্রিপশন তৈরি হয়েছে। "
                        "নিচে লেখাটি যাচাই করুন।"
                    )

                else:
                    st.warning(
                        "কোনো নির্ভরযোগ্য লেখা পাওয়া যায়নি। "
                        "আবার স্পষ্টভাবে কথা বলুন।"
                    )

            else:
                st.error(
                    transcription.get(
                        "error",
                        "অডিও প্রসেস করা যায়নি।",
                    )
                )

    # -----------------------------------------------------
    # TRANSCRIPTION TEXT AREA
    # -----------------------------------------------------

    st.markdown("#### ✍️ আপনার কথার লেখা")

    transcript = st.text_area(
        "লেখাটি যাচাই করুন এবং প্রয়োজনে সংশোধন করুন",
        height=130,
        key="transcript_box",
        placeholder="আপনার সমস্যাটি এখানে লিখুন...",
    )

    st.session_state["transcript"] = transcript

    # -----------------------------------------------------
    # ANALYZE BUTTON
    # -----------------------------------------------------

    if st.button(
        "লেখা বিশ্লেষণ করুন",
        type="primary",
        width="stretch",
    ):

        clean_transcript = transcript.strip()

        if not clean_transcript:

            st.error("আগে কথা বলুন অথবা আপনার সমস্যা লিখুন।")

        else:

            reset_analysis_state()

            with st.spinner("লক্ষণগুলো বিশ্লেষণ করা হচ্ছে..."):

                extraction = call_with_optional_context(
                    extract_symptoms,
                    clean_transcript,
                    context=case_context,
                )

            st.session_state["extraction"] = extraction
            st.session_state["transcript"] = clean_transcript

    # -----------------------------------------------------
    # EXTRACTION RESULTS & FOLLOW-UP QUESTION
    # -----------------------------------------------------

    if st.session_state["extraction"] is not None:

        st.divider()

        st.subheader("২. শনাক্ত তথ্য যাচাই করুন")

        ext = st.session_state["extraction"]

        st.caption(
            "AI ভুল বুঝতে পারে। শনাক্ত তথ্য যাচাই করুন। "
            "তথ্য পাওয়া যায়নি মানে লক্ষণটি নেই—এমন নয়।"
        )

        extraction_method = ext.get(
            "extraction_method",
            "unknown",
        )

        if extraction_method == "gemini":

            st.success("Gemini AI বিশ্লেষণ সম্পন্ন হয়েছে।")

        elif extraction_method == "keyword_fallback":

            st.warning(
                "Gemini AI ব্যবহার করা যায়নি। "
                "প্রাথমিক keyword-based fallback ব্যবহার করা হয়েছে। "
                "এই ফলাফল নির্ভরযোগ্য ক্লিনিক্যাল মূল্যায়ন নয়।"
            )

        else:

            st.warning(
                "লক্ষণ শনাক্তকরণ সম্পূর্ণ নির্ভরযোগ্য নয়। "
                "স্বাস্থ্যকর্মীর মাধ্যমে তথ্য যাচাই করুন।"
            )

        st.json(ext)

        follow_up = call_with_optional_context(
            next_question,
            ext,
            context=case_context,
        )

        if follow_up:
            st.markdown("#### 💬 অতিরিক্ত জিজ্ঞাসা")
            st.info(follow_up)
            st.caption(
                "উপরের প্রশ্ন অনুযায়ী মূল বক্তব্যে আরও তথ্য যোগ করে আবার 'লেখা বিশ্লেষণ করুন' চাপতে পারেন, "
                "অথবা সরাসরি নিচে 'ঝুঁকি মূল্যায়ন করুন' চাপতে পারেন।"
            )

        st.info(
            "এই MVP-তে শনাক্ত তথ্য সরাসরি সম্পাদনার সুবিধা নেই। "
            "তথ্যে ভুল থাকলে মূল বক্তব্য সংশোধন করে আবার বিশ্লেষণ করুন।"
        )

        # -------------------------------------------------
        # RISK ASSESSMENT
        # -------------------------------------------------

        if st.button(
            "ঝুঁকি মূল্যায়ন করুন",
            type="primary",
            width="stretch",
        ):

            with st.spinner("প্রাথমিক ঝুঁকি মূল্যায়ন করা হচ্ছে..."):

                result = call_with_optional_context(
                    assess,
                    ext,
                    context=case_context,
                )

            st.session_state["result"] = result
            st.session_state["assessment_saved"] = False
            st.session_state["saved_assessment_id"] = None

    # -----------------------------------------------------
    # FINAL RISK RESULT
    # -----------------------------------------------------

    if st.session_state["result"] is not None:

        res = st.session_state["result"]
        ext = st.session_state["extraction"]

        st.divider()

        st.subheader("৩. মূল্যায়নের ফলাফল")

        risk_level = res.get("risk_level", "UNKNOWN")

        risk_display = {
            "HIGH": ("🔴", "উচ্চ ঝুঁকি"),
            "MODERATE": ("🟠", "মাঝারি ঝুঁকি"),
            "LOW": ("🟢", "প্রাথমিকভাবে কম ঝুঁকি"),
            "UNKNOWN": ("⚪", "তথ্য অপর্যাপ্ত"),
        }

        icon, label = risk_display.get(
            risk_level,
            ("⚪", "তথ্য অপর্যাপ্ত"),
        )

        st.markdown(f"## {icon} {label}")

        recommendation = res.get("recommendation", "")

        if risk_level == "HIGH":
            st.error(
                recommendation
                or "জরুরি ঝুঁকির লক্ষণ থাকতে পারে। দেরি না করে নিকটস্থ হাসপাতাল বা জরুরি মাতৃস্বাস্থ্য সেবাকেন্দ্রে যান।"
            )

        if res.get("assessment_reliable"):

            st.caption("প্রাথমিক স্ক্রিনিং সম্পন্ন হয়েছে।")

        else:

            st.warning(
                "প্রাপ্ত তথ্যের ভিত্তিতে নির্ভরযোগ্য ঝুঁকি "
                "মূল্যায়ন করা সম্ভব হয়নি।"
            )

        reasons = res.get("reasons", [])

        if reasons:

            st.markdown("#### শনাক্ত বিষয়")

            for reason in reasons:
                st.write(f"- {reason}")

        if recommendation and risk_level != "HIGH":

            st.markdown("#### করণীয়")

            st.info(recommendation)

        advice = call_with_optional_context(
            advice_for,
            res,
            context=case_context,
            extraction=ext,
        )

        if advice:

            st.markdown("#### স্বাস্থ্য পরামর্শ")

            for item in advice:
                st.write(f"• {item}")

        # -------------------------------------------------
        # REFERRAL SMS
        # -------------------------------------------------

        sms = call_with_optional_context(
            make_sms,
            res,
            context=case_context,
            extraction=ext,
        )

        if risk_level in ("HIGH", "MODERATE", "UNKNOWN"):

            st.divider()

            st.subheader("রেফারেল বার্তা (ড্রাফট)")

            st.code(sms)

            st.caption(
                "এটি একটি ডেমো বার্তা। কোনো SMS পাঠানো হয়নি।"
            )

        # -------------------------------------------------
        # SAVE RECORD
        # -------------------------------------------------

        st.divider()

        if not st.session_state["assessment_saved"]:

            if st.button(
                "অ্যানোনিমাইজড রেকর্ড সংরক্ষণ করুন",
                width="stretch",
            ):

                assessment_id = save_assessment(
                    transcript=st.session_state["transcript"],
                    extraction=ext,
                    result=res,
                    advice=advice,
                    sms=sms,
                    gestational_weeks=normalized_weeks,
                    pregnancy_status=pregnancy_status,
                )

                st.session_state["assessment_saved"] = True
                st.session_state["saved_assessment_id"] = assessment_id

                st.success(
                    f"রেকর্ড সংরক্ষণ করা হয়েছে। ID: {assessment_id}"
                )

        else:

            st.success(
                "এই মূল্যায়নের রেকর্ড ইতিমধ্যে সংরক্ষণ করা হয়েছে। "
                f"ID: {st.session_state['saved_assessment_id']}"
            )


# =========================================================
# TAB 2: HEALTH WORKER DASHBOARD
# =========================================================

with tab2:

    st.subheader("স্বাস্থ্যকর্মী ড্যাশবোর্ড")

    records = list_assessments()

    if records:

        df = pd.DataFrame(records)

        st.markdown("#### মূল্যায়নের সারসংক্ষেপ")

        a, b, c, d = st.columns(4)

        risk_columns = [
            (a, "HIGH", "উচ্চ"),
            (b, "MODERATE", "মাঝারি"),
            (c, "LOW", "কম"),
            (d, "UNKNOWN", "অজানা"),
        ]

        for column, level, label in risk_columns:

            count = (
                int((df["risk_level"] == level).sum())
                if "risk_level" in df.columns
                else 0
            )

            column.metric(label, count)

        st.divider()

        st.markdown("#### সংরক্ষিত মূল্যায়ন")

        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
        )

        st.download_button(
            label="📥 CSV ডাউনলোড করুন",
            data=export_csv(),
            file_name="matrikontho_cases.csv",
            mime="text/csv",
            width="stretch",
        )

    else:

        st.info(
            "এখনো কোনো মূল্যায়ন সংরক্ষণ করা হয়নি। "
            "নতুন মূল্যায়ন সম্পন্ন করে এখানে রেকর্ড দেখতে পারবেন।"
        )


# =========================================================
# TAB 3: LIMITATIONS
# =========================================================

with tab3:

    st.subheader("গুরুত্বপূর্ণ সীমাবদ্ধতা")

    st.markdown(
        """
        ### মাতৃকণ্ঠ কী করতে পারে?

- বাংলা বক্তব্য থেকে সম্ভাব্য মাতৃস্বাস্থ্য-সংক্রান্ত
          লক্ষণ শনাক্ত করার চেষ্টা করে।
- শনাক্ত তথ্যের ভিত্তিতে একটি প্রাথমিক স্ক্রিনিং
          অগ্রাধিকার দেখায়।
- সম্ভাব্য পরবর্তী পদক্ষেপ সম্পর্কে বাংলা ভাষায়
          সাধারণ নির্দেশনা দেয়।
- স্বাস্থ্যকর্মীর জন্য মূল্যায়নের রেকর্ড সংরক্ষণ করে।

        ### মাতৃকণ্ঠ কী করতে পারে না?

- এটি রোগ নির্ণয় করতে পারে না।
- এটি চিকিৎসক বা প্রশিক্ষিত স্বাস্থ্যকর্মীর বিকল্প নয়।
- এটি ওষুধ নির্ধারণ বা চিকিৎসা শুরু করার নির্দেশ দেয় না।
- এটি জরুরি চিকিৎসার বিকল্প নয়।

        ### প্রযুক্তিগত ও ক্লিনিক্যাল সীমাবদ্ধতা

- Whisper-এর ট্রান্সক্রিপশন ভুল হতে পারে।
- Gemini ভুলভাবে লক্ষণ শনাক্ত করতে পারে।
- Keyword-based fallback সীমিত এবং সব ধরনের
          বাংলা বক্তব্য বুঝতে পারে না।
- ঝুঁকি নির্ধারণের নিয়মগুলো প্রাথমিক ডেমো নিয়ম;
          WHO বা DGHS-এর অনুমোদিত ক্লিনিক্যাল প্রোটোকল নয়।
- বাস্তব ব্যবহারের আগে প্রসূতি ও জনস্বাস্থ্য
          বিশেষজ্ঞের পর্যালোচনা প্রয়োজন।
- স্থানীয় হাসপাতাল ও রেফারেল ব্যবস্থার সঙ্গে
          সংযোগ স্থাপন করা হয়নি।
- ডেমোতে কেবল কাল্পনিক তথ্য ব্যবহার করুন।

        ### জরুরি সতর্কতা

        গুরুতর বা উদ্বেগজনক কোনো লক্ষণ দেখা দিলে
        AI-এর উত্তরের অপেক্ষা না করে নিকটস্থ হাসপাতাল
        বা জরুরি মাতৃস্বাস্থ্য সেবাকেন্দ্রে যান।
        """
    )
