import streamlit as st
import pandas as pd
from modules.asr import transcribe_audio
from modules.llm_extractor import extract_symptoms
from modules.conversation import next_question
from modules.triage_engine import assess
from modules.advice_generator import advice_for
from modules.referral_sms import make_sms
from modules.database import init_db, save_assessment, list_assessments, get_assessment, export_csv

st.set_page_config(page_title="মাতৃকণ্ঠ | Matrikontho", page_icon="🌸", layout="centered")
init_db()
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {font-family:'Hind Siliguri', sans-serif;}
.block-container{max-width:900px;padding-top:1.2rem}
.hero{background:linear-gradient(120deg,#fff1f2,#fef3c7);padding:1.3rem;border-radius:18px}
.big{font-size:1.25rem;font-weight:700}
div.stButton>button{min-height:3rem;border-radius:12px;font-weight:700}
</style>""", unsafe_allow_html=True)

if "transcript" not in st.session_state: st.session_state.transcript = ""
if "extraction" not in st.session_state: st.session_state.extraction = None
if "result" not in st.session_state: st.session_state.result = None
if "history" not in st.session_state: st.session_state.history = []

st.markdown('<div class="hero"><h1>🌸 মাতৃকণ্ঠ</h1><div class="big">আপনার কথা শুনি, ঝুঁকি বুঝি, সাহায্যের পথ দেখাই।</div><p>Bangla Voice-based Maternal Risk Screener · Hackathon MVP</p></div>', unsafe_allow_html=True)
st.warning("এটি পরীক্ষামূলক স্ক্রিনিং সহায়ক—রোগ নির্ণয় বা চিকিৎসার বিকল্প নয়। জরুরি সমস্যা হলে AI-এর উত্তরের অপেক্ষা না করে হাসপাতালে যান।")

tab1, tab2, tab3 = st.tabs(["🎙️ নতুন মূল্যায়ন", "📋 স্বাস্থ্যকর্মী ড্যাশবোর্ড", "ℹ️ সীমাবদ্ধতা"])

with tab1:
    st.subheader("১. আপনার কথা বলুন")
    st.write("আসসালামু আলাইকুম। আমি মাতৃকণ্ঠ। আপনার শরীরের কোনো সমস্যা হচ্ছে? আমাকে বলুন।")
    pregnancy = st.selectbox("আপনি কি বর্তমানে গর্ভবতী?", ["জানি না", "হ্যাঁ", "না"])
    weeks = st.number_input("গর্ভাবস্থার কত সপ্তাহ চলছে? জানা না থাকলে ০ দিন", min_value=0, max_value=45, value=0)
    audio = st.audio_input("মাইক্রোফোনে কথা বলুন (সমর্থিত ব্রাউজারে)")
    uploaded = st.file_uploader("অথবা অডিও ফাইল দিন", type=["wav","mp3","m4a","ogg"])
    if audio or uploaded:
        if st.button("অডিও থেকে লেখা তৈরি করুন"):
            with st.spinner("কথা থেকে লেখা তৈরি হচ্ছে..."):
                st.session_state.transcript, err = transcribe_audio(audio or uploaded)
                if err: st.error(err)
                else: st.success("ট্রান্সক্রিপশন তৈরি হয়েছে। নিচে যাচাই করুন।")
    st.session_state.transcript = st.text_area("আপনার কথার লেখা (ভুল থাকলে সংশোধন করুন)", value=st.session_state.transcript, height=130, key="transcript_box")
    if st.button("লেখা বিশ্লেষণ করুন", type="primary", use_container_width=True):
        if not st.session_state.transcript.strip():
            st.error("আগে কথা বলুন অথবা নিচে লিখুন।")
        else:
            with st.spinner("লক্ষণগুলো বোঝার চেষ্টা করছি..."):
                st.session_state.extraction = extract_symptoms(
                    st.session_state.transcript,
                    pregnancy_status={"হ্যাঁ":"pregnant","না":"not_pregnant","জানি না":"unknown"}[pregnancy],
                    gestational_age_weeks=int(weeks) if weeks else None
                )
                st.session_state.result = assess(st.session_state.extraction)
    if st.session_state.extraction:
        st.divider()
        st.subheader("২. শনাক্ত তথ্য যাচাই করুন")
        st.caption("মডেল ভুল বুঝতে পারে। তথ্য সংশোধন করুন। 'unknown' মানে তথ্য পাওয়া যায়নি—'না' নয়।")
        ext = st.session_state.extraction
        st.json(ext)
        st.info("প্রয়োজনে স্বাস্থ্যকর্মী তথ্য সংশোধন করে আবার মূল্যায়ন করবেন।")
        if st.button("ঝুঁকি মূল্যায়ন করুন", type="primary", use_container_width=True):
            st.session_state.result = assess(ext)
    if st.session_state.result:
        res = st.session_state.result
        st.divider()
        st.subheader("৩. মূল্যায়নের ফল")
        colors = {"HIGH":"🔴","MEDIUM":"🟠","LOW":"🟢","INCOMPLETE":"⚪"}
        st.markdown(f"## {colors[res['risk_level']]} {res['risk_level']} — {res['assessment_status']}")
        st.write(res["explanation"])
        if res["triggered_symptoms"]: st.write("**চিহ্নিত লক্ষণ:**", ", ".join(res["triggered_symptoms"]))
        st.markdown(f"### করণীয়\n{advice_for(res)}")
        if res["risk_level"] == "HIGH":
            sms = make_sms(ext, res)
            st.subheader("রেফারেল SMS (শুধু ড্রাফট)")
            st.code(sms)
            st.caption("এটি সিমুলেটেড SMS; কোনো বার্তা পাঠানো হয়নি।")
        if st.button("অ্যানোনিমাইজড রেকর্ড সংরক্ষণ করুন"):
            aid = save_assessment(ext, res, advice_for(res))
            st.success(f"রেকর্ড সংরক্ষিত: {aid}")

with tab2:
    st.subheader("স্বাস্থ্যকর্মী ড্যাশবোর্ড")
    records = list_assessments()
    if records:
        df = pd.DataFrame(records)
        a,b,c,d = st.columns(4)
        for col, level in zip([a,b,c,d],["HIGH","MEDIUM","LOW","INCOMPLETE"]):
            col.metric(level, int((df["risk_level"]==level).sum()))
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("CSV ডাউনলোড", export_csv(), "matrikontho_cases.csv", "text/csv")
    else: st.info("এখনো কোনো ডেমো মূল্যায়ন সংরক্ষিত হয়নি।")

with tab3:
    st.subheader("গুরুত্বপূর্ণ সীমাবদ্ধতা")
    st.markdown("""
- এটি **রোগ নির্ণয় করে না** এবং চিকিৎসা/ওষুধের পরামর্শ দেয় না।
- ঝুঁকির নিয়মগুলো প্রাথমিক ডেমো নিয়ম; WHO/DGHS-এর অনুমোদিত ক্লিনিক্যাল প্রোটোকল হিসেবে দাবি করা হচ্ছে না।
- বাস্তব ব্যবহারের আগে প্রসূতি ও জনস্বাস্থ্য বিশেষজ্ঞের পর্যালোচনা, স্থানীয় রেফারেল ডিরেক্টরি, নিরাপত্তা পরীক্ষা ও নৈতিক অনুমোদন দরকার।
- Whisper/LLM বন্ধ থাকলে টেক্সট-ভিত্তিক নিয়ম ও প্রশ্ন-পরিকল্পনার fallback চালু থাকে।
- ডেমোতে কেবল কাল্পনিক তথ্য ব্যবহার করুন।
""")
