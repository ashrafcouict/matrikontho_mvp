import mimetypes
import os
import tempfile
import threading
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
    api_key = ""
    model_name = "gemini-2.5-flash"

    try:
        if "GEMINI_API_KEY" in st.secrets:
            api_key = str(st.secrets["GEMINI_API_KEY"] or "").strip()
        if "GEMINI_MODEL" in st.secrets:
            model_name = str(st.secrets["GEMINI_MODEL"] or "gemini-2.5-flash").strip()
    except Exception:
        pass

    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if os.getenv("GEMINI_MODEL"):
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

    return api_key, model_name or "gemini-2.5-flash"


def _default_compute_type(device: str) -> str:
    explicit = os.getenv("WHISPER_COMPUTE_TYPE", "").strip()
    if explicit:
        return explicit
    return "float16" if device.lower() == "cuda" else "int8"


def _load_whisper_model():
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


def _transcribe_with_gemini(payload: bytes, suffix: str) -> tuple[str, str | None]:
    api_key, model_name = _get_gemini_settings()
    if not api_key:
        return "", "GEMINI_API_KEY পাওয়া যায়নি।"

    mime_type = (
        MIME_BY_EXT.get(suffix.lower())
        or mimetypes.guess_type(f"audio{suffix}")[0]
        or "audio/wav"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_bytes(data=payload, mime_type=mime_type),
                (
                    "এই অডিওতে বলা বাংলা কথা হুবহু বাংলা লিপিতে লিখে দাও। "
                    "কোনো অনুবাদ বা অতিরিক্ত মন্তব্য লিখবে না। "
                    "অডিওতে কোনো স্পষ্ট কথা না থাকলে শুধু খালি উত্তর দাও।"
                ),
            ],
        )
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            return "", "অডিওতে কোনো স্পষ্ট কথা শনাক্ত হয়নি।"
        return text, None
    except Exception as exc:
        return "", f"Gemini অডিও ট্রান্সক্রিপশন ব্যর্থ হয়েছে: {exc}"


def _collect_whisper_transcript(model, temp_path: str, vad_filter: bool) -> str:
    kwargs = {
        "language": "bn",
        "task": "transcribe",
        "beam_size": 5,
        "temperature": [0.0, 0.2],
        "vad_filter": vad_filter,
        "condition_on_previous_text": False,
        "no_speech_threshold": 0.9,
        "log_prob_threshold": -2.5,
        "compression_ratio_threshold": 3.0,
        "initial_prompt": (
            "বাংলা ভাষায় একজন নারী তার শারীরিক সমস্যা, "
            "গর্ভাবস্থার লক্ষণ এবং স্বাস্থ্যগত অবস্থা বর্ণনা করছেন।"
        ),
    }
    if vad_filter:
        kwargs["vad_parameters"] = {
            "threshold": 0.3,
            "min_speech_duration_ms": 100,
            "min_silence_duration_ms": 700,
            "speech_pad_ms": 600,
        }

    segments, _info = model.transcribe(temp_path, **kwargs)
    return " ".join(
        segment.text.strip()
        for segment in segments
        if getattr(segment, "text", None) and segment.text.strip()
    ).strip()


def _transcribe_with_whisper(payload: bytes, suffix: str) -> tuple[str, str | None]:
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(payload)
            temp_path = temp_file.name

        model = _load_whisper_model()
        text = _collect_whisper_transcript(model, temp_path, vad_filter=True)
        if not text:
            text = _collect_whisper_transcript(model, temp_path, vad_filter=False)

        if not text:
            return "", "Whisper থেকে কোনো কথা শনাক্ত হয়নি।"
        return text, None
    except ImportError:
        return "", "faster-whisper ইনস্টল করা নেই।"
    except Exception as exc:
        return "", f"Whisper অডিও প্রসেসিং ব্যর্থ হয়েছে: {exc}"
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def transcribe_audio(audio_file):
    """
    Transcribe audio using Gemini (preferred when API key is configured)
    with fallback to faster-whisper if available.
    """
    if audio_file is None or not callable(getattr(audio_file, "read", None)):
        return {
            "success": False,
            "text": "",
            "error": "কোনো বৈধ অডিও ইনপুট পাওয়া যায়নি। অনুগ্রহ করে আবার চেষ্টা করুন।",
        }

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
    api_key, _ = _get_gemini_settings()
    errors = []

    # 1. Try Gemini first in auto/gemini mode when GEMINI_API_KEY is available
    if backend in ("auto", "gemini") and api_key:
        text, err = _transcribe_with_gemini(payload, suffix)
        if text:
            return {"success": True, "text": text, "error": None}
        if err:
            errors.append(err)

    # 2. Try local faster-whisper in auto/whisper mode
    if backend in ("auto", "whisper"):
        text, err = _transcribe_with_whisper(payload, suffix)
        if text:
            return {"success": True, "text": text, "error": None}
        if err:
            errors.append(err)

    # 3. Last-resort Gemini attempt if not already run
    if backend == "whisper" and api_key:
        text, err = _transcribe_with_gemini(payload, suffix)
        if text:
            return {"success": True, "text": text, "error": None}
        if err:
            errors.append(err)

    detail = f" ({' | '.join(errors)})" if errors else ""
    return {
        "success": False,
        "text": "",
        "error": (
            "অডিও থেকে কথা শনাক্ত করা যায়নি। আবার স্পষ্টভাবে রেকর্ড করুন "
            f"অথবা নিচে লিখে দিন।{detail}"
        ),
    }
