import json
import os
import re
import time

import streamlit as st
from google import genai
from google.genai.errors import APIError

SYMPTOM_FIELDS = [
    "bleeding",
    "severe_headache",
    "blurred_vision",
    "swelling_face_hands",
    "severe_abdominal_pain",
    "fever",
    "difficulty_breathing",
    "convulsions",
    "reduced_fetal_movement",
    "water_breaking",
]

NEGATION_MARKERS = [
    "নেই",
    "নাই",
    "হচ্ছে না",
    "হয় না",
    "হয় না",
    "পড়ছে না",
    "পড়ছে না",
    "যাচ্ছে না",
    "নড়ছে না",
    "নড়ছে না",
    "কম নড়ছে",
    "কম নড়ছে",
    "no ",
    "not ",
    "without ",
]


def _get_api_settings():
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        model_name = st.secrets.get(
            "GEMINI_MODEL",
            "gemini-2.5-flash",
        )
    except Exception:
        api_key = os.getenv("GEMINI_API_KEY", "")
        model_name = os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash",
        )

    return (api_key or os.getenv("GEMINI_API_KEY", "")).strip(), model_name


def _empty_extraction(transcript, method="fallback"):
    data = {
        "transcript": transcript,
        "extraction_method": method,
        "extraction_success": False,
        "needs_clarification": True,
        "symptoms": [],
    }
    for field in SYMPTOM_FIELDS:
        data[field] = None
    data.update(
        {
            "other_symptoms": [],
            "duration": None,
            "severity": None,
            "notes": "নির্ভরযোগ্যভাবে লক্ষণ শনাক্ত করা যায়নি।",
        }
    )
    return data


def _parse_json(text):
    cleaned = (text or "").strip()

    # Remove Markdown code fences if the model adds them.
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        if start == -1:
            raise ValueError("Gemini did not return valid JSON.")
        decoder = json.JSONDecoder()
        parsed, _ = decoder.raw_decode(cleaned[start:])

    if not isinstance(parsed, dict):
        raise ValueError("Top-level JSON value must be an object.")

    return parsed


def _sanitize_str_list(value):
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text and text not in items:
                items.append(text)
    return items


def _is_negated_around(text, keyword):
    """Heuristic check for Bangla/English negation near a matched keyword."""
    idx = text.find(keyword)
    if idx == -1:
        return False

    window_start = max(0, idx - 12)
    window_end = min(len(text), idx + len(keyword) + 24)
    window = text[window_start:window_end]

    return any(marker in window for marker in NEGATION_MARKERS)


def _fallback_extraction(transcript):
    """
    Conservative keyword fallback.
    A keyword match is only a signal for further assessment,
    not a clinical diagnosis.
    """
    text = (transcript or "").lower()

    patterns = {
        "bleeding": [
            "রক্তপাত",
            "রক্ত যাচ্ছে",
            "রক্ত পড়ছে",
            "রক্ত পড়ছে",
            "bleeding",
            "blood",
        ],
        "severe_headache": [
            "তীব্র মাথাব্যথা",
            "অনেক মাথা ব্যথা",
            "মাথা প্রচণ্ড ব্যথা",
            "মাথা প্রচন্ড ব্যথা",
        ],
        "blurred_vision": [
            "ঝাপসা",
            "চোখে ঝাপসা",
            "চোখে কম দেখি",
        ],
        "swelling_face_hands": [
            "মুখ ফুলে",
            "হাত ফুলে",
            "হঠাৎ ফুলে",
            "মুখ ও হাত ফুলে",
        ],
        "severe_abdominal_pain": [
            "তীব্র পেট ব্যথা",
            "প্রচণ্ড পেট ব্যথা",
            "প্রচন্ড পেট ব্যথা",
            "পেটে অনেক ব্যথা",
        ],
        "fever": [
            "জ্বর",
            "অনেক জ্বর",
        ],
        "difficulty_breathing": [
            "শ্বাসকষ্ট",
            "শ্বাস নিতে কষ্ট",
            "দম নিতে কষ্ট",
        ],
        "convulsions": [
            "খিঁচুনি",
            "খিচুনি",
        ],
        "reduced_fetal_movement": [
            "বাচ্চা নড়ছে না",
            "বাচ্চা নড়ছে না",
            "বাচ্চা কম নড়ছে",
            "বাচ্চা কম নড়ছে",
            "বাচ্চার নড়াচড়া কম",
            "বাচ্চার নড়াচড়া কম",
        ],
        "water_breaking": [
            "পানি ভেঙে",
            "পানি ভেঙ্গে",
            "পানি বের হচ্ছে",
            "গর্ভের পানি",
        ],
    }

    result = _empty_extraction(transcript, method="keyword_fallback")
    found = []

    for symptom, keywords in patterns.items():
        positive_match = False
        negated_match = False

        for keyword in keywords:
            if keyword in text:
                if _is_negated_around(text, keyword):
                    negated_match = True
                else:
                    positive_match = True
                    break

        if positive_match:
            result[symptom] = True
            found.append(symptom)
        elif negated_match:
            result[symptom] = False
        else:
            result[symptom] = None

    result["symptoms"] = found
    result["other_symptoms"] = []
    result["extraction_success"] = bool(found)
    result["needs_clarification"] = True

    if not found:
        result["notes"] = (
            "কোনো নির্দিষ্ট সতর্কতামূলক লক্ষণ শনাক্ত হয়নি। "
            "এটি লক্ষণ নেই—এমন প্রমাণ নয়।"
        )

    return result


