
import json
import os
import re
import time

import streamlit as st
from google import genai
from google.genai.errors import APIError


def _get_api_settings():
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        model_name = st.secrets.get(
            "GEMINI_MODEL",
            "gemini-2.5-flash"
        )
    except Exception:
        api_key = os.getenv("GEMINI_API_KEY", "")
        model_name = os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash"
        )

    return api_key or os.getenv("GEMINI_API_KEY", ""), model_name


def _empty_extraction(transcript, method="fallback"):
    return {
        "transcript": transcript,
        "extraction_method": method,
        "extraction_success": False,
        "needs_clarification": True,
        "symptoms": [],
        "bleeding": None,
        "severe_headache": None,
        "blurred_vision": None,
        "swelling_face_hands": None,
        "severe_abdominal_pain": None,
        "fever": None,
        "difficulty_breathing": None,
        "convulsions": None,
        "reduced_fetal_movement": None,
        "water_breaking": None,
        "other_symptoms": [],
        "duration": None,
        "severity": None,
        "notes": "নির্ভরযোগ্যভাবে লক্ষণ শনাক্ত করা যায়নি।",
    }


def _parse_json(text):
    text = (text or "").strip()

    # Remove Markdown code fences if the model adds them.
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("Gemini did not return valid JSON.")
        return json.loads(match.group(0))


def _fallback_extraction(transcript):
    """
    Conservative keyword fallback.
    A keyword match is only a signal for further assessment,
    not a clinical diagnosis.
    """
    text = (transcript or "").lower()

    patterns = {
        "bleeding": [
            "রক্তপাত", "রক্ত যাচ্ছে", "রক্ত পড়ছে",
            "bleeding", "blood"
        ],
        "severe_headache": [
            "তীব্র মাথাব্যথা", "অনেক মাথা ব্যথা",
            "মাথা প্রচণ্ড ব্যথা"
        ],
        "blurred_vision": [
            "ঝাপসা", "চোখে ঝাপসা", "চোখে কম দেখি"
        ],
        "swelling_face_hands": [
            "মুখ ফুলে", "হাত ফুলে", "হঠাৎ ফুলে",
            "মুখ ও হাত ফুলে"
        ],
        "severe_abdominal_pain": [
            "তীব্র পেট ব্যথা", "প্রচণ্ড পেট ব্যথা",
            "পেটে অনেক ব্যথা"
        ],
        "fever": [
            "জ্বর", "অনেক জ্বর"
        ],
        "difficulty_breathing": [
            "শ্বাসকষ্ট", "শ্বাস নিতে কষ্ট",
            "দম নিতে কষ্ট"
        ],
        "convulsions": [
            "খিঁচুনি", "খিচুনি"
        ],
        "reduced_fetal_movement": [
            "বাচ্চা নড়ছে না", "বাচ্চা কম নড়ছে",
            "বাচ্চার নড়াচড়া কম"
        ],
        "water_breaking": [
            "পানি ভেঙে", "পানি বের হচ্ছে",
            "গর্ভের পানি"
        ],
    }

    result = _empty_extraction(transcript)

    found = []

    for symptom, keywords in patterns.items():
        matched = any(keyword in text for keyword in keywords)
        result[symptom] = True if matched else None

        if matched:
            found.append(symptom)

    result["symptoms"] = found
    result["other_symptoms"] = []
    result["extraction_method"] = "keyword_fallback"
    result["extraction_success"] = bool(found)
    result["needs_clarification"] = True

    if not found:
        result["notes"] = (
            "কোনো নির্দিষ্ট সতর্কতামূলক লক্ষণ শনাক্ত হয়নি। "
            "এটি লক্ষণ নেই—এমন প্রমাণ নয়।"
        )

    return result


def extract_symptoms(transcript):
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

        allowed_fields = [
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

        result = _empty_extraction(transcript, method="gemini")
        result["extraction_success"] = True
        result["needs_clarification"] = False

        for field in allowed_fields:
            value = data.get(field)

            if value not in (True, False, None):
                value = None

            result[field] = value

        result["symptoms"] = (
            data.get("symptoms")
            if isinstance(data.get("symptoms"), list)
            else []
        )

        result["other_symptoms"] = (
            data.get("other_symptoms")
            if isinstance(data.get("other_symptoms"), list)
            else []
        )

        result["duration"] = data.get("duration")
        result["severity"] = data.get("severity")
        result["notes"] = str(data.get("notes", ""))

        return result

    except Exception:
        # Do not expose API keys or raw provider errors to the user.
        return _fallback_extraction(transcript)
