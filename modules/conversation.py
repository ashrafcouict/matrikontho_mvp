import re
KEYWORDS={
"vaginal_bleeding":["রক্তপাত","রক্ত যাচ্ছে","ব্লিডিং"],
"convulsions":["খিঁচুনি","অজ্ঞান হয়ে","ফিট"],
"headache":["মাথা ব্যথা","মাথাব্যথা"],
"blurred_vision":["ঝাপসা","চোখে কম দেখি","চোখে ঝাপসা"],
"facial_hand_swelling":["মুখ ফুল","হাত ফুল","ফুলে গেছে"],
"fever":["জ্বর","গা গরম"],
"reduced_fetal_movement":["বাচ্চা নড়ছে না","বাচ্চা কম নড়","নড়াচড়া কম"],
"abdominal_pain":["পেটে ব্যথা","তলপেটে ব্যথা","পেট ব্যথা"],
"breathing_difficulty":["শ্বাসকষ্ট","শ্বাস নিতে কষ্ট"],
"severe_weakness":["খুব দুর্বল","অতিরিক্ত দুর্বল"]
}
NEGATIONS=["নেই","হয়নি","হয়নি","না","কোনো"]
def fallback_extract(text, pregnancy_status="unknown", weeks=None):
    t=text.lower(); symptoms=[]
    for name, words in KEYWORDS.items():
        hits=[w for w in words if w in t]
        if hits:
            # Conservative: negation is not reliably resolved by keyword matching.
            neg=any(n in t[max(0,t.find(hits[0])-12):t.find(hits[0])+len(hits[0])+12] for n in NEGATIONS)
            symptoms.append({"name":name,"present":False if neg else True,"severity":"unknown","duration":None,"evidence":f"টেক্সটে পাওয়া শব্দ: {hits[0]}"})
    return {"pregnancy_status":pregnancy_status,"gestational_age_weeks":weeks,"symptoms":symptoms,
            "missing_information":["গর্ভাবস্থার সপ্তাহ" if not weeks else ""],"uncertainty":["স্থানীয় keyword fallback; প্রসঙ্গভিত্তিক ভাষা বোঝে না"],
            "source_transcript":text,"extraction_method":"fallback"}
def next_question(extraction):
    present={s["name"] for s in extraction.get("symptoms",[]) if s.get("present") is True}
    if "headache" in present and "blurred_vision" not in present:
        return "আপনার কি চোখে ঝাপসা দেখাচ্ছে?"
    if "reduced_fetal_movement" in present:
        return "শিশুর স্বাভাবিক নড়াচড়ার তুলনায় কি নড়াচড়া কমে গেছে বা বন্ধ হয়েছে?"
    if not extraction.get("gestational_age_weeks"):
        return "আপনার গর্ভাবস্থার কত সপ্তাহ চলছে?"
    return "আর কোনো সমস্যা হচ্ছে কি?"