def _format_context_block(context):
    if not isinstance(context, dict) or not context:
        return "Context: Not provided."

    status = context.get("pregnancy_status") or "unknown"
    weeks = context.get("gestational_weeks")
    weeks_text = f"{weeks} weeks" if weeks is not None else "unknown/not provided"
    return f"Context: pregnancy_status={status}, gestational_weeks={weeks_text}"


def extract_symptoms(transcript, context=None):
    """
    Extract symptom information from a Bangla transcript.

    Returns a structured dictionary. If the API is unavailable,
    returns conservative fallback data.
    """
    transcript = (transcript or "").strip()

    if len(transcript) < 3:
        return _empty_extraction(transcript)

    api_key, model_name = _get_api_settings()

    if not api_key:
        return _fallback_extraction(transcript)

    context_line = _format_context_block(context)

    prompt = f"""
তুমি মাতৃকণ্ঠ নামের একটি maternal-health screening support system-এর
symptom extraction component।

কাজ:
ব্যবহারকারীর বাংলা বক্তব্য থেকে কেবল স্পষ্টভাবে বলা লক্ষণগুলো শনাক্ত করো।
কোনো রোগ নির্ণয় করবে না। কোনো তথ্য অনুমান করবে না।
কোনো লক্ষণ উল্লেখ না থাকলে সেটিকে false লিখবে না; null লিখবে।
লক্ষণটি স্পষ্টভাবে অস্বীকার করলে false লিখবে।
অস্পষ্ট হলে null লিখবে।

শুধু valid JSON দেবে। কোনো Markdown বা অতিরিক্ত ব্যাখ্যা দেবে না।

JSON schema:
{{
  "symptoms": [],
  "bleeding": null,
  "severe_headache": null,
  "blurred_vision": null,
  "swelling_face_hands": null,
  "severe_abdominal_pain": null,
  "fever": null,
  "difficulty_breathing": null,
  "convulsions": null,
  "reduced_fetal_movement": null,
  "water_breaking": null,
  "other_symptoms": [],
  "duration": null,
  "severity": null,
  "notes": ""
}}

Boolean fields must be true, false, or null.
symptoms and other_symptoms must be arrays of strings.
Do not add keys outside this schema.

{context_line}
User statement:
{transcript}
"""

    try:
        client = genai.Client(api_key=api_key)

        response = None
        last_error = None

        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                break
            except APIError as exc:
                last_error = exc
                status = str(getattr(exc, "code", ""))

                if status not in {"429", "500", "502", "503", "504"}:
                    raise

                if attempt == 2:
                    raise

                time.sleep(2 ** (attempt + 1))

        if response is None:
            raise last_error or RuntimeError("No response from Gemini.")

        raw_text = getattr(response, "text", None)

        if not raw_text:
            raise ValueError("Gemini returned an empty response.")

        data = _parse_json(raw_text)

        result = _empty_extraction(transcript, method="gemini")
        result["extraction_success"] = True
        result["needs_clarification"] = False

        detected_flags = []
        for field in SYMPTOM_FIELDS:
            value = data.get(field)
            if value not in (True, False, None):
                value = None
            result[field] = value
            if value is True:
                detected_flags.append(field)

        raw_symptoms = _sanitize_str_list(data.get("symptoms"))
        merged_symptoms = list(detected_flags)
        for item in raw_symptoms:
            if item not in merged_symptoms:
                merged_symptoms.append(item)

        result["symptoms"] = merged_symptoms
        result["other_symptoms"] = _sanitize_str_list(data.get("other_symptoms"))

        duration = data.get("duration")
        result["duration"] = duration.strip() if isinstance(duration, str) and duration.strip() else None

        severity = data.get("severity")
        result["severity"] = severity.strip() if isinstance(severity, str) and severity.strip() else None

        notes = data.get("notes")
        result["notes"] = notes.strip() if isinstance(notes, str) else ""

        return result

    except Exception:
        # Do not expose API keys or raw provider errors to the user.
        return _fallback_extraction(transcript)
