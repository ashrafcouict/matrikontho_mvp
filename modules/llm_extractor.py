import json, os, re
from modules.conversation import fallback_extract

SYSTEM = """You extract only explicitly stated maternal symptoms from Bangla. Return valid JSON only.
Schema: pregnancy_status (pregnant/not_pregnant/unknown), gestational_age_weeks (integer/null),
symptoms: array of {name, present (true/false/null), severity (mild/moderate/severe/unknown),
duration, evidence}, missing_information (array), uncertainty (array).
Recognized names: vaginal_bleeding, convulsions, headache, blurred_vision, facial_hand_swelling,
fever, reduced_fetal_movement, abdominal_pain, breathing_difficulty, severe_weakness.
Never infer absence from silence. Null means unknown. Preserve uncertainty. Do not classify risk."""
def extract_symptoms(transcript, pregnancy_status="unknown", gestational_age_weeks=None):
    key=os.getenv("GEMINI_API_KEY")
    if key:
        try:
            from google import genai
            client=genai.Client(api_key=key)
            prompt=f"{SYSTEM}\nContext pregnancy_status={pregnancy_status}, gestational_age_weeks={gestational_age_weeks}\nTranscript: {transcript}"
            response=client.models.generate_content(model=os.getenv("GEMINI_MODEL","gemini-2.0-flash"), contents=prompt)
            raw=response.text.strip().replace("```json","").replace("```","")
            data=json.loads(raw)
            data["pregnancy_status"]=pregnancy_status if pregnancy_status!="unknown" else data.get("pregnancy_status","unknown")
            if gestational_age_weeks: data["gestational_age_weeks"]=gestational_age_weeks
            data["source_transcript"]=transcript
            return normalize(data)
        except Exception:
            pass
    return fallback_extract(transcript, pregnancy_status, gestational_age_weeks)

def normalize(data):
    allowed={"vaginal_bleeding","convulsions","headache","blurred_vision","facial_hand_swelling","fever","reduced_fetal_movement","abdominal_pain","breathing_difficulty","severe_weakness"}
    out=[]
    for s in data.get("symptoms",[]):
        if s.get("name") in allowed and s.get("present") in (True,False,None):
            out.append({k:s.get(k) for k in ["name","present","severity","duration","evidence"]})
    data["symptoms"]=out
    data.setdefault("missing_information",[])
    data.setdefault("uncertainty",[])
    data.setdefault("source_transcript","")
    return data
