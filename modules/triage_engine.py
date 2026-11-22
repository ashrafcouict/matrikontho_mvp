
RED_FLAGS = {
    "bleeding": "গর্ভাবস্থায় রক্তপাতের কথা জানিয়েছেন।",
    "severe_headache": "তীব্র মাথাব্যথার কথা জানিয়েছেন।",
    "blurred_vision": "দৃষ্টিতে ঝাপসা বা সমস্যা হওয়ার কথা জানিয়েছেন।",
    "swelling_face_hands": "মুখ বা হাতে ফোলাভাবের কথা জানিয়েছেন।",
    "severe_abdominal_pain": "তীব্র পেটব্যথার কথা জানিয়েছেন।",
    "difficulty_breathing": "শ্বাসকষ্টের কথা জানিয়েছেন।",
    "convulsions": "খিঁচুনির কথা জানিয়েছেন।",
    "reduced_fetal_movement": "শিশুর নড়াচড়া কমে যাওয়ার কথা জানিয়েছেন।",
    "water_breaking": "গর্ভের পানি বের হওয়ার কথা জানিয়েছেন।",
}

MODERATE_FLAGS = {
    "fever": "জ্বরের কথা জানিয়েছেন।",
}


def assess(extraction):
    """
    Assign a screening priority from extracted symptoms.

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

    if not extraction.get("transcript", "").strip():
        return {
            "risk_level": "UNKNOWN",
            "reasons": ["কোনো বক্তব্য পাওয়া যায়নি।"],
            "recommendation": "আবার বক্তব্য রেকর্ড করুন অথবা স্বাস্থ্যকর্মীর সাহায্য নিন।",
            "requires_urgent_care": False,
            "assessment_reliable": False,
        }

    found_red_flags = [
        description
        for key, description in RED_FLAGS.items()
        if extraction.get(key) is True
    ]

    found_moderate_flags = [
        description
        for key, description in MODERATE_FLAGS.items()
        if extraction.get(key) is True
    ]

    # Any identified warning sign receives HIGH priority.
    if found_red_flags:
        return {
            "risk_level": "HIGH",
            "reasons": found_red_flags,
            "recommendation": (
                "দেরি না করে নিকটস্থ হাসপাতাল বা জরুরি মাতৃস্বাস্থ্য "
                "সেবাকেন্দ্রে যান। সম্ভব হলে একজন সহায়তাকারীকে সঙ্গে নিন।"
            ),
            "requires_urgent_care": True,
            "assessment_reliable": True,
        }

    # A fallback extraction is not sufficient to declare LOW risk.
    if extraction.get("extraction_method") != "gemini":
        return {
            "risk_level": "UNKNOWN",
            "reasons": [
                "স্বয়ংক্রিয় লক্ষণ শনাক্তকরণ নির্ভরযোগ্যভাবে সম্পন্ন হয়নি।"
            ],
            "recommendation": (
                "লক্ষণগুলো স্বাস্থ্যকর্মীকে সরাসরি জানান। "
                "প্রয়োজনে আবার স্পষ্ট করে বক্তব্য দিন।"
            ),
            "requires_urgent_care": False,
            "assessment_reliable": False,
        }

    # A successful extraction with moderate symptoms needs review.
    if found_moderate_flags:
        return {
            "risk_level": "MODERATE",
            "reasons": found_moderate_flags,
            "recommendation": (
                "আজই একজন স্বাস্থ্যকর্মী বা চিকিৎসকের সঙ্গে যোগাযোগ করুন। "
                "অবস্থা খারাপ হলে জরুরি চিকিৎসা নিন।"
            ),
            "requires_urgent_care": False,
            "assessment_reliable": True,
        }

    # Uncertain or incomplete extraction must not be labelled LOW.
    if extraction.get("needs_clarification"):
        return {
            "risk_level": "UNKNOWN",
            "reasons": ["আরও তথ্য প্রয়োজন।"],
            "recommendation": (
                "আরও বিস্তারিত তথ্য দিন অথবা স্বাস্থ্যকর্মীর সঙ্গে কথা বলুন।"
            ),
            "requires_urgent_care": False,
            "assessment_reliable": False,
        }

    # Only a successful extraction with no identified warning signs
    # reaches this category. This is still not a clinical clearance.
    return {
        "risk_level": "LOW",
        "reasons": [
            "প্রদত্ত বক্তব্যে এই প্রাথমিক স্ক্রিনিংয়ের সতর্কতামূলক "
            "লক্ষণ শনাক্ত হয়নি।"
        ],
        "recommendation": (
            "নিয়মিত ANC চেকআপ চালিয়ে যান। নতুন বা উদ্বেগজনক কোনো "
            "লক্ষণ দেখা দিলে দ্রুত স্বাস্থ্যকর্মীর সঙ্গে যোগাযোগ করুন।"
        ),
        "requires_urgent_care": False,
        "assessment_reliable": True,
    }
