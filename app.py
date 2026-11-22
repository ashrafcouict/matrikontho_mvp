
import streamlit as st
import pandas as pd

from modules.asr import transcribe_audio
from modules.llm_extractor import extract_symptoms
from modules.triage_engine import assess
from modules.advice_generator import advice_for
from modules.referral_sms import make_sms
from modules.database import (
    init_db,
    save_assessment,
    list_assessments,
    export_csv
)


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="মাতৃকণ্ঠ | Matrikontho",
    page_icon="🌸",
    layout="centered"
)

init_db()


# =========================================================
# 2. CUSTOM CSS
# =========================================================

st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], button, input, textarea {
    font-family: 'Hind Siliguri', sans-serif !important;
}

.block-container {
    max-width: 900px;
    padding-top: 1.2rem;
    padding-bottom: 3rem;
}

.hero {
    background: linear-gradient(120deg, #fff0ed, #fff3c4);
    padding: 28px;
    border-radius: 22px;
    margin-bottom: 20px;
}

.hero-title {
    color: #7b2638;
    font-family: 'Hind Siliguri', sans-serif;
    font-size: 42px;
    font-weight: 700;
    text-align: center;
}

.big {
    color: #512b32;
    font-family: 'Hind Siliguri', sans-serif;
    font-size: 25px;
    font-weight: 600;
    text-align: center;
    margin-top: 12px;
}

.hero-subtitle {
    color: #72535a;
    font-size: 15px;
    text-align: center;
    margin-top: 12px;
}

div.stButton > button {
    min-height: 3rem;
    border-radius: 12px;
    font-weight: 700;
}

div[data-testid="stMetric"] {
    background: rgba(128, 128, 128, 0.08);
    padding: 0.8rem;
    border-radius: 12px;
}

@media (max-width: 600px) {
    .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
    }

    .hero {
        padding: 1.1rem;
    }
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# 3. SESSION STATE
# =========================================================

defaults = {
    "transcript": "",
    "transcript_box": "",
    "extraction": None,
    "result": None,
    "history": []
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# 4. HEADER
# =========================================================

st.markdown("""
<div class="hero">
    <div class="hero-title">
        🌸 মাতৃকণ্ঠ
    </div>

    <div class="big">
        আপনার কথা শুনি, ঝুঁকি বুঝি, সাহায্যের পথ দেখাই
    </div>

    <div class="hero-subtitle">
        Bangla Voice-based Maternal Risk Screener · Hackathon MVP
    </div>
</div>
""", unsafe_allow_html=True)


st.warning(
    "এটি পরীক্ষামূলক স্ক্রিনিং সহায়ক—রোগ নির্ণয় "
    "বা চিকিৎসার বিকল্প নয়। জরুরি সমস্যা হলে "
    "AI-এর উত্তরের অপেক্ষা না করে হাসপাতালে যান।"
)


# =========================================================
# 5. TABS
# =========================================================

tab1, tab2, tab3 = st.tabs([
    "🎙️ নতুন মূল্যায়ন",
    "📋 স্বাস্থ্যকর্মী ড্যাশবোর্ড",
    "ℹ️ সীমাবদ্ধতা"
])


# =========================================================
# TAB 1: NEW ASSESSMENT
# =========================================================

with tab1:

    st.subheader("১. আপনার কথা বলুন")

    st.write(
        "আসসালামু আলাইকুম। আমি মাতৃকণ্ঠ। "
        "আপনার শরীরের কোনো সমস্যা হচ্ছে? আমাকে বলুন।"
    )

    pregnancy = st.selectbox(
        "আপনি কি বর্তমানে গর্ভবতী?",
        ["জানি না", "হ্যাঁ", "না"]
    )

    weeks = st.number_input(
        "গর্ভাবস্থার কত সপ্তাহ চলছে? জানা না থাকলে ০ দিন",
        min_value=0,
        max_value=45,
        value=0
    )

    # -----------------------------------------------------
    # AUDIO INPUT
    # -----------------------------------------------------

    audio = st.audio_input(
        "মাইক্রোফোনে কথা বলুন (সমর্থিত ব্রাউজারে)"
    )

    uploaded = st.file_uploader(
        "অথবা অডিও ফাইল দিন",
        type=["wav", "mp3", "m4a", "ogg"]
    )

    if audio or uploaded:

        if st.button("অডিও থেকে লেখা তৈরি করুন"):

            with st.spinner("বাংলা কথা শনাক্ত করা হচ্ছে..."):

                transcript, err = transcribe_audio(
                    audio or uploaded
                )

                if err:

                    st.error(err)

                elif transcript and transcript.strip():

                    # Update widget state before text_area renders.
                    st.session_state["transcript_box"] = transcript.strip()
                    st.session_state["transcript"] = transcript.strip()

                    # Clear previous analysis.
                    st.session_state["extraction"] = None
                    st.session_state["result"] = None

                    st.success(
                        "ট্রান্সক্রিপশন তৈরি হয়েছে। নিচে যাচাই করুন।"
                    )

                else:

                    st.warning(
                        "কোনো নির্ভরযোগ্য বাংলা লেখা শনাক্ত হয়নি। "
                        "আবার স্পষ্টভাবে কথা বলুন।"
                    )

    # -----------------------------------------------------
    # TRANSCRIPTION TEXT AREA
    # -----------------------------------------------------

    transcript = st.text_area(
        "আপনার কথার লেখা (ভুল থাকলে সংশোধন করুন)",
        height=130,
        key="transcript_box",
        placeholder="আপনার কথার লেখা এখানে দেখা যাবে..."
    )

    st.session_state["transcript"] = transcript

    # -----------------------------------------------------
    # ANALYZE BUTTON
    # -----------------------------------------------------

    if st.button(
        "লেখা বিশ্লেষণ করুন",
        type="primary",
        width="stretch"
    ):

        clean_transcript = transcript.strip()

        if not clean_transcript:

            st.error("আগে কথা বলুন অথবা নিচে লিখুন।")

        else:

            # Remove old analysis before starting a new one.
            st.session_state["extraction"] = None
            st.session_state["result"] = None

            pregnancy_status = {
                "হ্যাঁ": "pregnant",
                "না": "not_pregnant",
                "জানি না": "unknown"
            }[pregnancy]

            with st.spinner("লক্ষণগুলো বোঝার চেষ্টা করছি..."):

                extraction = extract_symptoms(
                    clean_transcript,
                    pregnancy_status=pregnancy_status,
                    gestational_age_weeks=int(weeks) if weeks else None
                )

                st.session_state["extraction"] = extraction

    # -----------------------------------------------------
    # EXTRACTION RESULTS
    # -----------------------------------------------------

    if st.session_state["extraction"]:

        st.divider()

        st.subheader("২. শনাক্ত তথ্য যাচাই করুন")

        st.caption(
            "মডেল ভুল বুঝতে পারে। তথ্য যাচাই করুন। "
            "'unknown' মানে তথ্য পাওয়া যায়নি—'না' নয়।"
        )

        ext = st.session_state["extraction"]

        # Display Gemini / fallback status.
        if ext.get("extraction_method") == "gemini":

            st.success("Gemini AI বিশ্লেষণ সম্পন্ন হয়েছে।")

        elif ext.get("extraction_method") == "fallback":

            st.warning(
                "Gemini AI ব্যবহার করা যায়নি। "
                "প্রাথমিক keyword-based fallback ব্যবহার করা হয়েছে। "
                "এই ফলাফল স্বাস্থ্যকর্মীর মাধ্যমে যাচাই করুন।"
            )

        st.json(ext)

        st.info(
            "প্রয়োজনে স্বাস্থ্যকর্মী তথ্য সংশোধন করে "
            "আবার মূল্যায়ন করবেন।"
        )

        # -------------------------------------------------
        # RISK ASSESSMENT
        # -------------------------------------------------

        if st.button(
            "ঝুঁকি মূল্যায়ন করুন",
            type="primary",
            width="stretch"
        ):

            with st.spinner("ঝুঁকি মূল্যায়ন করা হচ্ছে..."):

                st.session_state["result"] = assess(ext)

    # -----------------------------------------------------
    # FINAL RISK RESULT
    # -----------------------------------------------------

    if st.session_state["result"]:

        res = st.session_state["result"]
        ext = st.session_state["extraction"]

        st.divider()

        st.subheader("৩. মূল্যায়নের ফল")

        colors = {
            "HIGH": "🔴",
            "MEDIUM": "🟠",
            "LOW": "🟢",
            "INCOMPLETE": "⚪"
        }

        risk_level = res.get("risk_level", "INCOMPLETE")

        st.markdown(
            f"## {colors.get(risk_level, '⚪')} "
            f"{risk_level} — "
            f"{res.get('assessment_status', '')}"
        )

        st.write(res.get("explanation", ""))

        triggered = res.get("triggered_symptoms", [])

        if triggered:

            st.write(
                "**চিহ্নিত লক্ষণ:**",
                ", ".join(triggered)
            )

        st.markdown(
            f"### করণীয়\n{advice_for(res)}"
        )

        # -------------------------------------------------
        # REFERRAL SMS
        # -------------------------------------------------

        if risk_level == "HIGH":

            sms = make_sms(ext, res)

            st.subheader("রেফারেল SMS (শুধু ড্রাফট)")

            st.code(sms)

            st.caption(
                "এটি সিমুলেটেড SMS; কোনো বার্তা পাঠানো হয়নি।"
            )

        # -------------------------------------------------
        # SAVE RECORD
        # -------------------------------------------------

        if st.button("অ্যানোনিমাইজড রেকর্ড সংরক্ষণ করুন"):

            aid = save_assessment(
                ext,
                res,
                advice_for(res)
            )

            st.success(f"রেকর্ড সংরক্ষিত: {aid}")


# =========================================================
# TAB 2: HEALTH WORKER DASHBOARD
# =========================================================

with tab2:

    st.subheader("স্বাস্থ্যকর্মী ড্যাশবোর্ড")

    records = list_assessments()

    if records:

        df = pd.DataFrame(records)

        if "risk_level" in df.columns:

            a, b, c, d = st.columns(4)

            for col, level in zip(
                [a, b, c, d],
                ["HIGH", "MEDIUM", "LOW", "INCOMPLETE"]
            ):

                col.metric(
                    level,
                    int((df["risk_level"] == level).sum())
                )

        st.dataframe(
            df,
            width="stretch",
            hide_index=True
        )

        st.download_button(
            "CSV ডাউনলোড",
            export_csv(),
            "matrikontho_cases.csv",
            "text/csv",
            width="stretch"
        )

    else:

        st.info(
            "এখনো কোনো ডেমো মূল্যায়ন সংরক্ষিত হয়নি।"
        )


# =========================================================
# TAB 3: LIMITATIONS
# =========================================================

with tab3:

    st.subheader("গুরুত্বপূর্ণ সীমাবদ্ধতা")

    st.markdown("""
- এটি **রোগ নির্ণয় করে না** এবং চিকিৎসা/ওষুধের পরামর্শ দেয় না।
- ঝুঁকির নিয়মগুলো প্রাথমিক ডেমো নিয়ম; WHO/DGHS-এর অনুমোদিত ক্লিনিক্যাল প্রোটোকল হিসেবে দাবি করা হচ্ছে না।
- বাস্তব ব্যবহারের আগে প্রসূতি ও জনস্বাস্থ্য বিশেষজ্ঞের পর্যালোচনা, স্থানীয় রেফারেল ডিরেক্টরি, নিরাপত্তা পরীক্ষা ও নৈতিক অনুমোদন দরকার।
- Whisper/LLM বন্ধ থাকলে টেক্সট-ভিত্তিক নিয়ম ও প্রশ্ন-পরিকল্পনার fallback চালু থাকতে পারে।
- ডেমোতে কেবল কাল্পনিক তথ্য ব্যবহার করুন।
- ভুল বা অসম্পূর্ণ ট্রান্সক্রিপশনকে কখনোই LOW risk হিসেবে ধরে নেওয়া যাবে না।
""")
