
import os
import tempfile
from pathlib import Path

from faster_whisper import WhisperModel


_MODEL = None


def _get_model():
    """Load Whisper once and reuse it during the Streamlit session."""
    global _MODEL

    if _MODEL is None:
        model_name = os.getenv("WHISPER_MODEL", "small")

        _MODEL = WhisperModel(
            model_name,
            device=os.getenv("WHISPER_DEVICE", "cpu"),
            compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        )

    return _MODEL


def _is_usable_bangla(text: str) -> bool:
    """Basic script-quality check, not a complete language detector."""
    text = (text or "").strip()

    if len(text) < 3:
        return False

    bangla_chars = sum(
        1 for char in text
        if "\u0980" <= char <= "\u09FF"
    )

    meaningful_chars = sum(1 for char in text if char.isalpha())

    if meaningful_chars == 0:
        return False

    return bangla_chars / meaningful_chars >= 0.35


def transcribe_audio(audio_file):
    """
    Accepts a Streamlit UploadedFile or file-like audio object.

    Returns:
        {
            "success": bool,
            "text": str,
            "error": str | None
        }
    """
    temp_path = None

    try:
        suffix = Path(getattr(audio_file, "name", "audio.wav")).suffix
        if not suffix:
            suffix = ".wav"

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as temp_file:
            audio_file.seek(0)
            temp_file.write(audio_file.read())
            temp_path = temp_file.name

        model = _get_model()

        segments, info = model.transcribe(
            temp_path,
            language="bn",
            task="transcribe",
            beam_size=5,
            temperature=0.0,
            vad_filter=True,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            log_prob_threshold=-1.0,
            compression_ratio_threshold=2.4,
            initial_prompt=(
                "বাংলা ভাষায় একজন গর্ভবতী নারী তার শারীরিক সমস্যা, "
                "গর্ভাবস্থার লক্ষণ এবং স্বাস্থ্যগত অবস্থা বর্ণনা করছেন।"
            ),
        )

        text = " ".join(
            segment.text.strip()
            for segment in segments
            if segment.text and segment.text.strip()
            and segment.no_speech_prob < 0.65
            and segment.avg_logprob > -1.1
            and segment.compression_ratio < 2.4
        ).strip()

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

    except Exception as exc:
        return {
            "success": False,
            "text": "",
            "error": f"অডিও প্রসেস করা যায়নি: {str(exc)}",
        }

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
