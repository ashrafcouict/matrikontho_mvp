from datetime import datetime, timezone
import uuid
def make_sms(extraction, result):
    symptoms=", ".join(result.get("triggered_symptoms",[])) or "Not specified"
    weeks=extraction.get("gestational_age_weeks") or "Not provided"
    return (f"MATRIKONTHO ALERT [SIMULATED]\\nRisk: HIGH\\nGestational age: {weeks} weeks\\n"
            f"Reported symptoms: {symptoms}\\nRecommended action: Immediate emergency assessment\\n"
            f"Assessment ID: MK-{uuid.uuid4().hex[:6].upper()}\\nDRAFT ONLY — NOT SENT")
