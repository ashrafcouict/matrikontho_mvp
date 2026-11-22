"""Deterministic demo triage. Requires clinical review before any real-world use."""
def assess(extraction):
    symptoms=extraction.get("symptoms",[])
    present={s["name"]:s for s in symptoms if s.get("present") is True}
    unknown=[s["name"] for s in symptoms if s.get("present") is None]
    names=set(present)
    rules=[]
    if "vaginal_bleeding" in names: rules.append("DEMO-HIGH-01")
    if "convulsions" in names: rules.append("DEMO-HIGH-02")
    if "headache" in names and "blurred_vision" in names: rules.append("DEMO-HIGH-03")
    if "reduced_fetal_movement" in names: rules.append("DEMO-HIGH-04")
    if "abdominal_pain" in names and present["abdominal_pain"].get("severity")=="severe": rules.append("DEMO-HIGH-05")
    if "breathing_difficulty" in names and present["breathing_difficulty"].get("severity")=="severe": rules.append("DEMO-HIGH-06")
    if "fever" in names and "severe_weakness" in names: rules.append("DEMO-HIGH-07")
    if rules:
        level="HIGH"; status="EMERGENCY_SIGN_FOUND"
        explanation="আপনার বর্ণনায় একটি বা একাধিক ডেমো জরুরি সংকেত পাওয়া গেছে।"
    elif "facial_hand_swelling" in names or names.intersection({"fever","headache","abdominal_pain","breathing_difficulty"}):
        level="MEDIUM"; status="PROMPT_REVIEW"
        explanation="কিছু উদ্বেগজনক লক্ষণ পাওয়া গেছে; দ্রুত স্বাস্থ্যকর্মী/চিকিৎসকের মূল্যায়ন দরকার।"
    elif not symptoms or unknown or extraction.get("uncertainty") or extraction.get("pregnancy_status")=="unknown":
        level="INCOMPLETE"; status="INSUFFICIENT_INFORMATION"
        explanation="তথ্য অপর্যাপ্ত বা অনিশ্চিত; এটিকে কম ঝুঁকি বলা যাচ্ছে না।"
    else:
        level="LOW"; status="NO_LISTED_TRIGGER_IDENTIFIED"
        explanation="প্রদত্ত তথ্যের মধ্যে ডেমো তালিকার কোনো বিপদচিহ্ন শনাক্ত হয়নি; এটি সুস্থতার নিশ্চয়তা নয়।"
    return {"risk_level":level,"assessment_status":status,"triggered_symptoms":sorted(names),
            "rule_ids":rules,"explanation":explanation,"missing_information":extraction.get("missing_information",[]),
            "assessment_complete":level!="INCOMPLETE"}
