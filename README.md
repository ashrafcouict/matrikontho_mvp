# মাতৃকণ্ঠ (Matrikontho)
Bangla voice-first maternal risk-screening hackathon MVP.

## What works
- Streamlit mobile-friendly UI, microphone/audio upload and text fallback.
- Optional Faster-Whisper Bangla ASR.
- Optional Gemini structured symptom extraction; deterministic keyword fallback if absent.
- Deterministic Python triage rules, Bangla advice, simulated referral SMS.
- SQLite case log and CSV dashboard.
- Automated unit tests and synthetic cases.

## Run locally
```bash
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
Copy `.env.example` to `.env` and set `GEMINI_API_KEY` only if using Gemini. Export variables in your shell; this MVP does not automatically load `.env`.

## Tests
```bash
pytest -q
```

## Safety
This is a demonstration, not a medical device or validated clinical decision support system. Rule thresholds and advice are provisional and must be reviewed by qualified maternal-health professionals against current WHO/DGHS protocols before any real-world use. Use synthetic data only.
