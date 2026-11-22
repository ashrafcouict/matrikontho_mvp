import json
from pathlib import Path

DEFAULT_RED_FLAGS = {
    "bleeding": "রক্তপাতের কথা জানিয়েছেন।",
    "severe_headache": "তীব্র মাথাব্যথার কথা জানিয়েছেন।",
    "blurred_vision": "দৃষ্টিতে ঝাপসা বা সমস্যা হওয়ার কথা জানিয়েছেন।",
    "swelling_face_hands": "মুখ বা হাতে ফোলাভাবের কথা জানিয়েছেন।",
    "severe_abdominal_pain": "তীব্র পেটব্যথার কথা জানিয়েছেন।",
    "difficulty_breathing": "শ্বাসকষ্টের কথা জানিয়েছেন।",
    "convulsions": "খিঁচুনির কথা জানিয়েছেন।",
    "reduced_fetal_movement": "শিশুর নড়াচড়া কমে যাওয়ার কথা জানিয়েছেন।",
    "water_breaking": "গর্ভের পানি বের হওয়ার কথা জানিয়েছেন।",
}

DEFAULT_MODERATE_FLAGS = {
    "fever": "জ্বরের কথা জানিয়েছেন।",
}


def _load_clinical_rules():
    """
    Load flag definitions from data/clinical_rules.json if present and valid,
    falling back safely to DEFAULT_RED_FLAGS / DEFAULT_MODERATE_FLAGS.
    """
    rules_path = Path(__file__).resolve().parent.parent / "data" / "clinical_rules.json"
    if not rules_path.exists():
        return dict(DEFAULT_RED_FLAGS), dict(DEFAULT_MODERATE_FLAGS)

    try:
        raw = json.loads(rules_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return dict(DEFAULT_RED_FLAGS), dict(DEFAULT_MODERATE_FLAGS)

        red = raw.get("red_flags")
        moderate = raw.get("moderate_flags")

        red_flags = (
            {k: str(v) for k, v in red.items() if isinstance(v, str)}
            if isinstance(red, dict) and red
            else dict(DEFAULT_RED_FLAGS)
        )
        moderate_flags = (
            {k: str(v) for k, v in moderate.items() if isinstance(v, str)}
            if isinstance(moderate, dict) and moderate
            else dict(DEFAULT_MODERATE_FLAGS)
        )
        return red_flags, moderate_flags
    except Exception:
        return dict(DEFAULT_RED_FLAGS), dict(DEFAULT_MODERATE_FLAGS)


RED_FLAGS, MODERATE_FLAGS = _load_clinical_rules()


def _format_flag_reason(key, default_desc, pregnancy_status, gestational_weeks):
    if key == "bleeding":
        if pregnancy_status == "pregnant":
            return "গর্ভাবস্থায় রক্তপাতের কথা জানিয়েছেন।"
        if pregnancy_status == "not_pregnant":
            return "অস্বাভাবিক রক্তপাতের কথা জানিয়েছেন।"
        return "রক্তপাতের কথা জানিয়েছেন (গর্ভাবস্থার তথ্য নিশ্চিত নয়)।"

    if key == "water_breaking" and isinstance(gestational_weeks, int) and 0 < gestational_weeks < 37:
        return f"নির্ধারিত সময়ের আগে ({gestational_weeks} সপ্তাহে) গর্ভের পানি বের হওয়ার কথা জানিয়েছেন।"

    if key == "reduced_fetal_movement" and isinstance(gestational_weeks, int) and gestational_weeks > 0:
        return f"{gestational_weeks} সপ্তাহে শিশুর নড়াচড়া কমে যাওয়ার কথা জানিয়েছেন।"

    return default_desc


def assess(extraction, context=None):
    """
    Assign a screening priority from extracted symptoms and optional pregnancy context.

    This is not a medical diagnosis or a validated clinical protocol.
    """
    if not isinstance(extraction, dict):
        return {
            "risk_level": "UNKNOWN",
            "reasons": ["লক্ষণসংক্রান্ত তথ্য পাওয়া যায়নি।"],
            "recommendation": (
                "স্বাস্থ্যকর্মীর সঙ্গে কথা বলুন। "
                "তথ্য না পাওয়াকে কম ঝুঁকি হিসেবে ধরা যাবে না।"
            ),
            "requires_urgent_care": False,
            "assessment_reliable": False,
        }

    transcript = extraction.get("transcript", "")
    if not isinstance(transcript, str) or not transcript.strip():
        return {
            "risk_level": "UNKNOWN",
            "reasons": ["কোনো বক্তব্য পাওয়া যায়নি।"],
            "recommendation": "আবার বক্তব্য রেকর্ড করুন অথবা স্বাস্থ্যকর্মীর সাহায্য নিন।",
            "requires_urgent_care": False,
            "assessment_reliable": False,
        }

    ctx = context if isinstance(context, dict) else {}
    pregnancy_status = ctx.get("pregnancy_status", "unknown")
    gestational_weeks = ctx.get("gestational_weeks")

    matched_red_keys = [
        key for key in RED_FLAGS if extraction.get(key) is True
    ]
    found_red_flags = [
        _format_flag_reason(key, RED_FLAGS[key], pregnancy_status, gestational_weeks)
        for key in matched_red_keys
    ]

    matched_moderate_keys = [
        key for key in MODERATE_FLAGS if extraction.get(key) is True
    ]
    found_moderate_flags = [
        MODERATE_FLAGS[key] for key in matched_moderate_keys
    ]

    other_symptoms = [
        s.strip()
        for s in (extraction.get("other_symptoms") or [])
        if isinstance(s, str) and s.strip()
    ]

    # Any identified warning sign receives HIGH priority—even if extracted via fallback.
    if found_red_flags:
        return {
            "risk_level": "HIGH",
            "reasons": found_red_flags,
            "matched_flags": matched_red_keys,
            "recommendation": (
                "দেরি না করে নিকটস্থ হাসপাতাল বা জরুরি মাতৃস্বাস্থ্য "
                "সেবাকেন্দ্রে যান। সম্ভব হলে একজন সহায়তাকারীকে সঙ্গে নিন।"
            ),
            "requires_urgent_care": True,
            "assessment_reliable": True,
        }

    # A fallback extraction is not sufficient to declare LOW or MODERATE safety.
    if extraction.get("extraction_method") != "gemini":
        return {
            "risk_level": "UNKNOWN",
            "reasons": [
                "স্বয়ংক্রিয় লক্ষণ শনাক্তকরণ নির্ভরযোগ্যভাবে সম্পন্ন হয়নি।"
            ],
            "matched_flags": matched_moderate_keys,
            "recommendation": (
                "লক্ষণগুলো স্বাস্থ্যকর্মীকে সরাসরি জানান। "
                "প্রয়োজনে আবার স্পষ্ট করে বক্তব্য দিন।"
            ),
            "requires_urgent_care": False,
            "assessment_reliable": False,
        }

    # A successful extraction with moderate symptoms or unmapped symptoms needs review.
    if found_moderate_flags or other_symptoms:
        reasons = list(found_moderate_flags)
        if other_symptoms:
            reasons.append(
                f"অতিরিক্ত উপসর্গ উল্লেখ করেছেন: {', '.join(other_symptoms)}।"
            )

        return {
            "risk_level": "MODERATE",
            "reasons": reasons,
            "matched_flags": matched_moderate_keys,
            "recommendation": (
                "আজই একজন স্বাস্থ্যকর্মী বা চিকিৎসকের সঙ্গে যোগাযোগ করুন। "
                "অবস্থা খারাপ হলে জরুরি চিকিৎসা নিন।"
            ),
            "requires_urgent_care": False,
            "assessment_reliable": True,
        }

    # Uncertain or incomplete extraction must not be labelled LOW.
    if extraction.get("needs_clarification") or extraction.get("extraction_success") is False:
        return {
            "risk_level": "UNKNOWN",
            "reasons": ["আরও তথ্য প্রয়োজন।"],
            "matched_flags": [],
            "recommendation": (
                "আরও বিস্তারিত তথ্য দিন অথবা স্বাস্থ্যকর্মীর সঙ্গে কথা বলুন।"
            ),
            "requires_urgent_care": False,
            "assessment_reliable": False,
        }

    low_reasons = [
        "প্রদত্ত বক্তব্যে এই প্রাথমিক স্ক্রিনিংয়ের সতর্কতামূলক "
        "লক্ষণ শনাক্ত হয়নি।"
    ]
    if pregnancy_status == "unknown":
        low_reasons.append(
            "গর্ভাবস্থার তথ্য নিশ্চিত করা হয়নি—প্রয়োজনে স্বাস্থ্যকর্মীর মাধ্যমে যাচাই করুন।"
        )

    return {
        "risk_level": "LOW",
        "reasons": low_reasons,
        "matched_flags": [],
        "recommendation": (
            "নিয়মিত ANC চেকআপ চালিয়ে যান। নতুন বা উদ্বেগজনক কোনো "
            "লক্ষণ দেখা দিলে দ্রুত স্বাস্থ্যকর্মীর সঙ্গে যোগাযোগ করুন।"
        ),
        "requires_urgent_care": False,
        "assessment_reliable": True,
    }
