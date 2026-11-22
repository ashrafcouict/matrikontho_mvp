def _format_pregnancy_summary(context):
    if not isinstance(context, dict):
        return ""

    status = context.get("pregnancy_status")
    weeks = context.get("gestational_weeks")

    parts = []
    if status == "pregnant":
        parts.append("গর্ভবতী")
    elif status == "not_pregnant":
        parts.append("গর্ভবতী নন")

    if isinstance(weeks, int) and weeks > 0:
        parts.append(f"{weeks} সপ্তাহ")

    return f" ({', '.join(parts)})" if parts else ""


def _format_reasons_summary(result, extraction):
    if isinstance(result, dict):
        reasons = result.get("reasons")
        if isinstance(reasons, list):
            cleaned = [r.strip() for r in reasons if isinstance(r, str) and r.strip()]
            if cleaned:
                return f" কারণ: {' / '.join(cleaned[:2])}"

    if isinstance(extraction, dict):
        symptoms = extraction.get("symptoms")
        if isinstance(symptoms, list):
            cleaned = [s.strip() for s in symptoms if isinstance(s, str) and s.strip()]
            if cleaned:
                return f" লক্ষণ: {', '.join(cleaned[:3])}।"

    return ""


def make_sms(
    result,
    patient_name="রোগী",
    phone_number="",
    context=None,
    extraction=None,
):
    """
    Generate a referral SMS draft. No SMS is actually sent.
    This is a screening summary, not a medical diagnosis.
    """
    clean_name = (
        patient_name.strip()
        if isinstance(patient_name, str) and patient_name.strip()
        else "রোগী"
    )

    if not isinstance(result, dict):
        return (
            f"মাতৃকণ্ঠ রেফারেল (যাচাই প্রয়োজন): {clean_name}। "
            "রোগীর তথ্য যাচাই করা প্রয়োজন। স্বাস্থ্যকর্মীর সঙ্গে যোগাযোগ করুন। "
            "এটি একটি প্রাথমিক স্ক্রিনিং বার্তা, চিকিৎসকের রোগনির্ণয় নয়।"
        )

    level = str(result.get("risk_level", "UNKNOWN")).upper()

    if level == "HIGH":
        urgency = "জরুরি"
        instruction = "দ্রুত নিকটস্থ হাসপাতালে যাওয়ার পরামর্শ দেওয়া হয়েছে।"
    elif level == "MODERATE":
        urgency = "দ্রুত পরামর্শ"
        instruction = "আজই স্বাস্থ্যকর্মী বা চিকিৎসকের সঙ্গে যোগাযোগ করুন।"
    elif level == "LOW":
        urgency = "নিয়মিত"
        instruction = "নিয়মিত চেকআপ চালিয়ে যান।"
    else:
        urgency = "যাচাই প্রয়োজন"
        instruction = "স্বাস্থ্যকর্মীর মাধ্যমে রোগীর অবস্থা যাচাই করুন।"

    preg_tag = _format_pregnancy_summary(context)
    details = _format_reasons_summary(result, extraction) if level != "LOW" else ""
    contact_note = (
        f" যোগাযোগ: {phone_number.strip()}।"
        if isinstance(phone_number, str) and phone_number.strip()
        else ""
    )

    return (
        f"মাতৃকণ্ঠ রেফারেল ({urgency}): {clean_name}{preg_tag}। "
        f"{instruction}{details}{contact_note} "
        f"এটি একটি প্রাথমিক স্ক্রিনিং বার্তা, চিকিৎসকের রোগনির্ণয় নয়।"
    )
