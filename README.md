# মাতৃকণ্ঠ (Matrikontho)
Bangla voice-first maternal risk-screening hackathon MVP.

## Quick start (uv)
```bash
# 1. install uv (once) — see "Install uv" below for Windows
# 2. from the project folder:
uv sync                      # install Python 3.12 + all dependencies into .venv
uv run streamlit run app.py  # start the app → http://localhost:8501
```
Add your Gemini key in `.streamlit/secrets.toml` for fast voice transcription (see step 3 below).

## What works
- Streamlit mobile-friendly UI, microphone/audio upload and text fallback.
- Optional Faster-Whisper Bangla ASR.
- Optional Gemini structured symptom extraction; deterministic keyword fallback if absent.
- Deterministic Python triage rules, Bangla advice, simulated referral SMS.
- SQLite case log and CSV dashboard.
- Automated unit tests and synthetic cases.

## Run locally

### 1. Install uv
[uv](https://docs.astral.sh/uv/) manages Python, the virtual environment and the dependencies.

**Linux / macOS**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# then open a new terminal (or run: source $HOME/.local/bin/env)
uv --version
```

**Windows (PowerShell)**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# then open a new PowerShell window
uv --version
```
Alternatives: `winget install --id=astral-sh.uv -e` (Windows) or `pipx install uv` / `pip install uv` (any OS).

### 2. Install dependencies and run
```bash
uv sync                      # creates .venv with Python 3.12 and installs everything from uv.lock
uv run streamlit run app.py  # opens http://localhost:8501
```
You don't need to activate the venv; `uv run` uses it automatically. uv downloads Python 3.12 if it isn't installed (the project supports 3.11–3.12).

Without uv, plain pip still works:
```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS:        source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### Everyday uv commands
| What | Command |
|---|---|
| Run the app | `uv run streamlit run app.py` |
| Run on another port | `uv run streamlit run app.py --server.port 8502` |
| Open to other devices on your Wi-Fi (e.g. a phone) | `uv run streamlit run app.py --server.address 0.0.0.0` |
| Run the tests | `uv run pytest -q` |
| Re-install after pulling new code | `uv sync` |
| Add a package | `uv add <package>` (then update `requirements.txt` too) |
| Stop the app | `Ctrl+C` in the terminal |

### 3. Gemini API key (`.streamlit/secrets.toml`)
Gemini handles Bangla speech-to-text and symptom extraction. **Without a key the app still runs**, but it falls back to local Faster-Whisper on the CPU (slow, often minutes per clip) and keyword-based extraction (less accurate).

1. Get a free key at <https://aistudio.google.com/apikey>.
2. Create the file `.streamlit/secrets.toml` in the project root:

   **Linux / macOS**
   ```bash
   mkdir -p .streamlit
   nano .streamlit/secrets.toml
   ```
   **Windows (PowerShell)**
   ```powershell
   New-Item -ItemType Directory -Force .streamlit
   notepad .streamlit\secrets.toml
   ```
3. Put this inside it:
   ```toml
   GEMINI_API_KEY = "your-key-here"
   GEMINI_MODEL = "gemini-2.5-flash"
   ```
4. Restart the app (Ctrl+C, then `uv run streamlit run app.py`). Streamlit reads secrets only at startup.

The app reads `st.secrets` first, then environment variables, so you can set the key in the environment instead:
```bash
export GEMINI_API_KEY="your-key-here"        # Linux/macOS
$env:GEMINI_API_KEY = "your-key-here"        # Windows PowerShell
```
`.env` files are **not** loaded automatically.

> 🔒 `.streamlit/secrets.toml` is in `.gitignore`. Never commit your key. On Streamlit Community Cloud, paste the same two lines into *App settings → Secrets* instead.

## Tests
```bash
uv run pytest -q
```

## Safety
This is a demonstration , not a medical device or validated clinical decision support system. Rule thresholds and advice are provisional and must be reviewed by qualified maternal-health professionals against current WHO/DGHS protocols before any real-world use. Use synthetic data only.
