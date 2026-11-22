import os, tempfile
def transcribe_audio(uploaded_file):
    """Optional Faster-Whisper ASR. Failure never means symptom absence."""
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return "", "Whisper ইনস্টল নেই। আপাতত টেক্সট বক্সে লিখুন।"
    path = None
    try:
        suffix = os.path.splitext(getattr(uploaded_file, "name", "audio.wav"))[1] or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(uploaded_file.getvalue()); path=f.name
        model_name = os.getenv("WHISPER_MODEL", "small")
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(path, language="bn", vad_filter=True)
        text = " ".join(s.text.strip() for s in segments).strip()
        if not text: return "", "কথা বোঝা যায়নি। আবার বলুন বা লিখে দিন।"
        return text, None
    except Exception as e:
        return "", f"অডিও প্রক্রিয়াকরণ সম্ভব হয়নি: {e}"
    finally:
        if path and os.path.exists(path): os.remove(path)
