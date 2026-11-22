
import os
import re
import tempfile
from pathlib import Path


def is_reliable_bangla(text):
    if not text or not text.strip():
        return False

    letters = [c for c in text if c.isalpha()]
    bangla = [c for c in letters if "\u0980" <= c <= "\u09FF"]

    if len(bangla) < 3:
        return False

    # Reject output dominated by non-Bangla scripts.
    if len(letters) >= 10:
        ratio = len(bangla) / len(letters)
        if ratio < 0.65:
            return False

    return True


def transcribe_audio(uploaded_file):
    temp_path = None

    try:
        from faster_whisper import WhisperModel

        suffix = Path(
            getattr(uploaded_file, "name", "recording.wav")
        ).suffix or ".wav"

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix
        ) as tmp:
            tmp.write(uploaded_file.getvalue())
            temp_path = tmp.name

        model_name = os.getenv("WHISPER_MODEL", "small")

        model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8"
        )

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
                "বাংলা কথোপকথন। মাতৃস্বাস্থ্য, গর্ভাবস্থা, "
                "মাথাব্যথা, জ্বর, রক্তপাত, শিশুর নড়াচড়া।"
            )
        )

        accepted = []

        for segment in segments:
            text = (segment.text or "").strip()

            if not text:
                continue

            if segment.no_speech_prob > 0.65:
                continue

            if segment.avg_logprob < -1.1:
                continue

            if segment.compression_ratio > 2.4:
                continue

            accepted.append(text)

        transcript = " ".join(accepted)
        transcript = re.sub(r"\s+", " ", transcript).strip()

        if not transcript:
            return "", (
                "কোনো নির্ভরযোগ্য কথা শনাক্ত করা যায়নি। "
                "আবার ৫–১০ সেকেন্ড স্পষ্টভাবে বাংলায় বলুন।"
            )

        if not is_reliable_bangla(transcript):
            return "", (
                "নির্ভরযোগ্য বাংলা ট্রান্সক্রিপশন পাওয়া যায়নি। "
                "আবার চেষ্টা করুন অথবা সরাসরি লিখুন।"
            )

        if info.language != "bn":
            return "", (
                "অডিওর ভাষা বাংলা হিসেবে নিশ্চিত করা যায়নি। "
                "দয়া করে আবার বাংলায় রেকর্ড করুন।"
            )

        return transcript, None

    except Exception:
        return "", (
            "অডিও প্রক্রিয়াকরণে সমস্যা হয়েছে। "
            "আবার চেষ্টা করুন অথবা লিখে দিন।"
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
