import mimetypes
import os
import tempfile
import threading
import unicodedata
from pathlib import Path

from google import genai
from google.genai import types
import streamlit as st

_MODEL = None
_MODEL_LOCK = threading.Lock()

MIME_BY_EXT = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
    ".flac": "audio/flac",
}


def _get_gemini_settings():
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        model_name = st.secrets.get("GEMINI_MODEL", "gemini-2.5-flash")
    except Exception:
        api_key = os.getenv("GEMINI_API_KEY", "")
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    return (api_key or os.getenv("GEMINI_API_KEY", "")).strip(), (
        model_name or "gemini-2.5-flash"
    ).strip()


def _default_compute_type(device: str) -> str:
    explicit = os.getenv("WHISPER_COMPUTE_TYPE", "").strip()
    if explicit:
        return explicit
    return "float16" if device.lower() == "cuda" else "int8"


def _load_whisper_model():
    """Import and initialize faster-whisper lazily so module import never crashes."""
    global _MODEL

    if _MODEL is not None:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is None:
            from faster_whisper import WhisperModel

            model_name = os.getenv("WHISPER_MODEL", "small").strip() or "small"
            device = os.getenv("WHISPER_DEVICE", "cpu").strip() or "cpu"
            compute_type = _default_compute_type(device)

            _MODEL = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
            )

    return _MODEL


def _is_usable_bangla(text: str) -> bool:
    """Basic script-quality check for Bangla transcripts."""
    cleaned = (text or "").strip()
    if len(cleaned) < 2:
        return False

    bangla_chars = 0
    latin_chars = 0
    content_chars = 0

    for char in cleaned:
        category = unicodedata.category(char)
        if category.startswith(("Z", "P", "S")):
            continue

        content_chars += 1
        if "\u0980" <= char <= "\u09FF":
            bangla_chars += 1
        elif ("A" <= char <= "Z") or ("a" <= char <= "z"):
            latin_chars += 1

    if content_chars == 0:
        return False

    if latin_chars > bangla_chars and bangla_chars == 0:
        return False

    return (bangla_chars / content_chars) >= 0.35


def _transcribe_with_gemini(payload: bytes, suffix: str) -> str:
    api_key, model_name = _get_gemini_settings()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    mime_type = (
        MIME_BY_EXT.get(suffix.lower())
        or mimetypes.guess_type(f"audio{suffix}")[0]
        or "audio/wav"
    )

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_bytes(data=payload, mime_type=mime_type),
            (
                "এই অডিওতে বলা বাংলা কথা হুবহু বাংলা লিপিতে লিখে দাও। "
                "কোনো ইংরেজি অনুবাদ, ভূমিকা বা অতিরিক্ত মন্তব্য করবে না।"
            ),
        ],
    )
    return (getattr(response, "text", None) or "").strip()


def _collect_whisper_transcript(model, temp_path: str, vad_filter: bool) -> str:
    kwargs = {
        "language": "bn",
        "task": "transcribe",
        "beam_size": 5,
        "temperature": [0.0, 0.2],
        "vad_filter": vad_filter,
        "condition_on_previous_text": False,
        "no_speech_threshold": 0.85,
        "log_prob_threshold": -2.0,
        "compression_ratio_threshold": 2.8,
        "initial_prompt": (
            "বাংলা ভাষায় একজন নারী তার শারীরিক সমস্যা, "
            "গর্ভাবস্থার লক্ষণ এবং স্বাস্থ্যগত অবস্থা বর্ণনা করছেন।"
        ),
    }
    if vad_filter:
        kwargs["vad_parameters"] = {
            "threshold": 0.35,
            "min_speech_duration_ms": 150,
            "min_silence_duration_ms": 600,
            "speech_pad_ms": 500,
        }

    segments, _info = model.transcribe(temp_path, **kwargs)

    return " ".join(
        segment.text.strip()
        for segment in segments
        if getattr(segment, "text", None)
        and segment.text.strip()
        and getattr(segment, "no_speech_prob", 0.0) < 0.90
        and getattr(segment, "avg_logprob", 0.0) > -2.0
        and getattr(segment, "compression_ratio", 1.0) < 2.8
    ).strip()


def _transcribe_with_whisper(payload: bytes, suffix: str) -> str:
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(payload)
            temp_path = temp_file.name

        model = _load_whisper_model()
        text = _collect_whisper_transcript(model, temp_path, vad_filter=True)
        if not text:
            text = _collect_whisper_transcript(model, temp_path, vad_filter=False)
        return text
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def transcribe_audio(audio_file):
    """
    Transcribe a Streamlit UploadedFile, recorded audio buffer, or file-like object.

    Returns:
        {
            "success": bool,
            "text": str,
            "error": str | None,
        }
    """
    if audio_file is None or not callable(getattr(audio_file, "read", None)):
        return {
            "success": False,
            "text": "",
            "error": "কোনো বৈধ অডিও ইনপুট পাওয়া যায়নি। অনুগ্রহ করে আবার চেষ্টা করুন।",
        }

    try:
        raw_name = getattr(audio_file, "name", "") or "audio.wav"
        suffix = Path(raw_name).suffix.lower()
        if suffix not in MIME_BY_EXT:
            suffix = ".wav"

        seeker = getattr(audio_file, "seek", None)
        if callable(seeker):
            seeker(0)

        payload = audio_file.read()
        if not payload:
            return {
                "success": False,
                "text": "",
                "error": "অডিও ফাইলটি খালি। অনুগ্রহ করে আবার রেকর্ড করুন বা আপলোড করুন।",
            }

        backend = os.getenv("ASR_BACKEND", "auto").strip().lower()
        text = ""

        if backend != "gemini":
            try:
                text = _transcribe_with_whisper(payload, suffix)
            except ImportError:
                if backend == "whisper":
                    return {
                        "success": False,
                        "text": "",
                        "error": (
                            "faster-whisper ইনস্টল করা নেই। "
                            "requirements.txt-এ faster-whisper যুক্ত করুন অথবা GEMINI_API_KEY সেট করুন।"
                        ),
                    }
                text = ""

        if not text and backend != "whisper":
            try:
                text = _transcribe_with_gemini(payload, suffix)
            except Exception:
                if not text:
                    return {
                        "success": False,
                        "text": "",
                        "error": "অডিও প্রসেস করা যায়নি। অনুগ্রহ করে আবার চেষ্টা করুন বা নিচে লিখে দিন।",
                    }

        if not text:
            return {
                "success": False,
                "text": "",
                "error": "কথা স্পষ্টভাবে বোঝা যায়নি। অনুগ্রহ করে আবার রেকর্ড করুন।",
            }

        if not _is_usable_bangla(text):
            return {
                "success": False,
                "text": "",
                "error": (
                    "অডিও থেকে নির্ভরযোগ্য বাংলা লেখা পাওয়া যায়নি। "
                    "অনুগ্রহ করে আবার ধীরে ও স্পষ্টভাবে বলুন।"
                ),
            }

        return {
            "success": True,
            "text": text,
            "error": None,
        }

    except Exception:
        return {
            "success": False,
            "text": "",
            "error": "অডিও প্রসেস করা যায়নি। ফাইলটি সঠিক কি না যাচাই করে আবার চেষ্টা করুন।",
        }
