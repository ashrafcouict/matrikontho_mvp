import json
import logging
import os
import re

import streamlit as st

from modules.conversation import fallback_extract

logger = logging.getLogger(__name__)

SYSTEM = """You extract only explicitly stated maternal symptoms from Bangla. Return valid JSON only.
Schema: pregnancy_status (pregnant/not_pregnant/unknown), gestational_age_weeks (integer/null),
symptoms: array of {name, present (true/false/null), severity (mild/moderate/severe/unknown),
duration, evidence}, missing_information (array), uncertainty (array).
Recognized names: vaginal_bleeding, convulsions, headache, blurred_vision, facial_hand_swelling,
fever, reduced_fetal_movement, abdominal_pain, breathing_difficulty, severe_weakness.
Never infer absence from silence. Null means unknown. Preserve uncertainty. Do not classify risk."""

DEFAULT_MODEL = "gemini-3.8-flash"


def get_gemini_key():
    """Read Streamlit Cloud secrets first, then local environment variables."""
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        key = ""

    return key or os.getenv("GEMINI_API_KEY", "")


def _fallback(transcript, pregnancy_status, gestational_age_weeks, reason=None):
    data = fallback_extract(
        transcript,
        pregnancy_status,
        gestational_age_weeks,
    )
    data["extraction_method"] = "fallback"

    if reason:
        data.setdefault("uncertainty", [])
        data["uncertainty"].append(
            "Gemini ব্যবহার করা যায়নি; স্থানীয় keyword fallback ব্যবহার করা হয়েছে."
        )
        # Keep the technical detail in server logs, not in the patient-facing output.

    return normalize(data)


def extract_symptoms(
    transcript,
    pregnancy_status="unknown",
    gestational_age_weeks=None,
):
    key = get_gemini_key()

    if not key:
        logger.warning("GEMINI_API_KEY not found; using local fallback.")
        return _fallback(
            transcript,
            pregnancy_status,
            gestational_age_weeks,
            reason="missing_api_key",
        )

    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)

    try:
        from google import genai

        client = genai.Client(api_key=key)
        prompt = (
            f"{SYSTEM}\n"
            f"Context pregnancy_status={pregnancy_status}, "
            f"gestational_age_weeks={gestational_age_weeks}\n"
            f"Transcript: {transcript}"
        )

        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )

        raw = (response.text or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)

        if not isinstance(data, dict):
            raise ValueError("Gemini response was not a JSON object.")

        if pregnancy_status != "unknown":
            data["pregnancy_status"] = pregnancy_status

        if gestational_age_weeks is not None:
            data["gestational_age_weeks"] = gestational_age_weeks

        data["source_transcript"] = transcript
        data["extraction_method"] = "gemini"

        return normalize(data)

    except Exception:
        # The full exception is available in Streamlit Cloud logs for debugging.
        logger.exception("Gemini extraction failed; switching to local fallback.")
        return _fallback(
            transcript,
            pregnancy_status,
            gestational_age_weeks,
            reason="gemini_request_failed",
        )


def normalize(data):
    allowed = {
        "vaginal_bleeding",
        "convulsions",
        "headache",
        "blurred_vision",
        "facial_hand_swelling",
        "fever",
        "reduced_fetal_movement",
        "abdominal_pain",
        "breathing_difficulty",
        "severe_weakness",
    }

    out = []
    for symptom in data.get("symptoms", []):
        if (
            isinstance(symptom, dict)
            and symptom.get("name") in allowed
            and symptom.get("present") in (True, False, None)
        ):
            out.append(
                {
                    key: symptom.get(key)
                    for key in [
                        "name",
                        "present",
                        "severity",
                        "duration",
                        "evidence",
                    ]
                }
            )

    data["symptoms"] = out
    data.setdefault("missing_information", [])
    data.setdefault("uncertainty", [])
    data.setdefault("source_transcript", "")
    data.setdefault("extraction_method", "unknown")
    return data
