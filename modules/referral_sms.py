
def make_sms(result, patient_name="রোগী", phone_number=""):
    """Generate a referral SMS draft. No SMS is actually sent."""
    if not isinstance(result, dict):
        return "মাতৃকণ্ঠ: রোগীর তথ্য যাচাই করা প্রয়োজন। স্বাস্থ্যকর্মীর সঙ্গে যোগাযোগ করুন।"

    level = str(result.get("risk_level", "UNKNOWN")).upper()

    if level == "HIGH":
        urgency = "জরুরি"
        instruction = "দ্রুত নিকটস্থ হাসপাতালে যাওয়ার পরামর্শ দেওয়া হয়েছে।"
    elif level == "MODERATE":
        urgency = "দ্রুত পরামর্শ"
        instruction = "আজই স্বাস্থ্যকর্মী বা চিকিৎসকের সঙ্গে যোগাযোগ করুন।"
    elif level == "LOW":
        urgency = "নিয়মিত"
        instruction = "নিয়মিত ANC চেকআপ চালিয়ে যান।"
    else:
        urgency = "যাচাই প্রয়োজন"
        instruction = "স্বাস্থ্যকর্মীর মাধ্যমে রোগীর অবস্থা যাচাই করুন।"

    return (
        f"মাতৃকণ্ঠ রেফারেল ({urgency}): {patient_name}। "
        f"{instruction} এটি একটি প্রাথমিক স্ক্রিনিং বার্তা, "
        f"চিকিৎসকের রোগনির্ণয় নয়।"
    )
