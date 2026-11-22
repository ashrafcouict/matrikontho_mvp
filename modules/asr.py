from google import genai
from google.genai import types

def transcribe_with_gemini(audio_bytes: bytes, mime_type: str, api_key: str, model_name: str) -> str:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
            "এই অডিওতে বলা বাংলা কথা হুবহু বাংলা লিপিতে লিখে দাও। কোনো অতিরিক্ত মন্তব্য বা অনুবাদ করবে না।",
        ],
    )
    return (getattr(response, "text", None) or "").strip()
