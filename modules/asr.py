import os
import tempfile
import threading
import unicodedata
from pathlib import Path

from faster_whisper import WhisperModel

_MODEL = None
_MODEL_LOCK = threading.Lock()


def _default_compute_type(device: str) -> str:
    explicit = os.getenv("WHISPER_COMPUTE_TYPE", "").strip()
    if explicit:
        return explicit
    return "float16" if device.lower() == "cuda" else "int8"


def _get_model() -> WhisperModel:
    """Load Whisper once and reuse it safely across requests."""
    global _MODEL

    if _MODEL is not None:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is None:
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
    """
    Basic script-quality check for Bangla transcripts.
    Not a full language detector; allows occasional English medical terms
    while rejecting mostly non-Bangla or noise output.
    """
    cleaned = (text or "").strip()
    if len(cleaned) < 2:
        return False

    bangla_chars = 0
    latin_chars = 0
    content_chars = 0

    for char in cleaned:
        category = unicodedata.category(char)
        # Skip whitespace and punctuation/symbols when measuring script ratio
        if category.startswith(("Z", "P", "S")):
            continue

        content_chars += 1
        if "\u0980" <= char <= "\u09FF":
            bangla_chars += 1
        elif ("A" <= char <= "Z") or ("a" <= char <= "z"):
            latin_chars += 1

    if content_chars == 0:
        return False

    # Reject transcripts dominated by Latin characters (e.g., accidental English song/noise)
    if latin_chars > bangla_chars and bangla_chars == 0:
        return False

    return (bangla_chars / content_chars) >= 0.35


def _collect_transcript(model: WhisperModel, temp_path: str, vad_filter: bool) -> str:
    """Run Whisper transcription with optional VAD and return joined segment text."""
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


def transcribe_audio(audio_file):
    """
    Accepts a Streamlit UploadedFile, recorded audio buffer, or file-like object.

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

    temp_path = None

    try:
        raw_name = getattr(audio_file, "name", "") or "audio.wav"
        suffix = Path(raw_name).suffix.lower()
        if suffix not in {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}:
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

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(payload)
            temp_path = temp_file.name

        model = _get_model()

        text = _collect_transcript(model, temp_path, vad_filter=True)

        # Retry without VAD in case leading silence, short clips, or low mic gain caused VAD to drop speech
        if not text:
            text = _collect_transcript(model, temp_path, vad_filter=False)

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

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
